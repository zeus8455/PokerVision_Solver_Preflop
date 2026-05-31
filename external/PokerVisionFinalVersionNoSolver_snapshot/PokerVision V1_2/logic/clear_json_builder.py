"""
logic/clear_json_builder.py

PokerVision V1.2 — Dark_JSON -> minimal Clear_JSON contract.

Purpose:
- Build a compact poker-state JSON from the full detector/runtime state.
- Keep detector/debug/runtime/service details out of Clear_JSON.
- Provide strict validation helpers for replay tests and future state-machine logic.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple


REQUIRED_CLEAR_TOP_LEVEL_KEYS = {"frame_id", "board", "Total_pot", "players"}
ALLOWED_CLEAR_TOP_LEVEL_KEYS = REQUIRED_CLEAR_TOP_LEVEL_KEYS | {"click_result"}

FORBIDDEN_CLEAR_KEYS = {
    "frame_name", "table_id", "hand_id", "action_event_id", "action_signature",
    "pipeline_meta", "processing_time_ms", "cycle_id", "status_values", "note",
    "model_name", "input_scope", "thresholds", "raw_detection_count", "next_stage_hint",
    "trigger_ui", "trigger", "table_structure",
    "Player_seat1", "Player_seat2", "Player_seat3", "Player_seat4", "Player_seat5", "Player_seat6",
    "raw_bbox", "bbox", "bbox_xyxy", "confidence", "slot_bbox", "btn_seat",
    "detected_classes", "strong_detected_classes",
    "runtime_event", "runtime_action", "solver_payload_path", "solver_status", "solver_action",
    "click_points",
    "service_branch", "action_button_branch", "errors", "warnings", "stable_state",
}

VALID_STREETS = {"preflop", "flop", "turn", "river"}
BOARD_CARD_COUNT_BY_STREET = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}

VALID_POSITIONS = {"UTG", "UTG1", "UTG2", "LJ", "HJ", "MP", "CO", "BTN", "SB", "BB"}

_FRAME_NAME_RE = re.compile(
    r"^(?P<hand>hand_\d+)(?:_(?P<street>preflop|flop|turn|river)(?:_(?P<idx>\d+))?)?$",
    re.IGNORECASE,
)


def _deep_get(data: Dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _clean_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "да"}:
        return True
    if text in {"0", "false", "no", "n", "нет"}:
        return False
    return default


def _extract_table_id(dark_state: Dict[str, Any]) -> Optional[str]:
    return _clean_string(dark_state.get("table_id")) or _clean_string(_deep_get(dark_state, "table", "table_id"))


def _extract_frame_name(dark_state: Dict[str, Any]) -> Optional[str]:
    return _clean_string(dark_state.get("frame_name")) or _clean_string(_deep_get(dark_state, "table", "frame_name"))


def _normalize_frame_name_with_state_index(frame_name: str) -> str:
    """hand_01_preflop -> hand_01_preflop_01; hand_01_preflop_02 stays _02."""
    match = _FRAME_NAME_RE.match(frame_name)
    if not match:
        return frame_name
    hand = match.group("hand")
    street = match.group("street")
    idx = match.group("idx")
    if not street:
        return hand
    return f"{hand}_{street.lower()}_{int(idx or '1'):02d}"


def _extract_frame_id(dark_state: Dict[str, Any]) -> str:
    explicit = _clean_string(dark_state.get("frame_id")) or _clean_string(_deep_get(dark_state, "table", "frame_id"))
    if explicit:
        return explicit
    table_id = _extract_table_id(dark_state) or "table_unknown"
    frame_name = _extract_frame_name(dark_state) or _clean_string(dark_state.get("hand_id")) or "hand_unknown"
    normalized_frame_name = _normalize_frame_name_with_state_index(frame_name)
    if normalized_frame_name.startswith(f"{table_id}_"):
        return normalized_frame_name
    return f"{table_id}_{normalized_frame_name}"


def _extract_board(dark_state: Dict[str, Any]) -> Dict[str, Any]:
    board = dark_state.get("board")
    if isinstance(board, dict):
        street = _clean_string(board.get("street"))
        cards = board.get("cards")
        return {"cards": [str(card) for card in cards] if isinstance(cards, list) else [], "street": street.lower() if street else "preflop"}

    board = _deep_get(dark_state, "table_structure", "classes", "Board")
    if isinstance(board, dict):
        street = _clean_string(board.get("street"))
        cards = board.get("cards")
        return {"cards": [str(card) for card in cards] if isinstance(cards, list) else [], "street": street.lower() if street else "preflop"}

    return {"cards": [], "street": "preflop"}


def _extract_total_pot(dark_state: Dict[str, Any], previous_clear_state: Optional[Dict[str, Any]] = None) -> Optional[float]:
    if "Total_pot" in dark_state:
        value = _as_number_or_none(dark_state.get("Total_pot"))
        if value is not None:
            return value

    value = _as_number_or_none(_deep_get(dark_state, "table_structure", "classes", "Total_pot", "value"))
    if value is not None:
        return value

    if isinstance(previous_clear_state, dict):
        previous_value = _as_number_or_none(previous_clear_state.get("Total_pot"))
        if previous_value is not None:
            return previous_value
    return None


def _candidate_cards(player: Dict[str, Any]) -> List[str]:
    for key in ("cards", "hero_cards"):
        value = player.get(key)
        if isinstance(value, list):
            return [str(card) for card in value if str(card).strip()]
    return []


def _normalize_stack(player: Dict[str, Any], previous_player: Optional[Dict[str, Any]] = None) -> Optional[float]:
    stack = player.get("stack")
    value = _as_number_or_none(stack.get("value")) if isinstance(stack, dict) else _as_number_or_none(stack)
    if value is not None:
        return value
    if isinstance(previous_player, dict):
        return _as_number_or_none(previous_player.get("stack"))
    return None


def _normalize_chips(player: Dict[str, Any], previous_player: Optional[Dict[str, Any]] = None) -> Any:
    chips = player.get("chips")
    if isinstance(chips, dict):
        value = _as_number_or_none(chips.get("value"))
        detected = _as_bool(chips.get("detect"), default=value is not None)
        if detected and value is not None:
            return value
        return False
    if chips is False or chips is None:
        return False
    value = _as_number_or_none(chips)
    if value is not None:
        return value
    if isinstance(previous_player, dict):
        previous_chips = previous_player.get("chips")
        if previous_chips is False:
            return False
        previous_value = _as_number_or_none(previous_chips)
        if previous_value is not None:
            return previous_value
    return False


def _extract_raw_players(dark_state: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    players = dark_state.get("players")
    if isinstance(players, dict) and "seats" not in players:
        return [(str(position), dict(player)) for position, player in players.items() if isinstance(player, dict)]
    seats = _deep_get(dark_state, "players", "seats")
    if isinstance(seats, dict):
        return [(str(seat_name), dict(seat)) for seat_name, seat in seats.items() if isinstance(seat, dict)]
    return []


def _resolve_position(source_key: str, player: Dict[str, Any]) -> Optional[str]:
    position = _clean_string(player.get("position"))
    if position and position in VALID_POSITIONS:
        return position
    if source_key in VALID_POSITIONS:
        return source_key
    return None


def _build_clear_player(player: Dict[str, Any], previous_player: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stack_value = _normalize_stack(player, previous_player)
    chips_value = _normalize_chips(player, previous_player)
    fold_value = _as_bool(player.get("fold"), default=False)
    clear_player: Dict[str, Any] = {"stack": stack_value, "fold": fold_value, "chips": chips_value}

    # V2.46: preserve reliable all-in semantic state in Clear_JSON.
    # Only propagate all_in when the source all-in flag is true and the committed
    # amount is numeric. Missing-amount all-in remains a later V2.48 diagnostic
    # problem instead of pretending to know the amount.
    all_in_value = _as_bool(player.get("all_in"), default=False) or _as_bool(player.get("allin"), default=False)
    if all_in_value and chips_value is not False and _as_number_or_none(chips_value) is not None:
        clear_player["all_in"] = True
        # V2.47: all-in players can legitimately have no remaining stack value.
        # Downstream layers expect numeric stack, so normalize stack=None to 0.0
        # only when all_in is reliable and committed chips are numeric.
        if clear_player.get("stack") is None:
            clear_player["stack"] = 0.0
    elif all_in_value and chips_value is False:
        # V2.48: do not invent an all-in amount, but do not silently lose the
        # state either. Solver will classify this as facing_allin_unknown_amount.
        clear_player["all_in_unknown_amount"] = True

    cards = _candidate_cards(player)
    is_hero = _as_bool(player.get("hero"), default=False) or len(cards) == 2
    if is_hero:
        clear_player = {"hero": True, "cards": cards, **clear_player}
    return clear_player


def _build_player_participation_audit_entry(
    *,
    source_key: str,
    player: Dict[str, Any],
    resolved_position: Optional[str],
) -> Dict[str, Any]:
    """Diagnostic-only audit for why a raw player is included/excluded from Clear_JSON."""
    cards = _candidate_cards(player)
    fold_value = _as_bool(player.get("fold"), default=False)
    sitout_value = _as_bool(player.get("sitout"), default=False)
    hero_value = _as_bool(player.get("hero"), default=False) or len(cards) == 2
    logical_sitout = _as_bool(player.get("logical_sitout"), default=False)
    raw_fold_before_logical_sitout = _as_bool(
        player.get("raw_fold_before_logical_sitout"),
        default=False,
    )
    sitout_source = _clean_string(player.get("sitout_source"))
    if sitout_value and not sitout_source:
        sitout_source = "detector_or_upstream_unknown"

    exclusion_reason: Optional[str] = None
    clear_json_rule = "included_participating_player"
    if sitout_value:
        exclusion_reason = "sitout_true"
        clear_json_rule = "excluded_because_sitout_dominates_fold"
    elif not resolved_position:
        exclusion_reason = "missing_or_invalid_position"
        clear_json_rule = "excluded_because_position_unresolved"

    danger_flags: List[str] = []
    if fold_value and sitout_value:
        danger_flags.append("fold_and_sitout_player_will_be_excluded")
    if fold_value and sitout_value and logical_sitout:
        danger_flags.append("fold_converted_to_logical_sitout_will_be_excluded")
    if hero_value and exclusion_reason:
        danger_flags.append("hero_would_be_excluded_from_clear_json")
    if len(cards) == 2 and sitout_value:
        danger_flags.append("cards_infer_hero_but_sitout_excludes_player")

    return {
        "source_key": str(source_key),
        "resolved_position": resolved_position,
        "fold": bool(fold_value),
        "sitout": bool(sitout_value),
        "sitout_source": sitout_source,
        "logical_sitout": bool(logical_sitout),
        "raw_fold_before_logical_sitout": bool(raw_fold_before_logical_sitout),
        "hero": bool(hero_value),
        "cards_count": len(cards),
        "included_in_clear_json": exclusion_reason is None,
        "exclude_reason": exclusion_reason,
        "clear_json_rule": clear_json_rule,
        "danger_flags": danger_flags,
    }


def build_clear_json_from_dark_state(
    dark_state: Dict[str, Any],
    previous_clear_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build minimal Clear_JSON from full Dark_JSON/current state."""
    if not isinstance(dark_state, dict):
        raise TypeError("dark_state must be a dict")

    previous_players = previous_clear_state.get("players", {}) if isinstance(previous_clear_state, dict) else {}
    if not isinstance(previous_players, dict):
        previous_players = {}

    raw_players = _extract_raw_players(dark_state)
    participation_audit: Dict[str, Any] = {
        "schema_version": "player_participation_audit_v0_5_2",
        "behavior": "sitout_dominates_fold_with_sitout_source_diagnostics",
        "raw_player_count": len(raw_players),
        "included_count": 0,
        "excluded_count": 0,
        "included_in_clear_json": [],
        "excluded_from_clear_json": [],
        "hero_exclusion_detected": False,
        "fold_and_sitout_exclusion_detected": False,
        "logical_sitout_exclusion_detected": False,
        "sitout_source_counts": {},
    }

    clear_players: Dict[str, Dict[str, Any]] = {}
    for source_key, player in raw_players:
        position = _resolve_position(source_key, player)
        audit_entry = _build_player_participation_audit_entry(
            source_key=source_key,
            player=player,
            resolved_position=position,
        )

        if _as_bool(player.get("sitout"), default=False):
            participation_audit["excluded_from_clear_json"].append(audit_entry)
            sitout_source = str(audit_entry.get("sitout_source") or "detector_or_upstream_unknown")
            source_counts = participation_audit.get("sitout_source_counts")
            if isinstance(source_counts, dict):
                source_counts[sitout_source] = int(source_counts.get(sitout_source, 0)) + 1
            if audit_entry.get("hero"):
                participation_audit["hero_exclusion_detected"] = True
            if bool(audit_entry.get("fold")) and bool(audit_entry.get("sitout")):
                participation_audit["fold_and_sitout_exclusion_detected"] = True
            if bool(audit_entry.get("logical_sitout")):
                participation_audit["logical_sitout_exclusion_detected"] = True
            continue
        if not position:
            participation_audit["excluded_from_clear_json"].append(audit_entry)
            if audit_entry.get("hero"):
                participation_audit["hero_exclusion_detected"] = True
            continue

        participation_audit["included_in_clear_json"].append(audit_entry)
        previous_player = previous_players.get(position) if isinstance(previous_players.get(position), dict) else None
        clear_players[position] = _build_clear_player(player, previous_player)

    participation_audit["included_count"] = len(participation_audit["included_in_clear_json"])
    participation_audit["excluded_count"] = len(participation_audit["excluded_from_clear_json"])
    dark_state["player_participation_audit"] = participation_audit

    return {
        "frame_id": _extract_frame_id(dark_state),
        "board": _extract_board(dark_state),
        "Total_pot": _extract_total_pot(dark_state, previous_clear_state),
        "players": clear_players,
    }


