"""M5 rule-only meal plan assembly from confirmed data and published content."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.care_plan import CarePlan
from app.models.content import EvidenceSource, KnowledgeItem
from app.models.food_safety import FoodSafetyProfile
from app.models.user import UserProfile
from app.repositories.health_repository import health_repository
from app.schemas.care_plan import (
    CarePlanRequest,
    CarePlanSnapshot,
    PlanDay,
    PlanAlternative,
    PlanGoal,
    PlanMaterial,
    PlanRecipe,
    ShoppingItem,
)
from app.schemas.content import IngredientPayload, RecipePayload
from app.services.content_service import content_service
from app.services.metric_catalog import resolve_metric_code
from app.services.safety_decision_service import evaluate_safety
from app.services.safety_rule_service import REQUIRED_SAFETY_RULE_CODES, active_safety_release


class CarePlanConflict(RuntimeError):
    pass


def _norm(value: str) -> str:
    return value.strip().casefold()


def _grams(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _published(item: KnowledgeItem | None) -> bool:
    return bool(item and item.status == "published" and item.is_active)


class CarePlanService:
    @staticmethod
    def _relevant_rules(recipes: list[PlanRecipe], maps: dict) -> list[KnowledgeItem]:
        recipe_codes = {recipe.code for recipe in recipes}
        ingredient_codes = {
            material.code for recipe in recipes for material in recipe.materials
        }
        explicit_codes = {
            code for recipe in recipes
            for code in (
                maps["recipe"][(recipe.code, recipe.version)].payload.get("contraindication_codes", [])
                if (recipe.code, recipe.version) in maps["recipe"] else []
            )
        }
        return [
            rule for rule in maps["contraindication"].values()
            if rule.code in explicit_codes or (
                rule.payload.get("subject_type") == "recipe"
                and rule.payload.get("subject_code") in recipe_codes
            ) or (
                rule.payload.get("subject_type") == "ingredient"
                and rule.payload.get("subject_code") in ingredient_codes
            )
        ]

    @staticmethod
    def _verified_safety_release(db: Session) -> bool:
        release = active_safety_release(db)
        return bool(
            release and release.attested and release.reviewer_id != "demo-reviewer"
            and REQUIRED_SAFETY_RULE_CODES.issubset(release.reviewed_rule_codes)
        )

    def _content_maps(self, db: Session):
        items = list(db.scalars(select(KnowledgeItem).where(
            KnowledgeItem.status == "published", KnowledgeItem.is_active.is_(True)
        )))
        sources = {source.ref: source for source in db.scalars(select(EvidenceSource))}
        return {
            kind: {(item.code, item.version): item for item in items if item.content_type == kind}
            for kind in ("ingredient", "recipe", "contraindication")
        }, sources

    def _approved(self, db: Session, item: KnowledgeItem, sources: dict[str, EvidenceSource]) -> bool:
        result = content_service.validate_item(db, item)
        if not result.valid:
            return False
        review = content_service.latest_review(db, item.id)
        if review is None or review.reviewer_id == "demo-reviewer":
            return False
        for ref in item.payload.get("source_refs", []):
            source = sources.get(ref)
            if (source is None or source.status != "active" or source.code.endswith("-demo")
                    or source.url_or_archive_ref.startswith("internal://synthetic-demo")):
                return False
        return True

    def _contraindicated(
        self, db: Session, profile: FoodSafetyProfile, item: KnowledgeItem,
        contraindications: dict, sources: dict[str, EvidenceSource],
    ) -> bool:
        references = set(item.payload.get("contraindication_codes", []))
        relevant = [
            rule for rule in contraindications.values()
            if rule.code in references or (
                rule.payload.get("subject_type") == item.content_type
                and rule.payload.get("subject_code") == item.code
            )
        ]
        if references - {rule.code for rule in relevant}:
            return True
        for rule in relevant:
            if not _published(rule) or not self._approved(db, rule, sources):
                return True
            trigger = rule.payload["trigger_type"]
            field = {
                "allergy": "allergens",
                "medication": "medications",
                "condition": "conditions",
                "liver_kidney": "liver_kidney_conditions",
                "clinician_restriction": "clinician_restrictions",
            }.get(trigger)
            values = getattr(profile, field, []) if field else (
                [profile.special_status] if trigger in {"pregnancy", "breastfeeding"} else []
            )
            if trigger == "missing_information":
                return True
            if {_norm(value) for value in values} & {
                _norm(value) for value in rule.payload["trigger_values"]
            }:
                return True
        return False

    def _ingredient_safe(
        self, db: Session, ingredient: KnowledgeItem | None,
        profile: FoodSafetyProfile, maps: dict, sources: dict,
    ) -> bool:
        if not _published(ingredient) or not self._approved(db, ingredient, sources):
            return False
        payload = IngredientPayload.model_validate(ingredient.payload)
        if payload.category == "food_medicine" and payload.catalog_status != "listed":
            return False
        if {_norm(value) for value in profile.allergens} & {
            _norm(value) for value in payload.allergens
        }:
            return False
        return not self._contraindicated(
            db, profile, ingredient, maps["contraindication"], sources
        )

    def _resolve_materials(
        self, db: Session, payload: RecipePayload, request: CarePlanRequest,
        profile: FoodSafetyProfile, maps: dict, sources: dict,
    ) -> list[PlanMaterial] | None:
        unavailable = set(request.unavailable_ingredient_codes)
        result: list[PlanMaterial] = []
        for material in payload.materials:
            options = [(material.code, material.version, Decimal("1"), None)] + [
                (sub.code, sub.version, Decimal(str(sub.ratio)), material.code)
                for sub in material.substitutions
            ]
            picked = None
            for code, version, ratio, substituted_for in options:
                if code in unavailable:
                    continue
                ingredient = maps["ingredient"].get((code, version))
                if not self._ingredient_safe(db, ingredient, profile, maps, sources):
                    continue
                picked = (ingredient, ratio, substituted_for)
                break
            if picked is None:
                return None
            ingredient, ratio, substituted_for = picked
            alternatives = []
            for sub in material.substitutions:
                alternative = maps["ingredient"].get((sub.code, sub.version))
                if sub.code in unavailable or not self._ingredient_safe(
                    db, alternative, profile, maps, sources
                ):
                    continue
                alternatives.append(PlanAlternative(
                    code=sub.code, version=sub.version, title=alternative.title,
                    grams=_grams(
                        Decimal(str(material.grams)) * Decimal(str(sub.ratio))
                        * Decimal(request.servings) / Decimal(payload.servings)
                    ),
                    note=sub.note,
                ))
            scaled = Decimal(str(material.grams)) * ratio * Decimal(request.servings) / Decimal(payload.servings)
            result.append(PlanMaterial(
                code=ingredient.code, version=ingredient.version, title=ingredient.title,
                grams=_grams(scaled), edible_part=IngredientPayload.model_validate(ingredient.payload).edible_part,
                preparation=material.preparation, substituted_for=substituted_for,
                alternatives=alternatives,
            ))
        return result

    def build_snapshot(self, db: Session, user: UserProfile, request: CarePlanRequest) -> CarePlanSnapshot:
        decision = evaluate_safety(db, user)
        if not decision.can_generate_plan:
            raise CarePlanConflict(decision.message)
        if not self._verified_safety_release(db):
            raise CarePlanConflict("安全规则仍缺少非演示专业审核发布版本，暂不能生成正式方案")
        report = health_repository.latest_report(db, user.id)
        profile = db.get(FoodSafetyProfile, user.id)
        if report is None or profile is None:
            raise CarePlanConflict("报告或安全档案未准备完成")
        metrics = health_repository.metrics_for_report(db, report.id)
        by_code = {metric.code: metric for metric in metrics if metric.confirmed}
        chosen = request.selected_metric_codes or [
            metric.code for metric in metrics if metric.confirmed and metric.flag == "attention"
        ][:3]
        if not chosen:
            raise CarePlanConflict("没有可用于匹配已审核食谱的关注指标；请先核对报告")
        if any(code not in by_code for code in chosen):
            raise CarePlanConflict("目标指标必须来自最新的已确认报告")
        if any(not by_code[code].reference_range.strip() for code in chosen):
            raise CarePlanConflict("所选指标缺少原报告参考范围，请先核对")
        if len(chosen) > 3:
            raise CarePlanConflict("每期最多选择 3 个目标指标")
        definitions = [resolve_metric_code(code) for code in chosen]
        if any(definition is None for definition in definitions):
            raise CarePlanConflict("所选指标尚未纳入 P0 标准字典")
        report_date = (report.examined_at or report.created_at).date().isoformat()
        goals = [PlanGoal(
            metric_id=by_code[code].id, code=code, name=by_code[code].name,
            value=by_code[code].value, unit=by_code[code].unit,
            reference_range=by_code[code].reference_range, report_date=report_date,
            statement=f"关注已确认的{by_code[code].name}记录，选择经审核的日常膳食模板。",
        ) for code in chosen]
        maps, sources = self._content_maps(db)
        candidates: list[PlanRecipe] = []
        for item in maps["recipe"].values():
            if not self._approved(db, item, sources):
                continue
            payload = RecipePayload.model_validate(item.payload)
            # A free-text frequency cannot safely drive a seven-day schedule.
            if payload.max_weekly_uses is None or not payload.dining_alternatives:
                continue
            tags = {_norm(tag) for tag in payload.target_tags}
            matched = [
                code for code, definition in zip(chosen, definitions)
                if _norm(code) in tags or _norm(definition.group) in tags or _norm(definition.name) in tags
            ]
            if not matched or self._contraindicated(
                db, profile, item, maps["contraindication"], sources
            ):
                continue
            total_minutes = sum(step.duration_minutes for step in payload.steps)
            if request.max_minutes is not None and total_minutes > request.max_minutes:
                continue
            if request.max_budget_yuan_per_serving is not None and (
                payload.estimated_cost_yuan_per_serving is None
                or payload.estimated_cost_yuan_per_serving > request.max_budget_yuan_per_serving
            ):
                continue
            if request.preferred_taste and _norm(request.preferred_taste) not in {
                _norm(tag) for tag in payload.taste_tags
            }:
                continue
            if request.region and _norm(request.region) not in {
                _norm(tag) for tag in payload.region_tags
            }:
                continue
            if request.available_cookware and not {
                _norm(tool) for step in payload.steps for tool in step.cookware
            }.issubset({_norm(tool) for tool in request.available_cookware}):
                continue
            materials = self._resolve_materials(db, payload, request, profile, maps, sources)
            if materials is None:
                continue
            review = content_service.latest_review(db, item.id)
            if review is None or item.published_at is None:
                continue
            time_points = (
                7.5 * (1 - total_minutes / request.max_minutes)
                if request.max_minutes is not None else 3.75
            )
            budget_points = (
                7.5 * (1 - payload.estimated_cost_yuan_per_serving / request.max_budget_yuan_per_serving)
                if request.max_budget_yuan_per_serving and payload.estimated_cost_yuan_per_serving is not None
                else 7.5 if request.max_budget_yuan_per_serving == 0 else 3.75
            )
            breakdown = {
                "approved_evidence": 30.0,
                "goal_match": round(25 * len(matched) / len(chosen), 1),
                "preference_match": 20.0 if request.preferred_taste or request.region else 10.0,
                "feasibility": round(time_points + budget_points, 1),
                "availability": 10.0 if not any(material.substituted_for for material in materials) else 5.0,
            }
            score = round(sum(breakdown.values()), 1)
            candidates.append(PlanRecipe(
                code=item.code, version=item.version, title=item.title,
                servings=request.servings, score=score, score_breakdown=breakdown,
                matched_metric_codes=matched,
                reason="关联已确认指标与经审核模板；分数仅用于候选排序，不代表健康效果。",
                goal_statement=payload.goal_statement, materials=materials,
                preprocessing=payload.preprocessing,
                steps=[step.model_dump(mode="json") for step in payload.steps],
                frequency=payload.frequency, cycle=payload.cycle,
                max_weekly_uses=payload.max_weekly_uses,
                serving_note=payload.serving_note, caution=payload.caution,
                nutrition_tags=payload.nutrition_tags,
                dining_alternatives=payload.dining_alternatives,
                total_minutes=total_minutes,
                estimated_cost_yuan_per_serving=payload.estimated_cost_yuan_per_serving,
                source_refs=payload.source_refs, review_id=review.id,
                published_at=item.published_at,
            ))
        candidates.sort(key=lambda recipe: (-recipe.score, recipe.code))
        if len(candidates) < 3:
            raise CarePlanConflict("符合目标和个人条件的已审核食谱不足 3 个，暂不生成方案；请等待专业审核或调整烹饪条件")
        recipes = candidates[:7]
        start = request.start_on or date.today()
        if start < date.today():
            raise CarePlanConflict("开始日期不能早于今天")
        if start > date.today() + timedelta(days=30):
            raise CarePlanConflict("开始日期最多可提前 30 天")
        chosen_days: list[PlanRecipe] = []
        uses: dict[str, int] = defaultdict(int)
        while len(chosen_days) < 7:
            added = False
            for recipe in recipes:
                if uses[recipe.code] >= recipe.max_weekly_uses:
                    continue
                chosen_days.append(recipe)
                uses[recipe.code] += 1
                added = True
                if len(chosen_days) == 7:
                    break
            if not added:
                raise CarePlanConflict("已审核食谱的每周使用上限不足以覆盖 7 天，请补充经审核模板")
        schedule = [PlanDay(
            day=index + 1, date=start + timedelta(days=index),
            recipe_code=recipe.code, recipe_version=recipe.version,
            servings=request.servings,
        ) for index, recipe in enumerate(chosen_days)]
        recipe_by_ref = {(recipe.code, recipe.version): recipe for recipe in recipes}
        grocery: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        material_meta: dict[tuple[str, str], PlanMaterial] = {}
        for day in schedule:
            for material in recipe_by_ref[(day.recipe_code, day.recipe_version)].materials:
                key = (material.code, material.version)
                grocery[key] += Decimal(str(material.grams))
                material_meta[key] = material
        shopping = [ShoppingItem(
            code=code, version=version, title=material_meta[(code, version)].title,
            total_grams=_grams(quantity), edible_part=material_meta[(code, version)].edible_part,
        ) for (code, version), quantity in sorted(grocery.items())]
        all_refs = set()
        for recipe in recipes:
            all_refs.update(recipe.source_refs)
            for material in recipe.materials:
                ingredient = maps["ingredient"][(material.code, material.version)]
                all_refs.update(ingredient.payload["source_refs"])
        relevant_rules = self._relevant_rules(recipes, maps)
        for rule in relevant_rules:
            all_refs.update(rule.payload["source_refs"])
        return CarePlanSnapshot(
            report_id=report.id, report_date=report_date,
            safety_rule_version=decision.rule_version, goals=goals, recipes=recipes,
            schedule=schedule, shopping_list=shopping,
            contraindication_refs=sorted(f"{rule.code}@{rule.version}" for rule in relevant_rules),
            source_refs=sorted(all_refs),
            constraints=request.model_copy(update={"start_on": start}),
            general_principle="按已审核食谱安排每日一项示例餐食；其余餐食仍需保持均衡，方案不构成全天营养处方。",
            professional_consultation="如报告注明需咨询医生的事项，或出现不适、用药及其他新限制，应暂停方案并先寻求专业评估。",
            follow_up="按报告、医生建议或既定体检计划复查；上传新报告后重新核对指标和约束。",
            disclaimer="仅供一般健康教育与自我记录，不用于诊断、治疗、调药或推断单个食谱的疗效。",
        )

    def current(self, db: Session, user: UserProfile) -> CarePlan | None:
        plan = db.scalar(select(CarePlan).where(CarePlan.user_id == user.id).order_by(
            CarePlan.created_at.desc(), CarePlan.id.desc()
        ).limit(1))
        return self.refresh_status(db, user, plan) if plan is not None else None

    def refresh_status(self, db: Session, user: UserProfile, plan: CarePlan) -> CarePlan:
        if plan.status not in {"READY", "ACTIVE"}:
            return plan
        try:
            snapshot = CarePlanSnapshot.model_validate(plan.snapshot)
            self._check_live(db, user, snapshot)
        except (CarePlanConflict, ValueError):
            plan.status = "PAUSED"
            plan.paused_at = datetime.now(timezone.utc)
            latest = health_repository.latest_report(db, user.id)
            plan.pause_reason = "new_report" if latest and latest.id != plan.report_id else "reassessment_required"
            db.add(AuditLog(event_type="care_plan.paused", actor_id=user.id, payload={
                "plan_id": plan.id, "reason": plan.pause_reason,
            }))
            db.commit()
            db.refresh(plan)
        return plan

    def _check_live(self, db: Session, user: UserProfile, snapshot: CarePlanSnapshot) -> None:
        decision = evaluate_safety(db, user)
        if not decision.can_generate_plan or decision.rule_version != snapshot.safety_rule_version:
            raise CarePlanConflict("安全规则或个人风险状态已变化，请重新评估")
        if not self._verified_safety_release(db):
            raise CarePlanConflict("安全规则的正式审核状态已变化，请重新评估")
        report = health_repository.latest_report(db, user.id)
        if report is None or report.id != snapshot.report_id:
            raise CarePlanConflict("最新报告已变化，请重新生成方案")
        if (report.examined_at or report.created_at).date().isoformat() != snapshot.report_date:
            raise CarePlanConflict("报告检查日期已变化，请重新生成方案")
        current_metrics = {metric.id: metric for metric in health_repository.metrics_for_report(db, report.id)}
        if any(
            goal.metric_id not in current_metrics
            or not current_metrics[goal.metric_id].confirmed
            or current_metrics[goal.metric_id].value != goal.value
            or current_metrics[goal.metric_id].unit != goal.unit
            or current_metrics[goal.metric_id].reference_range != goal.reference_range
            for goal in snapshot.goals
        ):
            raise CarePlanConflict("关联指标已变化，请重新生成方案")
        profile = db.get(FoodSafetyProfile, user.id)
        if profile is None:
            raise CarePlanConflict("安全档案已变化，请重新生成方案")
        maps, sources = self._content_maps(db)
        current_rules = self._relevant_rules(snapshot.recipes, maps)
        if sorted(f"{rule.code}@{rule.version}" for rule in current_rules) != snapshot.contraindication_refs:
            raise CarePlanConflict("禁忌规则版本已变化，请重新生成方案")
        if any(not self._approved(db, rule, sources) for rule in current_rules):
            raise CarePlanConflict("禁忌规则审核状态已变化，请重新生成方案")
        for recipe in snapshot.recipes:
            item = maps["recipe"].get((recipe.code, recipe.version))
            if not _published(item) or not self._approved(db, item, sources):
                raise CarePlanConflict("食谱版本已变化，请重新生成方案")
            if self._contraindicated(db, profile, item, maps["contraindication"], sources):
                raise CarePlanConflict("食谱禁忌已变化，请重新生成方案")
            for material in recipe.materials:
                ingredient = maps["ingredient"].get((material.code, material.version))
                if not self._ingredient_safe(db, ingredient, profile, maps, sources):
                    raise CarePlanConflict("食材版本已变化，请重新生成方案")

    def create(self, db: Session, user: UserProfile, request: CarePlanRequest) -> CarePlan:
        previous = self.current(db, user)
        if previous is not None and previous.pause_reason == "adverse_feedback":
            raise CarePlanConflict("曾记录不适，不能自动生成新方案；请先寻求专业评估")
        latest = health_repository.latest_report(db, user.id)
        if previous is not None and latest is not None and previous.report_id != latest.id:
            raise CarePlanConflict("已有旧方案和新报告，请使用复查修订流程生成新版本")
        snapshot = self.build_snapshot(db, user, request)
        payload = snapshot.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        existing = db.scalar(select(CarePlan).where(
            CarePlan.user_id == user.id, CarePlan.request_hash == digest
        ))
        if existing is not None:
            return existing
        if previous is not None and previous.status == "READY":
            if date.fromisoformat(previous.snapshot["schedule"][0]["date"]) >= date.today():
                raise CarePlanConflict("已有待确认的方案草案，请先核对当前草案")
            previous.status = "PAUSED"
            previous.pause_reason = "expired_draft"
            previous.paused_at = datetime.now(timezone.utc)
            db.add(AuditLog(event_type="care_plan.paused", actor_id=user.id, payload={
                "plan_id": previous.id, "reason": "expired_draft",
            }))
        active = db.scalar(select(CarePlan).where(CarePlan.user_id == user.id, CarePlan.status == "ACTIVE"))
        if active is not None:
            raise CarePlanConflict("已有进行中的方案，请先处理当前方案")
        plan = CarePlan(
            user_id=user.id, report_id=snapshot.report_id, request_hash=digest,
            snapshot=payload, version=(previous.version + 1 if previous else 1),
            previous_plan_id=(previous.id if previous else None),
        )
        db.add(plan)
        db.flush()
        db.add(AuditLog(event_type="care_plan.ready", actor_id=user.id, payload={
            "plan_id": plan.id, "report_id": plan.report_id,
            "recipe_refs": [f"{item.code}@{item.version}" for item in snapshot.recipes],
        }))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise CarePlanConflict("方案状态已变化，请刷新后重试") from exc
        db.refresh(plan)
        return plan

    def activate(self, db: Session, user: UserProfile, plan_id: str) -> CarePlan:
        plan = db.get(CarePlan, plan_id)
        if plan is None or plan.user_id != user.id:
            raise LookupError("方案不存在")
        if plan.status == "ACTIVE":
            return self.current(db, user) or plan
        if plan.status != "READY":
            raise CarePlanConflict("当前方案不可确认，请重新生成")
        snapshot = CarePlanSnapshot.model_validate(plan.snapshot)
        self._check_live(db, user, snapshot)
        if snapshot.schedule[0].date < date.today():
            raise CarePlanConflict("方案开始日期已过，请重新生成")
        rebuilt = self.build_snapshot(db, user, snapshot.constraints)
        if rebuilt.model_dump(mode="json") != plan.snapshot:
            raise CarePlanConflict("报告、档案或内容已变化，请重新生成方案")
        if plan.previous_plan_id:
            previous = db.get(CarePlan, plan.previous_plan_id)
            if previous is None or previous.user_id != user.id:
                raise CarePlanConflict("旧方案版本不存在，请重新生成")
            if previous.status not in {"PAUSED", "SUPERSEDED"}:
                raise CarePlanConflict("旧方案尚未暂停，不能确认新版本")
            if previous.status == "PAUSED":
                previous.status = "SUPERSEDED"
                previous.superseded_at = datetime.now(timezone.utc)
        plan.status = "ACTIVE"
        plan.activated_at = datetime.now(timezone.utc)
        db.add(AuditLog(event_type="care_plan.activated", actor_id=user.id, payload={"plan_id": plan.id}))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise CarePlanConflict("已有进行中的方案") from exc
        db.refresh(plan)
        return plan


care_plan_service = CarePlanService()
