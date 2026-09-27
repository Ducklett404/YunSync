#!/usr/bin/env sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_RUNNER="${YUNSYNC_PYTHON:-.venv/bin/python}"

"$PYTHON_RUNNER" -m pytest
"$PYTHON_RUNNER" -m alembic upgrade head
"$PYTHON_RUNNER" -m alembic check
"$PYTHON_RUNNER" scripts/alert_rules_check.py
"$PYTHON_RUNNER" scripts/generate_sbom.py --version "local-verification"

cd frontend
npm run typecheck
npm run build

printf '%s\n' "YunSync verification completed."
