from __future__ import annotations

from typing import Any

from .cards import normalize_cards
from .contracts import NormalizedPlayer, NormalizedPreflopFrame, POSITIONS_6MAX


def _chips_to_committed_bb(value: Any, *, position: str) -> float:
    # PokerVision rule:
    # chips:false means 0bb committed, not missing detection.
    if value is False or value is None:
        return 0.0
    if isinstance(value, bool):
        raise ValueError(f"{position}: chips must be false or numeric, got {value!r}")
    try:
        committed = float(value)
    except Exception as exc:
        raise ValueError(f"{position}: chips must be numeric or false, got {value!r}") from exc
    if committed < 0:
        raise ValueError(f"{position}: chips cannot be negative")
    return committed


def _stack_to_bb(value: Any, *, position: str) -> float:
    if value is False or value is None:
        return 0.0
    try:
        stack = float(value)
    except Exception as exc:
        raise ValueError(f"{position}: stack must be numeric, got {value!r}") from exc
    if stack < 0:
        raise ValueError(f"{position}: stack cannot be negative")
    return stack


def parse_clear_json_preflop(data: dict[str, Any]) -> NormalizedPreflopFrame:
    if not isinstance(data, dict):
        raise TypeError("Clear_JSON input must be a dict")

    board = data.get("board") or {}
    street = str(board.get("street") or "").lower()
    if street != "preflop":
        raise ValueError(f"Expected preflop Clear_JSON, got street={street!r}")

    if data.get("click_result"):
        raise ValueError("Input Clear_JSON already has click_result; expected pre-click Clear_JSON")

    board_cards = board.get("cards") or []
    if board_cards:
        raise ValueError("Preflop Clear_JSON must not contain board cards")

    raw_players = data.get("players") or {}
    if not isinstance(raw_players, dict) or not raw_players:
        raise ValueError("Clear_JSON must contain non-empty players dict")

    unknown_positions = [pos for pos in raw_players if pos not in POSITIONS_6MAX]
    if unknown_positions:
        raise ValueError(f"Unknown player positions in Clear_JSON: {unknown_positions}")

    players: dict[str, NormalizedPlayer] = {}
    hero_positions: list[str] = []
    warnings: list[str] = []

    for position in POSITIONS_6MAX:
        if position not in raw_players:
            continue

        raw = dict(raw_players[position] or {})
        folded = bool(raw.get("fold", False))
        sitout = bool(raw.get("sitout", False))
        all_in = bool(raw.get("all_in", False))
        all_in_unknown_amount = bool(raw.get("all_in_unknown_amount", False))
        hero = bool(raw.get("hero", False))
        committed = _chips_to_committed_bb(raw.get("chips", False), position=position)
        stack = _stack_to_bb(raw.get("stack", 0.0), position=position)
        cards = normalize_cards(list(raw.get("cards") or [])) if hero else []

        # sitout dominates fold/participation if this field appears later in PokerVision.
        active_in_hand = (not folded) and (not sitout)

        if all_in and raw.get("chips", False) is False:
            raise ValueError(f"{position}: all_in=true requires numeric chips")
        if all_in and committed <= 0:
            raise ValueError(f"{position}: all_in=true requires chips > 0")
        if hero and folded:
            raise ValueError("Hero is marked folded; this is not a valid active solver input")
        if hero and sitout:
            raise ValueError("Hero is marked sitout; this is not a valid active solver input")

        player = NormalizedPlayer(
            position=position,
            hero=hero,
            cards=cards,
            stack_bb=stack,
            committed_bb=committed,
            folded=folded,
            sitout=sitout,
            all_in=all_in,
            all_in_unknown_amount=all_in_unknown_amount,
            active_in_hand=active_in_hand,
            raw=raw,
        )
        players[position] = player

        if hero:
            hero_positions.append(position)

    if len(hero_positions) != 1:
        raise ValueError(f"Expected exactly one hero, got {hero_positions}")

    hero_position = hero_positions[0]
    hero_cards = players[hero_position].cards
    if len(hero_cards) != 2:
        raise ValueError("Hero must have exactly two cards")

    all_cards = list(hero_cards)
    if len(all_cards) != len(set(all_cards)):
        raise ValueError("Duplicate cards detected in Clear_JSON")

    return NormalizedPreflopFrame(
        frame_id=str(data.get("frame_id") or ""),
        street="preflop",
        total_pot_bb=float(data.get("Total_pot") or 0.0),
        hero_position=hero_position,
        hero_cards=hero_cards,
        players=players,
        warnings=warnings,
    )
