from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.content import KnowledgeItem
from app.schemas.content import IngredientPayload, RecipePayload
from app.services.identity_service import CURRENT_CONSENT_VERSION


def _login(client: TestClient, account_id: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/demo", json={"account_id": account_id})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _participant(client: TestClient) -> dict[str, str]:
    headers = _login(client, "demo-student")
    accepted = client.post(
        "/api/v1/consents/accept",
        json={"version": CURRENT_CONSENT_VERSION},
        headers=headers,
    )
    assert accepted.status_code == 200
    return headers


def _ingredient(code: str, version: str, title: str) -> dict:
    return {
        "content_type": "ingredient",
        "code": code,
        "version": version,
        "title": title,
        "payload": {
            "aliases": [],
            "latin_species": "Oryza sativa L.",
            "edible_part": "籽粒",
            "category": "ordinary_food",
            "processing_methods": ["煮制"],
            "allergens": [],
            "contraindication_codes": [],
            "catalog_status": "ordinary_food",
            "catalog_ref": "M4 自动化测试",
            "source_refs": ["ordinary-demo@2026-09-21"],
        },
    }


def _recipe(code: str, ingredients: list[str]) -> dict:
    return {
        "content_type": "recipe",
        "code": code,
        "version": "1.0.0",
        "title": "自动化测试双食材粥",
        "payload": {
            "servings": 2,
            "goal_statement": "用于验证可发布食谱依赖关系。",
            "target_tags": ["自动化测试"],
            "materials": [
                {
                    "code": ingredient,
                    "version": "1.0.0",
                    "grams": 50,
                    "edible_part": "可食部",
                    "preparation": "清洗并称量",
                    "substitutions": [],
                }
                for ingredient in ingredients
            ],
            "preprocessing": ["分别清洗并称量材料。"],
            "steps": [
                {
                    "order": 1,
                    "instruction": "所有材料加入锅中并充分煮熟。",
                    "duration_minutes": 20,
                    "heat": "小火",
                    "cookware": ["汤锅"],
                }
            ],
            "frequency": "仅按经审核的个人计划安排。",
            "cycle": "按已确认方案周期记录。",
            "serving_note": "分为两份并记录实际份量。",
            "nutrition_tags": ["份量可量化"],
            "contraindication_codes": [],
            "caution": "过敏和特殊饮食限制须由专业人员确认。",
            "source_refs": ["ordinary-demo@2026-09-21"],
        },
    }


def _approve(client: TestClient, headers: dict[str, str], item_id: str) -> dict:
    response = client.post(
        f"/api/v1/admin/content/items/{item_id}/review",
        headers=headers,
        json={
            "decision": "approved",
            "reviewer_qualification": "自动化测试审核身份",
            "review_scope": "结构、来源与发布依赖测试",
            "evidence_ref": "test-evidence/m4",
            "attested": True,
            "notes": "仅供自动化测试。",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _delete_codes(codes: list[str]) -> None:
    with SessionLocal() as db:
        db.execute(delete(KnowledgeItem).where(KnowledgeItem.code.in_(codes)))
        db.commit()


def test_m4_seed_contains_complete_draft_catalog():
    with TestClient(app) as client:
        reviewer = _login(client, "demo-reviewer")
        items = client.get("/api/v1/admin/content/items", headers=reviewer)
        recipe_filter = client.get(
            "/api/v1/admin/content/items",
            params={"content_type": "recipe", "status": "draft"},
            headers=reviewer,
        )
        searched = client.get(
            "/api/v1/admin/content/items", params={"q": "化橘红"}, headers=reviewer
        )
        sources = client.get("/api/v1/admin/content/sources", headers=reviewer)

    assert items.status_code == 200
    payload = items.json()
    recipes = [item for item in payload if item["content_type"] == "recipe"]
    ingredients = [item for item in payload if item["content_type"] == "ingredient"]
    food_medicine_codes = {
        "rehmannia_root",
        "ophiopogon_root",
        "asparagus_cochinchinensis_root",
        "citrus_grandis_peel",
    }

    assert len(recipes) == 20
    assert recipe_filter.status_code == 200 and len(recipe_filter.json()) == 20
    assert searched.status_code == 200
    assert [item["code"] for item in searched.json()] == ["citrus_grandis_peel"]
    assert sources.status_code == 200
    assert "nhc-food-medicine-2024-4@2024-08-12" in {
        source["ref"] for source in sources.json()
    }
    assert len(ingredients) >= 28
    assert food_medicine_codes <= {item["code"] for item in ingredients}
    food_medicine = [item for item in ingredients if item["code"] in food_medicine_codes]
    assert all(item["payload"]["category"] == "food_medicine" for item in food_medicine)
    assert all(
        item["payload"]["source_refs"] == ["nhc-food-medicine-2024-4@2024-08-12"]
        for item in food_medicine
    )
    assert all(item["status"] == "draft" and not item["is_active"] for item in recipes)
    for item in recipes:
        parsed = RecipePayload.model_validate(item["payload"])
        assert parsed.materials
        assert parsed.steps
        assert any(material.substitutions for material in parsed.materials)
        assert parsed.frequency and parsed.cycle and parsed.serving_note
    for item in ingredients:
        IngredientPayload.model_validate(item["payload"])


def test_content_permissions_and_catalog_publication_boundary():
    with TestClient(app) as client:
        participant = _participant(client)
        reviewer = _login(client, "demo-reviewer")
        forbidden = client.get("/api/v1/admin/content/items", headers=participant)
        reviewer_forbidden = client.get("/api/v1/catalog/recipes", headers=reviewer)
        catalog = client.get("/api/v1/catalog/recipes", headers=participant)

    assert forbidden.status_code == 403
    assert reviewer_forbidden.status_code == 403
    assert catalog.status_code == 200
    assert not any(item["code"] == "oat_apple_porridge" for item in catalog.json())


def test_review_publish_compare_retire_and_rollback_workflow():
    codes = ["qa_m4_grain"]
    try:
        with TestClient(app) as client:
            reviewer = _login(client, "demo-reviewer")
            participant = _participant(client)

            created_v1 = client.post(
                "/api/v1/admin/content/items",
                headers=reviewer,
                json=_ingredient("qa_m4_grain", "1.0.0", "M4 测试谷物一版"),
            )
            assert created_v1.status_code == 201, created_v1.text
            v1 = created_v1.json()
            invalid_attestation = client.post(
                f"/api/v1/admin/content/items/{v1['id']}/review",
                headers=reviewer,
                json={
                    "decision": "approved",
                    "reviewer_qualification": "自动化测试审核身份",
                    "review_scope": "测试审核",
                    "evidence_ref": "test/m4",
                    "attested": False,
                    "notes": "",
                },
            )
            assert invalid_attestation.status_code == 422
            review = _approve(client, reviewer, v1["id"])
            assert review["decision"] == "approved"
            published_v1 = client.post(
                f"/api/v1/admin/content/items/{v1['id']}/publish", headers=reviewer
            )
            assert published_v1.status_code == 200, published_v1.text
            assert published_v1.json()["is_active"] is True

            payload_v2 = _ingredient("qa_m4_grain", "2.0.0", "M4 测试谷物二版")
            payload_v2["payload"]["processing_methods"] = ["煮制", "焖制"]
            created_v2 = client.post(
                "/api/v1/admin/content/items", headers=reviewer, json=payload_v2
            )
            assert created_v2.status_code == 201
            v2 = created_v2.json()
            _approve(client, reviewer, v2["id"])
            published_v2 = client.post(
                f"/api/v1/admin/content/items/{v2['id']}/publish", headers=reviewer
            )
            assert published_v2.status_code == 200, published_v2.text

            compared = client.get(
                "/api/v1/admin/content/ingredient/qa_m4_grain/compare",
                params={"from_version": "1.0.0", "to_version": "2.0.0"},
                headers=reviewer,
            )
            assert compared.status_code == 200
            assert "title" in compared.json()["changed_fields"]
            assert "payload.processing_methods[1]" in compared.json()["changed_fields"]

            blocked_source = client.patch(
                "/api/v1/admin/content/sources/source-ordinary-demo-2026/status",
                headers=reviewer,
                json={"status": "superseded"},
            )
            assert blocked_source.status_code == 409

            rolled_back = client.post(
                f"/api/v1/admin/content/items/{v1['id']}/rollback", headers=reviewer
            )
            assert rolled_back.status_code == 200, rolled_back.text
            assert rolled_back.json()["version"] == "1.0.0"
            catalog = client.get("/api/v1/catalog/ingredients", headers=participant)
            versions = {
                item["version"]
                for item in catalog.json()
                if item["code"] == "qa_m4_grain"
            }
            assert versions == {"1.0.0"}

        with SessionLocal() as db:
            item_ids = list(
                db.scalars(select(KnowledgeItem.id).where(KnowledgeItem.code == "qa_m4_grain"))
            )
            events = list(
                db.scalars(
                    select(AuditLog).where(AuditLog.event_type == "content.item.reviewed")
                )
            )
            relevant = [event for event in events if event.payload.get("item_id") in item_ids]
            assert relevant
            assert all("reviewer_qualification" not in event.payload for event in relevant)
            assert all("notes" not in event.payload for event in relevant)
    finally:
        _delete_codes(codes)


def test_recipe_dependencies_bulk_validation_and_claim_guard():
    codes = ["qa_m4_rice", "qa_m4_fruit", "qa_m4_recipe", "qa_m4_missing_recipe"]
    try:
        with TestClient(app) as client:
            reviewer = _login(client, "demo-reviewer")
            participant = _participant(client)
            ingredient_ids = []
            for code, title in [("qa_m4_rice", "测试米"), ("qa_m4_fruit", "测试果")]:
                response = client.post(
                    "/api/v1/admin/content/items",
                    headers=reviewer,
                    json=_ingredient(code, "1.0.0", title),
                )
                assert response.status_code == 201
                ingredient_ids.append(response.json()["id"])
                _approve(client, reviewer, response.json()["id"])
                published = client.post(
                    f"/api/v1/admin/content/items/{response.json()['id']}/publish",
                    headers=reviewer,
                )
                assert published.status_code == 200, published.text

            missing = client.post(
                "/api/v1/admin/content/items",
                headers=reviewer,
                json=_recipe("qa_m4_missing_recipe", ["ingredient_does_not_exist"]),
            )
            assert missing.status_code == 201
            validation = client.post(
                "/api/v1/admin/content/validate",
                headers=reviewer,
                json={"item_ids": [missing.json()["id"], "missing-item-id"]},
            )
            assert validation.status_code == 200
            assert validation.json()["valid"] is False
            assert "食材版本不存在" in validation.json()["results"][0]["errors"][0]
            assert validation.json()["results"][1]["errors"] == ["知识条目不存在"]

            recipe = client.post(
                "/api/v1/admin/content/items",
                headers=reviewer,
                json=_recipe("qa_m4_recipe", ["qa_m4_rice", "qa_m4_fruit"]),
            )
            assert recipe.status_code == 201, recipe.text
            _approve(client, reviewer, recipe.json()["id"])
            recipe_published = client.post(
                f"/api/v1/admin/content/items/{recipe.json()['id']}/publish",
                headers=reviewer,
            )
            assert recipe_published.status_code == 200, recipe_published.text
            blocked_dependency_retire = client.post(
                f"/api/v1/admin/content/items/{ingredient_ids[0]}/retire",
                headers=reviewer,
            )
            assert blocked_dependency_retire.status_code == 409
            assert "依赖项" in blocked_dependency_retire.json()["detail"]
            catalog = client.get("/api/v1/catalog/recipes", headers=participant)
            assert any(item["code"] == "qa_m4_recipe" for item in catalog.json())

            claim_payload = _ingredient("qa_claim_guard", "1.0.0", "宣称降血糖食材")
            rejected = client.post(
                "/api/v1/admin/content/items", headers=reviewer, json=claim_payload
            )
            assert rejected.status_code == 409
            assert "医疗功效表述" in rejected.json()["detail"]
    finally:
        _delete_codes(codes + ["qa_claim_guard"])
