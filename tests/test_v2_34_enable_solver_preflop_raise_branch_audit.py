from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_34_enable_solver_preflop_raise_branch_audit.py"


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise AssertionError("No JSON object found in tool stdout")


def test_v2_34_enable_solver_preflop_raise_branch_audit() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\nSTDERR:\n" + result.stderr

    report = _extract_json_object(result.stdout)
    assert report["schema"] == "pokervision_solver_preflop_v234_enable_raise_branch_audit_v1"
    assert report["status"] == "ok"
    assert report["real_project_touched"] is False
    assert report["physical_click_executed"] is False
    assert report["live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False

    checks: dict[str, Any] = report["checks"]
    assert checks["v234_marker_present"] is True
    assert checks["all_cases_select_solver_preflop"] is True
    assert checks["all_cases_v11_extract_solver_decision"] is True
    assert checks["all_cases_v11_not_stub"] is True
    assert checks["all_cases_runtime_plan_ok"] is True
    assert checks["all_cases_runtime_plan_validation_ok"] is True
    assert checks["all_cases_raise_branch_enabled"] is True
    assert checks["all_cases_expected_sequence"] is True
    assert checks["all_cases_policy_ok"] is True
    assert checks["no_case_blocked_by_v1_1"] is True

    expected = {
        "open_raise": ["Raise"],
        "iso_raise": ["98%", "Raise"],
        "3bet": ["98%", "Raise"],
        "4bet": ["50%", "Raise"],
        "all_in": ["98%", "Raise"],
    }
    rows = {item["raw_action"]: item for item in report["summary"]}
    assert set(rows) == set(expected)
    for raw_action, expected_sequence in expected.items():
        row = rows[raw_action]
        assert row["status"] == "ok"
        assert row["runtime_plan_status"] == "ok"
        assert row["planned_action"] == "bet_raise"
        assert row["raise_branch_enabled"] is True
        assert row["target_sequence"] == expected_sequence
        assert row["blocked_reason"] is None
