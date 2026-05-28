"""
logic/clear_json_recovery.py

PokerVision V1.2 — conservative Clear_JSON recovery layer.

Purpose:
- Recover only stable poker-state fields after Dark_JSON -> Clear_JSON build.
- Never recover dynamic betting/chips values from previous Clear_JSON.
- Recover HERO cards only when the current frame is proven to be the same hand
  by board/street continuation or non-conflicting partial HERO cards.

Pipeline position:
    Dark_JSON -> build_clear_json_from_dark_state -> recover_clear_json_state
    -> ClearJsonStateMachine -> save Clear_JSON
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


_VALID_STREETS = {"preflop", "flop", "turn", "river"}
_STREET_ORDER = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
_BOARD_COUNTS = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}


def _as_number_or_none(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        return round(float(text), 2)
    except Exception:
        return None


def _board(clear_state: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str]]:
    if not isinstance(clear_state, dict):
        return None, []
    board = clear_state.get("board")
    if not isinstance(board, dict):
        return None, []
    street = board.get("street")
    street_text = str(street).strip().lower() if street is not None else None
    if street_text not in _VALID_STREETS:
        street_text = None
    cards = board.get("cards")
    clean_cards = [str(card) for card in cards if str(card).strip()] if isinstance(cards, list) else []
    return street_text, clean_cards


def _players(clear_state: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(clear_state, dict):
        return {}
    players = clear_state.get("players")
    if not isinstance(players, dict):
        return {}
    return {str(pos): dict(player) for pos, player in players.items() if isinstance(player, dict)}


def _hero(players: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], Optional[Dict[str, Any]], List[str]]:
    for position, player in players.items():
        if bool(player.get("hero")):
            cards = player.get("cards")
            clean_cards = [str(card) for card in cards if str(card).strip()] if isinstance(cards, list) else []
            return position, player, clean_cards
    return None, None, []


def _cards_valid_two(cards: List[str]) -> bool:
    return len(cards) == 2 and len(set(cards)) == 2


def _board_counts_valid(street: Optional[str], cards: List[str]) -> bool:
    if street not in _BOARD_COUNTS:
        return False
    return len(cards) == _BOARD_COUNTS[street]


def _board_continuation_proves_same_hand(
    *,
    previous_street: Optional[str],
    previous_board: List[str],
    current_street: Optional[str],
    current_board: List[str],
) -> bool:
    """
    Board proof rules:
    - Same postflop street: board cards must be equal as a set.
    - New later street: previous board must be a subset of current board.
    - Preflop has no board, so board alone cannot prove continuation.
    """
    if previous_street not in _STREET_ORDER or current_street not in _STREET_ORDER:
        return False

    if not _board_counts_valid(previous_street, previous_board):
        return False
    if not _board_counts_valid(current_street, current_board):
        return False

    prev_order = _STREET_ORDER[previous_street]
    curr_order = _STREET_ORDER[current_street]

    if previous_street == "preflop" and current_street == "preflop":
        return False

    previous_set = set(previous_board)
    current_set = set(current_board)

    if curr_order == prev_order:
        return previous_street != "preflop" and previous_set == current_set

    if curr_order > prev_order:
        return previous_street != "preflop" and previous_set.issubset(current_set)

    return False


def _partial_hero_cards_prove_same_hand(current_cards: List[str], previous_cards: List[str]) -> bool:
    """
    Partial HERO-card proof:
    - One current HERO card matching one previous HERO card can confirm same hand
      when board proof is unavailable, especially preflop -> preflop.
    - Two current HERO cards equal to previous HERO cards are already valid.
    - Two different current HERO cards explicitly reject recovery.
    """
    if not previous_cards:
        return False
    clean_current = [str(card) for card in current_cards if str(card).strip()]
    if not clean_current:
        return False
    return set(clean_current).issubset(set(previous_cards))


def _can_recover_hero_cards(
    *,
    previous_clear: Dict[str, Any],
    current_clear: Dict[str, Any],
    current_hero_cards: List[str],
    previous_hero_cards: List[str],
) -> Tuple[bool, str]:
    if not _cards_valid_two(previous_hero_cards):
        return False, "previous_hero_cards_invalid"

    if _cards_valid_two(current_hero_cards):
        if set(current_hero_cards) == set(previous_hero_cards):
            return False, "current_hero_cards_already_valid"
        return False, "current_hero_cards_conflict_with_previous"

    previous_street, previous_board = _board(previous_clear)
    current_street, current_board = _board(current_clear)

    if _board_continuation_proves_same_hand(
        previous_street=previous_street,
        previous_board=previous_board,
        current_street=current_street,
        current_board=current_board,
    ):
        return True, "board_continuation_confirmed_same_hand"

    if _partial_hero_cards_prove_same_hand(current_hero_cards, previous_hero_cards):
        return True, "partial_hero_card_match_confirmed_same_hand"

    return False, "same_hand_not_proven"


def _copy_player_without_recovering_chips(previous_player: Dict[str, Any]) -> Dict[str, Any]:
    player = deepcopy(previous_player)
    # Chips are dynamic betting/action values. Never copy old chips into a
    # recovered player that is missing from the current frame.
    player["chips"] = False
    return player


def recover_clear_json_state(
    current_clear: Dict[str, Any],
    previous_clear: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Recover stable parts of a Clear_JSON candidate using previous stable Clear_JSON.

    Recovery policy:
    - Restore missing players from previous state, but force chips=False.
    - Restore missing stack from previous state.
    - Preserve fold=True once a player was folded.
    - Restore HERO cards only when same-hand continuation is proven.
    - Never recover chips from previous state.
    """
    recovered = deepcopy(current_clear)
    report: Dict[str, Any] = {
        "recovery_version": "clear_json_recovery_v1_2026_05_15",
        "applied": False,
        "rules": [],
        "warnings": [],
        "chips_recovery": "disabled",
        "hero_recovery": "not_needed_or_not_allowed",
    }

    if not isinstance(previous_clear, dict):
        report["reason"] = "no_previous_stable_clear_json"
        return recovered, report

    current_players = _players(recovered)
    previous_players = _players(previous_clear)
    if not previous_players:
        report["reason"] = "previous_clear_json_has_no_players"
        recovered["players"] = current_players
        return recovered, report

    previous_hero_pos, previous_hero_player, previous_hero_cards = _hero(previous_players)
    current_hero_pos, current_hero_player, current_hero_cards = _hero(current_players)

    can_recover_hero, hero_reason = _can_recover_hero_cards(
        previous_clear=previous_clear,
        current_clear=recovered,
        current_hero_cards=current_hero_cards,
        previous_hero_cards=previous_hero_cards,
    )

    if hero_reason == "current_hero_cards_conflict_with_previous":
        report["warnings"].append("HERO cards conflict with previous stable state; HERO was not recovered.")
    report["hero_recovery"] = hero_reason

    # 1. Restore missing players, but never restore old chips.
    for position, previous_player in previous_players.items():
        if position not in current_players:
            restored_player = _copy_player_without_recovering_chips(previous_player)
            if bool(previous_player.get("hero")) and not can_recover_hero:
                restored_player.pop("hero", None)
                restored_player.pop("cards", None)
            current_players[position] = restored_player
            report["applied"] = True
            report["rules"].append(f"restored_missing_player:{position}")

    # 2. Stable per-player recovery. Chips are intentionally not touched.
    for position, current_player in list(current_players.items()):
        previous_player = previous_players.get(position)
        if not isinstance(previous_player, dict) or not isinstance(current_player, dict):
            continue

        if _as_number_or_none(current_player.get("stack")) is None:
            previous_stack = _as_number_or_none(previous_player.get("stack"))
            if previous_stack is not None:
                current_player["stack"] = previous_stack
                report["applied"] = True
                report["rules"].append(f"restored_stack:{position}")

        if bool(previous_player.get("fold")) and not bool(current_player.get("fold")):
            current_player["fold"] = True
            report["applied"] = True
            report["rules"].append(f"preserved_fold_true:{position}")

        # Enforce no chips recovery. Missing/invalid current chips becomes false;
        # valid numeric chips from the current frame remain as-is.
        if "chips" not in current_player or current_player.get("chips") is None:
            current_player["chips"] = False
            report["applied"] = True
            report["rules"].append(f"normalized_missing_chips_to_false:{position}")

    # 3. HERO card recovery only with proof.
    current_hero_pos, current_hero_player, current_hero_cards = _hero(current_players)
    if previous_hero_pos and previous_hero_pos in current_players:
        target = current_players[previous_hero_pos]
        target_cards = target.get("cards")
        target_cards_clean = [str(card) for card in target_cards if str(card).strip()] if isinstance(target_cards, list) else []
        target_hero_valid = bool(target.get("hero")) and _cards_valid_two(target_cards_clean)

        if not target_hero_valid:
            if can_recover_hero:
                target["hero"] = True
                target["cards"] = list(previous_hero_cards)
                report["applied"] = True
                report["rules"].append(f"recovered_hero_cards:{previous_hero_pos}")
            else:
                # Do not silently pretend this is valid HERO when continuation is not proven.
                target.pop("hero", None)
                target.pop("cards", None)
                report["warnings"].append(
                    "HERO cards were missing/invalid and same-hand continuation was not proven."
                )

    recovered["players"] = current_players
    report["rules"] = sorted(set(report["rules"]))
    return recovered, report


__all__ = ["recover_clear_json_state"]
