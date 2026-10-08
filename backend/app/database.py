from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base, Recipe, RecommendationAudit, SeasonalContent


class DatabaseUnavailable(RuntimeError):
    pass


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
            class_=Session,
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
    recipes = payload.get("recipes", [])
    bundles = payload.get("bundles", [])
    with database.session() as session:
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
