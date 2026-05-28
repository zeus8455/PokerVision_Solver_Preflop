r"""
logic/action_button_policy.py

PokerVision Core V1.2 / V0.8 hotfix — deterministic policy for
Action_Button_Detector output.

Purpose:
- Normalize Action_Button_Detector classes.
- Convert solver/action decisions into ordered UI-button sequences.
- Keep this layer independent from YOLO execution and mouse clicking.

V0.8 hotfix:
- fold no longer means only FOLD.
- If FOLD is not visible but Check/fold is visible, dry-run/click planning may
  complete through Check/fold. This is required for poker clients where the UI
  offers Check/fold instead of a separate FOLD button.
"""

from __future__ import annotations

from typing import Dict, List, Optional


ACTION_BUTTON_CLASS_ORDER: List[str] = [
    "FOLD",
    "33%",
    "50%",
    "70%",
    "98%",
    "Call",
    "Check/fold",
    "Check",
    "Bet/Raise",
]

ACTION_BUTTON_CLASS_ALIASES: Dict[str, str] = {
    "fold": "FOLD",
    "Fold": "FOLD",
    "FOLD": "FOLD",
    "33": "33%",
    "33_pct": "33%",
    "33pct": "33%",
    "33_percent": "33%",
    "50": "50%",
    "50_pct": "50%",
    "50pct": "50%",
    "50_percent": "50%",
    "70": "70%",
    "70_pct": "70%",
    "70pct": "70%",
    "70_percent": "70%",
    "98": "98%",
    "98_pct": "98%",
    "98pct": "98%",
    "98_percent": "98%",
    "CALL": "Call",
    "call": "Call",
    "Call": "Call",
    "check/fold": "Check/fold",
    "Check/Fold": "Check/fold",
    "CHECK/FOLD": "Check/fold",
    "check_fold": "Check/fold",
    "Check_fold": "Check/fold",
    "CHECK_FOLD": "Check/fold",
    "CHECK": "Check",
    "check": "Check",
    "Check": "Check",
    "bet/raise": "Bet/Raise",
    "Bet/raise": "Bet/Raise",
    "BET/RAISE": "Bet/Raise",
    "bet_raise": "Bet/Raise",
    "Bet_Raise": "Bet/Raise",
    "raise": "Bet/Raise",
    "Raise": "Bet/Raise",
    "BET": "Bet/Raise",
    "Bet": "Bet/Raise",
}

VALID_SOLVER_ACTIONS = {"fold", "call", "check", "check_fold", "bet_raise"}
VALID_SIZE_PCTS = {33, 50, 70, 98}


def canonical_action_button_class(class_name: str) -> str:
    normalized = str(class_name).strip()
    return ACTION_BUTTON_CLASS_ALIASES.get(normalized, normalized)


def is_known_action_button_class(class_name: str) -> bool:
    return class_name in ACTION_BUTTON_CLASS_ORDER


def normalize_solver_action(action: object) -> str:
    normalized = str(action or "").strip().lower().replace("-", "_").replace("/", "_")
    aliases = {
        "fold": "fold",
        "call": "call",
        "check": "check",
        "checkfold": "check_fold",
        "check_fold": "check_fold",
        "check_f": "check_fold",
        "bet": "bet_raise",
        "raise": "bet_raise",
        "bet_raise": "bet_raise",
        "betraise": "bet_raise",
    }
    result = aliases.get(normalized, normalized)
    if result not in VALID_SOLVER_ACTIONS:
        raise ValueError(f"Unknown solver action={action!r}. Allowed: {sorted(VALID_SOLVER_ACTIONS)}")
    return result


def normalize_size_pct(size_pct: object) -> Optional[int]:
    if size_pct is None or size_pct == "":
        return None
    if isinstance(size_pct, str):
        size_pct = size_pct.strip().replace("%", "")
    value = int(size_pct)
    if value not in VALID_SIZE_PCTS:
        raise ValueError(f"Unsupported size_pct={size_pct!r}. Allowed: {sorted(VALID_SIZE_PCTS)}")
    return value


def build_required_button_sequence(action: object, size_pct: object = None) -> List[str]:
    """Return the exact/primary ordered button sequence for an action."""
    normalized_action = normalize_solver_action(action)
    normalized_size = normalize_size_pct(size_pct)

    if normalized_action == "fold":
        return ["FOLD"]
    if normalized_action == "call":
        return ["Call"]
    if normalized_action == "check":
        return ["Check"]
    if normalized_action == "check_fold":
        return ["Check/fold"]
    if normalized_action == "bet_raise":
        if normalized_size is None:
            return ["Bet/Raise"]
        return [f"{normalized_size}%", "Bet/Raise"]

    raise AssertionError(f"Unhandled solver action: {normalized_action}")


def build_fallback_button_sequences(action: object, size_pct: object = None) -> List[List[str]]:
    """Ordered click-plan alternatives from safest/most exact to fallback."""
    normalized_action = normalize_solver_action(action)
    normalized_size = normalize_size_pct(size_pct)

    # V0.8 hotfix: some clients expose Check/fold while a separate FOLD button is
    # missing. For a solver fold decision, Check/fold is an acceptable no-click or
    # click target fallback when FOLD is unavailable.
    if normalized_action == "fold":
        return [["FOLD"], ["Check/fold"]]
    if normalized_action == "check":
        return [["Check"], ["Check/fold"], ["FOLD"]]
    if normalized_action == "check_fold":
        return [["Check/fold"], ["Check"], ["FOLD"]]
    if normalized_action == "bet_raise" and normalized_size is not None:
        return [[f"{normalized_size}%", "Bet/Raise"]]

    return [build_required_button_sequence(normalized_action, normalized_size)]
