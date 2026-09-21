from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import re
from typing import Any

from app.core.config import settings
from app.services.metric_catalog import MetricDefinition, P0_METRICS


class OcrError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ExtractedMetric:
    code: str
    name: str
    value: float
    unit: str
    reference_range: str
    raw_text: str
    confidence: float
    source_page: int
    source_bbox: list[float]


@dataclass(frozen=True)
class OcrAnalysis:
    provider: str
    page_count: int
    metrics: list[ExtractedMetric]


class MockOcrClient:
    """Deterministic OCR contract simulator for synthetic files only."""

    provider = "mock_ocr"

    async def analyze(self, content: bytes, _filename: str) -> OcrAnalysis:
        marker = content.decode("latin-1", errors="ignore").lower()
        if "yunsync_scenario:timeout" in marker:
            raise OcrError("合成 OCR 超时，请稍后重试。", code="timeout", retryable=True)
        if "yunsync_scenario:failure" in marker:
            raise OcrError("合成 OCR 无法解析该文件。", code="unreadable", retryable=False)

        confidence_delta = 0.0
        bbox_shift = 0.0
        if "yunsync_scenario:blurred" in marker:
            confidence_delta = -0.34
        elif "yunsync_scenario:rotated" in marker:
            confidence_delta = -0.12
            bbox_shift = 0.04
        elif "yunsync_scenario:low_resolution" in marker:
            confidence_delta = -0.43

        rows = [
            ("bmi", "身体质量指数", 25.8, "kg/m²", "18.5-23.9", 0.98, [0.10, 0.18, 0.28, 0.05]),
            ("fasting_glucose", "空腹血糖", 6.2, "mmol/L", "3.9-6.1", 0.94, [0.10, 0.29, 0.32, 0.05]),
            ("triglyceride", "甘油三酯", 1.9, "mmol/L", "0.45-1.69", 0.91, [0.10, 0.40, 0.34, 0.05]),
            ("hdl_c", "高密度脂蛋白", 1.18, "mmol/L", ">=1.0", 0.88, [0.10, 0.51, 0.31, 0.05]),
            ("systolic_bp", "收缩压", 128.0, "mmHg", "90-139", 0.86, [0.10, 0.62, 0.29, 0.05]),
        ]
        metrics = [
            ExtractedMetric(
                code=code,
                name=name,
                value=value,
                unit=unit,
                reference_range=reference,
                raw_text=f"{name} {value:g} {unit} 参考 {reference}",
                confidence=max(0.01, min(0.99, confidence + confidence_delta)),
                source_page=1,
                source_bbox=[
                    round(min(1.0, coordinate + (bbox_shift if index == 0 else 0.0)), 3)
                    for index, coordinate in enumerate(bbox)
                ],
            )
            for code, name, value, unit, reference, confidence, bbox in rows
        ]
        return OcrAnalysis(provider=self.provider, page_count=1, metrics=metrics)


