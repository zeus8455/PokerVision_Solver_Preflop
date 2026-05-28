from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_FILE = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


OLD = '''        "dry_run_safe": True,
        "solver_stub": False,
        "decision_context": {
            "street": str(solver_action_decision.get("street") or "preflop"),
            "hero_position": str(solver_action_decision.get("hero_position") or ""),
            "source_frame_id": source_frame_id,
            "solver_preflop_runtime_source": True,
'''

NEW = '''        "dry_run_safe": True,
        # Legacy V06 validator still requires the stub flag to remain True.
        # The real source is carried below in decision_context.solver_preflop_runtime_source.
        "solver_stub": True,
        "decision_context": {
            "street": str(solver_action_decision.get("street") or "preflop"),
            "hero_position": str(solver_action_decision.get("hero_position") or ""),
            "source_frame_id": source_frame_id,
            "solver_preflop_runtime_source": True,
            "solver_stub_legacy_compat": True,
'''


def main() -> int:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    if '"solver_stub_legacy_compat": True' in text:
        print({
            "status": "already_patched",
            "file": str(DISPLAY_FILE),
            "solver_stub_legacy_compat": True,
        })
        return 0

    if OLD not in text:
        raise RuntimeError("V2.1 legacy solver_stub compatibility anchor not found.")

    text = text.replace(OLD, NEW, 1)
    DISPLAY_FILE.write_text(text, encoding="utf-8")

    print({
        "status": "patched",
        "file": str(DISPLAY_FILE),
        "solver_stub_legacy_compat": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
