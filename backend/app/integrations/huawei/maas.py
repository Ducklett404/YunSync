from app.core.config import settings


class MockMaaSClient:
    async def explain(self, metric_name: str, value: float, unit: str) -> str:
        return f"{metric_name}当前记录为 {value:g} {unit}。请结合原报告范围确认，仅用于健康管理参考。"


class HuaweiMaaSClient:
    async def explain(self, _metric_name: str, _value: float, _unit: str) -> str:
        raise RuntimeError(
            "Huawei MaaS adapter is selected but not configured. "
            "Inject the endpoint and API key through environment variables."
        )


def get_maas_client():
    if settings.use_mock_ai:
        return MockMaaSClient()
    return HuaweiMaaSClient()

