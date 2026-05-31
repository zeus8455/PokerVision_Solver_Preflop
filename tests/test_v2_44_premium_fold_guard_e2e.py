from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_44_premium_fold_guard_e2e_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_44_premium_fold_guard_e2e.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_44_premium_fold_guard_e2e.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.44_PREMIUM_FOLD_GUARD_E2E_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["cases_failed"] == 0

    by_id = {case["case_id"]: case for case in report["cases"]}
    assert by_id["kk_safe_fallback_fold_raise_visible"]["actual_sequence"] == ["Bet/Raise"]
    assert by_id["kk_safe_fallback_fold_call_fallback"]["actual_sequence"] == ["Call"]
    assert by_id["kk_safe_fallback_fold_only_fold_blocks"]["actual_status"] == "blocked"
    assert by_id["weak_72o_safe_fallback_still_folds"]["actual_sequence"] == ["FOLD"]
    assert by_id["kk_clean_raise_not_interfered"]["guard_active"] is False
