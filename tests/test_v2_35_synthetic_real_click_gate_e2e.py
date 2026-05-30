from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_v2_35_synthetic_real_click_gate_e2e(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "tools" / "run_v2_35_synthetic_real_click_gate_e2e.py"
    report_json = tmp_path / "v2_35_report.json"
    proc = subprocess.run([sys.executable, str(script), "--report-json", str(report_json)], cwd=str(root), text=True, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["ok"] is True
    by_case = {item["case_id"]: item for item in report["results"]}
    for case_id in ["fold", "call", "check", "open_raise", "iso_raise", "threebet", "fourbet", "fivebet", "all_in"]:
        item = by_case[case_id]
        assert item["status"] == "clicked", item
        assert item["gate_status"] == "CONTROLLED_LIVE_CLICK_GATE_PASSED", item
        assert item["mouse_spy_called"] is True, item
    assert by_case["open_raise"]["target_sequence"] == ["Bet/Raise"]
    assert by_case["iso_raise"]["target_sequence"] == ["98%", "Bet/Raise"]
    assert by_case["threebet"]["target_sequence"] == ["98%", "Bet/Raise"]
    assert by_case["fourbet"]["target_sequence"] == ["50%", "Bet/Raise"]
    assert by_case["fivebet"]["target_sequence"] == ["50%", "Bet/Raise"]
    assert by_case["all_in"]["target_sequence"] == ["98%", "Bet/Raise"]

    fivebet_plan = by_case["fivebet"].get("runtime_plan")
    if not fivebet_plan:
        probe = by_case["fivebet"].get("runtime_plan_probe", {})
        fivebet_plan = {
            "target_sequence": probe.get("sequence"),
            "planned_action": "bet_raise" if probe.get("status") == "ok" else None,
            "raise_branch_enabled": probe.get("status") == "ok",
        }
    assert fivebet_plan["target_sequence"] == ["50%", "Raise"]
    assert fivebet_plan["planned_action"] == "bet_raise"
    assert fivebet_plan["raise_branch_enabled"] is True

    assert by_case["legacy_stub_bet_raise"]["status"] == "blocked"
    assert "controlled_live_click_stub_decision_blocked" in by_case["legacy_stub_bet_raise"]["gate_blockers"]
    assert by_case["legacy_stub_bet_raise"]["mouse_spy_called"] is False
    assert by_case["wrong_source_bet_raise"]["status"] == "blocked"
    assert "controlled_live_click_solver_source_not_solver_preflop" in by_case["wrong_source_bet_raise"]["gate_blockers"]
    assert by_case["wrong_source_bet_raise"]["mouse_spy_called"] is False
    assert by_case["missing_bet_raise_button"]["status"] == "blocked"
    assert by_case["missing_bet_raise_button"]["mouse_spy_called"] is False
    assert by_case["missing_98_for_iso_raise"]["status"] == "blocked"
    assert by_case["missing_98_for_iso_raise"]["mouse_spy_called"] is False
