"""
logic/action_decision_stub.py

PokerVision V0.6 — Decision_JSON -> Action_Decision_JSON contract.

Purpose:
- Convert validated Decision_JSON into a compact action decision payload.
- Keep strategic/solver decision output separate from Action_Button_Detector.
- This is a safe stub, not a real solver.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import (
    V06_ACTION_DECISION_SCHEMA_VERSION,
    V06_ACTION_DECISION_STUB_DEFAULT_ACTION,
    V06_ACTION_DECISION_STUB_DEFAULT_REASON,
    V06_ACTION_DECISION_STUB_DEFAULT_SIZE_POLICY,
)
from logic.decision_json_builder import validate_decision_json_contract


VALID_ACTIONS = {"fold", "call", "check", "bet", "raise", "check_fold"}


def _normalize_action(action: Any) -> str:
    text = str(action or "").strip().lower()
    return text if text in VALID_ACTIONS else "fold"


def _normalize_size_policy(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"type": "pct", "value": float(value)}
    text = str(value).strip()
    if not text:
        return None
    return {"type": "raw", "value": text}


def _target_buttons_for_action(action: str, size_policy: Optional[Dict[str, Any]]) -> List[str]:
    if action == "fold":
        return ["FOLD"]
    if action == "call":
        return ["Call"]
    if action == "check":
        return ["Check"]
    if action == "check_fold":
        return ["Check", "Check/fold", "FOLD"]
    if action in {"bet", "raise"}:
        buttons: List[str] = []
        if isinstance(size_policy, dict):
            value = str(size_policy.get("value") or "").strip()
            if value in {"33", "50", "70", "98"}:
                buttons.append(f"{value}%")
        buttons.append("Bet/Raise")
        return buttons
    return ["FOLD"]


def build_action_decision_from_decision_json(decision_json: Dict[str, Any]) -> Dict[str, Any]:
    """Build a safe stub Action_Decision_JSON from validated Decision_JSON."""
    validation = validate_decision_json_contract(decision_json)
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise ValueError(f"Decision_JSON is not valid enough to build Action_Decision_JSON: {validation}")

    action = _normalize_action(V06_ACTION_DECISION_STUB_DEFAULT_ACTION)
    size_policy = _normalize_size_policy(V06_ACTION_DECISION_STUB_DEFAULT_SIZE_POLICY)

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": str(decision_json.get("source_frame_id") or ""),
        "status": "ok",
        "action": action,
        "size_policy": size_policy,
        "target_button_classes": _target_buttons_for_action(action, size_policy),
        "reason": str(V06_ACTION_DECISION_STUB_DEFAULT_REASON or "stub_default_action"),
        "dry_run_safe": True,
        "solver_stub": True,
        "decision_context": {
            "street": str(decision_json.get("street") or "unknown"),
            "hero_position": str((decision_json.get("hero") or {}).get("position") or ""),
            "source_frame_id": str(decision_json.get("source_frame_id") or ""),
        },
    }


def validate_action_decision_contract(action_decision: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(action_decision, dict):
        return {"ok": False, "errors": ["Action_Decision_JSON must be an object."], "warnings": []}

    required = {
        "schema_version", "source", "source_decision_frame_id", "status", "action",
        "size_policy", "target_button_classes", "reason", "dry_run_safe", "solver_stub",
        "decision_context",
    }
    missing = sorted(required - set(action_decision.keys()))
    if missing:
        errors.append(f"Action_Decision_JSON missing required keys: {missing}")

    forbidden = {
        "pipeline_meta", "trigger_ui", "table_structure", "runtime_event", "runtime_action",
        "click_result", "click_points", "bbox", "confidence", "errors", "warnings",
        "clear_json", "dark_json",
    }
    extra_forbidden = sorted(forbidden & set(action_decision.keys()))
    if extra_forbidden:
        errors.append(f"Action_Decision_JSON has forbidden technical keys: {extra_forbidden}")

    if action_decision.get("schema_version") != V06_ACTION_DECISION_SCHEMA_VERSION:
        errors.append(f"Action_Decision_JSON.schema_version mismatch: {action_decision.get('schema_version')!r}")
    if action_decision.get("source") != "Decision_JSON":
        errors.append("Action_Decision_JSON.source must be 'Decision_JSON'.")
    if str(action_decision.get("status") or "") != "ok":
        errors.append("Action_Decision_JSON.status must be 'ok'.")
    action = str(action_decision.get("action") or "")
    if action not in VALID_ACTIONS:
        errors.append(f"Action_Decision_JSON.action is invalid: {action!r}")
    if not isinstance(action_decision.get("target_button_classes"), list) or not action_decision.get("target_button_classes"):
        errors.append("Action_Decision_JSON.target_button_classes must be a non-empty list.")
    if action_decision.get("dry_run_safe") is not True:
        errors.append("Action_Decision_JSON.dry_run_safe must be True for V0.6 stub.")
    if action_decision.get("solver_stub") is not True:
        errors.append("Action_Decision_JSON.solver_stub must be True for V0.6 stub.")
    if not isinstance(action_decision.get("decision_context"), dict):
        errors.append("Action_Decision_JSON.decision_context must be an object.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
