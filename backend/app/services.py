from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date
from typing import Any, Iterable

from .cache import ResilientCache
from .config import Settings
from .database import ContentRepository
from .models import Recipe, RecommendationAudit, SeasonalContent
from .schemas import PantryRecommendationRequest, TodayRecommendationRequest
from .weather import WeatherClient


RULE_VERSION = "m12-deterministic-v1"
MISSING_SENTINEL = {"missing": True}

INGREDIENT_ALIAS_GROUPS = [
    ["番茄", "西红柿"],
    ["北豆腐", "嫩豆腐", "豆腐"],
    ["大豆", "豆类", "豆腐"],
    ["大蒜", "蒜"],
    ["当季绿叶菜", "绿叶菜", "青菜", "时蔬"],
    ["雪梨", "梨"],
    ["白萝卜", "萝卜"],
    ["小麦粉", "面粉"],
    ["红豆沙", "豆沙"],
    ["食用油", "油"],
]
AUTOMATIC_BASICS = ["清水"]


def _compact(value: str) -> str:
    return re.sub(r"[\s，,。.!！?？、]", "", value.strip().lower())


def _equivalent(left: str, right: str, groups: list[list[str]] = INGREDIENT_ALIAS_GROUPS) -> bool:
    a, b = _compact(left), _compact(right)
    if a == b:
        return True
    return any(a in {_compact(item) for item in group} and b in {_compact(item) for item in group} for group in groups)


def _contains_equivalent(values: Iterable[str], expected: str) -> bool:
    return any(_equivalent(value, expected) for value in values)


def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "name": recipe.name,
        "category": recipe.category,
        "minutes": recipe.minutes,
        "tags": recipe.tags,
        "reason": recipe.reason,
        "servings": recipe.servings,
        "ingredients": recipe.ingredients,
        "tools": recipe.tools,
        "steps": recipe.steps,
        "substitutions": recipe.substitutions,
        "allergens": recipe.allergens,
        "exclusions": recipe.exclusions,
        "regions": recipe.regions,
        "sceneTags": recipe.scene_tags,
        "sourceNote": recipe.source_note,
        "source": recipe.source,
        "isDemo": recipe.is_demo,
        "version": recipe.version,
        "reviewStatus": recipe.review_status,
        "updatedAt": recipe.content_updated_at.isoformat(),
    }


def seasonal_to_dict(content: SeasonalContent) -> dict[str, Any]:
    return {
        "id": content.id,
        "name": content.name,
        "kind": content.kind,
        "cultureNote": content.culture_note,
        "dateRule": content.date_rule,
        "regions": content.regions,
        "recipeIds": content.recipe_ids,
        "source": content.source,
        "isDemo": content.is_demo,
        "version": content.version,
        "reviewStatus": content.review_status,
        "updatedAt": content.content_updated_at.isoformat(),
    }


