from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DISPLAY = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


REQUIRED_SNIPPETS = {
    "toggle_present": "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True",
    "dry_run_only": "V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True",
    "selector": "def _select_v20_runtime_action_decision_state(",
    "optional_bridge_param": "solver_preflop_bridge_contract: Optional[Dict[str, object]] = None",
    "runtime_selection_call": "runtime_action_decision_state, v20_runtime_source_selection = _select_v20_runtime_action_decision_state(",
    "runtime_plan_uses_selected_state": "action_decision_state=runtime_action_decision_state",
    "selection_embedded": '"v20_runtime_source_selection": dict(v20_runtime_source_selection)',
    "pending_passes_bridge": "solver_preflop_bridge_contract=solver_preflop_bridge_contract",
}


def main() -> int:
    if not SNAPSHOT_DISPLAY.exists():
        raise FileNotFoundError(SNAPSHOT_DISPLAY)

    text = SNAPSHOT_DISPLAY.read_text(encoding="utf-8")
    checks = {name: snippet in text for name, snippet in REQUIRED_SNIPPETS.items()}

    report = {
        "schema": "pokervision_solver_preflop_v20_snapshot_runtime_source_switch_check_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_display": str(SNAPSHOT_DISPLAY),
        "real_project_touched": False,
        "nested_pytest_executed": False,
        "checks": checks,
        "missing": [name for name, ok in checks.items() if not ok],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
