from hashlib import sha256
from types import SimpleNamespace

import pytest

from app.integrations.huawei.obs import HuaweiObsClient, ObjectStorageError


def _config(**overrides):
    values = {
        "huawei_obs_endpoint": "https://obs.cn-north-4.myhuaweicloud.com",
        "huawei_obs_bucket": "synthetic-private-bucket",
        "huawei_credential_mode": "environment",
        "huawei_access_key": "synthetic-ak",
        "huawei_secret_key": "synthetic-sk",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeObsClient:
    def __init__(self, *, status=200, content=b"stored-content"):
        self.status = status
        self.content = content
        self.put_calls = []
        self.get_calls = []
        self.closed = False

    def putContent(self, bucket, key, content):
        self.put_calls.append((bucket, key, content))
        return SimpleNamespace(status=self.status)

    def getObject(self, bucket, key, *, loadStreamInMemory):
        self.get_calls.append((bucket, key, loadStreamInMemory))
        return SimpleNamespace(
            status=self.status,
            body=SimpleNamespace(buffer=self.content),
        )

    def close(self):
        self.closed = True


def test_obs_upload_uses_private_bucket_key_and_environment_credentials():
    fake = FakeObsClient()
    factory_calls = []

    def factory(**kwargs):
        factory_calls.append(kwargs)
        return fake

    client = HuaweiObsClient(client_factory=factory, config=_config())
    stored = client.put_private(b"synthetic-report", user_id="user_01", suffix=".PDF")

    assert stored.provider == "huawei_obs"
    assert stored.key.startswith("reports/user_01/")
    assert stored.key.endswith(".pdf")
    assert stored.content_sha256 == sha256(b"synthetic-report").hexdigest()
    assert stored.size == len(b"synthetic-report")
    assert fake.put_calls == [
        ("synthetic-private-bucket", stored.key, b"synthetic-report")
    ]
    assert factory_calls == [
        {
            "access_key_id": "synthetic-ak",
            "secret_access_key": "synthetic-sk",
            "server": "https://obs.cn-north-4.myhuaweicloud.com",
        }
    ]
    assert fake.closed is True


def test_obs_read_loads_content_in_memory_and_closes_client():
    fake = FakeObsClient(content=b"downloaded")
    key = "reports/user-01/0123456789abcdef0123456789abcdef.pdf"
    client = HuaweiObsClient(client_factory=lambda **_kwargs: fake, config=_config())

    assert client.read_private(key) == b"downloaded"
    assert fake.get_calls == [("synthetic-private-bucket", key, True)]
    assert fake.closed is True


def test_obs_instance_metadata_uses_ecs_security_provider():
    factory_calls = []

    def factory(**kwargs):
        factory_calls.append(kwargs)
        return FakeObsClient()

    client = HuaweiObsClient(
        client_factory=factory,
        config=_config(
            huawei_credential_mode="instance_metadata",
            huawei_access_key="",
            huawei_secret_key="",
        ),
    )
    client.put_private(b"content", user_id="user-01", suffix=".png")

    assert factory_calls == [
        {
            "server": "https://obs.cn-north-4.myhuaweicloud.com",
            "security_provider_policy": "ECS",
        }
    ]


@pytest.mark.parametrize(
    "key",
    [
        "../../outside.pdf",
        "reports/user/../outside.pdf",
        "reports/user/not-a-generated-key.pdf",
        "reports\\user\\0123456789abcdef0123456789abcdef.pdf",
    ],
)
def test_obs_rejects_untrusted_object_keys_before_provider_call(key):
    called = False

    def factory(**_kwargs):
        nonlocal called
        called = True
        return FakeObsClient()

    client = HuaweiObsClient(client_factory=factory, config=_config())

    with pytest.raises(ObjectStorageError, match="存储键无效"):
        client.read_private(key)
    assert called is False


def test_obs_provider_failure_is_generic_and_closes_client():
    fake = FakeObsClient(status=403)
    client = HuaweiObsClient(client_factory=lambda **_kwargs: fake, config=_config())

    with pytest.raises(ObjectStorageError, match="对象存储上传失败") as captured:
        client.put_private(b"content", user_id="user-01", suffix=".pdf")
    assert "synthetic-sk" not in str(captured.value)
    assert fake.closed is True


def test_obs_client_initialization_failure_does_not_expose_sdk_details():
    def factory(**_kwargs):
        raise RuntimeError("synthetic-sk provider internal details")

    client = HuaweiObsClient(client_factory=factory, config=_config())

    with pytest.raises(ObjectStorageError, match="客户端初始化失败") as captured:
        client.put_private(b"content", user_id="user-01", suffix=".pdf")
    assert "synthetic-sk" not in str(captured.value)
    assert "internal details" not in str(captured.value)
