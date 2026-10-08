from __future__ import annotations

import json

from app.config import Settings
from app.database import Database, seed_demo_content


def main() -> int:
    settings = Settings.from_env()
    database = Database(settings)
    database.create_schema()
    counts = seed_demo_content(database, settings.seed_path)
    print(json.dumps({"status": "ok", **counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
