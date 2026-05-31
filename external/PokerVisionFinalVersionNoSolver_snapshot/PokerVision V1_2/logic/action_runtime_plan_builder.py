"""
logic/action_runtime_plan_builder.py
PokerVision V1.1.2 — Action_Decision_JSON -> Action_Runtime_Plan_JSON через Action_Button_Runtime_Policy.

Назначение:
- RuntimePlan больше не выбирает кнопки собственной старой логикой.
- Все target_sequence / target_sequences берутся из logic.action_button_runtime_policy.
- Первый controlled real-click этап разрешает только простые кнопки: fold/check/call/check_fold.
- bet/raise/sizing branch сохраняется как заблокированная ветка до отдельного этапа.
"""
from __future__ import annotations

from typing import Any, Dict, List

try:
    from config import (
        V07_ACTION_RUNTIME_PLAN_SCHEMA_VERSION,
        V07_RUNTIME_ACTION_SOURCE_REQUIRED,
        V07_RUNTIME_PLAN_DRY_RUN_REQUIRED,
        V09_REAL_CLICK_MASTER_ARMED,
        V11_CLICK_DRY_RUN,
        V11_REAL_MOUSE_CLICK_ENABLED,
        V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED,
        V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE,
    )
except Exception:  # pragma: no cover - defensive fallback for isolated import checks
    V07_ACTION_RUNTIME_PLAN_SCHEMA_VERSION = "action_runtime_plan_v1"
    V07_RUNTIME_ACTION_SOURCE_REQUIRED = "Action_Decision_JSON"
    V07_RUNTIME_PLAN_DRY_RUN_REQUIRED = True
    V09_REAL_CLICK_MASTER_ARMED = False
    V11_CLICK_DRY_RUN = True
    V11_REAL_MOUSE_CLICK_ENABLED = False
    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = False
    V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE = True

from logic.action_decision_stub import validate_action_decision_contract
from logic.action_button_runtime_policy import (
    normalize_action,
    resolve_action_button_runtime_policy,
)

_VALID_ACTIONS = {"fold", "call", "check", "bet", "raise", "check_fold", "bet_raise"}
_VALID_PLAN_STATUS = {"ok", "blocked"}
_POLICY_VERSION = "v1.1.1_action_button_runtime_policy"
_PLAN_STAGE = "v1_1_simple_buttons_only"


def _is_controlled_action_button_live_ready() -> bool:
    """Return True when Action_Button runtime is explicitly allowed to build a live real-click plan.

    V9 full-live mode may keep Trigger_UI service real-click enabled.
    Service runtime readiness must not invalidate Action_Runtime_Plan_JSON for the Active/action-button branch.
    """
    return (
        not bool(V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE)
        and bool(V09_REAL_CLICK_MASTER_ARMED)
        and bool(V11_REAL_MOUSE_CLICK_ENABLED)
        and not bool(V11_CLICK_DRY_RUN)
    )


def _runtime_plan_dry_run_required() -> bool:
    return not _is_controlled_action_button_live_ready()


def _runtime_plan_real_click_enabled() -> bool:
    return _is_controlled_action_button_live_ready()


def _normalize_button_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _normalize_sequence_list(value: Any) -> List[List[str]]:
    if not isinstance(value, list):
        return []
    out: List[List[str]] = []
    for item in value:
        seq = _normalize_button_list(item)
        if seq:
            out.append(seq)
    return out



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
    if raw_action in {"iso_raise", "3bet", "jam", "all_in"}: return ["98%", "Raise"]
    if raw_action in {"4bet", "5bet"}: return ["50%", "Raise"]
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