class HuaweiOcrClient:
    provider = "huawei_ocr"

    async def analyze(self, content: bytes, filename: str) -> OcrAnalysis:
        credential_ready = settings.huawei_credential_mode == "instance_metadata" or all(
            (settings.huawei_access_key, settings.huawei_secret_key)
        )
        if not settings.huawei_project_id or not settings.huawei_ocr_endpoint or not credential_ready:
            raise OcrError(
                "华为云 OCR 连接参数不完整，不能发起真实识别。",
                code="provider_not_configured",
                retryable=False,
            )

        page_count = _pdf_page_count(content) if filename.lower().endswith(".pdf") else 1
        page_count = min(page_count, settings.ocr_pdf_max_pages)
        metrics: list[ExtractedMetric] = []
        for page_number in range(1, page_count + 1):
            payload = await asyncio.to_thread(
                self._recognize_page,
                content,
                page_number if filename.lower().endswith(".pdf") else None,
            )
            metrics.extend(parse_huawei_payload(payload, page_number=page_number))
        return OcrAnalysis(
            provider=self.provider,
            page_count=page_count,
            metrics=_deduplicate_metrics(metrics),
        )

    def _recognize_page(self, content: bytes, page_number: int | None) -> dict[str, Any]:
        try:
            from huaweicloudsdkcore.auth.credentials import BasicCredentials
            from huaweicloudsdkcore.auth.provider import MetadataCredentialProvider
            from huaweicloudsdkcore.exceptions import exceptions
            from huaweicloudsdkcore.http.http_config import HttpConfig
            from huaweicloudsdkocr.v1 import OcrClient
            from huaweicloudsdkocr.v1.model import (
                RecognizeSmartDocumentRecognizerRequest,
                SmartDocumentRecognizerRequestBody,
            )
        except ImportError as exc:
            raise OcrError(
                "缺少华为云 OCR SDK，请先安装项目依赖。",
                code="provider_dependency_missing",
                retryable=False,
            ) from exc

        if settings.huawei_credential_mode == "instance_metadata":
            credentials = (
                MetadataCredentialProvider.get_basic_credential_metadata_provider()
                .get_credentials()
                .with_project_id(settings.huawei_project_id)
            )
        else:
            credentials = BasicCredentials(
                settings.huawei_access_key,
                settings.huawei_secret_key,
                settings.huawei_project_id,
            )
        http_config = HttpConfig.get_default_config()
        http_config.timeout = settings.ocr_timeout_seconds
        client = (
            OcrClient.new_builder()
            .with_credentials(credentials)
            .with_endpoint(settings.huawei_ocr_endpoint.rstrip("/"))
            .with_http_config(http_config)
            .build()
        )
        request = RecognizeSmartDocumentRecognizerRequest()
        request.body = SmartDocumentRecognizerRequestBody(
            data=base64.b64encode(content).decode("ascii"),
            language="zh",
            kv=True,
            table=True,
            layout=True,
            pdf_page_number=page_number,
        )
        try:
            response = client.recognize_smart_document_recognizer(request)
        except exceptions.ClientRequestException as exc:
            status_code = getattr(exc, "status_code", 0) or 0
            retryable = status_code >= 500 or status_code in {408, 429}
            raise OcrError(
                "华为云 OCR 请求失败，请检查文件或服务配置。",
                code=str(getattr(exc, "error_code", "provider_rejected")),
                retryable=retryable,
            ) from exc
        except Exception as exc:
            raise OcrError(
                "华为云 OCR 暂时不可用，请稍后重试。",
                code="provider_error",
                retryable=True,
            ) from exc
        payload = response.to_json_object()
        if not isinstance(payload, dict):
            raise OcrError(
                "华为云 OCR 返回格式无效。",
                code="invalid_provider_payload",
                retryable=False,
            )
        return payload


def _pdf_page_count(content: bytes) -> int:
    """Bound provider calls without attempting to interpret PDF content locally."""
    count = len(re.findall(rb"/Type\s*/Page\b", content))
    return max(1, count)


def _identity_key(value: str) -> str:
    return "".join(value.casefold().split()).strip(":：")


