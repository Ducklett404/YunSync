"""Run privacy retention operations from a trusted application environment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.db.session import SessionLocal
from app.services.privacy_service import privacy_service


DELETE_CONFIRMATION = "APPLY_DUE_ACCOUNT_DELETIONS"
PURGE_CONFIRMATION = "PURGE_EXPIRED_SESSIONS"


def main() -> int:
    parser = argparse.ArgumentParser(description="YunSync privacy lifecycle operations")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for name in ("process-deletions", "purge-expired-sessions"):
        command = subparsers.add_parser(name)
        command.add_argument("--apply", action="store_true")
        command.add_argument("--confirm", default="")
    args = parser.parse_args()
    expected = DELETE_CONFIRMATION if args.operation == "process-deletions" else PURGE_CONFIRMATION
    if args.apply and args.confirm != expected:
        parser.error(f"--apply requires --confirm {expected}")

    with SessionLocal() as db:
        if args.operation == "process-deletions":
            result = privacy_service.process_due_deletions(db, dry_run=not args.apply)
        else:
            result = {
                "eligible": privacy_service.purge_expired_sessions(db, dry_run=not args.apply)
            }
    result["mode"] = "apply" if args.apply else "dry-run"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
