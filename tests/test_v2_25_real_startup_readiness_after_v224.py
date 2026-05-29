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


def test_v2_25_real_startup_readiness_after_v224() -> None:
    project_root = _project_root()
    tool = project_root / "tools" / "run_v2_25_real_startup_readiness_after_v224.py"

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout + "\nSTDERR:\n" + proc.stderr

    payload = _extract_json_object(proc.stdout)
    assert payload["schema"] == "pokervision_solver_preflop_v225_real_startup_readiness_after_v224_v1"
    assert payload["status"] == "ok"

    checks: dict[str, Any] = payload["checks"]
    assert checks["v224_version_record_present"] is True
    assert checks["v220_tool_returncode_zero"] is True
    assert checks["v220_status_ok"] is True
    assert checks["v220_real_click_ready_true"] is True
    assert checks["real_project_not_touched"] is True
    assert checks["live_ui_not_launched"] is True
    assert checks["screen_capture_not_executed"] is True
    assert checks["yolo_detector_not_executed"] is True
    assert checks["physical_click_not_executed"] is True
    assert checks["no_click_mode_disabled"] is True
    assert checks["master_armed"] is True
    assert checks["action_real_click_enabled"] is True
    assert checks["service_real_click_enabled"] is True
    assert checks["readiness_ready"] is True
    assert checks["startup_audit_only"] is True
    assert checks["max_clicks_zero"] is True
    assert checks["startup_readiness_line_present"] is True
    assert checks["startup_audit_skip_line_present"] is True
    assert checks["no_traceback"] is True

    assert payload["real_project_touched"] is False
    assert payload["live_ui_launched"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False
    assert payload["physical_click_executed"] is False
    assert payload["real_click_ready"] is True
