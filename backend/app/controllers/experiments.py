from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_active_participant, require_safe_participant
from app.db.session import get_db
from app.models.action import ActionTemplate
from app.models.experiment import Experiment
from app.models.user import UserProfile
from app.repositories.experiment_repository import experiment_repository
from app.schemas.common import ApiMessage
from app.schemas.experiment import ExperimentCreate, ExperimentOut, ExperimentResultOut, ObservationCreate
from app.services.experiment_service import experiment_service


router = APIRouter(prefix="/experiments", tags=["experiments"])


def _serialize_experiment(db: Session, experiment: Experiment) -> ExperimentOut:
    action = db.get(ActionTemplate, experiment.action_id)
    observations = experiment_repository.observations(db, experiment.id)
    completed_dates = {
        item.observed_on.isoformat() for item in observations if item.completed
    }
    schedule = [
        {**day, "completed": day["date"] in completed_dates}
        for day in experiment.schedule
    ]
    return ExperimentOut(
        id=experiment.id,
        user_id=experiment.user_id,
        action_id=experiment.action_id,
        action_code=action.code if action else "unknown",
        action_title=action.title if action else "未知行动",
        primary_metric=action.primary_metric if action else "未知指标",
        status=experiment.status,
        start_date=experiment.start_date,
        end_date=experiment.end_date,
        progress=len([item for item in observations if item.completed]),
        schedule=schedule,
    )


@router.post("", response_model=ExperimentOut)
def create_experiment(
    payload: ExperimentCreate,
    user: UserProfile = Depends(require_safe_participant),
    db: Session = Depends(get_db),
):
    try:
        experiment = experiment_service.create(db, user.id, payload.action_id, payload.start_date)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_experiment(db, experiment)


@router.get("/current", response_model=ExperimentOut)
def current_experiment(
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    experiment = experiment_repository.latest_for_user(db, user.id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="尚无实验计划")
    return _serialize_experiment(db, experiment)


@router.post("/{experiment_id}/observations", response_model=ApiMessage)
def save_observation(
    experiment_id: str,
    payload: ObservationCreate,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    experiment = experiment_repository.get(db, experiment_id)
    if experiment is None or experiment.user_id != user.id:
        raise HTTPException(status_code=404, detail="实验不存在")
    try:
        experiment_service.save_observation(db, experiment_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiMessage(message="今日记录已保存")


@router.get("/{experiment_id}/result", response_model=ExperimentResultOut)
def experiment_result(
    experiment_id: str,
    user: UserProfile = Depends(require_active_participant),
    db: Session = Depends(get_db),
):
    experiment = experiment_repository.get(db, experiment_id)
    if experiment is None or experiment.user_id != user.id:
        raise HTTPException(status_code=404, detail="实验不存在")
    try:
        return experiment_service.result(db, experiment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
