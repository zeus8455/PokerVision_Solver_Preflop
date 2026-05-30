from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_37_lineage_cleanup_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_37_lineage_cleanup_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_37_lineage_cleanup_audit.py",
            "--report-json",
            str(report_path),
            "--out-dir",
            str(tmp_path / "out"),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )
    assert "V2.37_LINEAGE_CLEANUP_AUDIT_OK = True" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["runtime_lineage_results"]
    assert report["runtime_plan_lineage_results"]
    for item in report["runtime_lineage_results"]:
        assert item["ok"] is True
        assert item["runtime_lineage"]["source"] == "PokerVision_Solver_Preflop"
        assert item["runtime_lineage"]["selected_source"] == "Solver_Preflop_Bridge"
        assert item["runtime_lineage"]["decision_id"] == item["decision_id"]
        assert item["click_lineage"]["solver_source"] == "PokerVision_Solver_Preflop"
    for item in report["runtime_plan_lineage_results"]:
        assert item["ok"] is True
        assert item["solver_source"] == "PokerVision_Solver_Preflop"
