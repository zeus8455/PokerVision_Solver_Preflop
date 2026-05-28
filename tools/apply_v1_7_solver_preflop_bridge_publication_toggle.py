from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_FILE = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


BRIDGE_IMPORT = "from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract"
TOGGLE_LINE = "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False"

CALL_OLD = """                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                            )
"""

CALL_NEW = """                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                            )
"""


def main() -> int:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    changed = False

    if TOGGLE_LINE not in text:
        if BRIDGE_IMPORT not in text:
            raise RuntimeError("Bridge import anchor not found in display_analysis_cycle.py")
        text = text.replace(
            BRIDGE_IMPORT,
            BRIDGE_IMPORT + "\n\n# V1.7: diagnostic-only Solver_Preflop bridge file publication toggle.\n"
            "# Default remains False: bridge result is embedded into state/contract only.\n"
            + TOGGLE_LINE,
            1,
        )
        changed = True

    if CALL_NEW not in text:
        if CALL_OLD not in text:
            raise RuntimeError("Solver_Preflop bridge call anchor not found or already changed unexpectedly.")
        text = text.replace(CALL_OLD, CALL_NEW, 1)
        changed = True

    if changed:
        DISPLAY_FILE.write_text(text, encoding="utf-8")

    print({
        "status": "patched" if changed else "already_patched",
        "file": str(DISPLAY_FILE),
        "toggle_present": TOGGLE_LINE in text,
        "toggle_call_present": "publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES)" in text,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
