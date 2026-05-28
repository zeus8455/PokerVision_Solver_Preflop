r"""
logic/live_hand_continuity.py

PokerVision V0.8 — Live hand continuity reconciler.

Purpose:
- Keep the same hand_id across temporary inactive/service gaps in live mode.
- Continuation proof is strict and poker-state based:
  same table + same HERO cards + same/forward board progression + non-backward street.
- This module does not create JSON and does not run detectors/clicks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


VALID_STREET_ORDER = {
    "preflop": 0,
    "flop": 1,
    "turn": 2,
    "river": 3,
}


@dataclass(frozen=True)
class HandContinuityDecision:
    should_continue: bool
    reason: str
    same_hero_cards: bool
    board_continuation: bool
    street_forward: bool
    previous_street: Optional[str]
    current_street: Optional[str]
    previous_board_len: int
    current_board_len: int

    def to_json(self) -> dict[str, object]:
        return {
            "should_continue": self.should_continue,
            "reason": self.reason,
            "same_hero_cards": self.same_hero_cards,
            "board_continuation": self.board_continuation,
            "street_forward": self.street_forward,
            "previous_street": self.previous_street,
            "current_street": self.current_street,
            "previous_board_len": self.previous_board_len,
            "current_board_len": self.current_board_len,
        }


def normalize_card_list(cards: Optional[Iterable[object]]) -> List[str]:
    if cards is None:
        return []
    out: List[str] = []
    for card in cards:
        text = str(card).strip()
        if text:
            out.append(text)
    return out


def normalize_hero_cards_key(cards: Optional[Iterable[object]]) -> Optional[Tuple[str, str]]:
    clean = normalize_card_list(cards)
    if len(clean) != 2 or len(set(clean)) != 2:
        return None
    return tuple(sorted(clean))


def normalize_street(street: Optional[object]) -> Optional[str]:
    if street is None:
        return None
    text = str(street).strip().lower()
    return text if text in VALID_STREET_ORDER else None


def board_is_same_or_forward_extension(previous_board: Sequence[str], current_board: Sequence[str]) -> bool:
    """
    Accept same board or strict forward extension.

    Examples:
    [] -> [flop cards]                  OK
    [a,b,c] -> [a,b,c]                 OK
    [a,b,c] -> [a,b,c,d]               OK
    [a,b,c,d] -> [a,b,c,d,e]           OK
    [a,b,c,d] -> [a,b,c]               FAIL
    [a,b,c] -> [x,b,c,d]               FAIL
    """
    prev = list(previous_board)
    curr = list(current_board)
    if not prev:
        return True
    if len(curr) < len(prev):
        return False
    return curr[: len(prev)] == prev


def street_is_same_or_forward(previous_street: Optional[str], current_street: Optional[str]) -> bool:
    prev = normalize_street(previous_street)
    curr = normalize_street(current_street)
    if prev is None or curr is None:
        return True
    return VALID_STREET_ORDER[curr] >= VALID_STREET_ORDER[prev]


def decide_live_hand_continuity(
    *,
    previous_hero_cards_key: Optional[Tuple[str, str]],
    current_hero_cards_key: Optional[Tuple[str, str]],
    previous_board_cards: Optional[Iterable[object]],
    current_board_cards: Optional[Iterable[object]],
    previous_street: Optional[object],
    current_street: Optional[object],
) -> HandContinuityDecision:
    prev_board = normalize_card_list(previous_board_cards)
    curr_board = normalize_card_list(current_board_cards)
    prev_street = normalize_street(previous_street)
    curr_street = normalize_street(current_street)

    same_hero = (
        previous_hero_cards_key is not None
        and current_hero_cards_key is not None
        and previous_hero_cards_key == current_hero_cards_key
    )
    board_ok = board_is_same_or_forward_extension(prev_board, curr_board)
    street_ok = street_is_same_or_forward(prev_street, curr_street)

    if not same_hero:
        reason = "hero_cards_changed_or_missing"
    elif not board_ok:
        reason = "board_not_forward_continuation"
    elif not street_ok:
        reason = "street_went_backwards"
    else:
        reason = "same_hero_and_board_forward_continuation"

    return HandContinuityDecision(
        should_continue=bool(same_hero and board_ok and street_ok),
        reason=reason,
        same_hero_cards=bool(same_hero),
        board_continuation=bool(board_ok),
        street_forward=bool(street_ok),
        previous_street=prev_street,
        current_street=curr_street,
        previous_board_len=len(prev_board),
        current_board_len=len(curr_board),
    )
