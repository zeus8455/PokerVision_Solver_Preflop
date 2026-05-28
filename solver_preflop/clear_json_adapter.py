from __future__ import annotations

from typing import Any

from .cards import normalize_cards
from .contracts import NormalizedPlayer, NormalizedPreflopFrame, POSITIONS_6MAX


def _chips_to_committed_bb(value: Any) -> float:
    # PokerVision rule:
    # chips: false means 0bb committed, not missing detection.
    if value is False or value is None:
        return 0.0
    return float(value)


def parse_clear_json_preflop(data: dict[str, Any]) -> NormalizedPreflopFrame:
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
    players: dict[str, NormalizedPlayer] = {}
    hero_positions: list[str] = []
    warnings: list[str] = []

    for position in POSITIONS_6MAX:
        if position not in raw_players:
            continue

        raw = dict(raw_players[position] or {})
        folded = bool(raw.get("fold", False))
        all_in = bool(raw.get("all_in", False))
        hero = bool(raw.get("hero", False))
        committed = _chips_to_committed_bb(raw.get("chips", False))
        stack = float(raw.get("stack") or 0.0)
        cards = normalize_cards(list(raw.get("cards") or [])) if hero else []

        active_in_hand = not folded

        if all_in and raw.get("chips", False) is False:
            raise ValueError(f"{position}: all_in=true but chips=false")

        player = NormalizedPlayer(
            position=position,
            hero=hero,
            cards=cards,
            stack_bb=stack,
            committed_bb=committed,
            folded=folded,
            all_in=all_in,
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

    return NormalizedPreflopFrame(
        frame_id=str(data.get("frame_id") or ""),
        street="preflop",
        total_pot_bb=float(data.get("Total_pot") or 0.0),
        hero_position=hero_position,
        hero_cards=hero_cards,
        players=players,
        warnings=warnings,
    )
