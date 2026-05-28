from __future__ import annotations


CLICK_SEQUENCE_BY_ACTION = {
    "open_raise": ["Raise"],
    "raise": ["Raise"],
    "iso_raise": ["98%", "Raise"],
    "3bet": ["98%", "Raise"],
    "4bet": ["50%", "Raise"],
    "5bet": ["50%", "Raise"],
    "5bet_jam": ["98%", "Raise"],
    "jam": ["98%", "Raise"],
    "all_in": ["98%", "Raise"],
    "check": ["Check"],
    "call": ["CALL"],
    "limp": ["CALL"],
    "fold": ["FOLD"],
}

SAFE_FALLBACK_SEQUENCE = ["Check", "Check/fold", "FOLD"]


def click_sequence_for_action(action: str) -> list[str]:
    return list(CLICK_SEQUENCE_BY_ACTION.get(action, SAFE_FALLBACK_SEQUENCE))


def size_pct_for_action(action: str) -> float | None:
    if action in {"iso_raise", "3bet", "jam", "all_in", "5bet_jam"}:
        return 98.0
    if action in {"4bet", "5bet"}:
        return 50.0
    return None
