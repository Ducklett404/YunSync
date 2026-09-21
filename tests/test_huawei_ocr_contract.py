import asyncio

import pytest

from app.integrations.huawei.ocr import HuaweiOcrClient, OcrError, _pdf_page_count, parse_huawei_payload


PROVIDER_PAYLOAD = {
    "result": [
        {
            "table_result": {
                "table_list": [
                    {
                        "words_block_list": [
                            {"words": "项目", "rows": [0], "columns": [0]},
                            {"words": "结果", "rows": [0], "columns": [1]},
                            {"words": "单位", "rows": [0], "columns": [2]},
                            {"words": "参考范围", "rows": [0], "columns": [3]},
                            {"words": "空腹血糖", "rows": [1], "columns": [0]},
                            {"words": "6.2", "rows": [1], "columns": [1]},
                            {"words": "mmol/L", "rows": [1], "columns": [2]},
                            {"words": "3.9-6.1", "rows": [1], "columns": [3]},
                            {"words": "无法识别项目", "rows": [2], "columns": [0]},
                            {"words": "123", "rows": [2], "columns": [1]},
                            {"words": "x", "rows": [2], "columns": [2]},
                        ]
                    }
                ]
            }
        },
        {
            "ocr_result": {
                "words_block_list": [
                    {
                        "words": "空腹血糖",
                        "confidence": 0.93,
                        "location": [[100, 200], [300, 200], [300, 240], [100, 240]],
                    },
                    {
                        "words": "页脚",
                        "confidence": 0.99,
                        "location": [[0, 900], [600, 900], [600, 940], [0, 940]],
                    },
                ]
            }
        },
    ]
}


def test_huawei_payload_parser_only_emits_reviewable_p0_rows():
    metrics = parse_huawei_payload(PROVIDER_PAYLOAD, page_number=2)

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.code == "fasting_glucose"
    assert metric.value == pytest.approx(6.2)
    assert metric.unit == "mmol/L"
    assert metric.reference_range == "3.9-6.1"
    assert metric.confidence == pytest.approx(0.93)
    assert metric.source_page == 2
    assert all(0 <= value <= 1 for value in metric.source_bbox)


def test_huawei_payload_parser_drops_conflicting_duplicate_metric_rows():
    payload = {
        "result": [
            {
                "table_result": {
                    "table_list": [
                        {
                            "words_block_list": [
                                {"words": "空腹血糖", "rows": [0], "columns": [0]},
                                {"words": "6.2", "rows": [0], "columns": [1]},
                                {"words": "mmol/L", "rows": [0], "columns": [2]},
                                {"words": "空腹血糖", "rows": [1], "columns": [0]},
                                {"words": "7.1", "rows": [1], "columns": [1]},
                                {"words": "mmol/L", "rows": [1], "columns": [2]},
                            ]
                        }
                    ]
                }
            }
        ]
    }

    assert parse_huawei_payload(payload, page_number=1) == []


def test_huawei_client_aggregates_bounded_pdf_pages(monkeypatch):
    content = b"%PDF /Type /Page /Type /Pages /Type /Page"
    calls = []
    client = HuaweiOcrClient()
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_project_id", "project")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_access_key", "ak")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_secret_key", "sk")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_ocr_endpoint", "https://ocr.example.com")

    def recognize_page(_content, page_number):
        calls.append(page_number)
        return PROVIDER_PAYLOAD

    monkeypatch.setattr(client, "_recognize_page", recognize_page)
    analysis = asyncio.run(client.analyze(content, "report.pdf"))

    assert _pdf_page_count(content) == 2
    assert calls == [1, 2]
    assert analysis.page_count == 2
    assert [metric.source_page for metric in analysis.metrics] == [1]


def test_huawei_client_fails_closed_without_configuration(monkeypatch):
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_credential_mode", "environment")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_project_id", "")
    with pytest.raises(OcrError) as captured:
        asyncio.run(HuaweiOcrClient().analyze(b"image", "report.png"))
    assert captured.value.code == "provider_not_configured"
    assert captured.value.retryable is False


def test_huawei_client_accepts_instance_metadata_mode_without_static_keys(monkeypatch):
    client = HuaweiOcrClient()
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_credential_mode", "instance_metadata")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_project_id", "project")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_access_key", "")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_secret_key", "")
    monkeypatch.setattr("app.integrations.huawei.ocr.settings.huawei_ocr_endpoint", "https://ocr.example.com")
    monkeypatch.setattr(client, "_recognize_page", lambda _content, _page: PROVIDER_PAYLOAD)

    analysis = asyncio.run(client.analyze(b"image", "report.png"))

    assert analysis.provider == "huawei_ocr"
    assert len(analysis.metrics) == 1