def _build_policy_result(action_decision: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve V1.1 action-button policy in plan-building mode.

    No detector classes are passed here; Action_Button_Detector runs later.
    Therefore selected_sequence means the primary planned sequence, not proof that
    the button is already visible on screen.
    """
    return resolve_action_button_runtime_policy(
        action=action_decision.get("action"),
        size_policy=action_decision.get("size_policy"),
        detected_classes=None,
        real_click_enabled=bool(V11_REAL_MOUSE_CLICK_ENABLED),
    )


def build_action_runtime_plan_from_action_decision(action_decision: Dict[str, Any]) -> Dict[str, Any]:
    """Build Action_Runtime_Plan_JSON from Action_Decision_JSON only.

    V1.1.2 routing:
        Action_Decision_JSON -> Action_Button_Runtime_Policy -> Action_Runtime_Plan_JSON.
    """
    validation = validate_action_decision_contract(action_decision)
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise ValueError(
            "Action_Decision_JSON is not valid enough to build Action_Runtime_Plan_JSON: "
            f"{validation}"
        )

    action = normalize_action(action_decision.get("action"))
    policy = _build_policy_result(action_decision)
    policy_ok = bool(policy.get("ok"))

    target_sequence = _normalize_button_list(policy.get("selected_sequence"))
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


    # V2.51: explicit postflop unsupported fallback.
    # Preserve safe ordered runtime sequence: Check -> Check/fold -> FOLD.
    decision_context = action_decision.get("decision_context")
    if isinstance(decision_context, dict) and bool(decision_context.get("postflop_solver_missing")):
        v251_sequence = ["Check", "Check/fold", "FOLD"]
        target_sequence = list(v251_sequence)
        target_sequences = [list(v251_sequence)]
        policy = dict(policy)
        policy.update(
            {
                "ok": True,
                "action": action,
                "selected_sequence": list(v251_sequence),
                "target_sequences": [list(v251_sequence)],
                "blocked_reason": None,
                "missing_classes": [],
                "v251_postflop_solver_missing_safe_runtime_fallback": True,
            }
        )
        policy_ok = True

    plan_status = "ok" if policy_ok else "blocked"
    blocked_reason = None if policy_ok else str(policy.get("blocked_reason") or "action_button_policy_blocked")

    # V2.37: expose Solver_Preflop lineage in Action_Runtime_Plan_JSON.
    decision_context = action_decision.get("decision_context")
    if not isinstance(decision_context, dict):
        decision_context = {}
    solver_preflop_runtime_source = bool(decision_context.get("solver_preflop_runtime_source"))
    solver_lineage = {
        "schema_version": "solver_preflop_runtime_plan_lineage_v2_37",
        "source": "PokerVision_Solver_Preflop" if solver_preflop_runtime_source else str(action_decision.get("source") or ""),
        "selected_source": "Solver_Preflop_Bridge" if solver_preflop_runtime_source else "Action_Decision_JSON",
        "adapted_to_legacy_action_decision": bool(decision_context.get("solver_stub_legacy_compat")),
        "decision_id": decision_context.get("solver_decision_id") or action_decision.get("decision_id"),
        "solver_fingerprint": decision_context.get("solver_fingerprint") or action_decision.get("solver_fingerprint"),
        "source_frame_id": decision_context.get("source_frame_id") or action_decision.get("source_decision_frame_id"),
        "solver_raw_action": decision_context.get("solver_raw_action") or action_decision.get("raw_action"),
        "solver_engine_action": decision_context.get("solver_engine_action") or action_decision.get("engine_action") or action_decision.get("action"),
        "runtime_action": action,
        "target_sequence": list(target_sequence),
        "target_sequences": [list(seq) for seq in target_sequences],
        "raise_branch_enabled": bool(v234_raise_branch_enabled),
    }

    return {
        "schema_version": V07_ACTION_RUNTIME_PLAN_SCHEMA_VERSION,
        "source": V07_RUNTIME_ACTION_SOURCE_REQUIRED,
        "source_action_decision_frame_id": str(action_decision.get("source_decision_frame_id") or ""),
        "decision_id": solver_lineage.get("decision_id"),
        "solver_source": solver_lineage.get("source"),
        "solver_raw_action": solver_lineage.get("solver_raw_action"),
        "solver_engine_action": solver_lineage.get("solver_engine_action"),
        "solver_fingerprint": solver_lineage.get("solver_fingerprint"),
        "runtime_source_selection": {
            "selected_source": solver_lineage.get("selected_source"),
            "adapted_to_legacy_action_decision": solver_lineage.get("adapted_to_legacy_action_decision"),
        },
        "lineage": dict(solver_lineage),
        "status": plan_status,
        "planned_action": action,
        "size_policy": action_decision.get("size_policy"),
        "target_button_classes": list(target_sequence),
        "target_sequence": list(target_sequence),
        "target_sequences": [list(seq) for seq in target_sequences],
        "runtime_branch": "action_button",
        "dry_run_required": bool(_runtime_plan_dry_run_required()),
        "dry_run": bool(V11_CLICK_DRY_RUN),
        "real_click_enabled": bool(V11_REAL_MOUSE_CLICK_ENABLED),
        "guards_required": [
            "active_confirmed",
            "slot_guard",
            "no_repeat",
            "button_availability",
            "dry_run_or_real_click_flag",
            "click_execution_guard",
            "action_button_runtime_policy",
        ],
        "action_decision_reason": str(action_decision.get("reason") or ""),
        "solver_stub": bool(action_decision.get("solver_stub", False)),
        "policy_stage": _PLAN_STAGE,
        "policy_version": str(policy.get("policy_version") or _POLICY_VERSION),
        "raise_branch_enabled": bool(v234_raise_branch_enabled),
        "action_button_policy": dict(policy),
        "blocked_reason": blocked_reason,
        "plan_note": (
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
    }


def validate_action_runtime_plan_contract(plan: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(plan, dict):
        return {"ok": False, "errors": ["Action_Runtime_Plan_JSON must be an object."], "warnings": []}

    required = {
        "schema_version",
        "source",
        "source_action_decision_frame_id",
        "status",
        "planned_action",
        "size_policy",
        "target_button_classes",
        "target_sequence",
        "target_sequences",
        "runtime_branch",
        "dry_run_required",
        "dry_run",
        "real_click_enabled",
        "guards_required",
        "action_decision_reason",
        "solver_stub",
        "policy_stage",
        "policy_version",
        "raise_branch_enabled",
        "action_button_policy",
        "blocked_reason",
        "plan_note",
    }
    missing = sorted(required - set(plan.keys()))
    if missing:
        errors.append(f"Action_Runtime_Plan_JSON missing required keys: {missing}")

    forbidden = {
        "pipeline_meta",
        "trigger_ui",
        "table_structure",
        "runtime_event",
        "runtime_action",
        "click_result",
        "click_points",
        "bbox",
        "confidence",
        "errors",
        "warnings",
        "clear_json",
        "dark_json",
        "mouse",
    }
    extra_forbidden = sorted(forbidden & set(plan.keys()))
    if extra_forbidden:
        errors.append(f"Action_Runtime_Plan_JSON has forbidden technical keys: {extra_forbidden}")

    if plan.get("schema_version") != V07_ACTION_RUNTIME_PLAN_SCHEMA_VERSION:
        errors.append(f"Action_Runtime_Plan_JSON.schema_version mismatch: {plan.get('schema_version')!r}")

    if plan.get("source") != V07_RUNTIME_ACTION_SOURCE_REQUIRED:
        errors.append(f"Action_Runtime_Plan_JSON.source must be {V07_RUNTIME_ACTION_SOURCE_REQUIRED!r}.")

    status = str(plan.get("status") or "")
    if status not in _VALID_PLAN_STATUS:
        errors.append("Action_Runtime_Plan_JSON.status must be 'ok' or 'blocked'.")

    if str(plan.get("planned_action") or "") not in _VALID_ACTIONS:
        errors.append(f"Action_Runtime_Plan_JSON.planned_action is invalid: {plan.get('planned_action')!r}")

    target_sequence = plan.get("target_sequence")
    target_sequences = plan.get("target_sequences")

    if status == "ok":
        if not isinstance(target_sequence, list) or not target_sequence:
            errors.append("Action_Runtime_Plan_JSON.target_sequence must be a non-empty list when status='ok'.")
        if not isinstance(target_sequences, list) or not target_sequences:
            errors.append("Action_Runtime_Plan_JSON.target_sequences must be a non-empty list of alternatives when status='ok'.")
    else:
        if plan.get("blocked_reason") in (None, ""):
            errors.append("Blocked Action_Runtime_Plan_JSON must include blocked_reason.")

    if isinstance(target_sequences, list):
        for seq in target_sequences:
            if not isinstance(seq, list) or not seq:
                errors.append("Each Action_Runtime_Plan_JSON.target_sequences item must be a non-empty list.")
                break
    elif status == "ok":
        errors.append("Action_Runtime_Plan_JSON.target_sequences must be a list.")

    if plan.get("runtime_branch") != "action_button":
        errors.append("Action_Runtime_Plan_JSON.runtime_branch must be 'action_button'.")

    expected_dry_run_required = bool(_runtime_plan_dry_run_required())
    expected_real_click_enabled = bool(_runtime_plan_real_click_enabled())

    if plan.get("dry_run_required") is not expected_dry_run_required:
        errors.append(
            "Action_Runtime_Plan_JSON.dry_run_required does not match current runtime mode: "
            f"expected={expected_dry_run_required!r}, got={plan.get('dry_run_required')!r}."
        )

    if plan.get("real_click_enabled") is not expected_real_click_enabled:
        errors.append(
            "Action_Runtime_Plan_JSON.real_click_enabled does not match current runtime mode: "
            f"expected={expected_real_click_enabled!r}, got={plan.get('real_click_enabled')!r}."
        )

    if plan.get("dry_run") is not expected_dry_run_required:
        errors.append(
            "Action_Runtime_Plan_JSON.dry_run does not match current runtime mode: "
            f"expected={expected_dry_run_required!r}, got={plan.get('dry_run')!r}."
        )

    if not isinstance(plan.get("guards_required"), list) or not plan.get("guards_required"):
        errors.append("Action_Runtime_Plan_JSON.guards_required must be a non-empty list.")

    if plan.get("policy_stage") != _PLAN_STAGE:
        errors.append(f"Action_Runtime_Plan_JSON.policy_stage must be {_PLAN_STAGE!r}.")

    if plan.get("raise_branch_enabled") is not False:
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

    policy = plan.get("action_button_policy")
    if not isinstance(policy, dict):
        errors.append("Action_Runtime_Plan_JSON.action_button_policy must be an object.")
    else:
        if str(policy.get("policy_version") or "") != str(plan.get("policy_version") or ""):
            errors.append("Action_Runtime_Plan_JSON.policy_version must mirror action_button_policy.policy_version.")
        if status == "ok" and policy.get("ok") is not True:
            errors.append("Action_Runtime_Plan_JSON status='ok' requires action_button_policy.ok=True.")
        if status == "blocked" and policy.get("ok") is not False:
            errors.append("Blocked Action_Runtime_Plan_JSON requires action_button_policy.ok=False.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
