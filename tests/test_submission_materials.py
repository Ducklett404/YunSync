import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_m12a_submission_materials_are_complete_and_linked():
    completed = subprocess.run(
        [sys.executable, "scripts/materials_check.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout or "materials check failed"
    result = json.loads(completed.stdout.strip())
    assert result["status"] == "passed"
    assert result["required_files"] == 9
    assert result["checked_links"] >= 20
    assert result["direct_dependencies"] == 18
    assert result["defense_questions"] == 21
    assert result["errors"] == []
