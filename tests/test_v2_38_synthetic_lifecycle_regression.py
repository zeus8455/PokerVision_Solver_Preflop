from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_38_synthetic_lifecycle_regression_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_38_synthetic_lifecycle_regression.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_38_synthetic_lifecycle_regression.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.38_SYNTHETIC_LIFECYCLE_REGRESSION_OK = True" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    sections = {item["case_id"]: item for item in report["sections"]}
    assert sections["action_event_duplicate_and_inactive_release"]["ok"] is True
    assert sections["v230_duplicate_active_runtime_retry_policy"]["ok"] is True
    assert sections["table_action_transaction_lifecycle"]["ok"] is True
    assert sections["dry_run_completion_policy"]["ok"] is True
    assert sections["click_no_repeat_same_decision"]["ok"] is True
