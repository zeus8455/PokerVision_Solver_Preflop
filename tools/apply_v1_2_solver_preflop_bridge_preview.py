from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_FILE = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


IMPORT_ANCHOR = """from logic.action_runtime_plan_builder import (
    build_action_runtime_plan_from_action_decision,
    validate_action_runtime_plan_contract,
)
"""

IMPORT_INSERT = """from logic.action_runtime_plan_builder import (
    build_action_runtime_plan_from_action_decision,
    validate_action_runtime_plan_contract,
)
from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract
"""


CALL_ANCHOR = """                            action_decision_contract = build_and_save_action_decision_contract(
                                decision_state=decision_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                            )
"""

CALL_REPLACEMENT = """                            action_decision_contract = build_and_save_action_decision_contract(
                                decision_state=decision_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                            )
                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                            )
                            if isinstance(action_decision_contract, dict):
                                action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
                                state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
"""


def main() -> int:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    changed = False

    if "build_solver_preflop_dryrun_bridge_contract" not in text:
        if IMPORT_ANCHOR not in text:
            raise RuntimeError("Import anchor not found in display_analysis_cycle.py")
        text = text.replace(IMPORT_ANCHOR, IMPORT_INSERT, 1)
        changed = True

    if "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract" not in text:
        if CALL_ANCHOR not in text:
            raise RuntimeError("Pending preview action_decision_contract anchor not found in display_analysis_cycle.py")
        text = text.replace(CALL_ANCHOR, CALL_REPLACEMENT, 1)
        changed = True

    if changed:
        DISPLAY_FILE.write_text(text, encoding="utf-8")

    print({
        "status": "patched" if changed else "already_patched",
        "file": str(DISPLAY_FILE),
        "import_present": "build_solver_preflop_dryrun_bridge_contract" in text,
        "bridge_call_present": "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract" in text,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
