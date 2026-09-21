from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import UserProfile
from app.schemas.content import (
    BulkValidationIn,
    BulkValidationOut,
    ContentCompareOut,
    ContentItemCreate,
    ContentItemOut,
    ContentReviewIn,
    ContentReviewOut,
    EvidenceSourceIn,
    EvidenceSourceOut,
    EvidenceSourceStatusUpdate,
)
from app.services.content_service import ContentConflictError, content_service


router = APIRouter(prefix="/admin/content", tags=["content-admin"])


@router.get("/sources", response_model=list[EvidenceSourceOut])
def list_sources(
    q: str = Query(default="", max_length=120),
    status: Literal["active", "superseded", "withdrawn"] | None = None,
    _reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return content_service.list_sources(db, q=q, status=status)


@router.post("/sources", response_model=EvidenceSourceOut, status_code=201)
def create_source(
    payload: EvidenceSourceIn,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    try:
        return content_service.create_source(db, payload, reviewer.id)
    except ContentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/sources/{source_id}/status", response_model=EvidenceSourceOut)
def update_source_status(
    source_id: str,
    payload: EvidenceSourceStatusUpdate,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    try:
        return content_service.update_source_status(db, source_id, payload.status, reviewer.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/items", response_model=list[ContentItemOut])
def list_items(
    content_type: Literal["ingredient", "recipe", "contraindication"] | None = None,
    status: Literal["draft", "reviewed", "published", "retired"] | None = None,
    q: str = Query(default="", max_length=120),
    _reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return content_service.list_items(db, content_type=content_type, status=status, q=q)


@router.post("/items", response_model=ContentItemOut, status_code=201)
def create_item(
    payload: ContentItemCreate,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    try:
        return content_service.create_item(db, payload, reviewer.id)
    except ContentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/items/{item_id}/review", response_model=ContentReviewOut)
def review_item(
    item_id: str,
    payload: ContentReviewIn,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    try:
        return content_service.review_item(db, item_id, payload, reviewer.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _governance_action(action: str, item_id: str, reviewer: UserProfile, db: Session):
    try:
        operation = {
            "publish": content_service.publish_item,
            "retire": content_service.retire_item,
            "rollback": content_service.rollback_item,
        }[action]
        return operation(db, item_id, reviewer.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/items/{item_id}/publish", response_model=ContentItemOut)
def publish_item(
    item_id: str,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return _governance_action("publish", item_id, reviewer, db)


@router.post("/items/{item_id}/retire", response_model=ContentItemOut)
def retire_item(
    item_id: str,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return _governance_action("retire", item_id, reviewer, db)


@router.post("/items/{item_id}/rollback", response_model=ContentItemOut)
def rollback_item(
    item_id: str,
    reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return _governance_action("rollback", item_id, reviewer, db)


@router.get("/{content_type}/{code}/compare", response_model=ContentCompareOut)
def compare_versions(
    content_type: Literal["ingredient", "recipe", "contraindication"],
    code: str,
    from_version: str,
    to_version: str,
    _reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    try:
        return content_service.compare_versions(
            db, content_type, code, from_version, to_version
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/validate", response_model=BulkValidationOut)
def bulk_validate(
    payload: BulkValidationIn,
    _reviewer: UserProfile = Depends(require_permission("content:manage")),
    db: Session = Depends(get_db),
):
    return content_service.bulk_validate(db, payload.item_ids)
