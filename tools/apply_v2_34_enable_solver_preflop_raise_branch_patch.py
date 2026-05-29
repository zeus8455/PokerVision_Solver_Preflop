
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER = (
    PROJECT_ROOT
    / "external"
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "logic"
    / "action_runtime_plan_builder.py"
)

MARKER = "V2.34: enable Solver_Preflop controlled bet_raise branch"

HELPER_BLOCK = '''
# V2.34: enable Solver_Preflop controlled bet_raise branch.
#
# The legacy V1.1 simple-button stage intentionally blocked bet/raise.
# Full live profile already enables V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED,
# but the plan builder still hard-coded raise_branch_enabled=False.
# This helper opens the raise branch only for Solver_Preflop-adapted preflop
# decisions. All lower click guards remain enforced later by action_click_stub.py:
# slot ROI, no-repeat decision_id, button availability, real-click flag, and
# Solver_Preflop source/status checks.
def _v234_solver_preflop_raise_branch_enabled() -> bool:
    try:
        from config import V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED
        return bool(V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED)
    except Exception:
        return False


def _v234_solver_preflop_raise_sequence(action_decision: Dict[str, Any], normalized_action: str) -> List[str]:
    if normalized_action != "bet_raise":
        return []

    decision_context = action_decision.get("decision_context")
    if not isinstance(decision_context, dict):
        return []

    if not bool(decision_context.get("solver_preflop_runtime_source")):
        return []

    raw_action = str(
        decision_context.get("solver_raw_action")
        or decision_context.get("solver_engine_action")
        or action_decision.get("raw_action")
        or action_decision.get("engine_action")
        or action_decision.get("action")
        or ""
    ).strip().lower()

    if raw_action == "open_raise":
        return ["Raise"]
    if raw_action in {"iso_raise", "3bet", "5bet", "jam", "all_in"}:
        return ["98%", "Raise"]
    if raw_action == "4bet":
        return ["50%", "Raise"]

    raw_targets = action_decision.get("target_button_classes")
    if isinstance(raw_targets, list):
        out: List[str] = []
        for item in raw_targets:
            token = str(item or "").strip()
            if not token:
                continue
            if token == "Bet/Raise":
                token = "Raise"
            out.append(token)
        if out:
            return out

    return []
'''


def _insert_helper(text: str) -> str:
    if MARKER in text:
        return text

    anchor = "def _build_policy_result(action_decision: Dict[str, Any]) -> Dict[str, Any]:"
    if anchor not in text:
        raise RuntimeError("Could not find _build_policy_result anchor")

    return text.replace(anchor, HELPER_BLOCK + "\n\n" + anchor, 1)


def _patch_build_function(text: str) -> str:
    old = '''    target_sequence = _normalize_button_list(policy.get("selected_sequence"))
    target_sequences = _normalize_sequence_list(policy.get("target_sequences"))

    plan_status = "ok" if policy_ok else "blocked"
    blocked_reason = None if policy_ok else str(policy.get("blocked_reason") or "action_button_policy_blocked")
'''
    new = '''    target_sequence = _normalize_button_list(policy.get("selected_sequence"))
    target_sequences = _normalize_sequence_list(policy.get("target_sequences"))

    v234_raise_sequence = _v234_solver_preflop_raise_sequence(action_decision, action)
    v234_raise_branch_enabled = bool(_v234_solver_preflop_raise_branch_enabled() and v234_raise_sequence)
    if v234_raise_branch_enabled:
        target_sequence = list(v234_raise_sequence)
        target_sequences = [list(v234_raise_sequence)]
        policy = dict(policy)
        policy.update(
            {
                "ok": True,
                "action": action,
                "selected_sequence": list(v234_raise_sequence),
                "target_sequences": [list(v234_raise_sequence)],
                "blocked_reason": None,
                "missing_classes": [],
                "real_click_allowed": bool(V11_REAL_MOUSE_CLICK_ENABLED),
                "v234_solver_preflop_raise_branch": True,
            }
        )
        policy_ok = True

    plan_status = "ok" if policy_ok else "blocked"
    blocked_reason = None if policy_ok else str(policy.get("blocked_reason") or "action_button_policy_blocked")
'''
    if old not in text:
        if "v234_raise_sequence = _v234_solver_preflop_raise_sequence" in text:
            return text
        raise RuntimeError("Could not find target_sequence/plan_status anchor")
    return text.replace(old, new, 1)


