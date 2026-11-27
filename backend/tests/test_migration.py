from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_creates_m12_tables(tmp_path):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"recipes", "seasonal_contents", "recommendation_audits", "ai_output_audits", "catalogue_state"} <= tables
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT revision FROM catalogue_state WHERE id = 1"))
        assert revision and len(revision) == 32
    finally:
        engine.dispose()
