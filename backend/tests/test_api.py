from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select

from app.database import DatabaseUnavailable, seed_demo_content
from app.main import create_app
from app.models import RecommendationAudit
from app.schemas import PantryRecommendationRequest, TodayRecommendationRequest
from conftest import make_settings


TODAY_PAYLOAD = {
    "city": "北京",
    "region": "华北",
    "date": "2026-01-26",
    "feelings": ["有点着凉"],
    "allergies": [],
    "dietaryRestrictions": [],
    "preferences": ["清淡"],
    "constitutionTags": [],
    "recentRecipeIds": [],
}


def route_endpoint(app, path: str, method: str):
    return next(
        route.endpoint
        for route in app.routes
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set())
    )


def test_openapi_exposes_exact_m12_contract(app_client):
    schema = app_client.openapi()
    assert {
        "/health",
        "/v1/context/today",
        "/v1/recommendations/today",
        "/v1/recommendations/pantry",
        "/v1/recipes/{recipe_id}",
    } <= set(schema["paths"])


def test_health_exposes_explicit_local_degradation(app_client):
    payload = route_endpoint(app_client, "/health", "GET")()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["database"] == {
        "status": "degraded",
        "kind": "sqlite",
    }
    assert payload["dependencies"]["cache"]["backend"] == "memory"
    assert payload["dependencies"]["weather"]["status"] == "degraded"


def test_today_context_marks_weather_degradation(app_client):
    payload = app_client.state.service.context_today("北京", date(2026, 1, 26))
    assert payload["seasonalContent"]["id"] == "m2-laba"
    assert payload["weather"]["available"] is False
    assert {"weather", "cache", "database_local"} <= set(payload["degraded"])


def test_recipe_returns_traceable_source_and_version(app_client):
    payload = route_endpoint(app_client, "/v1/recipes/{recipe_id}", "GET")(
        "demo-yam-millet"
    )
    recipe = payload["recipe"]
    assert recipe["source"] == "demo-recipe-library"
    assert recipe["version"] == "m2-demo-1"
    assert recipe["reviewStatus"] == "demo"
    assert recipe["isDemo"] is True


def test_today_recommendation_uses_festival_and_cache(app_client):
    request = TodayRecommendationRequest.model_validate(TODAY_PAYLOAD)
    first = app_client.state.service.recommend_today(request)
    second = app_client.state.service.recommend_today(request)
    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert first["seasonalContent"]["id"] == "m2-laba"
    assert first["main"]["id"] in {"m2-laba-porridge", "m2-laba-garlic"}
    assert "weather" in first["degraded"]


def test_expired_recommendation_cache_is_rebuilt(tmp_path):
    settings = make_settings(tmp_path, recommendation_ttl_seconds=1)
    app = create_app(settings)
    app.state.database.create_schema()
    seed_demo_content(app.state.database, settings.seed_path)
    clock = [100.0]
    app.state.cache.memory._now = lambda: clock[0]
    request = TodayRecommendationRequest.model_validate(TODAY_PAYLOAD)
    assert app.state.service.recommend_today(request)["cache"]["status"] == "miss"
    assert app.state.service.recommend_today(request)["cache"]["status"] == "hit"
    clock[0] += 2
    assert app.state.service.recommend_today(request)["cache"]["status"] == "miss"
    app.state.database.engine.dispose()


def test_pantry_matches_reviewed_template_and_filters_allergy(app_client):
    request = PantryRecommendationRequest.model_validate(
        {
            "ingredients": ["西红柿", "豆腐", "鸡蛋", "食用油"],
            "tools": ["汤锅", "菜刀"],
            "maxMinutes": 30,
            "targetServings": 2,
            "maxAdditionalIngredients": 0,
            "allergies": ["大豆"],
            "dietaryRestrictions": [],
        }
    )
    payload = app_client.state.service.recommend_pantry(request)
    ids = [item["recipe"]["id"] for item in payload["matches"]]
    assert "demo-tomato-tofu" not in ids
    assert payload["filteredCount"] >= 1


def test_database_failure_never_returns_recommendation(app_client, monkeypatch):
    def fail():
        raise DatabaseUnavailable("simulated")

    monkeypatch.setattr(app_client.state.repository, "list_recipes", fail)
    request = TodayRecommendationRequest.model_validate(TODAY_PAYLOAD)
    try:
        app_client.state.service.recommend_today(request)
    except DatabaseUnavailable:
        pass
    else:
        raise AssertionError("database failure must stop recommendation generation")
    assert DatabaseUnavailable in app_client.exception_handlers


def test_audit_stores_ids_and_reason_codes_only(app_client):
    request = TodayRecommendationRequest.model_validate(TODAY_PAYLOAD)
    app_client.state.service.recommend_today(request)
    with app_client.state.database.session() as session:
        audit = session.scalar(select(RecommendationAudit))
        assert audit is not None
        assert audit.request_kind == "today"
        assert audit.selected_ids
        serialized = str(audit.__dict__)
        assert "有点着凉" not in serialized
        assert "北京" not in serialized


def test_rate_limit_falls_back_without_redis(tmp_path):
    settings = make_settings(tmp_path, rate_limit_requests=2)
    app = create_app(settings)
    assert app.state.cache.allow("client") == (True, "memory", True)
    assert app.state.cache.allow("client") == (True, "memory", True)
    assert app.state.cache.allow("client") == (False, "memory", True)


def test_recipe_negative_cache(app_client):
    service = app_client.state.service
    assert service.recipe("not-present")[0] is None
    app_client.state.repository.get_recipe = lambda _: (_ for _ in ()).throw(
        AssertionError("database should not be queried")
    )
    assert service.recipe("not-present")[0] is None


def test_invalid_recipe_id_is_rejected(app_client):
    endpoint = route_endpoint(app_client, "/v1/recipes/{recipe_id}", "GET")
    try:
        endpoint("../secret")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("invalid recipe id should be rejected")
