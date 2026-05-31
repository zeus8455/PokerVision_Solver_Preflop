from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_v2_52_invalid_hero_runtime_fallback_audit_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "v2_52_invalid_hero_runtime_fallback_audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_v2_52_invalid_hero_runtime_fallback_audit.py",
            "--report-json",
            str(report_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "V2.52_INVALID_HERO_RUNTIME_FALLBACK_AUDIT_OK = True" in completed.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    checks = report["checks"]

    for name in ["no_hero", "one_hero_one_card", "duplicate_hero_cards", "two_heroes"]:
        assert checks[f"{name}_bridge_ok"] is True
        assert checks[f"{name}_node_active_invalid_hero_cards"] is True
        assert checks[f"{name}_raw_safe_runtime_fallback"] is True
        assert checks[f"{name}_engine_fold"] is True
        assert checks[f"{name}_runtime_target_fold"] is True
        assert checks[f"{name}_not_legacy_runtime_source"] is True
