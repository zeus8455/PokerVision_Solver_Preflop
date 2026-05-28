"""
logic/decision_json_builder.py

PokerVision V0.5 — Clear_JSON -> Decision_JSON contract.

Purpose:
- Build a compact decision/solver input only from validated Clear_JSON.
- Never read Dark_JSON, detector bbox/confidence, runtime_action or service debug.
- Keep Clear_JSON clean while giving the future solver a stable payload.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from config import V05_DECISION_JSON_SCHEMA_VERSION
from logic.clear_json_builder import validate_clear_json_contract


VALID_STREETS = {"preflop", "flop", "turn", "river"}


def _as_number(value: Any) -> Optional[float]:
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


def _clean_cards(cards: Any) -> List[str]:
    if not isinstance(cards, list):
        return []
    return [str(card).strip() for card in cards if str(card).strip()]


def _find_hero(players: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    hero_position: Optional[str] = None
    hero_player: Optional[Dict[str, Any]] = None
    for position, player in players.items():
        if isinstance(player, dict) and player.get("hero") is True:
            if hero_position is not None:
                return None, None
            hero_position = str(position)
            hero_player = player
    return hero_position, hero_player


def build_decision_json_from_clear_state(clear_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build Decision_JSON from Clear_JSON only.

    The input may be a pending Clear_JSON candidate or a final Clear_JSON with
    click_result. click_result is intentionally ignored because it is an output
    of the action cycle, not an input to the next decision.
    """
    if not isinstance(clear_state, dict):
        raise ValueError("clear_state must be a dict")

    validation = validate_clear_json_contract(clear_state)
    if not isinstance(validation, dict) or not validation.get("ok"):
        raise ValueError(f"Clear_JSON is not valid enough to build Decision_JSON: {validation}")

    board_block = clear_state.get("board") if isinstance(clear_state.get("board"), dict) else {}
    street = str(board_block.get("street") or "").strip().lower()
    board_cards = _clean_cards(board_block.get("cards"))
    players = clear_state.get("players") if isinstance(clear_state.get("players"), dict) else {}

    hero_position, hero_player = _find_hero(players)
    if not hero_position or not isinstance(hero_player, dict):
        raise ValueError("Decision_JSON requires exactly one HERO in Clear_JSON.players")

    hero_cards = _clean_cards(hero_player.get("cards"))
    if len(hero_cards) != 2:
        raise ValueError("Decision_JSON requires exactly two HERO cards")

    active_players: Dict[str, Dict[str, Any]] = {}
    folded_players: Dict[str, Dict[str, Any]] = {}
    for position, player in players.items():
        if not isinstance(player, dict):
            continue
        player_payload = {
            "stack": _as_number(player.get("stack")),
            "fold": bool(player.get("fold", False)),
            "chips": player.get("chips") if player.get("chips") is False else _as_number(player.get("chips")),
        }
        if player_payload["fold"]:
            folded_players[str(position)] = player_payload
        else:
            active_players[str(position)] = player_payload

    decision_json: Dict[str, Any] = {
        "schema_version": V05_DECISION_JSON_SCHEMA_VERSION,
        "source": "Clear_JSON",
        "source_frame_id": str(clear_state.get("frame_id") or ""),
        "street": street if street in VALID_STREETS else "unknown",
        "board": board_cards,
        "total_pot": _as_number(clear_state.get("Total_pot")),
        "hero": {
            "position": hero_position,
            "cards": hero_cards,
            "stack": _as_number(hero_player.get("stack")),
            "chips": hero_player.get("chips") if hero_player.get("chips") is False else _as_number(hero_player.get("chips")),
        },
        "players": {
            str(position): {
                "stack": _as_number(player.get("stack")),
                "fold": bool(player.get("fold", False)),
                "chips": player.get("chips") if player.get("chips") is False else _as_number(player.get("chips")),
            }
            for position, player in players.items()
            if isinstance(player, dict) and str(position) != hero_position
        },
        "active_positions": sorted(active_players.keys()),
        "folded_positions": sorted(folded_players.keys()),
        "decision_context": {
            "is_preflop": street == "preflop",
            "is_postflop": street in {"flop", "turn", "river"},
            "players_total": len(players),
            "active_players_total": len(active_players),
            "folded_players_total": len(folded_players),
        },
    }
    return decision_json


def validate_decision_json_contract(decision_json: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(decision_json, dict):
        return {"ok": False, "errors": ["Decision_JSON must be an object."], "warnings": []}

    required = {
        "schema_version", "source", "source_frame_id", "street", "board",
        "total_pot", "hero", "players", "active_positions", "folded_positions",
        "decision_context",
    }
    missing = sorted(required - set(decision_json.keys()))
    if missing:
        errors.append(f"Decision_JSON missing required keys: {missing}")

    forbidden = {
        "pipeline_meta", "trigger_ui", "table_structure", "runtime_event", "runtime_action",
        "click_result", "click_points", "bbox", "confidence", "errors", "warnings",
    }
    extra_forbidden = sorted(forbidden & set(decision_json.keys()))
    if extra_forbidden:
        errors.append(f"Decision_JSON has forbidden technical keys: {extra_forbidden}")

    if decision_json.get("schema_version") != V05_DECISION_JSON_SCHEMA_VERSION:
        errors.append(f"Decision_JSON.schema_version mismatch: {decision_json.get('schema_version')!r}")
    if decision_json.get("source") != "Clear_JSON":
        errors.append("Decision_JSON.source must be 'Clear_JSON'.")
    if str(decision_json.get("street") or "") not in VALID_STREETS:
        errors.append(f"Decision_JSON.street is invalid: {decision_json.get('street')!r}")
    if not isinstance(decision_json.get("board"), list):
        errors.append("Decision_JSON.board must be a list.")

    hero = decision_json.get("hero")
    if not isinstance(hero, dict):
        errors.append("Decision_JSON.hero must be an object.")
    else:
        if not hero.get("position"):
            errors.append("Decision_JSON.hero.position is required.")
        cards = hero.get("cards")
        if not isinstance(cards, list) or len(cards) != 2:
            errors.append("Decision_JSON.hero.cards must contain exactly two cards.")
        if _as_number(hero.get("stack")) is None:
            errors.append("Decision_JSON.hero.stack must be a number.")
        chips = hero.get("chips")
        if chips is not False and _as_number(chips) is None:
            errors.append("Decision_JSON.hero.chips must be a number or false.")

    players = decision_json.get("players")
    if not isinstance(players, dict):
        errors.append("Decision_JSON.players must be an object.")
    else:
        for position, player in players.items():
            if not isinstance(player, dict):
                errors.append(f"Decision_JSON.players.{position} must be an object.")
                continue
            if not isinstance(player.get("fold"), bool):
                errors.append(f"Decision_JSON.players.{position}.fold must be boolean.")
            if _as_number(player.get("stack")) is None:
                errors.append(f"Decision_JSON.players.{position}.stack must be a number.")
            chips = player.get("chips")
            if chips is not False and _as_number(chips) is None:
                errors.append(f"Decision_JSON.players.{position}.chips must be a number or false.")

    for key in ("active_positions", "folded_positions"):
        if not isinstance(decision_json.get(key), list):
            errors.append(f"Decision_JSON.{key} must be a list.")

    context = decision_json.get("decision_context")
    if not isinstance(context, dict):
        errors.append("Decision_JSON.decision_context must be an object.")

    return {"ok": not errors, "errors": errors, "warnings": warnings}
