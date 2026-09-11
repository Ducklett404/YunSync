from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.experiment_policy import ScheduleIntegrityError
from app.core.security import require_active_participant, require_safe_participant
from app.db.session import get_db
from app.models.experiment import Experiment
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.schemas.common import ApiMessage
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOut,
    ExperimentResultOut,
    ExperimentTransition,
    NextStepChoiceIn,
    NextStepChoiceOut,
    ObservationCreate,
    ObservationImportIn,
    ObservationImportOut,
)
from app.services.experiment_service import (
    ExperimentConflictError,
    ExperimentStateError,
    experiment_service,
)
from app.services.result_review_service import result_review_service


router = APIRouter(prefix="/experiments", tags=["experiments"])


def _serialize_experiment(db: Session, experiment: Experiment) -> ExperimentOut:
    return ExperimentOut(**experiment_service.snapshot(db, experiment))


def _owned_experiment(db: Session, experiment_id: str, user_id: str) -> Experiment:
    experiment = experiment_repository.get(db, experiment_id)
    if experiment is None or experiment.user_id != user_id:
        raise HTTPException(status_code=404, detail="实验不存在")
    return experiment


def _transition_owned(
    db: Session,
    experiment_id: str,
    transition: ExperimentTransition,
    user: UserProfile,
) -> ExperimentOut:
    _owned_experiment(db, experiment_id, user.id)
    try:
        experiment = experiment_service.transition(
            db, experiment_id, transition, user.id
        )
        return _serialize_experiment(db, experiment)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ExperimentStateError, ExperimentConflictError, ScheduleIntegrityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("", response_model=ExperimentOut)
def create_experiment(
    payload: ExperimentCreate,
    user: UserProfile = Depends(require_safe_participant),
    db: Session = Depends(get_db),
):
    try:
        experiment = experiment_service.create(
            db, user.id, payload.action_id, payload.start_date
        )
        return _serialize_experiment(db, experiment)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PermissionError, ExperimentConflictError, ScheduleIntegrityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/current", response_model=ExperimentOut)
def current_experiment(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    experiment = experiment_repository.latest_for_user(db, user.id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="尚无实验计划")
    try:
        return _serialize_experiment(db, experiment)
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{experiment_id}/pause", response_model=ExperimentOut)
def pause_experiment(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return _transition_owned(db, experiment_id, "pause", user)


@router.post("/{experiment_id}/resume", response_model=ExperimentOut)
def resume_experiment(
    experiment_id: str,
    user: UserProfile = Depends(require_safe_participant),
    db: Session = Depends(get_db),
):
    return _transition_owned(db, experiment_id, "resume", user)


@router.post("/{experiment_id}/terminate", response_model=ExperimentOut)
def terminate_experiment(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return _transition_owned(db, experiment_id, "terminate", user)


@router.post("/{experiment_id}/complete", response_model=ExperimentOut)
def complete_experiment(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    return _transition_owned(db, experiment_id, "complete", user)


@router.post("/{experiment_id}/observations", response_model=ApiMessage)
def save_observation(
    experiment_id: str,
    payload: ObservationCreate,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    _owned_experiment(db, experiment_id, user.id)
    try:
        experiment_service.save_observation(db, experiment_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExperimentStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    message = (
        "记录已保存；因记录了明显身体不适，实验已自动暂停，请先评估是否需要专业帮助"
        if payload.discomfort_level == "significant"
        else "今日记录已保存"
    )
    return ApiMessage(message=message)


@router.get("/{experiment_id}/observations/template")
def observation_import_template(
    experiment_id: str,
    format_name: Literal["csv", "json"] = Query(default="csv", alias="format"),
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    experiment = _owned_experiment(db, experiment_id, user.id)
    try:
        filename, media_type, content = experiment_service.import_template(
            db, experiment, format_name
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    prefix = "\ufeff" if format_name == "csv" else ""
    return Response(
        content=prefix + content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{experiment_id}/observations/import",
    response_model=ObservationImportOut,
)
def import_observations(
    experiment_id: str,
    payload: ObservationImportIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    _owned_experiment(db, experiment_id, user.id)
    try:
        return experiment_service.import_observations(db, experiment_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExperimentStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{experiment_id}/result", response_model=ExperimentResultOut)
async def experiment_result(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    _owned_experiment(db, experiment_id, user.id)
    try:
        analysis = experiment_service.result(db, experiment_id)
        return await result_review_service.explain(analysis)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{experiment_id}/next-step", response_model=NextStepChoiceOut)
def select_next_step(
    experiment_id: str,
    payload: NextStepChoiceIn,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    _owned_experiment(db, experiment_id, user.id)
    try:
        return experiment_service.select_next_step(
            db, experiment_id, payload.code, user.id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExperimentStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
