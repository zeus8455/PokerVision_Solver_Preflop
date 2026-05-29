from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    PROJECT_ROOT
    / "external"
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "display_analysis_cycle.py"
)

MARKER = "V2.28: release early lifecycle lock if the frame cannot enter action runtime"

INSERT_BEFORE = "        # V2.0: the table transaction lifecycle starts before heavy analysis and"

PATCH_BLOCK = """        # V2.28: release early lifecycle lock if the frame cannot enter action runtime.
        #
        # Real-live failure fixed here:
        # - Trigger_UI can briefly open the early per-table lifecycle before the
        #   post-analysis action_event_id/signature is available.
        # - If the resulting frame is later classified as no_active_confirmed,
        #   duplicate_active_frame_blocked, or missing action_event_id, the
        #   Action_Button runtime will not run and therefore no click_result can
        #   close the lifecycle.
        # - Without this release, the next scans are blocked by
        #   table_lifecycle_already_open_before_analysis and the bot never
        #   reaches Solver_Preflop -> Action_Button -> click for that table.
        early_lifecycle_release_before_action = None
        if (
            table_action_transaction_gate is not None
            and early_action_transaction_decision is not None
            and bool(getattr(early_action_transaction_decision, "should_process", False))
            and not bool(action_runtime_candidate)
        ):
            release_reason = str(action_runtime_skip_reason or "action_runtime_not_candidate_after_analysis")
            early_lifecycle_release_before_action = table_action_transaction_gate.abort_analysis_cycle(
                table_id=slot.table_id,
                reason=f"v228_release_early_lifecycle_{release_reason}",
                message=(
                    "V2.28 released early table lifecycle because this frame reached "
                    "post-analysis but cannot enter the Action_Button runtime/click branch."
                ),
            )
            _update_runtime_lifecycle_diagnostics(
                state,
                early_lifecycle_release_before_action=early_lifecycle_release_before_action,
            )

"""


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"Target file not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")

    if MARKER in text:
        print(f"[V2.28] Patch already present: {TARGET}")
        return 0

    if INSERT_BEFORE not in text:
        raise RuntimeError(
            "Could not find insertion anchor in display_analysis_cycle.py: "
            f"{INSERT_BEFORE!r}"
        )

    updated = text.replace(INSERT_BEFORE, PATCH_BLOCK + INSERT_BEFORE, 1)

    backup = TARGET.with_suffix(TARGET.suffix + ".v2_28_before_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    TARGET.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.28] Patched: {TARGET}")
    print(f"[V2.28] Backup:  {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
