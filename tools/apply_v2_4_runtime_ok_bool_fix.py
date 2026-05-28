from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_FILE = ROOT / "tools" / "run_v2_4_snapshot_click_guard_eligibility_check.py"

OLD = '''    runtime_ok = (
        runtime_plan_contract.get("status") == "preview_not_saved_pending_only"
        and runtime_state.get("status") == "ok"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and target_button
    )
'''

NEW = '''    runtime_ok = bool(
        runtime_plan_contract.get("status") == "preview_not_saved_pending_only"
        and runtime_state.get("status") == "ok"
        and runtime_state.get("dry_run") is True
        and runtime_state.get("real_click_enabled") is False
        and bool(target_button)
    )
'''


def main() -> int:
    text = TOOL_FILE.read_text(encoding="utf-8")
    if NEW in text:
        print({"status": "already_patched", "file": str(TOOL_FILE), "runtime_ok_boolean": True})
        return 0
    if OLD not in text:
        raise RuntimeError("V2.4 runtime_ok anchor not found.")
    text = text.replace(OLD, NEW, 1)
    TOOL_FILE.write_text(text, encoding="utf-8")
    print({"status": "patched", "file": str(TOOL_FILE), "runtime_ok_boolean": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
