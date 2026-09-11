import os
from pathlib import Path
import shutil

import pytest


TEST_DB_PATH = Path("backend/data/yunsync-test.db").resolve()
TEST_UPLOAD_PATH = Path("backend/data/test-uploads").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["UPLOAD_STORAGE_DIR"] = str(TEST_UPLOAD_PATH)

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
if TEST_UPLOAD_PATH.exists():
    shutil.rmtree(TEST_UPLOAD_PATH)


@pytest.fixture(scope="session", autouse=True)
def clean_test_database():
    yield

    from app.db.session import engine

    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    if TEST_UPLOAD_PATH.exists():
        shutil.rmtree(TEST_UPLOAD_PATH)
