from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import UserProfile
from app.repositories.action_repository import action_repository
from app.schemas.action import (
    ActionTemplateAdminOut,
    ActionTemplateStatusUpdate,
    ActionTemplateVersionCreate,
)
from app.services.template_admin_service import (
    TemplateConflictError,
    template_admin_service,
)


router = APIRouter(prefix="/admin/action-templates", tags=["action-template-admin"])


@router.get("", response_model=list[ActionTemplateAdminOut])
def list_templates(
    _reviewer: UserProfile = Depends(require_permission("templates:manage")),
    db: Session = Depends(get_db),
):
    return action_repository.list_all(db)


@router.post("/{template_id}/versions", response_model=ActionTemplateAdminOut)
def create_template_version(
    template_id: str,
    payload: ActionTemplateVersionCreate,
    reviewer: UserProfile = Depends(require_permission("templates:manage")),
    db: Session = Depends(get_db),
):
    try:
        return template_admin_service.create_version(
            db, template_id, payload.version, reviewer.id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TemplateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{template_id}/status", response_model=ActionTemplateAdminOut)
def update_template_status(
    template_id: str,
    payload: ActionTemplateStatusUpdate,
    reviewer: UserProfile = Depends(require_permission("templates:manage")),
    db: Session = Depends(get_db),
):
    try:
        return template_admin_service.update_status(
            db, template_id, payload, reviewer.id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TemplateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
