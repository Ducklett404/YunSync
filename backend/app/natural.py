from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from .database import ContentRepository
from .maas import PROMPT_VERSION, MaaSClient, mentioned_ingredients
from .models import AiOutputAudit
from .schemas import NaturalRecommendationRequest, PantryRecommendationRequest, TodayRecommendationRequest
from .services import INGREDIENT_ALIAS_GROUPS, YunSyncService, _equivalent


URGENT_TERMS = (
    "高热", "高烧", "39度", "39℃", "体温39", "呼吸困难", "喘不上气", "无法呼吸",
    "气短加重", "胸痛", "胸口痛", "胸部疼痛", "意识异常", "意识不清", "昏迷",
    "叫不醒", "持续呕吐", "一直吐", "反复呕吐", "明显脱水", "无法喝水",
    "喝不下水", "尿量明显减少", "持续加重", "越来越严重", "明显恶化",
)
UNSUPPORTED_RESTRICTIONS = (
    "低盐", "限盐", "低钠", "限钠", "限钾", "低钾", "限磷", "低磷",
    "限糖", "糖尿病饮食", "流质", "半流质", "低嘌呤", "低蛋白",
)
MEDICAL_TERMS = ("糖尿病", "肾病", "肿瘤", "透析", "正在服药", "吃药", "用药", "处方", "治愈", "治疗", "治病", "治感冒", "退烧", "药方")
OUT_OF_SCOPE_TERMS = ("孕妇", "怀孕", "哺乳", "儿童", "小孩", "婴儿", "未成年")
COMMON_PANTRY_INGREDIENTS = ("鸡蛋",)
FEELING_TERMS = {
    "有点着凉": ("着凉", "受凉", "轻微感冒", "感冒"),
    "胃口较差": ("胃口差", "没胃口", "食欲差"),
    "睡眠不足": ("睡眠不足", "没睡好", "熬夜"),
    "口干": ("口干", "嘴干"),
    "排便不规律": ("排便不规律",),
}
EXPLANATION_TEXT = {
    "seasonal_content": "结合今日节庆或节气内容。",
    "weather_ranked": "天气已参与排序。",
    "region_ranked": "地域标签已参与排序。",
    "feeling_ranked": "已考虑当天受控体感。",
    "pantry_match": "与已登记食材和厨具相匹配。",
    "safety_filtered": "已排除已知过敏和明确饮食限制。",
    "general_safe_content": "选自当前可用的审核食谱库。",
}


def _private_text(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已移除]", value)
    value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[电话已移除]", value)
    value = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "[证件号已移除]", value)
    return re.sub(r"我叫[\u4e00-\u9fa5]{2,4}", "[姓名已移除]", value)


def _restrictions_from_text(text: str, known: list[str]) -> list[str]:
    restrictions: list[str] = []
    for item in known:
        for match in re.finditer(re.escape(item), text):
            before = text[max(0, match.start() - 4):match.start()]
            after = text[match.end():match.end() + 5]
            if any(token in after for token in ("过敏", "不耐受", "不能吃", "别放", "不吃")) or any(token in before for token in ("不吃", "不能吃", "禁", "忌")):
                restrictions.append(item)
                break
    return list(dict.fromkeys(restrictions))


