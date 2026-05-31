r"""
runtime/solver_payload_builder.py

PokerVision Core V1.1 — build compact solver payload JSON from full table-state JSON.

This is the second JSON that remains after the cleanup:
current_cycle/solver_payloads/table_N/frame_name.json

The payload intentionally follows the compact solver/engine template and contains
only frame identity, board state and players by poker position.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    CARD_HERO_SEAT_NAME,
    UI_DISPLAY_CYCLE_OUTPUT_DIR,
    CURRENT_CYCLE_DIR_NAME,
    V11_SOLVER_PAYLOAD_OUTPUT_DIR_NAME,
    ensure_dir,
)

POSITION_EXPORT_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "BB", "BTN/SB"]


def _seat_sort_key(seat_name: str) -> int:
    if seat_name.startswith("Player_seat"):
        try:
            return int(seat_name.replace("Player_seat", ""))
        except ValueError:
            return 999
    return 999


def _chips_payload(chips_block: Dict[str, Any]) -> Any:
    if not chips_block or not chips_block.get("detect"):
        return False
    value = chips_block.get("value")
    return value if value is not None else True


def _stack_payload(stack_block: Dict[str, Any]) -> Any:
    if not stack_block or not stack_block.get("detect"):
        return None
    return stack_block.get("value")


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "РґР°"}:
        return True
    if text in {"0", "false", "no", "n", "РЅРµС‚"}:
        return False
    return default


def _is_numeric_chips(value: Any) -> bool:
    return value is not False and value is not None and not isinstance(value, bool)


def _ordered_players_by_position(players_by_position: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ordered: Dict[str, Dict[str, Any]] = {}
    seen = set()

    for position in POSITION_EXPORT_ORDER:
        if position in players_by_position:
            ordered[position] = players_by_position[position]
            seen.add(position)

    for position in sorted(players_by_position.keys()):
        if position not in seen:
            ordered[position] = players_by_position[position]

    return ordered


def _active_event_from_state(full_state: Dict[str, Any]) -> tuple[str, str]:
    """
    Solver payload is allowed only for a fresh strong Active action event.

    This blocks empty/passive table JSON files from entering solver_payloads.
    The display cycle writes runtime_event only after ActionEventGate accepts a
    new Active spot, so absence of these fields means: do not send to engine.
    """
    table = full_state.get("table") or {}
    runtime_event = full_state.get("runtime_event") or {}
    if not isinstance(runtime_event, dict):
        runtime_event = {}

    should_process = bool(runtime_event.get("should_process"))
    action_event_id = table.get("action_event_id") or runtime_event.get("action_event_id")
    action_signature = runtime_event.get("action_signature")

    if not should_process or not action_event_id or not action_signature:
        raise ValueError(
            "Solver payload was not created: source frame is not a new strong Active action_event."
        )

    return str(action_event_id), str(action_signature)


def _validate_solver_payload_for_engine(payload: Dict[str, Any]) -> None:
    if not payload.get("action_event_id") or not payload.get("action_signature"):
        raise ValueError("Solver payload rejected: missing action_event_id/action_signature.")

    players = payload.get("players")
    if not isinstance(players, dict) or not players:
        raise ValueError("Solver payload rejected: players block is empty.")

    hero_entries = [player for player in players.values() if isinstance(player, dict) and player.get("hero") is True]
    if len(hero_entries) != 1:
        raise ValueError("Solver payload rejected: expected exactly one HERO player in players block.")

    hero_cards = hero_entries[0].get("cards")
    if not isinstance(hero_cards, list) or len([card for card in hero_cards if str(card).strip()]) != 2:
        raise ValueError("Solver payload rejected: HERO cards must contain exactly two cards.")


def build_solver_payload(full_state: Dict[str, Any]) -> Dict[str, Any]:
    """Build compact solver payload from the full runtime table-state JSON."""
    table = full_state.get("table") or {}
    table_structure = full_state.get("table_structure") or {}
    structure_classes = table_structure.get("classes") or {}
    board_block = structure_classes.get("Board") or {}
    total_pot_block = structure_classes.get("Total_pot") or {}
    players_block = full_state.get("players") or {}
    seats = players_block.get("seats") or {}
    action_event_id, action_signature = _active_event_from_state(full_state)

    players_by_position: Dict[str, Dict[str, Any]] = {}

    for seat_name in sorted(seats.keys(), key=_seat_sort_key):
        seat = seats.get(seat_name) or {}
        position = seat.get("position")
        if not position:
            continue

        player_payload: Dict[str, Any] = {
            "stack": _stack_payload(seat.get("stack") or {}),
            "fold": bool(seat.get("fold", False)),
            "chips": _chips_payload(seat.get("chips") or {}),
        }

        # V2.47: carry reliable all-in semantic state into solver payload.
        # Numeric committed chips + all_in=true can have no remaining stack;
        # normalize stack to 0.0 for downstream solver compatibility.
        seat_all_in = _as_bool(seat.get("all_in"), default=False) or _as_bool(seat.get("allin"), default=False)
        if seat_all_in and _is_numeric_chips(player_payload.get("chips")):
            player_payload["all_in"] = True
            if player_payload.get("stack") is None:
                player_payload["stack"] = 0.0

        if seat_name == CARD_HERO_SEAT_NAME:
            player_payload = {
                "hero": True,
                "cards": list(seat.get("hero_cards") or []),
                **player_payload,
            }

        players_by_position[str(position)] = player_payload

    return {
        "frame_id": table.get("frame_id"),
        "frame_name": table.get("frame_name"),
        "table_id": table.get("table_id"),
        "hand_id": table.get("hand_id"),
        "action_event_id": action_event_id,
        "action_signature": action_signature,
        "board": {
            "cards": list(board_block.get("cards") or []),
            "street": board_block.get("street") or "preflop",
        },
        "Total_pot": total_pot_block.get("value"),
        "players": _ordered_players_by_position(players_by_position),
    }


def get_solver_payload_path(*, cycle_dir: Optional[Path], table_id: str, frame_name: str) -> Path:
    base_dir = Path(cycle_dir) if cycle_dir is not None else UI_DISPLAY_CYCLE_OUTPUT_DIR / CURRENT_CYCLE_DIR_NAME
    return base_dir / V11_SOLVER_PAYLOAD_OUTPUT_DIR_NAME / table_id / f"{frame_name}.json"


def save_solver_payload_json(
    *,
    payload: Dict[str, Any],
    cycle_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    table_id = str(payload.get("table_id") or "unknown_table")
    frame_name = str(payload.get("frame_name") or "unknown_frame")
    path = Path(output_path) if output_path is not None else get_solver_payload_path(
        cycle_dir=cycle_dir,
        table_id=table_id,
        frame_name=frame_name,
    )
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def build_and_save_solver_payload(full_state: Dict[str, Any], *, cycle_dir: Optional[Path] = None) -> tuple[Dict[str, Any], Path]:
    payload = build_solver_payload(full_state)
    _validate_solver_payload_for_engine(payload)
    path = save_solver_payload_json(payload=payload, cycle_dir=cycle_dir)
    return payload, path
