from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_active_participant
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.content import CatalogItemOut
from app.services.content_service import content_service


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/ingredients", response_model=list[CatalogItemOut])
def list_ingredients(
    _user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return content_service.published_catalog(db, "ingredient")


@router.get("/recipes", response_model=list[CatalogItemOut])
def list_recipes(
    _user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return content_service.published_catalog(db, "recipe")


@router.get("/contraindications", response_model=list[CatalogItemOut])
def list_contraindications(
    _user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return content_service.published_catalog(db, "contraindication")
