from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.privacy import AccountDeletionIn, PrivacyRequestOut, PrivacyStatusOut
from app.services.identity_service import identity_service
from app.services.privacy_service import privacy_service


router = APIRouter(prefix="/account", tags=["privacy"])


@router.get("/export")
def export_account(
    user: UserProfile = Depends(require_permission("health:use")),
    db: Session = Depends(get_db),
):
    payload = privacy_service.export_account(db, user)
    filename = quote(f"yunsync-account-{user.id}.json")
    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


@router.get("/privacy-status", response_model=PrivacyStatusOut)
def privacy_status(
    user: UserProfile = Depends(require_permission("health:use")),
    db: Session = Depends(get_db),
):
    return PrivacyStatusOut(
        active_consent=identity_service.active_consent(db, user.id) is not None,
        pending_deletion=privacy_service.pending_request(db, user.id),
        deletion_grace_hours=settings.account_deletion_grace_hours,
    )


@router.post("/deletion-request", response_model=PrivacyRequestOut)
def request_deletion(
    _payload: AccountDeletionIn,
    user: UserProfile = Depends(require_permission("health:use")),
    db: Session = Depends(get_db),
):
    return privacy_service.request_account_deletion(db, user.id)


@router.delete("/deletion-request", response_model=PrivacyRequestOut)
def cancel_deletion(
    user: UserProfile = Depends(require_permission("health:use")),
    db: Session = Depends(get_db),
):
    try:
        return privacy_service.cancel_account_deletion(db, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
