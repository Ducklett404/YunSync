from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Callable
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

    def __init__(
        self,
        *,
        client_factory: Callable[..., Any] | None = None,
        config: Any = settings,
    ) -> None:
        self._client_factory = client_factory
        self._config = config

    def put_private(self, content: bytes, *, user_id: str, suffix: str) -> StoredObject:
        if not isinstance(content, bytes) or not content:
            raise ObjectStorageError("上传内容为空或格式无效")
        safe_user_id = self._safe_user_id(user_id)
        safe_suffix = suffix.lower() if suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"} else ".bin"
        key = f"reports/{safe_user_id}/{uuid4().hex}{safe_suffix}"
        client = self._build_client()
        try:
            response = client.putContent(self._config.huawei_obs_bucket, key, content)
            self._ensure_success(response, operation="上传")
        except ObjectStorageError:
            raise
        except Exception as exc:
            raise ObjectStorageError("私有对象存储暂时不可用，请稍后重试") from exc
        finally:
            self._close(client)
        return StoredObject(
            provider=self.provider,
            key=key,
            content_sha256=sha256(content).hexdigest(),
            size=len(content),
        )

    def read_private(self, key: str) -> bytes:
        self._validate_key(key)
        client = self._build_client()
        try:
            response = client.getObject(
                self._config.huawei_obs_bucket,
                key,
                loadStreamInMemory=True,
            )
            self._ensure_success(response, operation="读取")
            body = getattr(response, "body", None)
            buffer = getattr(body, "buffer", None)
            if not isinstance(buffer, (bytes, bytearray)):
                raise ObjectStorageError("对象存储返回了无效内容")
            return bytes(buffer)
        except ObjectStorageError:
            raise
        except Exception as exc:
            raise ObjectStorageError("报告源文件暂时不可读取") from exc
        finally:
            self._close(client)

    def _build_client(self):
        endpoint = self._config.huawei_obs_endpoint.strip()
        bucket = self._config.huawei_obs_bucket.strip()
        credential_ready = self._config.huawei_credential_mode == "instance_metadata" or all(
            (self._config.huawei_access_key, self._config.huawei_secret_key)
        )
        if not endpoint or not bucket or not credential_ready:
            raise ObjectStorageError("华为云 OBS 连接参数不完整")
        factory = self._client_factory
        if factory is None:
            try:
                from obs import ObsClient
            except ImportError as exc:
                raise ObjectStorageError("缺少华为云 OBS SDK，请先安装项目依赖") from exc
            factory = ObsClient
        try:
            if self._config.huawei_credential_mode == "instance_metadata":
                return factory(server=endpoint, security_provider_policy="ECS")
            return factory(
                access_key_id=self._config.huawei_access_key,
                secret_access_key=self._config.huawei_secret_key,
                server=endpoint,
            )
        except Exception as exc:
            raise ObjectStorageError("华为云 OBS 客户端初始化失败") from exc

    @staticmethod
    def _ensure_success(response: Any, *, operation: str) -> None:
        status = getattr(response, "status", None)
        if not isinstance(status, int) or status < 200 or status >= 300:
            raise ObjectStorageError(f"对象存储{operation}失败")

    @staticmethod
    def _safe_user_id(user_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):
            raise ObjectStorageError("用户存储标识无效")
        return user_id

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not isinstance(key, str)
            or len(key) > 255
            or "\\" in key
            or not re.fullmatch(
                r"reports/[A-Za-z0-9_-]{1,64}/[a-f0-9]{32}\.(?:pdf|png|jpg|jpeg|bin)",
                key,
            )
        ):
            raise ObjectStorageError("对象存储键无效")

    @staticmethod
    def _close(client: Any) -> None:
        try:
            client.close()
        except Exception:
            pass


def get_object_storage():
    if settings.use_local_storage:
        return LocalPrivateStorageClient()
    return HuaweiObsClient()
