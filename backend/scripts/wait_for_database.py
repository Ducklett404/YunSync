"""Wait for an authenticated database connection before board migrations."""

import time

from app.config import Settings
from app.database import Database


def main() -> int:
    database = Database(Settings.from_env())
    deadline = time.monotonic() + 120
    try:
        while True:
            ready, error = database.health()
            if ready:
                return 0
            if time.monotonic() >= deadline:
                print(f"Database did not become ready: {error}", flush=True)
                return 1
            time.sleep(2)
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
