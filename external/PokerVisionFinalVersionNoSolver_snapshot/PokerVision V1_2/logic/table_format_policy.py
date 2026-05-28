r"""
logic/table_format_policy.py

PokerVision Core V0.4 — table format and player-seat processing policy.

This module contains deterministic logic only. It does not run YOLO and does not
write JSON files.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


PLAYER_SEAT_CLASS_ORDER: List[str] = [
    "Player_seat1",
    "Player_seat2",
    "Player_seat3",
    "Player_seat4",
    "Player_seat5",
    "Player_seat6",
]

TABLE_STRUCTURE_CLASS_ORDER: List[str] = [
    *PLAYER_SEAT_CLASS_ORDER,
    "Board",
    "Total_pot",
]


class TableFormatResult(TypedDict):
    table_format: Optional[str]
    seat_count: int
    status: str
    warning: Optional[str]


def is_known_table_structure_class(class_name: str) -> bool:
    return class_name in TABLE_STRUCTURE_CLASS_ORDER


def is_player_seat_class(class_name: str) -> bool:
    return class_name in PLAYER_SEAT_CLASS_ORDER


def determine_table_format(detected_player_seats: List[str]) -> TableFormatResult:
    """
    Determine poker table format from detected Player_seatN classes.

    Rules:
    - 6 detected seats -> 6-max
    - 5 detected seats -> 5-max
    - 4 detected seats -> 4-max
    - 3 detected seats -> 3-max
    - 2 detected seats -> HU / 2-max
    - 0..1 seats -> incomplete_table_structure
    """
    seat_count = len(set(detected_player_seats))

    if seat_count >= 6:
        return {"table_format": "6-max", "seat_count": seat_count, "status": "ok", "warning": None}
    if seat_count == 5:
        return {"table_format": "5-max", "seat_count": seat_count, "status": "ok", "warning": None}
    if seat_count == 4:
        return {"table_format": "4-max", "seat_count": seat_count, "status": "ok", "warning": None}
    if seat_count == 3:
        return {"table_format": "3-max", "seat_count": seat_count, "status": "ok", "warning": None}
    if seat_count == 2:
        return {"table_format": "HU / 2-max", "seat_count": seat_count, "status": "ok", "warning": None}

    return {
        "table_format": None,
        "seat_count": seat_count,
        "status": "warning",
        "warning": f"Incomplete table structure: expected at least 2 Player_seat classes, got {seat_count}.",
    }


def build_player_seat_processing_queue(detected_player_seats: List[str]) -> List[str]:
    """
    Stable queue for downstream Player_State_Detector.

    The queue is deterministic: Player_seat1 -> ... -> Player_seat6, but only for
    seats that were actually detected above the clean threshold.
    """
    detected = set(detected_player_seats)
    return [class_name for class_name in PLAYER_SEAT_CLASS_ORDER if class_name in detected]
