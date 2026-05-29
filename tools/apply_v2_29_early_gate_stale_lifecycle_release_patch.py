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

MARKER = "V2.29: release stale early lifecycle directly inside the early gate blocked path"

OLD = """            if not early_action_transaction_decision.should_process:
                print(
                    f"[TableActionTransactionGate][{slot.table_id}] heavy analysis skipped by early lifecycle gate: "
                    f"reason={early_action_transaction_decision.reason}, "
                    f"locked_by={early_action_transaction_decision.locked_by_transaction_id}"
                )
                continue
"""

NEW = """            if not early_action_transaction_decision.should_process:
                print(
                    f"[TableActionTransactionGate][{slot.table_id}] heavy analysis skipped by early lifecycle gate: "
                    f"reason={early_action_transaction_decision.reason}, "
                    f"locked_by={early_action_transaction_decision.locked_by_transaction_id}"
                )

                # V2.29: release stale early lifecycle directly inside the early gate blocked path.
                #
                # V2.28 released only after heavy analysis/action-runtime candidate calculation.
                # That does not help when this early branch immediately continues before heavy
                # analysis. In real live runs this left tables stuck at
                # table_lifecycle_already_open_before_analysis and prevented the chain from
                # reaching Clear_JSON -> Solver_Preflop -> Action_Button -> click.
                #
                # We still skip the current frame after releasing; the next scan can reopen a
                # fresh lifecycle and process a real Active frame without re-entering this
                # stale-lock loop.
                if (
                    table_action_transaction_gate is not None
                    and str(early_action_transaction_decision.reason) == "table_lifecycle_already_open_before_analysis"
                ):
                    stale_lifecycle_release_before_continue = table_action_transaction_gate.abort_analysis_cycle(
                        table_id=slot.table_id,
                        reason="v229_release_stale_lifecycle_before_heavy_analysis",
                        message=(
                            "V2.29 released stale early table lifecycle before heavy-analysis skip; "
                            "current frame remains skipped and the next scan may process normally."
                        ),
                    )
                    print(
                        f"[TableActionTransactionGate][{slot.table_id}] V2.29 released stale early lifecycle before continue: "
                        f"status={stale_lifecycle_release_before_continue.get('status')}, "
                        f"reason={stale_lifecycle_release_before_continue.get('reason')}, "
                        f"released_transaction_id={stale_lifecycle_release_before_continue.get('transaction_id')}"
                    )
                continue
"""


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"Target not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")

    if MARKER in text:
        print(f"[V2.29] Patch already present: {TARGET}")
        return 0

    if OLD not in text:
        raise RuntimeError(
            "Could not find exact early-gate blocked path anchor in display_analysis_cycle.py. "
            "Run the source snippet audit again before patching."
        )

    updated = text.replace(OLD, NEW, 1)

    backup = TARGET.with_suffix(TARGET.suffix + ".v2_29_before_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    TARGET.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.29] Patched: {TARGET}")
    print(f"[V2.29] Backup:  {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
