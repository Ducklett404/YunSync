from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action import ActionTemplate


class ActionRepository:
    def list_all(self, db: Session) -> list[ActionTemplate]:
        return list(db.scalars(select(ActionTemplate).order_by(ActionTemplate.title)))

    def get(self, db: Session, action_id: str) -> ActionTemplate | None:
        return db.get(ActionTemplate, action_id)

    def list_active(self, db: Session) -> list[ActionTemplate]:
        statement = (
            select(ActionTemplate)
            .where(ActionTemplate.is_active.is_(True))
            .order_by(ActionTemplate.title)
        )
        return list(db.scalars(statement))

    def version(self, db: Session, code: str, version: str) -> ActionTemplate | None:
        statement = select(ActionTemplate).where(
            ActionTemplate.code == code,
            ActionTemplate.version == version,
        )
        return db.scalar(statement)

    def active_versions(self, db: Session, code: str) -> list[ActionTemplate]:
        statement = select(ActionTemplate).where(
            ActionTemplate.code == code,
            ActionTemplate.is_active.is_(True),
        )
        return list(db.scalars(statement))


action_repository = ActionRepository()
