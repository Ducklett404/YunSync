from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .cache import ResilientCache
from .config import Settings


class WeatherClient:
    def __init__(self, settings: Settings, cache: ResilientCache):
        self.settings = settings
        self.cache = cache

    def _unavailable(self, city: str, reason: str) -> dict[str, Any]:
        return {
            "city": city,
            "available": False,
            "text": "实时天气暂不可用，推荐未使用天气加权",
            "source": "weather-unavailable",
            "version": "m12-weather-fallback-v1",
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "delivery": "fallback",
            "degradedReason": reason,
        }

    @staticmethod
    def _normalize(payload: Any, city: str, provider: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("invalid weather payload")
        value = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        temperature = value.get("temperature")
        text = value.get("text")
        observed_at = value.get("observedAt") or value.get("observed_at")
        response_city = str(value.get("city") or city).strip()
        if response_city != city:
            raise ValueError("weather city mismatch")
        if not isinstance(temperature, (int, float)) or temperature < -80 or temperature > 60:
            raise ValueError("invalid weather temperature")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("missing weather text")
        if not isinstance(observed_at, str):
            raise ValueError("missing weather observation time")
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        normalized: dict[str, Any] = {
            "city": city,
            "available": True,
            "temperature": float(temperature),
            "text": text.strip(),
            "source": str(value.get("source") or provider),
            "version": str(value.get("version") or "weather-api-v1"),
            "observedAt": observed_at,
            "delivery": "live",
        }
        for key in ("feelsLike", "humidity", "precipitation", "minTemperature", "maxTemperature"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)):
                normalized[key] = float(candidate)
        if "humidity" in normalized and not 0 <= normalized["humidity"] <= 100:
            raise ValueError("invalid weather humidity")
        if normalized.get("precipitation", 0) < 0:
            raise ValueError("invalid weather precipitation")
        return normalized

    def get(self, city: str) -> tuple[dict[str, Any], str, bool]:
        cache_key = self.cache.key("weather", city)
        cached = self.cache.get_json(cache_key)
        if cached.hit:
            value = dict(cached.value)
            value["delivery"] = "cache"
            return value, "hit", cached.degraded
        if not self.settings.weather_api_url:
            return self._unavailable(city, "weather_not_configured"), "bypass", True
        headers = {}
        if self.settings.weather_api_key:
            headers["X-API-Key"] = self.settings.weather_api_key
        try:
            with httpx.Client(timeout=self.settings.weather_timeout_seconds) as client:
                response = client.get(
                    self.settings.weather_api_url,
                    params={"city": city},
                    headers=headers,
                )
                response.raise_for_status()
                normalized = self._normalize(
                    response.json(), city, self.settings.weather_provider
                )
            _, degraded = self.cache.set_json(
                cache_key, normalized, self.settings.weather_ttl_seconds
            )
            return normalized, "miss", degraded
        except (httpx.HTTPError, ValueError, TypeError):
            return self._unavailable(city, "weather_unavailable"), "bypass", True
