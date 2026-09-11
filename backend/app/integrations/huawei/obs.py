from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


class ObjectStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredObject:
    provider: str
    key: str
    content_sha256: str
    size: int


class LocalPrivateStorageClient:
    """Private local adapter used only for synthetic development files."""

    provider = "local_private"

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.upload_storage_dir).resolve()

    def put_private(self, content: bytes, *, user_id: str, suffix: str) -> StoredObject:
        safe_suffix = suffix.lower() if suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"} else ".bin"
        key = f"{user_id}/{uuid4().hex}{safe_suffix}"
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ObjectStorageError("存储路径校验失败")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        except OSError as exc:
            raise ObjectStorageError("私有存储暂时不可用，请稍后重试") from exc
        return StoredObject(
            provider=self.provider,
            key=key,
            content_sha256=sha256(content).hexdigest(),
            size=len(content),
        )

    def read_private(self, key: str) -> bytes:
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root) or not target.is_file():
            raise ObjectStorageError("报告源文件不可用")
        try:
            return target.read_bytes()
        except OSError as exc:
            raise ObjectStorageError("报告源文件暂时不可读取") from exc


class HuaweiObsClient:
    provider = "huawei_obs"

    def put_private(self, _content: bytes, *, user_id: str, suffix: str) -> StoredObject:
        del user_id, suffix
        raise ObjectStorageError(
            "华为云 OBS 适配器尚未配置，不能将本地存储记录冒充真实云上传。"
        )

    def read_private(self, _key: str) -> bytes:
        raise ObjectStorageError("华为云 OBS 适配器尚未配置")


def get_object_storage():
    if settings.use_local_storage:
        return LocalPrivateStorageClient()
    return HuaweiObsClient()
