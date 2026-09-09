import os
from pathlib import Path

import pytest


TEST_DB_PATH = Path("backend/data/yunsync-test.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()


@pytest.fixture(scope="session", autouse=True)
def clean_test_database():
    yield

    from app.db.session import engine

    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
