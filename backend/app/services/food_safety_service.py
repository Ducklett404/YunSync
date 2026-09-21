from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.food_safety import FoodSafetyProfile
from app.models.user import UserProfile
from app.schemas.food_safety import FoodSafetyProfileIn, FoodSafetyProfileOut, Readiness


def _readiness(data: FoodSafetyProfileIn, user: UserProfile) -> Readiness:
    if user.screening_status == "needs_professional_review" or user.high_risk:
        return "needs_professional_review"
    if user.screening_status != "eligible" or "unknown" in (
        data.allergy_status,
        data.medication_status,
        data.condition_status,
        data.liver_kidney_status,
        data.clinician_restriction_status,
        data.special_status,
    ):
        return "needs_information"
    if "present" in (
        data.allergy_status,
        data.medication_status,
        data.condition_status,
        data.liver_kidney_status,
        data.clinician_restriction_status,
    ) or data.special_status != "none":
        return "needs_professional_review"
    return "awaiting_review_rules"


def get_food_safety_profile(db: Session, user: UserProfile) -> FoodSafetyProfileOut:
    stored = db.get(FoodSafetyProfile, user.id)
    values = (
        {field: getattr(stored, field) for field in FoodSafetyProfileIn.model_fields}
        if stored
        else {
            "allergy_status": "unknown",
            "medication_status": "unknown",
            "condition_status": "unknown",
            "liver_kidney_status": "unknown",
            "clinician_restriction_status": "unknown",
            "special_status": "unknown",
        }
    )
    data = FoodSafetyProfileIn.model_validate(values)
    return FoodSafetyProfileOut(
        **data.model_dump(),
        readiness=_readiness(data, user),
        updated_at=stored.updated_at if stored else None,
    )


def save_food_safety_profile(
    db: Session, user: UserProfile, data: FoodSafetyProfileIn
) -> FoodSafetyProfileOut:
    stored = db.get(FoodSafetyProfile, user.id)
    if stored is None:
        stored = FoodSafetyProfile(user_id=user.id)
        changed_fields = list(FoodSafetyProfileIn.model_fields)
    else:
        changed_fields = [
            field for field, value in data.model_dump().items()
            if getattr(stored, field) != value
        ]
    for field, value in data.model_dump().items():
        setattr(stored, field, value)
    stored.updated_at = datetime.now(timezone.utc)
    db.add(stored)
    db.add(
        AuditLog(
            event_type="food_safety_profile.updated",
            actor_id=user.id,
            payload={"changed_fields": sorted(changed_fields), "readiness": _readiness(data, user)},
        )
    )
    db.commit()
    db.refresh(stored)
    return get_food_safety_profile(db, user)
