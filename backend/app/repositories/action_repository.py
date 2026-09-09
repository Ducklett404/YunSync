from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.action import ActionTemplate


class ActionRepository:
    def list_all(self, db: Session) -> list[ActionTemplate]:
        return list(db.scalars(select(ActionTemplate).order_by(ActionTemplate.title)))

    def get(self, db: Session, action_id: str) -> ActionTemplate | None:
        return db.get(ActionTemplate, action_id)


action_repository = ActionRepository()

