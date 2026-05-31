from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_50_remove_game_service_policy_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_50_remove_game_service_policy_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_50_remove_game_service_policy_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.50_REMOVE_GAME_SERVICE_POLICY_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]
    assert checks["remove_table_not_in_runtime_service_config"] is True
    assert checks["remove_table_only_no_actionable_target"] is True
    assert checks["remove_table_only_no_detected_only"] is True
    assert checks["remove_game_only_actionable"] is True
    assert checks["remove_game_wins_over_remove_table"] is True
