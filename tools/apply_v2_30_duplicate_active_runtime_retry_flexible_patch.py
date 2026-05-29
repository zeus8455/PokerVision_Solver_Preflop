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

MARKER = "V2.30: recover duplicate Active into runtime retry when no runtime/final artifact exists"
DUPLICATE_LOG_NEEDLE = 'f"[ActionEventGate][{slot.table_id}] duplicate Active action suppressed, "'
DUPLICATE_OF_NEEDLE = 'f"duplicate_of={action_event_decision.duplicate_of}"'


INSERT_BLOCK = '''
                # V2.30: recover duplicate Active into runtime retry when no runtime/final artifact exists.
                #
                # Real-live failure fixed here:
                # - ActionEventGate correctly suppresses identical Active frames to avoid repeated output.
                # - However, if the original Active produced only Pending/Solver payload diagnostics and never
                #   reached Action_Runtime_Plan_JSON or Final Clear_JSON/click_result, then treating every
                #   following identical Active as a hard duplicate permanently prevents clicking.
                # - In that unfinished state we convert the duplicate decision into a guarded retry event.
                #   Existing click guards/no-repeat guards still decide whether a physical click is allowed.
                v230_runtime_plan_dir = cycle_dir / V07_ACTION_RUNTIME_PLAN_DIR_NAME / slot.table_id
                v230_final_clear_dir = cycle_dir / V04_CLEAR_JSON_FINAL_DIR_NAME / slot.table_id
                v230_has_runtime_plan = v230_runtime_plan_dir.exists() and any(v230_runtime_plan_dir.glob("*.json"))
                v230_has_final_clear = v230_final_clear_dir.exists() and any(v230_final_clear_dir.glob("*.json"))
                v230_duplicate_retry_allowed = (
                    str(action_event_decision.reason) == "duplicate_active_frame_blocked"
                    and not bool(v230_has_runtime_plan)
                    and not bool(v230_has_final_clear)
                )
                if v230_duplicate_retry_allowed:
                    v230_retry_base = (
                        action_event_decision.duplicate_of
                        or f"evt_{slot.table_id}_{str(action_event_decision.action_signature or 'no_signature')[:16]}"
                    )
                    v230_retry_event_id = f"{v230_retry_base}_v230_retry"
                    action_event_decision = replace(
                        action_event_decision,
                        should_process=True,
                        action_event_id=v230_retry_event_id,
                        reason="v230_duplicate_active_runtime_retry_without_completed_runtime",
                    )
                    print(
                        f"[ActionEventGate][{slot.table_id}] V2.30 duplicate Active runtime retry enabled: "
                        f"event_id={v230_retry_event_id}, "
                        f"has_runtime_plan={v230_has_runtime_plan}, "
                        f"has_final_clear={v230_has_final_clear}"
                    )
'''


def _ensure_replace_import(text: str) -> str:
    if "from dataclasses import dataclass, field, replace" in text:
        return text
    if "from dataclasses import dataclass, replace, field" in text:
        return text.replace(
            "from dataclasses import dataclass, replace, field",
            "from dataclasses import dataclass, field, replace",
            1,
        )
    if "from dataclasses import dataclass, field" in text:
        return text.replace(
            "from dataclasses import dataclass, field",
            "from dataclasses import dataclass, field, replace",
            1,
        )
    if "from dataclasses import dataclass" in text:
        return text.replace(
            "from dataclasses import dataclass",
            "from dataclasses import dataclass, replace",
            1,
        )
    raise RuntimeError("Could not find dataclasses import to add replace")


def _insert_after_duplicate_print(text: str) -> str:
    lines = text.splitlines(keepends=True)

    duplicate_log_idx = None
    for idx, line in enumerate(lines):
        if DUPLICATE_LOG_NEEDLE in line:
            duplicate_log_idx = idx
            break

    if duplicate_log_idx is None:
        raise RuntimeError("Could not find duplicate Active action suppressed log line")

    duplicate_of_idx = None
    for idx in range(duplicate_log_idx, min(len(lines), duplicate_log_idx + 12)):
        if DUPLICATE_OF_NEEDLE in lines[idx]:
            duplicate_of_idx = idx
            break

    if duplicate_of_idx is None:
        raise RuntimeError("Could not find duplicate_of line after duplicate Active log")

    # Insert after the closing parenthesis of the print(...) call.
    insert_idx = None
    for idx in range(duplicate_of_idx + 1, min(len(lines), duplicate_of_idx + 8)):
        if lines[idx].strip() == ")":
            insert_idx = idx + 1
            break

    if insert_idx is None:
        raise RuntimeError("Could not find closing print parenthesis after duplicate Active log")

    lines.insert(insert_idx, INSERT_BLOCK)
    return "".join(lines)


def main() -> int:
    if not TARGET.exists():
        raise FileNotFoundError(f"Target not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8", errors="replace")

    if MARKER in text:
        print(f"[V2.30] Patch already present: {TARGET}")
        return 0

    updated = _ensure_replace_import(text)
    updated = _insert_after_duplicate_print(updated)

    backup = TARGET.with_suffix(TARGET.suffix + ".v2_30_before_flexible_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    TARGET.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.30] Flexible patch applied: {TARGET}")
    print(f"[V2.30] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