class NaturalRecommendationService:
    def __init__(self, repository: ContentRepository, recommendation: YunSyncService, maas: MaaSClient):
        self.repository = repository
        self.recommendation = recommendation
        self.maas = maas

    def _audit(self, request_id: str, stage: str, status: str, recipe: dict[str, Any] | None) -> None:
        self.repository.write_ai_audit(AiOutputAudit(
            id=str(uuid.uuid4()), request_id=request_id, prompt_version=PROMPT_VERSION,
            stage=stage, status=status, recipe_id=recipe["id"] if recipe else None,
            recipe_version=recipe["version"] if recipe else None,
        ))

    def recommend(self, request: NaturalRecommendationRequest) -> dict[str, Any]:
        text = request.text
        request_id = str(uuid.uuid4())
        scope_block = request.serviceScope != "adult" or any(term in text for term in OUT_OF_SCOPE_TERMS)
        urgent_block = any(term in text for term in URGENT_TERMS)
        medical_block = (
            request.hasMedicalConditions or request.hasMedications
            or any(term in text for term in MEDICAL_TERMS)
            or any(term in text for term in UNSUPPORTED_RESTRICTIONS)
            or any(term in item for item in request.dietaryRestrictions for term in UNSUPPORTED_RESTRICTIONS)
        )
        if urgent_block or scope_block or medical_block:
            level = "urgent" if urgent_block else "out-of-scope" if scope_block else "medical-review"
            message = (
                "当前描述需要先处理健康风险，请及时咨询医生；情况紧急时联系当地急救服务。"
                if urgent_block else "当前情况需要专业人员结合具体情况给出建议，已停止个体化推荐。"
            )
            self._audit(request_id, "safety", "blocked_" + level, None)
            return {"requestId": request_id, "main": None, "alternatives": [], "safety": {"blocked": True, "level": level, "message": message}, "degraded": [], "ai": {"status": "not_called", "promptVersion": PROMPT_VERSION}}

        recipes = self.repository.list_recipes()
        known = list(dict.fromkeys(
            [item.get("name", "") for recipe in recipes for item in recipe.ingredients]
            + [item for recipe in recipes for item in recipe.allergens]
            + [alias for group in INGREDIENT_ALIAS_GROUPS for alias in group]
            + list(COMMON_PANTRY_INGREDIENTS)
        ))
        known = [item for item in known if item]
        preference_tags = sorted({tag for recipe in recipes for tag in recipe.tags})
        text_restrictions = _restrictions_from_text(text, known)
        restrictions = list(dict.fromkeys([*request.allergies, *request.dietaryRestrictions, *text_restrictions]))
        mentioned = [item for item in mentioned_ingredients(text, known) if not any(_equivalent(item, restriction) for restriction in restrictions)]
        baseline_feelings = [label for label, terms in FEELING_TERMS.items() if any(term in text for term in terms)]
        pantry_intent = any(term in text for term in ("手上有", "家里有", "现成", "冰箱", "食材", "做什么", "做点", "做饭")) or (bool(mentioned) and "我有" in text)
        clean_text = _private_text(text)
        tags, extract_status = self.maas.extract(clean_text, known, preference_tags)
        self._audit(request_id, "extract", extract_status, None)
        if tags:
            # The model may only confirm ingredient mentions; it cannot invent pantry stock.
            model_ingredients = [item for item in tags.ingredients if any(_equivalent(item, value) for value in mentioned)]
            ingredients = list(dict.fromkeys([*mentioned, *model_ingredients]))[:15]
            feelings = list(dict.fromkeys([*baseline_feelings, *tags.feelings]))[:4]
            preferences = list(dict.fromkeys([*request.preferences, *tags.preferences]))[:10]
            pantry_intent = pantry_intent or tags.intent == "pantry"
            max_minutes = tags.maxMinutes or 45
        else:
            ingredients, feelings, preferences, max_minutes = mentioned[:15], baseline_feelings, request.preferences, 45
        feelings = [item for item in feelings if item != "正常"] or ["正常"]

        if pantry_intent and not ingredients:
            self._audit(request_id, "explain", "no_result", None)
            return {
                "requestId": request_id, "mode": "pantry", "main": None, "alternatives": [],
                "safety": {"blocked": False, "level": "clear", "message": "仅供日常饮食参考。"},
                "message": "没有识别到当前审核食谱库可匹配的食材，请换一种说法或到食材页逐项选择。",
                "degraded": ["maas"] if not tags else [],
                "ai": {"status": "rules_fallback", "extractStatus": extract_status, "explainStatus": "no_result", "promptVersion": PROMPT_VERSION},
            }

        date_value = request.date or date.today()
        if pantry_intent and ingredients:
            pantry = self.recommendation.recommend_pantry(PantryRecommendationRequest(
                ingredients=ingredients,
                tools=request.tools or ["汤锅", "炒锅", "菜刀"],
                maxMinutes=max_minutes,
                allergies=restrictions,
                dietaryRestrictions=[],
            ))
            selected = [item["recipe"] for item in pantry["matches"]]
            context = self.recommendation.context_today(request.city, date_value)
            reasons = ["pantry_match"] + (["safety_filtered"] if restrictions else [])
            payload = {
                "main": selected[0] if selected else None,
                "alternatives": selected[1:3],
                "seasonalContent": context["seasonalContent"],
                "weather": context["weather"],
                "reasons": reasons,
                "degraded": sorted(set(pantry["degraded"] + context["degraded"])),
                "message": pantry["message"],
                "mode": "pantry",
            }
        else:
            today = self.recommendation.recommend_today(TodayRecommendationRequest(
                city=request.city, region=request.region, date=date_value,
                feelings=feelings, allergies=restrictions, dietaryRestrictions=[],
                preferences=preferences, constitutionTags=request.constitutionTags,
                recentRecipeIds=request.recentRecipeIds,
            ))
            payload = {**today, "mode": "today"}

        main = payload["main"]
        clauses = [item for item in payload["reasons"] if item in EXPLANATION_TEXT][:3]
        explain_status = "no_result"
        if main and tags:
            model_clauses, explain_status = self.maas.explain(main, payload["reasons"])
            if model_clauses:
                clauses = model_clauses
        elif main:
            explain_status = "rules_fallback"
        self._audit(request_id, "explain", explain_status, main)
        payload.update({
            "requestId": request_id,
            "safety": {"blocked": False, "level": "clear", "message": "仅供日常饮食参考。"},
            "ai": {"status": "assisted" if tags and explain_status in {"ok", "cache"} else "rules_fallback", "extractStatus": extract_status, "explainStatus": explain_status, "promptVersion": PROMPT_VERSION},
            "explanation": "".join(EXPLANATION_TEXT[item] for item in clauses),
            "factors": {
                "weather": payload["weather"].get("text", "天气不可用") if payload.get("weather") else "天气不可用",
                "region": request.region,
                "seasonal": payload.get("seasonalContent", {}).get("name") if payload.get("seasonalContent") else None,
                "feelings": feelings,
                "ingredients": ingredients if pantry_intent else [],
            },
        })
        if payload["ai"]["status"] != "assisted":
            payload["degraded"] = sorted(set([*payload["degraded"], "maas"]))
        return payload