def _walk_keys(data: Any, prefix: str = "$") -> Iterable[Tuple[str, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}"
            yield str(key), path
            yield from _walk_keys(value, path)
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            yield from _walk_keys(value, f"{prefix}[{idx}]")


def _hero_players(clear_state: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    players = clear_state.get("players")
    if not isinstance(players, dict):
        return []
    return [(position, player) for position, player in players.items() if isinstance(player, dict) and bool(player.get("hero"))]


def validate_clear_json_contract(clear_state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate minimal Clear_JSON contract. Returns {ok, errors, warnings}."""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(clear_state, dict):
        return {"ok": False, "errors": ["Clear_JSON root must be a dict."], "warnings": []}

    top_keys = set(clear_state.keys())
    extra_top_keys = sorted(top_keys - ALLOWED_CLEAR_TOP_LEVEL_KEYS)
    missing_top_keys = sorted(REQUIRED_CLEAR_TOP_LEVEL_KEYS - top_keys)
    if extra_top_keys:
        errors.append(f"Clear_JSON has forbidden top-level keys: {extra_top_keys}")
    if missing_top_keys:
        errors.append(f"Clear_JSON is missing required top-level keys: {missing_top_keys}")

    for key, path in _walk_keys(clear_state):
        if key in FORBIDDEN_CLEAR_KEYS:
            errors.append(f"Forbidden key in Clear_JSON at {path}: {key}")

    frame_id = _clean_string(clear_state.get("frame_id"))
    if not frame_id:
        errors.append("Clear_JSON.frame_id is required and must be non-empty string.")

    board = clear_state.get("board")
    if not isinstance(board, dict):
        errors.append("Clear_JSON.board must be an object.")
    else:
        board_extra_keys = sorted(set(board.keys()) - {"cards", "street"})
        if board_extra_keys:
            errors.append(f"Clear_JSON.board has forbidden keys: {board_extra_keys}")
        street = _clean_string(board.get("street"))
        if street not in VALID_STREETS:
            errors.append(f"Clear_JSON.board.street must be one of {sorted(VALID_STREETS)}, got {street!r}.")
        cards = board.get("cards")
        if not isinstance(cards, list):
            errors.append("Clear_JSON.board.cards must be a list.")
        elif street in BOARD_CARD_COUNT_BY_STREET and len(cards) != BOARD_CARD_COUNT_BY_STREET[street]:
            errors.append(
                f"Clear_JSON.board.cards count mismatch for {street}: "
                f"expected={BOARD_CARD_COUNT_BY_STREET[street]}, actual={len(cards)}"
            )

    total_pot = clear_state.get("Total_pot")
    if total_pot is not None and _as_number_or_none(total_pot) is None:
        errors.append("Clear_JSON.Total_pot must be number or null.")

    players = clear_state.get("players")
    if not isinstance(players, dict):
        errors.append("Clear_JSON.players must be an object.")
    else:
        if not players:
            warnings.append("Clear_JSON.players is empty.")
        for position, player in players.items():
            if position.startswith("Player_seat"):
                errors.append(f"Clear_JSON.players must be keyed by poker position, not technical seat: {position}")
            if position not in VALID_POSITIONS:
                warnings.append(f"Clear_JSON.players has non-standard poker position key: {position}")
            if not isinstance(player, dict):
                errors.append(f"Clear_JSON.players.{position} must be an object.")
                continue
            allowed_player_keys = {"hero", "cards", "stack", "fold", "chips", "all_in", "all_in_unknown_amount"}
            extra_player_keys = sorted(set(player.keys()) - allowed_player_keys)
            if extra_player_keys:
                errors.append(f"Clear_JSON.players.{position} has forbidden keys: {extra_player_keys}")
            if _as_number_or_none(player.get("stack")) is None:
                errors.append(f"Clear_JSON.players.{position}.stack must be a number.")
            if not isinstance(player.get("fold"), bool):
                errors.append(f"Clear_JSON.players.{position}.fold must be boolean.")
            chips = player.get("chips")
            if chips is not False and _as_number_or_none(chips) is None:
                errors.append(f"Clear_JSON.players.{position}.chips must be number or false.")
            all_in = player.get("all_in")
            if all_in is not None and not isinstance(all_in, bool):
                errors.append(f"Clear_JSON.players.{position}.all_in must be boolean when present.")
            if all_in is True and chips is False:
                errors.append(f"Clear_JSON.players.{position}.all_in requires numeric chips.")

            all_in_unknown_amount = player.get("all_in_unknown_amount")
            if all_in_unknown_amount is not None and not isinstance(all_in_unknown_amount, bool):
                errors.append(f"Clear_JSON.players.{position}.all_in_unknown_amount must be boolean when present.")
            if all_in_unknown_amount is True and chips is not False:
                errors.append(f"Clear_JSON.players.{position}.all_in_unknown_amount requires chips=false.")
            if all_in_unknown_amount is True and all_in is True:
                errors.append(f"Clear_JSON.players.{position} cannot have both all_in and all_in_unknown_amount.")

            if bool(player.get("hero")):
                cards = player.get("cards")
                if not isinstance(cards, list) or len(cards) != 2:
                    errors.append(f"Clear_JSON.players.{position}.cards must contain exactly 2 HERO cards.")


    click_result = clear_state.get("click_result")
    if click_result is not None:
        if not isinstance(click_result, dict):
            errors.append("Clear_JSON.click_result must be an object when present.")
        else:
            allowed_click_keys = {
                "status", "branch", "action", "size_pct", "dry_run",
                "real_click_enabled", "guard_passed", "decision_id", "message",
            }
            extra_click_keys = sorted(set(click_result.keys()) - allowed_click_keys)
            if extra_click_keys:
                errors.append(f"Clear_JSON.click_result has forbidden keys: {extra_click_keys}")
            status = _clean_string(click_result.get("status"))
            if status not in {"clicked", "confirmed", "dry_run"}:
                errors.append(f"Clear_JSON.click_result.status must confirm completed click cycle, got {status!r}.")
            if not isinstance(click_result.get("dry_run"), bool):
                errors.append("Clear_JSON.click_result.dry_run must be boolean.")
            if not isinstance(click_result.get("real_click_enabled"), bool):
                errors.append("Clear_JSON.click_result.real_click_enabled must be boolean.")

    heroes = _hero_players(clear_state)
    if len(heroes) != 1:
        errors.append(f"Clear_JSON must contain exactly one HERO, got {len(heroes)}.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def canonical_clear_json_signature(clear_state: Dict[str, Any]) -> str:
    """Canonical poker-state signature for deduplication. frame_id is excluded."""
    payload = {
        "board": deepcopy(clear_state.get("board")),
        "Total_pot": _as_number_or_none(clear_state.get("Total_pot")),
        "players": deepcopy(clear_state.get("players")),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
