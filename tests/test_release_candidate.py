import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_rc1_synthetic_main_flow_succeeds_three_times():
    completed = subprocess.run(
        [sys.executable, "scripts/rc1_acceptance.py", "--rounds", "3"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary["mode"] == "synthetic"
    assert summary["rounds"] == 3
    assert summary["successful_rounds"] == 3
    assert summary["task_success_rate"] == 1.0
    assert all(item["status"] == "passed" for item in summary["results"])


def test_frontend_has_actionable_network_failure_messages():
    api_source = (ROOT / "frontend" / "src" / "services" / "api.ts").read_text(
        encoding="utf-8"
    )

    assert "网络响应超时，请检查连接后重试。" in api_source
    assert "暂时无法连接服务，请检查网络后重试。" in api_source
