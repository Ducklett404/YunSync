from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from sqlalchemy import Engine, create_engine, event, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import AiOutputAudit, Base, CatalogueState, Recipe, RecommendationAudit, SeasonalContent


class DatabaseUnavailable(RuntimeError):
    pass


class CatalogueSession(Session):
    pass


def _advance_catalogue_revision(session: Session) -> None:
    session.execute(
        update(CatalogueState).where(CatalogueState.id == 1).values(revision=uuid4().hex)
    )


@event.listens_for(CatalogueSession, "before_flush")
def invalidate_catalogue_cache(session: Session, _flush_context, _instances) -> None:
    content_types = (Recipe, SeasonalContent)
    changed = any(isinstance(row, content_types) for row in (*session.new, *session.deleted))
    if changed or any(
        isinstance(row, content_types) and session.is_modified(row) for row in session.dirty
    ):
        _advance_catalogue_revision(session)


def create_database_engine(settings: Settings) -> Engine:
    connect_args = {"check_same_thread": False} if settings.database_kind == "sqlite" else {}
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_database_engine(settings)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=CatalogueSession,
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        db = self.session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def health(self) -> tuple[bool, str | None]:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, None
        except SQLAlchemyError as exc:
            return False, exc.__class__.__name__


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seed_demo_content(database: Database, seed_path: Path) -> dict[str, int]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    recipes = payload["recipes"]
    bundles = payload["bundles"]
    if not isinstance(recipes, list) or not isinstance(bundles, list):
        raise ValueError("demo seed must contain recipes and bundles lists")
    recipe_ids = {item["id"] for item in recipes}
    bundle_ids = {item["id"] for item in bundles}
    if len(recipe_ids) != len(recipes) or len(bundle_ids) != len(bundles):
        raise ValueError("demo seed contains duplicate IDs")

    with database.session() as session, session.no_autoflush:
        # Lock the same row for each import before reading the old catalogue.
        _advance_catalogue_revision(session)
        for model, active_ids in ((Recipe, recipe_ids), (SeasonalContent, bundle_ids)):
            omitted = select(model).where(
                model.is_demo.is_(True),
                model.review_status == "demo",
                model.id.not_in(active_ids),
            )
            for row in session.scalars(omitted):
                row.review_status = "disabled"
        for item in recipes:
            session.merge(
                Recipe(
                    id=item["id"],
                    name=item["name"],
                    category=item["category"],
                    minutes=item["minutes"],
                    reason=item["reason"],
                    servings=item["servings"],
                    tags=item.get("tags", []),
                    ingredients=item.get("ingredients", []),
                    tools=item.get("tools", []),
                    steps=item.get("steps", []),
                    substitutions=item.get("substitutions", []),
                    allergens=item.get("allergens", []),
                    exclusions=item.get("exclusions", []),
                    regions=item.get("regions", []),
                    scene_tags=item.get("sceneTags", []),
                    source_note=item.get("sourceNote", ""),
                    source=item["source"],
                    is_demo=bool(item.get("isDemo", True)),
                    version=item["version"],
                    review_status=item["reviewStatus"],
                    content_updated_at=_parse_timestamp(item["updatedAt"]),
                )
            )
        for item in bundles:
            session.merge(
                SeasonalContent(
                    id=item["id"],
                    name=item["name"],
                    kind=item["kind"],
                    culture_note=item["cultureNote"],
                    date_rule=item["dateRule"],
                    regions=item.get("regions", []),
                    recipe_ids=item.get("recipeIds", []),
                    source=item["source"],
                    is_demo=bool(item.get("isDemo", True)),
                    version=item["version"],
                    review_status=item["reviewStatus"],
                    content_updated_at=_parse_timestamp(item["updatedAt"]),
                )
            )
    return {"recipes": len(recipes), "seasonalContents": len(bundles)}


class ContentRepository:
    def __init__(self, database: Database, allow_demo_content: bool):
        self.database = database
        self.allow_demo_content = allow_demo_content

    def catalogue_revision(self) -> str:
        try:
            with self.database.session() as session:
                return session.scalars(
                    select(CatalogueState.revision).where(CatalogueState.id == 1)
                ).one()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("catalogue revision is unavailable") from exc

    def _eligible_recipe_query(self):
        query = select(Recipe).where(Recipe.review_status.in_(["approved", "demo"]))
        if not self.allow_demo_content:
            query = query.where(Recipe.is_demo.is_(False), Recipe.review_status == "approved")
        return query

    def list_recipes(self) -> list[Recipe]:
        try:
            with self.database.session() as session:
                return list(session.scalars(self._eligible_recipe_query()).all())
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("recipe database is unavailable") from exc

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        try:
            with self.database.session() as session:
                query = self._eligible_recipe_query().where(Recipe.id == recipe_id)
                return session.scalar(query)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("recipe database is unavailable") from exc

    def list_seasonal_contents(self) -> list[SeasonalContent]:
        try:
            with self.database.session() as session:
                query = select(SeasonalContent).where(
                    SeasonalContent.review_status.in_(["approved", "demo"])
                )
                if not self.allow_demo_content:
                    query = query.where(
                        SeasonalContent.is_demo.is_(False),
                        SeasonalContent.review_status == "approved",
                    )
                return list(session.scalars(query).all())
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("seasonal content database is unavailable") from exc

    def write_audit(self, audit: RecommendationAudit) -> None:
        try:
            with self.database.session() as session:
                session.add(audit)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("audit database is unavailable") from exc

    def write_ai_audit(self, audit: AiOutputAudit) -> None:
        try:
            with self.database.session() as session:
                session.add(audit)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailable("audit database is unavailable") from exc
