from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_FILE = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2" / "display_analysis_cycle.py"


FALSE_LINE = "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = False"
TRUE_LINE = "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True"

SELECTOR_ANCHOR = "\ndef _select_v20_runtime_action_decision_state(\n"

ADAPTER_BLOCK = '\n\ndef _v21_normalize_solver_preflop_action(value: object) -> str:\n    text = str(value or "").strip().lower()\n    if text in {"fold", "call", "check", "bet", "raise", "check_fold"}:\n        return text\n    if text in {"4bet", "5bet", "3bet", "open_raise", "iso_raise", "jam", "all_in"}:\n        return "raise"\n    return "fold"\n\n\ndef _v21_solver_size_policy(solver_action_decision: Dict[str, object], action: str) -> Optional[Dict[str, object]]:\n    if action not in {"bet", "raise"}:\n        return None\n\n    raw_policy = solver_action_decision.get("size_policy")\n    if isinstance(raw_policy, dict):\n        return dict(raw_policy)\n\n    raw_pct = (\n        solver_action_decision.get("size_pct")\n        or solver_action_decision.get("raise_size_pct")\n        or solver_action_decision.get("button_pct")\n    )\n    if raw_pct is None:\n        return None\n\n    try:\n        pct_float = float(raw_pct)\n        pct_text = str(int(pct_float)) if pct_float.is_integer() else str(pct_float)\n    except Exception:\n        pct_text = str(raw_pct).replace("%", "").strip()\n\n    if pct_text in {"33", "50", "70", "98"}:\n        return {"type": "pct", "value": pct_text}\n    return {"type": "raw", "value": pct_text}\n\n\ndef _v21_target_buttons_for_solver_action(\n    *,\n    action: str,\n    size_policy: Optional[Dict[str, object]],\n    solver_action_decision: Dict[str, object],\n) -> list[str]:\n    raw_buttons = (\n        solver_action_decision.get("target_button_classes")\n        or solver_action_decision.get("target_sequence")\n        or solver_action_decision.get("click_sequence")\n    )\n    if isinstance(raw_buttons, list) and raw_buttons:\n        normalized: list[str] = []\n        for item in raw_buttons:\n            text = str(item or "").strip()\n            if text.upper() == "CALL":\n                normalized.append("Call")\n            elif text.upper() == "FOLD":\n                normalized.append("FOLD")\n            elif text == "Raise":\n                normalized.append("Bet/Raise")\n            else:\n                normalized.append(text)\n        return [b for b in normalized if b]\n\n    if action == "fold":\n        return ["FOLD"]\n    if action == "call":\n        return ["Call"]\n    if action == "check":\n        return ["Check"]\n    if action == "check_fold":\n        return ["Check", "Check/fold", "FOLD"]\n    if action in {"bet", "raise"}:\n        buttons: list[str] = []\n        if isinstance(size_policy, dict):\n            value = str(size_policy.get("value") or "").strip()\n            if value in {"33", "50", "70", "98"}:\n                buttons.append(f"{value}%")\n        buttons.append("Bet/Raise")\n        return buttons\n    return ["FOLD"]\n\n\ndef _adapt_v21_solver_preflop_action_decision_to_v06(\n    solver_action_decision: Dict[str, object],\n) -> Dict[str, object]:\n    """Convert Solver_Preflop bridge action_decision to legacy V06 Action_Decision_JSON.\n\n    Action_Runtime_Plan builder currently validates source=\'Decision_JSON\'.\n    The adapter keeps that legacy shape while carrying Solver_Preflop lineage\n    inside reason/decision_context. It does not bypass runtime guards.\n    """\n    from config import V06_ACTION_DECISION_SCHEMA_VERSION\n\n    action = _v21_normalize_solver_preflop_action(\n        solver_action_decision.get("action")\n        or solver_action_decision.get("engine_action")\n        or solver_action_decision.get("raw_action")\n    )\n    size_policy = _v21_solver_size_policy(solver_action_decision, action)\n    target_buttons = _v21_target_buttons_for_solver_action(\n        action=action,\n        size_policy=size_policy,\n        solver_action_decision=solver_action_decision,\n    )\n\n    source_frame_id = str(\n        solver_action_decision.get("source_decision_frame_id")\n        or solver_action_decision.get("source_frame_id")\n        or ""\n    )\n\n    return {\n        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,\n        "source": "Decision_JSON",\n        "source_decision_frame_id": source_frame_id,\n        "status": "ok",\n        "action": action,\n        "size_policy": size_policy,\n        "target_button_classes": list(target_buttons),\n        "reason": str(solver_action_decision.get("reason") or "solver_preflop_bridge_v21_runtime_source"),\n        "dry_run_safe": True,\n        "solver_stub": False,\n        "decision_context": {\n            "street": str(solver_action_decision.get("street") or "preflop"),\n            "hero_position": str(solver_action_decision.get("hero_position") or ""),\n            "source_frame_id": source_frame_id,\n            "solver_preflop_runtime_source": True,\n            "solver_decision_id": solver_action_decision.get("decision_id"),\n            "solver_fingerprint": solver_action_decision.get("solver_fingerprint"),\n            "solver_raw_action": solver_action_decision.get("raw_action"),\n            "solver_engine_action": solver_action_decision.get("engine_action") or solver_action_decision.get("action"),\n        },\n    }\n'

OLD_RETURN = """    selection["solver_fingerprint"] = solver_action_decision.get("solver_fingerprint")
    return dict(solver_action_decision), selection
"""

NEW_RETURN = """    selection["solver_fingerprint"] = solver_action_decision.get("solver_fingerprint")
    selection["adapted_to_legacy_action_decision"] = True
    return _adapt_v21_solver_preflop_action_decision_to_v06(solver_action_decision), selection
"""


def main() -> int:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    changed = False

    if FALSE_LINE in text:
        text = text.replace(FALSE_LINE, TRUE_LINE, 1)
        changed = True
    elif TRUE_LINE not in text:
        raise RuntimeError("V20 runtime source switch line not found.")

    if "def _adapt_v21_solver_preflop_action_decision_to_v06(" not in text:
        if SELECTOR_ANCHOR not in text:
            raise RuntimeError("V2.1 adapter insertion anchor not found.")
        text = text.replace(SELECTOR_ANCHOR, ADAPTER_BLOCK + SELECTOR_ANCHOR, 1)
        changed = True

    if OLD_RETURN in text:
        text = text.replace(OLD_RETURN, NEW_RETURN, 1)
        changed = True
    elif NEW_RETURN not in text:
        raise RuntimeError("V2.1 selector return anchor not found.")

    if changed:
        DISPLAY_FILE.write_text(text, encoding="utf-8")

    print({
        "status": "patched" if changed else "already_patched",
        "file": str(DISPLAY_FILE),
        "v20_solver_source_enabled": TRUE_LINE in text,
        "v20_dry_run_only": "V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True" in text,
        "v21_adapter_present": "def _adapt_v21_solver_preflop_action_decision_to_v06(" in text,
        "v21_selector_uses_adapter": "_adapt_v21_solver_preflop_action_decision_to_v06(solver_action_decision)" in text,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
