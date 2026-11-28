from __future__ import annotations

import json
from datetime import date

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.database import DatabaseUnavailable, seed_demo_content
from app.main import create_app
from app.models import Recipe, RecommendationAudit, SeasonalContent
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
    assert recipe["version"] == "m2-demo-2"
    assert "doneWhen" in recipe["steps"][2]
    assert recipe["reviewStatus"] == "demo"
    assert recipe["isDemo"] is True


def test_versioned_recipe_checks_current_catalogue_even_with_cached_detail(app_client):
    client = TestClient(app_client)
    path = "/v1/recipes/demo-yam-millet"
    assert client.get(path).json()["recipe"]["version"] == "m2-demo-2"
    assert client.get(path, params={"version": "m2-demo-2"}).status_code == 200

    with app_client.state.database.session() as session:
        recipe = session.get(Recipe, "demo-yam-millet")
        recipe.version = "m2-demo-3"
    assert client.get(path, params={"version": "m2-demo-2"}).status_code == 409
    response = client.get(path, params={"version": "m2-demo-3"})
    assert response.json()["recipe"]["version"] == "m2-demo-3"
    assert response.json()["cache"]["status"] == "bypass"
    assert client.get(path).json()["recipe"]["version"] == "m2-demo-3"

    with app_client.state.database.session() as session:
        session.get(Recipe, "demo-yam-millet").review_status = "disabled"
    assert client.get(path, params={"version": "m2-demo-3"}).status_code == 404
    assert client.get(path).status_code == 404


def test_seed_update_replaces_warm_results_and_retires_omitted_demo_content(app_client, tmp_path):
    client = TestClient(app_client)
    db = app_client.state.database
    seed = json.loads(app_client.state.settings.seed_path.read_text(encoding="utf-8"))
    seed_path = tmp_path / "catalogue.json"

    def import_seed() -> None:
        seed_path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
        seed_demo_content(db, seed_path)

    approved = {
        **seed["recipes"][0],
        "id": "approved-test-recipe",
        "isDemo": False,
        "reviewStatus": "approved",
    }
    seed["recipes"].append(approved)
    import_seed()

    today_path = "/v1/recommendations/today"
    first = client.post(today_path, json=TODAY_PAYLOAD).json()
    selected_id = first["main"]["id"]
    detail_path = f"/v1/recipes/{selected_id}"
    assert client.get(detail_path).json()["recipe"]["version"] == first["main"]["version"]
    assert client.post(today_path, json=TODAY_PAYLOAD).json()["cache"]["status"] == "hit"

    pantry_path = "/v1/recommendations/pantry"
    pantry_input = {
        "ingredients": ["西红柿", "豆腐", "鸡蛋", "食用油"],
        "tools": ["汤锅", "菜刀"],
        "maxAdditionalIngredients": 0,
    }
    assert client.post(pantry_path, json=pantry_input).json()["matches"][0]["recipe"]["id"] == "demo-tomato-tofu"

    selected = next(row for row in seed["recipes"] if row["id"] == selected_id)
    selected["version"] = "demo-test-new-version"
    seed["recipes"] = [row for row in seed["recipes"] if row["id"] not in {"demo-tomato-tofu", approved["id"]}]
    import_seed()

    updated = client.post(today_path, json=TODAY_PAYLOAD).json()
    assert updated["cache"]["status"] == "miss"
    assert updated["main"]["version"] == selected["version"]
    assert client.get(detail_path, params={"version": selected["version"]}).status_code == 200
    assert client.get("/v1/recipes/demo-tomato-tofu").status_code == 404
    assert client.post(pantry_path, json=pantry_input).json()["matches"] == []
    assert client.get(f"/v1/recipes/{approved['id']}").status_code == 200
    with db.session() as session:
        assert session.get(Recipe, "demo-tomato-tofu").review_status == "disabled"

    seed["bundles"] = [row for row in seed["bundles"] if row["id"] != "m2-laba"]
    import_seed()
    assert client.post(today_path, json=TODAY_PAYLOAD).json()["seasonalContent"] is None


def test_board_restart_preserves_content_promoted_from_demo_ids(app_client):
    db = app_client.state.database
    seed = json.loads(app_client.state.settings.seed_path.read_text(encoding="utf-8"))
    for model, item in ((Recipe, seed["recipes"][0]), (SeasonalContent, seed["bundles"][0])):
        with db.session() as session:
            row = session.get(model, item["id"])
            row.is_demo = False
            row.review_status = "approved"
            row.version = "signed-v1"
    counts = seed_demo_content(db, app_client.state.settings.seed_path)
    assert counts == {"recipes": len(seed["recipes"]) - 1, "seasonalContents": len(seed["bundles"]) - 1}
    with db.session() as session:
        for model, item in ((Recipe, seed["recipes"][0]), (SeasonalContent, seed["bundles"][0])):
            row = session.get(model, item["id"])
            assert (row.version, row.is_demo, row.review_status) == ("signed-v1", False, "approved")


def test_calendar_context_and_recommendations_cover_the_2027_boundary(app_client):
    client = TestClient(app_client)
    dates = {
        "2026-12-22": "m2-dongzhi",
        "2027-01-01": None,
        "2027-01-15": "m2-laba",
        "2027-02-06": "m2-spring-festival",
        "2027-09-08": "m2-bailu",
    }
    for day, bundle_id in dates.items():
        context = client.get("/v1/context/today", params={"city": "北京", "date": day}).json()
        today = client.post("/v1/recommendations/today", json={**TODAY_PAYLOAD, "date": day}).json()
        for response in (context, today):
            bundle = response["seasonalContent"]
            assert (bundle["id"] if bundle else None) == bundle_id


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


def test_pantry_rejects_a_substitute_that_conflicts_with_the_profile(app_client):
    client = TestClient(app_client)
    pantry = {
        "ingredients": ["小米", "南瓜"],
        "tools": ["汤锅", "菜刀"],
        "maxAdditionalIngredients": 0,
    }
    path = "/v1/recommendations/pantry"
    matches = client.post(path, json=pantry).json()["matches"]
    assert matches[0]["recipe"]["id"] == "demo-yam-millet"
    assert matches[0]["kind"] == "substitution"
    assert client.post(path, json={**pantry, "allergies": ["南瓜"]}).json()["matches"] == []


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


def test_rate_limit_separates_forwarded_clients_and_ignores_untrusted_peer(tmp_path):
    app = create_app(make_settings(tmp_path, rate_limit_requests=1))
    proxy_ip = "172.30.84.2"
    application = ProxyHeadersMiddleware(app, trusted_hosts=proxy_ip)
    proxy = TestClient(application, client=(proxy_ip, 5555))
    direct = TestClient(application, client=("172.30.84.40", 5555))
    path = "/v1/recipes/does-not-exist"

    with proxy:
        assert proxy.get(path, headers={"X-Forwarded-For": "192.0.2.11"}).status_code == 404
        assert proxy.get(path, headers={"X-Forwarded-For": "192.0.2.11"}).status_code == 429
        assert proxy.get(path, headers={"X-Forwarded-For": "192.0.2.12"}).status_code == 404
        assert direct.get(path, headers={"X-Forwarded-For": "192.0.2.21"}).status_code == 404
        assert direct.get(path, headers={"X-Forwarded-For": "192.0.2.22"}).status_code == 429
    app.state.database.engine.dispose()


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