def _definition_from_text(value: str) -> MetricDefinition | None:
    key = _identity_key(value)
    candidates: list[tuple[int, MetricDefinition]] = []
    for definition in P0_METRICS:
        for alias in (definition.name, *definition.aliases):
            alias_key = _identity_key(alias)
            if key == alias_key or (
                any("\u4e00" <= char <= "\u9fff" for char in alias_key)
                and alias_key in key
            ):
                candidates.append((len(alias_key), definition))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _first_number(value: str) -> float | None:
    match = re.search(r"(?<![\d.])[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group()) if match else None


def _looks_like_range(value: str) -> bool:
    compact = "".join(value.split())
    return bool(
        re.search(r"\d\s*[-–—~至]\s*\d", value)
        or any(symbol in compact for symbol in ("<", ">", "≤", "≥"))
    )


def _header_role(value: str) -> str | None:
    key = _identity_key(value)
    if any(label in key for label in ("项目", "名称", "指标", "检验项")):
        return "name"
    if any(label in key for label in ("结果", "测定值", "检测值", "数值")):
        return "value"
    if "单位" in key:
        return "unit"
    if any(label in key for label in ("参考范围", "参考值", "正常范围")):
        return "reference"
    return None


def _location_box(location: Any, *, max_x: float, max_y: float) -> list[float]:
    if not isinstance(location, list) or not location:
        return [0.0, 0.0, 1.0, 0.05]
    points = [point for point in location if isinstance(point, list) and len(point) >= 2]
    if not points:
        return [0.0, 0.0, 1.0, 0.05]
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    return [
        round(left / max_x, 4),
        round(top / max_y, 4),
        round(max(0.0, right - left) / max_x, 4),
        round(max(0.0, bottom - top) / max_y, 4),
    ]


def _deduplicate_metrics(metrics: list[ExtractedMetric]) -> list[ExtractedMetric]:
    """Return at most one unambiguous candidate per standard code."""
    unique: dict[str, ExtractedMetric] = {}
    ambiguous: set[str] = set()
    for metric in metrics:
        if metric.code in ambiguous:
            continue
        existing = unique.get(metric.code)
        if existing is None:
            unique[metric.code] = metric
            continue
        same_result = (
            existing.value == metric.value
            and _identity_key(existing.unit) == _identity_key(metric.unit)
            and _identity_key(existing.reference_range) == _identity_key(metric.reference_range)
        )
        if same_result:
            if metric.confidence > existing.confidence:
                unique[metric.code] = metric
        else:
            unique.pop(metric.code, None)
            ambiguous.add(metric.code)
    return list(unique.values())


def parse_huawei_payload(payload: dict[str, Any], *, page_number: int) -> list[ExtractedMetric]:
    """Conservatively turn provider table rows into review candidates.

    Rows that cannot identify a P0 name, one numeric result, and a unit are ignored.
    No clinical thresholds, flags, or missing values are inferred.
    """
    result_items = payload.get("result")
    if not isinstance(result_items, list):
        raise OcrError(
            "华为云 OCR 缺少结果列表。",
            code="invalid_provider_payload",
            retryable=False,
        )

    ocr_blocks: list[dict[str, Any]] = []
    table_blocks: list[dict[str, Any]] = []
    for item in result_items:
        if not isinstance(item, dict):
            continue
        ocr_result = item.get("ocr_result") or {}
        if isinstance(ocr_result, dict):
            ocr_blocks.extend(
                block for block in ocr_result.get("words_block_list", []) if isinstance(block, dict)
            )
        table_result = item.get("table_result") or {}
        if isinstance(table_result, dict):
            table_blocks.extend(
                block for block in table_result.get("table_list", []) if isinstance(block, dict)
            )

    all_points = [
        point
        for block in ocr_blocks
        for point in (block.get("location") or [])
        if isinstance(point, list) and len(point) >= 2
    ]
    max_x = max((float(point[0]) for point in all_points), default=1.0) or 1.0
    max_y = max((float(point[1]) for point in all_points), default=1.0) or 1.0
    candidate_metrics: list[ExtractedMetric] = []
    for table in table_blocks:
        rows: dict[int, list[tuple[int, str]]] = {}
        for cell in table.get("words_block_list", []):
            if not isinstance(cell, dict):
                continue
            row_ids = cell.get("rows") or []
            column_ids = cell.get("columns") or []
            if not row_ids or not column_ids:
                continue
            rows.setdefault(min(row_ids), []).append((min(column_ids), str(cell.get("words", "")).strip()))
        header_columns: dict[str, int] = {}
        for cells in rows.values():
            for column, cell_text in cells:
                role = _header_role(cell_text)
                if role is not None:
                    header_columns.setdefault(role, column)

        for cells in rows.values():
            by_column = {column: text for column, text in cells if text}
            ordered = sorted(by_column.items())
            texts = [text for _, text in ordered]
            definition_entry = next(
                (
                    (column, definition)
                    for column, text in ordered
                    if (definition := _definition_from_text(text))
                ),
                None,
            )
            if definition_entry is None:
                continue
            name_column, definition = definition_entry
            value_text = by_column.get(header_columns.get("value", -1), "")
            if not value_text:
                value_text = next(
                    (
                        text
                        for column, text in ordered
                        if column > name_column
                        and not _looks_like_range(text)
                        and _first_number(text) is not None
                    ),
                    "",
                )
            value = _first_number(value_text)
            unit_text = by_column.get(header_columns.get("unit", -1), "")
            if not unit_text:
                value_column = next(
                    (column for column, text in ordered if text == value_text),
                    name_column,
                )
                unit_text = next(
                    (
                        text
                        for column, text in ordered
                        if column > value_column
                        and not _looks_like_range(text)
                        and _first_number(text) is None
                    ),
                    "",
                )
            if value is None or not unit_text or _header_role(unit_text) is not None:
                continue
            reference_range = by_column.get(header_columns.get("reference", -1), "")
            if not _looks_like_range(reference_range):
                reference_range = next((text for text in texts if _looks_like_range(text)), "")
            name_block = next(
                (block for block in ocr_blocks if _definition_from_text(str(block.get("words", ""))) == definition),
                {},
            )
            confidence = float(name_block.get("confidence", 0.5))
            candidate_metrics.append(
                ExtractedMetric(
                    code=definition.code,
                    name=definition.name,
                    value=value,
                    unit=unit_text,
                    reference_range=reference_range,
                    raw_text=" | ".join(texts),
                    confidence=max(0.0, min(1.0, confidence)),
                    source_page=page_number,
                    source_bbox=_location_box(name_block.get("location"), max_x=max_x, max_y=max_y),
                )
            )

    return _deduplicate_metrics(candidate_metrics)


def get_ocr_client():
    if settings.use_mock_ai:
        return MockOcrClient()
    return HuaweiOcrClient()
