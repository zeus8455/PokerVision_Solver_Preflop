from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_19_live_no_click_capture_probe.py"


def test_v2_19_live_no_click_capture_probe_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v219_live_no_click_capture_probe_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["live_cycle_executed"] is True
    assert report["screen_capture_executed"] is True
    assert report["yolo_detector_executed"] is True
    assert report["physical_click_executed"] is False
    assert report["current_cycle_restored_after_probe"] is True

    assert report["slots_total"] == 6
    assert report["opened_table_ids"] == [
        "table_01",
        "table_02",
        "table_03",
        "table_04",
        "table_05",
        "table_06",
    ]

    assert isinstance(report["saved_paths_count"], int)
    assert report["saved_paths_count"] >= 0

    counts = report["output_counts"]
    assert set(counts) == {
        "dark_json",
        "pending_clear_json",
        "final_clear_json",
        "decision_json",
        "action_decision_json",
        "action_runtime_plan_json",
    }

    for value in counts.values():
        assert isinstance(value, int)
        assert value >= 0