def _cache_digest(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _conflicts(recipe: Recipe, restrictions: Iterable[str]) -> bool:
    ingredients = [item.get("name", "") for item in recipe.ingredients]
    searchable = [*recipe.allergens, *recipe.exclusions, *ingredients]
    for restriction in restrictions:
        if any(_equivalent(restriction, value) for value in searchable):
            return True
        token = _compact(restriction).replace("过敏", "").replace("不耐受", "")
        if token and any(token in _compact(value) for value in searchable):
            return True
    return False


def _find_content_for_date(
    contents: list[SeasonalContent], date_value: date
) -> SeasonalContent | None:
    date_key = date_value.isoformat()
    year_key = str(date_value.year)
    for content in contents:
        fixtures = content.date_rule.get("gregorianFixtures", {})
        if fixtures.get(year_key) == date_key:
            return content
    return None


class YunSyncService:
    def __init__(
        self,
        settings: Settings,
        repository: ContentRepository,
        cache: ResilientCache,
        weather: WeatherClient,
    ):
        self.settings = settings
        self.repository = repository
        self.cache = cache
        self.weather = weather

    def context_today(self, city: str, date_value: date) -> dict[str, Any]:
        contents = self.repository.list_seasonal_contents()
        content = _find_content_for_date(contents, date_value)
        weather, weather_cache, cache_degraded = self.weather.get(city)
        degraded: list[str] = []
        if not weather.get("available"):
            degraded.append("weather")
        if cache_degraded:
            degraded.append("cache")
        if self.settings.database_kind != "postgresql":
            degraded.append("database_local")
        return {
            "date": date_value.isoformat(),
            "weekday": date_value.strftime("%A"),
            "city": city,
            "seasonalContent": seasonal_to_dict(content) if content else None,
            "weather": weather,
            "cache": {"status": weather_cache, "backend": "memory" if cache_degraded else "redis"},
            "degraded": sorted(set(degraded)),
        }

    def recipe(self, recipe_id: str) -> tuple[dict[str, Any] | None, str, bool]:
        cache_key = self.cache.key("recipe", recipe_id)
        cached = self.cache.get_json(cache_key)
        if cached.hit:
            if cached.value == MISSING_SENTINEL:
                return None, "hit", cached.degraded
            return dict(cached.value), "hit", cached.degraded
        recipe = self.repository.get_recipe(recipe_id)
        if recipe is None:
            self.cache.set_json(cache_key, MISSING_SENTINEL, self.settings.negative_ttl_seconds)
            return None, "miss", cached.degraded
        payload = recipe_to_dict(recipe)
        _, degraded = self.cache.set_json(
            cache_key, payload, self.settings.recommendation_ttl_seconds
        )
        return payload, "miss", cached.degraded or degraded

    def recommend_today(self, request: TodayRecommendationRequest) -> dict[str, Any]:
        raw_request = request.model_dump(mode="json")
        cache_key = self.cache.key("recommendation:today", _cache_digest(raw_request))
        cached = self.cache.get_json(cache_key)
        if cached.hit:
            payload = dict(cached.value)
            payload["requestId"] = str(uuid.uuid4())
            payload["cache"] = {
                "status": "hit",
                "backend": cached.backend,
                "ttlSeconds": self.settings.recommendation_ttl_seconds,
            }
            if cached.degraded and "cache" not in payload["degraded"]:
                payload["degraded"].append("cache")
            return payload

        date_value = request.date or date.today()
        recipes = self.repository.list_recipes()
        contents = self.repository.list_seasonal_contents()
        seasonal = _find_content_for_date(contents, date_value)
        weather, _, weather_cache_degraded = self.weather.get(request.city)
        restrictions = [*request.allergies, *request.dietaryRestrictions]
        safe_recipes = [recipe for recipe in recipes if not _conflicts(recipe, restrictions)]
        seasonal_ids = set(seasonal.recipe_ids if seasonal else [])
        reason_codes: list[str] = []

        ranked: list[tuple[int, Recipe]] = []
        for recipe in safe_recipes:
            score = 0
            if recipe.id in seasonal_ids:
                score += 100
            if request.region in recipe.regions:
                score += 12
            if "全国" in recipe.regions:
                score += 4
            if any(item in request.feelings for item in ("有点着凉", "胃口较差")) and recipe.category in ("粥", "汤"):
                score += 8
            if "睡眠不足" in request.feelings and recipe.minutes <= 30:
                score += 5
            if "口干" in request.feelings and recipe.category in ("汤", "饮品"):
                score += 7
            score += len(set(request.preferences).intersection(recipe.tags)) * 3
            score += min(4, len(set(request.constitutionTags).intersection(set(recipe.tags + recipe.scene_tags))) * 2)
            if weather.get("available"):
                temperature = weather.get("temperature")
                if isinstance(temperature, (int, float)) and temperature <= 10 and recipe.category in ("粥", "汤"):
                    score += 8
                if isinstance(temperature, (int, float)) and temperature >= 28 and (
                    "清淡" in recipe.tags or recipe.category in ("汤", "饮品")
                ):
                    score += 6
            if recipe.id in request.recentRecipeIds:
                score -= 60
            ranked.append((score, recipe))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        selected = [recipe for _, recipe in ranked[:3]]

        if seasonal and any(recipe.id in seasonal_ids for recipe in selected):
            reason_codes.append("seasonal_content")
        if restrictions:
            reason_codes.append("safety_filtered")
        if weather.get("available"):
            reason_codes.append("weather_ranked")
        if request.region != "全国":
            reason_codes.append("region_ranked")
        if request.feelings != ["正常"]:
            reason_codes.append("feeling_ranked")
        if not reason_codes:
            reason_codes.append("general_safe_content")

        degraded: list[str] = []
        if not weather.get("available"):
            degraded.append("weather")
        if cached.degraded or weather_cache_degraded:
            degraded.append("cache")
        if self.settings.database_kind != "postgresql":
            degraded.append("database_local")

        request_id = str(uuid.uuid4())
        payload = {
            "requestId": request_id,
            "ruleVersion": RULE_VERSION,
            "main": recipe_to_dict(selected[0]) if selected else None,
            "alternatives": [recipe_to_dict(item) for item in selected[1:]],
            "seasonalContent": seasonal_to_dict(seasonal) if seasonal else None,
            "weather": weather,
            "reasons": reason_codes,
            "filteredCount": len(recipes) - len(safe_recipes),
            "degraded": sorted(set(degraded)),
            "cache": {
                "status": "miss",
                "backend": cached.backend,
                "ttlSeconds": self.settings.recommendation_ttl_seconds,
            },
        }
        self.repository.write_audit(
            RecommendationAudit(
                id=request_id,
                request_kind="today",
                rule_version=RULE_VERSION,
                candidate_ids=[item.id for item in safe_recipes],
                selected_ids=[item.id for item in selected],
                reason_codes=reason_codes,
                degraded_flags=payload["degraded"],
            )
        )
        cached_payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        _, cache_write_degraded = self.cache.set_json(
            cache_key, cached_payload, self.settings.recommendation_ttl_seconds
        )
        if cache_write_degraded and "cache" not in payload["degraded"]:
            payload["degraded"].append("cache")
            payload["cache"]["backend"] = "memory"
        return payload

    def recommend_pantry(self, request: PantryRecommendationRequest) -> dict[str, Any]:
        raw_request = request.model_dump(mode="json")
        cache_key = self.cache.key("recommendation:pantry", _cache_digest(raw_request))
        cached = self.cache.get_json(cache_key)
        if cached.hit:
            payload = dict(cached.value)
            payload["requestId"] = str(uuid.uuid4())
            payload["cache"] = {
                "status": "hit",
                "backend": cached.backend,
                "ttlSeconds": self.settings.recommendation_ttl_seconds,
            }
            if cached.degraded and "cache" not in payload["degraded"]:
                payload["degraded"].append("cache")
            return payload

        recipes = self.repository.list_recipes()
        restrictions = [*request.allergies, *request.dietaryRestrictions]
        safe_recipes = [recipe for recipe in recipes if not _conflicts(recipe, restrictions)]
        matches: list[dict[str, Any]] = []
        for recipe in safe_recipes:
            if recipe.minutes > request.maxMinutes:
                continue
            if not all(any(_equivalent(owned, needed, [[needed]]) for owned in request.tools) for needed in recipe.tools):
                continue
            matched: list[str] = []
            missing: list[str] = []
            missing_key: list[str] = []
            substitutions_used: list[dict[str, str]] = []
            for ingredient in recipe.ingredients:
                name = ingredient.get("name", "")
                if _contains_equivalent(AUTOMATIC_BASICS, name):
                    continue
                if _contains_equivalent(request.ingredients, name):
                    matched.append(name)
                    continue
                substitution = next(
                    (
                        item
                        for item in recipe.substitutions
                        if _equivalent(item.get("from", ""), name)
                        and _contains_equivalent(request.ingredients, item.get("to", ""))
                    ),
                    None,
                )
                if substitution:
                    substitutions_used.append(substitution)
                    matched.append(substitution["to"])
                    continue
                missing.append(name)
                if ingredient.get("isKey"):
                    missing_key.append(name)
            if missing_key or len(missing) > request.maxAdditionalIngredients:
                continue
            kind = "complete"
            if missing:
                kind = "missing"
            elif substitutions_used:
                kind = "substitution"
            matches.append(
                {
                    "recipe": recipe_to_dict(recipe),
                    "kind": kind,
                    "matchedIngredients": matched,
                    "missingIngredients": missing,
                    "substitutionsUsed": substitutions_used,
                    "targetServings": request.targetServings,
                }
            )
        kind_rank = {"complete": 0, "substitution": 1, "missing": 2}
        matches.sort(
            key=lambda item: (
                kind_rank[item["kind"]],
                len(item["missingIngredients"]),
                item["recipe"]["minutes"],
                item["recipe"]["id"],
            )
        )
        matches = matches[:5]
        reason_codes = ["pantry_match", "safety_filtered"] if restrictions else ["pantry_match"]
        degraded = ["database_local"] if self.settings.database_kind != "postgresql" else []
        if cached.degraded:
            degraded.append("cache")
        request_id = str(uuid.uuid4())
        payload = {
            "requestId": request_id,
            "ruleVersion": RULE_VERSION,
            "matches": matches,
            "filteredCount": len(recipes) - len(safe_recipes),
            "message": (
                f"找到 {len(matches)} 个安全匹配；完全具备材料的结果优先。"
                if matches
                else "没有安全匹配；系统不会临时拼出未经审核的配方。"
            ),
            "degraded": sorted(set(degraded)),
            "cache": {
                "status": "miss",
                "backend": cached.backend,
                "ttlSeconds": self.settings.recommendation_ttl_seconds,
            },
        }
        self.repository.write_audit(
            RecommendationAudit(
                id=request_id,
                request_kind="pantry",
                rule_version=RULE_VERSION,
                candidate_ids=[item.id for item in safe_recipes],
                selected_ids=[item["recipe"]["id"] for item in matches],
                reason_codes=reason_codes,
                degraded_flags=payload["degraded"],
            )
        )
        cached_payload = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
        _, cache_write_degraded = self.cache.set_json(
            cache_key, cached_payload, self.settings.recommendation_ttl_seconds
        )
        if cache_write_degraded and "cache" not in payload["degraded"]:
            payload["degraded"].append("cache")
            payload["cache"]["backend"] = "memory"
        return payload