def _patch_raise_enabled_field(text: str) -> str:
    old = '        "raise_branch_enabled": False,\n'
    new = '        "raise_branch_enabled": bool(v234_raise_branch_enabled),\n'
    if old not in text:
        if '"raise_branch_enabled": bool(v234_raise_branch_enabled),' in text:
            return text
        raise RuntimeError("Could not find raise_branch_enabled field")
    return text.replace(old, new, 1)


def _patch_plan_note(text: str) -> str:
    old = '''        "plan_note": (
            "V1.1 Action_Runtime_Plan_JSON is built through "
            "Action_Button_Runtime_Policy. First controlled real-click stage allows "
            "only fold/check/call/check_fold simple button actions; bet/raise sizing "
            "branch is disabled until a separate safety stage."
        ),
'''
    new = '''        "plan_note": (
            "V1.1 Action_Runtime_Plan_JSON is built through "
            "Action_Button_Runtime_Policy. V2.34 allows Solver_Preflop-controlled "
            "bet/raise branches only when the full live profile enables the raise "
            "branch; all click guards remain enforced."
            if bool(v234_raise_branch_enabled)
            else
            "V1.1 Action_Runtime_Plan_JSON is built through "
            "Action_Button_Runtime_Policy. First controlled real-click stage allows "
            "only fold/check/call/check_fold simple button actions; bet/raise sizing "
            "branch is disabled until a separate safety stage."
        ),
'''
    if old not in text:
        if "V2.34 allows Solver_Preflop-controlled" in text:
            return text
        raise RuntimeError("Could not find plan_note anchor")
    return text.replace(old, new, 1)


def _patch_validation(text: str) -> str:
    old = '''    if plan.get("raise_branch_enabled") is not False:
        errors.append("Action_Runtime_Plan_JSON.raise_branch_enabled must be False in V1.1 simple-button stage.")
'''
    new = '''    if plan.get("raise_branch_enabled") is not False:
        if not (
            str(plan.get("planned_action") or "") == "bet_raise"
            and str(plan.get("status") or "") == "ok"
            and isinstance(plan.get("target_sequence"), list)
            and bool(plan.get("target_sequence"))
        ):
            errors.append(
                "Action_Runtime_Plan_JSON.raise_branch_enabled may be True only for "
                "a valid V2.34 Solver_Preflop bet_raise runtime plan."
            )
'''
    if old not in text:
        if "V2.34 Solver_Preflop bet_raise runtime plan" in text:
            return text
        raise RuntimeError("Could not find validation raise_branch_enabled anchor")
    return text.replace(old, new, 1)


def main() -> int:
    if not BUILDER.exists():
        raise FileNotFoundError(f"Target not found: {BUILDER}")

    text = BUILDER.read_text(encoding="utf-8", errors="replace")
    updated = _insert_helper(text)
    updated = _patch_build_function(updated)
    updated = _patch_raise_enabled_field(updated)
    updated = _patch_plan_note(updated)
    updated = _patch_validation(updated)

    if updated == text:
        print(f"[V2.34] Patch already present: {BUILDER}")
        return 0

    backup = BUILDER.with_suffix(BUILDER.suffix + ".v2_34_before_patch.bak")
    backup.write_text(text, encoding="utf-8", newline="")
    BUILDER.write_text(updated, encoding="utf-8", newline="")

    print(f"[V2.34] Patched: {BUILDER}")
    print(f"[V2.34] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
