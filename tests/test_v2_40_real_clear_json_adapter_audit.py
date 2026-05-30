from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_40_real_clear_json_adapter_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_40_real_clear_json_adapter_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_40_real_clear_json_adapter_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.40_REAL_CLEAR_JSON_ADAPTER_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["real_project_touched"] is False
    assert report["full_live_ui_executed"] is False
    assert report["screen_capture_executed"] is False
    assert report["yolo_detector_executed"] is False
    assert report["physical_click_executed"] is False

    results = report["results"]
    assert len(results) >= 8
    assert all(item["ok"] for item in results)

    positive = [item for item in results if item["kind"] == "positive"]
    reject = [item for item in results if item["kind"] == "reject"]

    assert len(positive) >= 6
    assert len(reject) >= 2
    assert any(item["node_type"] == "bb_option_vs_1_limper" and item["raw_action"] == "check" for item in positive)
    assert any(item["node_type"] == "cold_vs_3bet_or_higher" and item["raw_action"] == "fold" for item in positive)
    assert any(item["node_type"] == "unopened" for item in positive)
    assert any(item["adapter_rejected"] for item in reject)
