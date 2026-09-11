from fastapi import APIRouter, Depends, HTTPException
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
    ObservationCreate,
)
from app.services.experiment_service import (
    ExperimentConflictError,
    ExperimentStateError,
    experiment_service,
)


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
    return ApiMessage(message="今日记录已保存")


@router.get("/{experiment_id}/result", response_model=ExperimentResultOut)
def experiment_result(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    _owned_experiment(db, experiment_id, user.id)
    try:
        return experiment_service.result(db, experiment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScheduleIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
