r"""
logic/positions_builder.py

PokerVision Core V0.6 — deterministic position builder.

Input:
- detected/active Player_seatN list from table_structure/player_state;
- BTN seat from Player_State_Detector;
- folded/sitout seats.

Output:
- runtime position result used by players block assembly.

V0.6:
- positions are no longer written as a separate clean JSON block;
- seat_positions are merged into players.seats.Player_seatN.position.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from logic.table_format_policy import PLAYER_SEAT_CLASS_ORDER


POSITION_ORDER_BY_ACTIVE_COUNT: Dict[int, List[str]] = {
    2: ["BTN/SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "MP", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "MP", "CO"],
}


def _seat_sort_key(seat_name: str) -> int:
    try:
        return PLAYER_SEAT_CLASS_ORDER.index(seat_name)
    except ValueError:
        return 999


def _rotate_from_btn(position_seats: List[str], btn_seat: str) -> List[str]:
    ordered = sorted(set(position_seats), key=_seat_sort_key)
    if btn_seat not in ordered:
        return ordered

    btn_index = ordered.index(btn_seat)
    return ordered[btn_index:] + ordered[:btn_index]


def build_positions_block(
    *,
    detected_player_seats: List[str],
    btn_seat: Optional[str],
    folded_seats: List[str],
    sitout_seats: List[str],
) -> Dict[str, Any]:
    """
    Build runtime positions result for compact players block assembly.

    V0.5 poker-state rule:
    - Fold != SitOut.
    - Folded seats still participated in the hand and must remain eligible for
      position assignment.
    - Only SitOut seats are excluded from the position map.
    - 5-max uses BTN -> SB -> BB -> MP -> CO.
    - action_active_seats is a separate list for players still able to act.
    - BTN may be folded, but BTN cannot be SitOut for reliable position assignment.
    """
    folded_set = set(folded_seats)
    sitout_set = set(sitout_seats)

    # Seats used for position assignment. Fold is NOT removed here.
    # A folded player still has a hand-position in the current deal.
    position_eligible_seats = [
        seat for seat in detected_player_seats
        if seat not in sitout_set
    ]
    position_eligible_seats = sorted(set(position_eligible_seats), key=_seat_sort_key)

    # Seats still able to act in the current hand/street.
    # This is intentionally separate from position_eligible_seats.
    action_active_seats = [
        seat for seat in detected_player_seats
        if seat not in folded_set and seat not in sitout_set
    ]
    action_active_seats = sorted(set(action_active_seats), key=_seat_sort_key)

    warnings: List[str] = []
    errors: List[str] = []

    if not position_eligible_seats:
        return {
            "status": "warning",
            "input_scope": "player_state",
            "btn_seat": btn_seat,
            "position_eligible_seats": [],
            "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
            "seat_positions": {},
            "warnings": ["No position-eligible seats available for position assignment."],
            "errors": [],
        }

    if btn_seat is None:
        warnings.append("BTN was not detected; positions cannot be assigned reliably.")
        return {
            "status": "warning",
            "input_scope": "player_state",
            "btn_seat": None,
            "position_eligible_seats": position_eligible_seats,
            "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
            "seat_positions": {},
            "warnings": warnings,
            "errors": errors,
        }

    if btn_seat in sitout_set:
        warnings.append(
            f"BTN seat {btn_seat} is SitOut; positions cannot be assigned reliably."
        )
        return {
            "status": "warning",
            "input_scope": "player_state",
            "btn_seat": btn_seat,
            "position_eligible_seats": position_eligible_seats,
            "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
            "seat_positions": {},
            "warnings": warnings,
            "errors": errors,
        }

    if btn_seat not in position_eligible_seats:
        warnings.append(
            f"BTN seat {btn_seat} is not in position-eligible seats; positions cannot be assigned reliably."
        )
        return {
            "status": "warning",
            "input_scope": "player_state",
            "btn_seat": btn_seat,
            "position_eligible_seats": position_eligible_seats,
            "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
            "seat_positions": {},
            "warnings": warnings,
            "errors": errors,
        }

    position_count = len(position_eligible_seats)
    position_order = POSITION_ORDER_BY_ACTIVE_COUNT.get(position_count)

    if position_order is None:
        warnings.append(f"Unsupported position-eligible seat count for positions: {position_count}.")
        return {
            "status": "warning",
            "input_scope": "player_state",
            "btn_seat": btn_seat,
            "position_eligible_seats": position_eligible_seats,
            "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
            "seat_positions": {},
            "warnings": warnings,
            "errors": errors,
        }

    rotated = _rotate_from_btn(position_eligible_seats, btn_seat)
    seat_positions = {
        seat: position_order[index]
        for index, seat in enumerate(rotated)
    }

    return {
        "status": "ok" if not warnings else "warning",
        "input_scope": "player_state",
        "btn_seat": btn_seat,
        "position_eligible_seats": rotated,
        "sitout_seats": sorted(sitout_set, key=_seat_sort_key),
        "seat_positions": seat_positions,
        "warnings": warnings,
        "errors": errors,
    }


# =============================================================================
# V0.6 PREFLOP BLIND-ANCHOR PARTICIPATION CORRECTION
# =============================================================================

PREFLOP_SB_CHIPS_VALUES = (0.4, 0.5)
PREFLOP_SB_CHIPS_TOLERANCE = 0.051
PREFLOP_BB_CHIPS_VALUE = 1.0
PREFLOP_BB_CHIPS_TOLERANCE = 0.051


def _amount_matches(value: Any, expected: float, tolerance: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return abs(float(value) - expected) <= tolerance


def _is_sb_chips_value(value: Any) -> bool:
    return any(
        _amount_matches(value, expected, PREFLOP_SB_CHIPS_TOLERANCE)
        for expected in PREFLOP_SB_CHIPS_VALUES
    )


def _is_bb_chips_value(value: Any) -> bool:
    return _amount_matches(value, PREFLOP_BB_CHIPS_VALUE, PREFLOP_BB_CHIPS_TOLERANCE)


def _single_seat_or_none(seats: List[str]) -> Optional[str]:
    unique = sorted(set(seats), key=_seat_sort_key)
    return unique[0] if len(unique) == 1 else None


def _seats_strictly_between_clockwise(
    ordered_detected_seats: List[str],
    start_seat: str,
    end_seat: str,
) -> List[str]:
    """
    Return physical Player_seatN nodes strictly between start_seat and end_seat
    while walking clockwise in the canonical Player_seat1..6 order.
    """
    if start_seat == end_seat:
        return []

    ordered = sorted(set(ordered_detected_seats), key=_seat_sort_key)
    if start_seat not in ordered or end_seat not in ordered:
        return []

    rotated = _rotate_from_btn(ordered, start_seat)
    if end_seat not in rotated:
        return []

    end_index = rotated.index(end_seat)
    return rotated[1:end_index]


def apply_preflop_blind_anchor_participation_check(
    *,
    table_structure_block: Dict[str, Any],
    players_block: Dict[str, Any],
) -> Dict[str, Any]:
    """
    V0.6 preflop correction for players who appear visually at the table but did
    not participate in the current hand.

    Guard conditions:
    - run only while Board is absent, i.e. preflop;
    - require exactly one BTN;
    - require exactly one SB anchor by Chips value 0.4/0.5;
    - require exactly one BB anchor by Chips value 1.0.

    Correction:
    BTN -> SB and SB -> BB must be consecutive among players who actually
    participate in the hand. If a visually detected seat is located strictly
    between these anchors and already has Fold=True, it is treated as a logical
    SitOut for this hand:
    - sitout=True;
    - logical_sitout=True;
    - sitout_source="blind_gap_fold_correction";
    - raw_fold_before_logical_sitout=True;
    - position=None after recomputing positions.

    Raw model facts are not stored separately in clean JSON, therefore this
    function updates the compact canonical player state in-place while retaining
    explicit participation-source diagnostics for Dark_JSON audit.
    """
    board_block = table_structure_block.get("classes", {}).get("Board", {})
    if board_block.get("detect"):
        return players_block

    seats = players_block.get("seats", {})
    if not isinstance(seats, dict) or not seats:
        return players_block

    btn_candidates = [
        seat_name
        for seat_name, seat_state in seats.items()
        if isinstance(seat_state, dict) and seat_state.get("btn") is True
    ]
    btn_seat = _single_seat_or_none(btn_candidates)
    if btn_seat is None:
        return players_block

    sb_candidates = [
        seat_name
        for seat_name, seat_state in seats.items()
        if isinstance(seat_state, dict)
        and seat_state.get("chips", {}).get("detect") is True
        and _is_sb_chips_value(seat_state.get("chips", {}).get("value"))
    ]
    bb_candidates = [
        seat_name
        for seat_name, seat_state in seats.items()
        if isinstance(seat_state, dict)
        and seat_state.get("chips", {}).get("detect") is True
        and _is_bb_chips_value(seat_state.get("chips", {}).get("value"))
    ]

    sb_seat = _single_seat_or_none(sb_candidates)
    bb_seat = _single_seat_or_none(bb_candidates)
    if sb_seat is None or bb_seat is None:
        return players_block
    if len({btn_seat, sb_seat, bb_seat}) != 3:
        return players_block

    detected_seats = sorted(set(seats.keys()), key=_seat_sort_key)
    blind_gap_seats = (
        _seats_strictly_between_clockwise(detected_seats, btn_seat, sb_seat)
        + _seats_strictly_between_clockwise(detected_seats, sb_seat, bb_seat)
    )

    # The correction is safe only when every non-SitOut seat in blind gaps is
    # already Fold=True. A live player in a blind gap means the blind anchors are
    # ambiguous, so we keep the original position map unchanged.
    for seat_name in blind_gap_seats:
        seat_state = seats.get(seat_name, {})
        if seat_state.get("sitout") is True:
            continue
        if seat_state.get("fold") is not True:
            return players_block

    corrected_any = False
    corrected_seats: List[str] = []
    for seat_name in blind_gap_seats:
        seat_state = seats.get(seat_name, {})
        if seat_state.get("sitout") is not True and seat_state.get("fold") is True:
            seat_state["sitout"] = True
            seat_state["logical_sitout"] = True
            seat_state["sitout_source"] = "blind_gap_fold_correction"
            seat_state["raw_fold_before_logical_sitout"] = True
            corrected_any = True
            corrected_seats.append(seat_name)

    if not corrected_any:
        return players_block

    folded_seats = [
        seat_name
        for seat_name, seat_state in seats.items()
        if isinstance(seat_state, dict) and seat_state.get("fold") is True
    ]
    sitout_seats = [
        seat_name
        for seat_name, seat_state in seats.items()
        if isinstance(seat_state, dict) and seat_state.get("sitout") is True
    ]

    positions_result = build_positions_block(
        detected_player_seats=detected_seats,
        btn_seat=btn_seat,
        folded_seats=folded_seats,
        sitout_seats=sitout_seats,
    )
    seat_positions = positions_result.get("seat_positions", {})
    for seat_name, seat_state in seats.items():
        if isinstance(seat_state, dict):
            seat_state["position"] = seat_positions.get(seat_name)

    players_block["btn_seat"] = btn_seat
    players_block["participation_correction"] = {
        "schema_version": "preflop_blind_anchor_participation_correction_v0_5_2",
        "status": "applied",
        "source": "positions_builder.apply_preflop_blind_anchor_participation_check",
        "rule": "blind_gap_fold_to_logical_sitout",
        "btn_seat": btn_seat,
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "blind_gap_seats": blind_gap_seats,
        "corrected_seats": corrected_seats,
    }
    return players_block
