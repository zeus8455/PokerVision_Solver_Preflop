import json
import subprocess
import sys

from solver_preflop.contracts import SOLVER_VERSION


def test_solver_version_is_v1():
    assert SOLVER_VERSION == "1.0.0"


def test_preintegration_check_tool_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_preintegration_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_preintegration_report_v1"
    assert payload["checks"]["pytest"]["ok"] is True
    assert payload["checks"]["cli_write_files"]["ok"] is True
    assert payload["checks"]["bridge_guard_contract"]["ok"] is True
    assert payload["checks"]["bridge_guard_contract"]["safety"]["must_not_execute_directly"] is True
