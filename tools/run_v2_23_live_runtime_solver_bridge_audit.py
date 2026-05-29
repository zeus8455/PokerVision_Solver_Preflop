from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
RUNTIME_PATH = SNAPSHOT_ROOT / "runtime" / "v11_stage1_runtime.py"


def main() -> int:
    text = RUNTIME_PATH.read_text(encoding="utf-8")

    checks = {
        "extract_helper_exists": "def _extract_solver_preflop_decision_from_state(" in text,
        "normalizer_helper_exists": "def _normalise_solver_preflop_runtime_action(" in text,

        "reads_solver_bridge_from_full_state": 'contract = full_state.get("solver_preflop_bridge_contract")' in text,
        "requires_bridge_status_ok": 'str(contract.get("status") or "") != "ok"' in text,
        "reads_bridge_payload": 'bridge_payload = contract.get("bridge_payload")' in text,
        "reads_action_decision": 'action_decision = bridge_payload.get("action_decision")' in text,

        "sets_solver_preflop_source": '"source": "PokerVision_Solver_Preflop"' in text,
        "sets_solver_status_ok": '"status": "ok"' in text,
        "uses_solver_decision_id": 'action_decision.get("decision_id")' in text,
        "uses_solver_fingerprint": 'action_decision.get("solver_fingerprint")' in text,

        "maps_open_raise_to_bet_raise": '"open_raise"' in text and 'return "bet_raise"' in text,
        "maps_3bet_to_bet_raise": '"3bet"' in text and 'return "bet_raise"' in text,
        "maps_4bet_to_bet_raise": '"4bet"' in text and 'return "bet_raise"' in text,
        "maps_all_in_to_bet_raise": '"all_in"' in text and 'return "bet_raise"' in text,

        "solver_preflop_attempts_before_stub": (
            "solver_decision = _extract_solver_preflop_decision_from_state(" in text
            and "if solver_decision is None:" in text
            and "solver_decision = build_solver_stub_decision(" in text
        ),

        "stub_blocker_still_present": "v21_stub_decision_cannot_execute_real_click" in text,
        "runtime_source_selection_present": "v23_solver_preflop_selected_for_live_runtime" in text,
    }

    report = {
        "schema": "pokervision_solver_preflop_v223_live_runtime_solver_bridge_audit_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "checks": checks,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
