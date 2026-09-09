from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.experiment import Experiment, Observation


class ExperimentRepository:
    def get(self, db: Session, experiment_id: str) -> Experiment | None:
        return db.get(Experiment, experiment_id)

    def latest_for_user(self, db: Session, user_id: str) -> Experiment | None:
        statement = (
            select(Experiment)
            .where(Experiment.user_id == user_id)
            .order_by(Experiment.created_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    def active_for_user(self, db: Session, user_id: str) -> list[Experiment]:
        statement = select(Experiment).where(
            Experiment.user_id == user_id,
            Experiment.status == "active",
        )
        return list(db.scalars(statement))

    def observations(self, db: Session, experiment_id: str) -> list[Observation]:
        statement = (
            select(Observation)
            .where(Observation.experiment_id == experiment_id)
            .order_by(Observation.observed_on)
        )
        return list(db.scalars(statement))

    def observation_on(self, db: Session, experiment_id: str, observed_on) -> Observation | None:
        statement = select(Observation).where(
            Observation.experiment_id == experiment_id,
            Observation.observed_on == observed_on,
        )
        return db.scalar(statement)


experiment_repository = ExperimentRepository()

