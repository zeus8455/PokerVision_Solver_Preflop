from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_39_spot_classifier_no_raise_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_39_spot_classifier_no_raise_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_39_spot_classifier_no_raise_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.39_SPOT_CLASSIFIER_NO_RAISE_AUDIT_OK = True" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    by_id = {item["case_id"]: item for item in report["results"]}

    assert by_id["sb_iso_vs_utg_limper_ako"]["node_type"] == "iso_vs_1_limper"
    assert by_id["sb_iso_vs_utg_limper_ako"]["raw_action"] == "iso_raise"
    assert by_id["sb_iso_vs_utg_limper_ako"]["to_call_bb"] == 0.5

    assert by_id["bb_unopened_option_no_raise_check"]["node_type"] == "bb_unopened_option_no_raise"
    assert by_id["bb_unopened_option_no_raise_check"]["raw_action"] == "check"

    for item in report["results"]:
        assert "unknown" not in item["node_type"], item
        assert item["raw_action"] != "safe_fallback", item
        assert item["click_sequence"], item
