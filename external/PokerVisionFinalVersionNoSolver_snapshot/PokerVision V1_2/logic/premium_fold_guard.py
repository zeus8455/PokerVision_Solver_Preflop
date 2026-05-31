from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


PREMIUM_HAND_CLASSES: Set[str] = {"AA", "KK", "QQ"}

SUSPICIOUS_NODE_TYPES: Set[str] = {
    "hero_is_current_aggressor_no_decision",
    "unknown_no_raise_preflop_spot",
    "facing_allin_unknown_amount",
    "facing_allin_or_allin_present",
    "solver_input_error",
}

SUSPICIOUS_REASON_TOKENS: tuple[str, ...] = (
    "safe_fallback",
    "fallback",
    "unsupported",
    "unsafe",
    "unknown",
    "ambiguous",
    "no_decision",
    "no decision",
    "all-in",
    "allin",
    "all_in",
    "input error",
)


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_action(value: Any) -> str:
    return _norm(value).lower().replace("-", "_").replace("/", "_")


def _cards_to_hand_class(cards: Any) -> str:
    if not isinstance(cards, (list, tuple)) or len(cards) != 2:
        return ""

    ranks: List[str] = []
    for card in cards:
        text = _norm(card)
        if not text:
            return ""
        head = text.split("_", 1)[0].strip().upper()
        if head in {"ACE", "ACES"}:
            rank = "A"
        elif head in {"KING", "KINGS"}:
            rank = "K"
        elif head in {"QUEEN", "QUEENS"}:
            rank = "Q"
        else:
            rank = head[:1]
        ranks.append(rank)

    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return ranks[0] + ranks[1]
    return "".join(ranks)


def _hand_class_from_decision(solver_decision: Dict[str, Any]) -> str:
    hand_class = _norm(solver_decision.get("hand_class")).upper()
    if hand_class:
        return hand_class
    return _cards_to_hand_class(solver_decision.get("hero_hand")).upper()


def _available_button_set(available_buttons: Iterable[Any]) -> Set[str]:
    return {_norm(item) for item in available_buttons if _norm(item)}


def _is_suspicious_fold_decision(solver_decision: Dict[str, Any]) -> bool:
    raw_action = _norm_action(solver_decision.get("solver_raw_action") or solver_decision.get("raw_action"))
    engine_action = _norm_action(solver_decision.get("solver_engine_action") or solver_decision.get("engine_action"))
    node_type = _norm(solver_decision.get("node_type"))
    reason = _norm(solver_decision.get("reason")).lower()
    status = _norm_action(solver_decision.get("status"))

    if bool(solver_decision.get("safe_fallback_used")):
        return True
    if raw_action == "safe_fallback":
        return True
    if engine_action == "safe_fallback":
        return True
    if status == "fallback":
        return True
    if node_type in SUSPICIOUS_NODE_TYPES:
        return True
    if any(token in reason for token in SUSPICIOUS_REASON_TOKENS):
        return True
    return False


def evaluate_premium_fold_guard(
    *,
    solver_decision: Dict[str, Any],
    available_buttons: Iterable[Any],
) -> Dict[str, Any]:
    action = _norm_action(solver_decision.get("action"))
    hand_class = _hand_class_from_decision(solver_decision)
    buttons = _available_button_set(available_buttons)
    premium = hand_class in PREMIUM_HAND_CLASSES
    suspicious = _is_suspicious_fold_decision(solver_decision)

    result: Dict[str, Any] = {
        "schema_version": "premium_fold_guard_v2_44",
        "active": False,
        "premium_hand": premium,
        "hand_class": hand_class,
        "action": action,
        "suspicious": suspicious,
        "available_buttons": sorted(buttons),
        "target_sequences": [],
        "selected_policy": None,
        "block_fold": False,
        "reason": None,
        "message": None,
    }

    if action != "fold" or not premium or not suspicious:
        result["reason"] = "guard_not_applicable"
        return result

    candidates: List[List[str]] = [["Bet/Raise"], ["Raise"], ["Call"], ["CALL"]]
    available_candidates = [seq for seq in candidates if all(token in buttons for token in seq)]

    result.update(
        {
            "active": True,
            "block_fold": True,
            "target_sequences": candidates,
            "available_target_sequences": available_candidates,
            "selected_policy": "raise_first_then_call_no_fold",
            "reason": "premium_fold_guard_active",
        }
    )

    if available_candidates:
        result["message"] = (
            "Premium fold guard active: suspicious fold with premium hand; "
            "override to Raise if available, otherwise Call."
        )
    else:
        result["message"] = (
            "Premium fold guard active: suspicious fold with premium hand; "
            "no Raise/Call button available, so physical FOLD is blocked."
        )

    return result
