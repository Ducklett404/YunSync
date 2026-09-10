#!/usr/bin/env sh
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_RUNNER="${YUNSYNC_PYTHON:-.venv/bin/python}"

"$PYTHON_RUNNER" -m pytest
"$PYTHON_RUNNER" -m alembic upgrade head
"$PYTHON_RUNNER" -m alembic check

cd frontend
npm run typecheck
npm run build

printf '%s\n' "YunSync verification completed."
