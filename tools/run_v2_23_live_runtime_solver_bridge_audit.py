from __future__ import annotations

import json
from pathlib import Path


SCHEMA = "pokervision_solver_preflop_v223_live_runtime_solver_bridge_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
V11_RUNTIME = SNAPSHOT_ROOT / "runtime" / "v11_stage1_runtime.py"
DISPLAY_ANALYSIS_CYCLE = SNAPSHOT_ROOT / "display_analysis_cycle.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _index_or_large(text: str, needle: str) -> int:
    idx = text.find(needle)
    return idx if idx >= 0 else 10**12


def build_report() -> dict:
    v11 = _read(V11_RUNTIME)
    display = _read(DISPLAY_ANALYSIS_CYCLE)

    strict_ok_check_present = (
        'str(contract.get("status") or "") != "ok"' in v11
        or "str(contract.get('status') or '') != 'ok'" in v11
    )
    v231_ok_or_fallback_check_present = (
        'contract_status not in {"ok", "fallback"}' in v11
        or "contract_status not in {'ok', 'fallback'}" in v11
        or '"fallback"' in v11 and "contract_status" in v11
    )

    extract_call_idx = _index_or_large(v11, "_extract_solver_preflop_decision_from_state(")
    stub_call_idx = _index_or_large(v11, "build_solver_stub_decision(")

    checks = {
        "extract_helper_exists": "def _extract_solver_preflop_decision_from_state" in v11,
        "normalizer_helper_exists": "def _normalise_solver_preflop_runtime_action" in v11,
        "reads_solver_bridge_from_full_state": 'full_state.get("solver_preflop_bridge_contract")' in v11,
        # V2.23 originally required strict bridge status == ok.
        # V2.31 deliberately extends this to accept status == fallback when bridge_payload.action_decision exists.
        # Keep the historical key for old tests, but treat the V2.31 ok-or-fallback guard as satisfying it.
        "requires_bridge_status_ok": strict_ok_check_present or v231_ok_or_fallback_check_present,
        "reads_bridge_payload": 'bridge_payload = contract.get("bridge_payload")' in v11,
        "reads_action_decision": 'action_decision = bridge_payload.get("action_decision")' in v11,
        "sets_solver_preflop_source": '"source": "PokerVision_Solver_Preflop"' in v11,
        "sets_solver_status_ok": '"status": "ok"' in v11,
        "uses_solver_decision_id": 'action_decision.get("decision_id")' in v11,
        "uses_solver_fingerprint": "solver_fingerprint" in v11,
        "maps_open_raise_to_bet_raise": '"open_raise"' in v11 and 'return "bet_raise"' in v11,
        "maps_3bet_to_bet_raise": '"3bet"' in v11 and 'return "bet_raise"' in v11,
        "maps_4bet_to_bet_raise": '"4bet"' in v11 and 'return "bet_raise"' in v11,
        "maps_all_in_to_bet_raise": '"all_in"' in v11 and 'return "bet_raise"' in v11,
        "solver_preflop_attempts_before_stub": extract_call_idx < stub_call_idx,
        "stub_blocker_still_present": "blocked_stub_real_click" in v11 and "v12_stub_" in v11,
        "runtime_source_selection_present": "runtime_source_selection" in v11 and "Solver_Preflop_Bridge" in v11,
    }

    report = {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "checks": checks,
        "v231_compatibility": {
            "strict_ok_check_present": strict_ok_check_present,
            "ok_or_fallback_check_present": v231_ok_or_fallback_check_present,
            "accepted_contract_statuses": ["ok", "fallback"] if v231_ok_or_fallback_check_present else ["ok"],
            "reason": "V2.31 accepts Solver_Preflop fallback bridge when action_decision is available.",
        },
    }
    return report


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
