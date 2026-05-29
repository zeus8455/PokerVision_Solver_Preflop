from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def test_v2_26_live_no_click_probe_after_v225() -> None:
    project_root = _project_root()
    tool = project_root / "tools" / "run_v2_26_live_no_click_probe_after_v225.py"

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=240,
    )

    assert proc.returncode == 0, proc.stdout + "\nSTDERR:\n" + proc.stderr

    payload = _extract_json_object(proc.stdout)
    assert payload["schema"] == "pokervision_solver_preflop_v226_live_no_click_probe_after_v225_v1"
    assert payload["status"] == "ok"

    checks: dict[str, Any] = payload["checks"]
    assert checks["v225_version_record_present"] is True
    assert checks["v219_tool_returncode_zero"] is True
    assert checks["v219_status_ok"] is True
    assert checks["real_project_not_touched"] is True
    assert checks["live_cycle_executed"] is True
    assert checks["screen_capture_executed"] is True
    assert checks["yolo_detector_executed"] is True
    assert checks["physical_click_not_executed"] is True
    assert checks["current_cycle_restored_after_probe"] is True
    assert checks["six_slots_available"] is True
    assert checks["table_ids_detected"] is True
    assert checks["no_traceback"] is True

    assert payload["real_project_touched"] is False
    assert payload["live_cycle_executed"] is True
    assert payload["screen_capture_executed"] is True
    assert payload["yolo_detector_executed"] is True
    assert payload["physical_click_executed"] is False
    assert payload["v226_scope"] == "safe_live_no_click_probe_only"

    # This probe is intentionally honest: if no Active table appears during the short live run,
    # it must not pretend that Solver_Preflop live bridge/click-chain was validated.
    assert payload["solver_live_chain_validated"] is False
    assert payload["solver_live_chain_validation_reason"] in {
        "no_active_or_json_artifacts_observed_in_this_probe",
        "active_or_json_artifacts_observed_but_v219_probe_does_not_validate_solver_bridge",
    }
