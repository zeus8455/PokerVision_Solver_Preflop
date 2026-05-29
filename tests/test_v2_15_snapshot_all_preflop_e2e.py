from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "run_v2_15_snapshot_all_preflop_e2e.py"


def test_v2_15_snapshot_all_preflop_e2e_tool_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["schema"] == "pokervision_solver_preflop_v215_snapshot_all_preflop_e2e_v1"
    assert report["status"] == "ok"

    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    assert report["files_total"] == 4
    assert report["ok_count"] == 4
    assert report["bad_count"] == 0
    assert report["final_files_count"] == 4
    assert report["runtime_files_count"] == 4

    assert all(report["checks"].values())

    for item in report["results"]:
        assert item["ok"] is True
        assert all(item["checks"].values())

        assert item["transaction_status"] == "completed"
        assert item["solver_bridge_status"] == "ok"
        assert item["runtime_selected_source"] == "Solver_Preflop_Bridge"
        assert item["runtime_selection_reason"] == "v20_solver_preflop_selected"
        assert item["final_path"]
