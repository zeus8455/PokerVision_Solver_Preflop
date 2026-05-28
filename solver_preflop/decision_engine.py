from __future__ import annotations

import hashlib
import json
from typing import Any

from .cards import hand_to_class
from .clear_json_adapter import parse_clear_json_preflop
from .contracts import SolverDecision
from .sizing_policy import SAFE_FALLBACK_SEQUENCE, click_sequence_for_action, size_pct_for_action
from .spot_classifier import classify_preflop_spot


def _hash_payload(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1((prefix + "|" + raw).encode("utf-8")).hexdigest()


def _build_identity(frame_id: str, node_type: str, hero_hand: list[str], hand_class: str, action: str) -> tuple[str, str]:
    payload = {
        "frame_id": frame_id,
        "node_type": node_type,
        "hero_hand": hero_hand,
        "hand_class": hand_class,
        "action": action,
    }
    fp = _hash_payload("solver_fingerprint_v1", payload)
    decision_id = _hash_payload("decision_id_v1", payload)[:24]
    return fp, decision_id


def _placeholder_action_for_node(node_type: str, to_call_bb: float) -> tuple[str, str]:
    # V0.3 still focuses on state classification. Ranges arrive next.
    if node_type.startswith("bb_option_vs_"):
        return "check", "BB has a logical free option vs limp; range engine can later upgrade to iso_raise."
    if node_type == "sb_first_in":
        return "open_raise", "SB first-in placeholder action until SB range engine is added."
    if node_type == "unopened":
        return "open_raise", "Unopened preflop node; placeholder open until range engine is added."
    if node_type.startswith("iso_vs_"):
        return "iso_raise", "Facing limp node; placeholder iso policy until range engine is added."
    if node_type in {"facing_open", "blind_vs_open", "limper_vs_iso"}:
        return "call", "Facing one raise level; placeholder defend/call until range engine is added."
    if node_type.startswith("opener_vs_small_3bet"):
        return "call", "Small 3bet detected; placeholder keeps defending wider until range engine is added."
    if node_type.startswith("opener_vs_") and "3bet" in node_type:
        return "call", "Opener facing 3bet; placeholder call until range engine is added."
    if node_type.startswith("threebettor_vs_") and "4bet" in node_type:
        return "call", "Threebettor facing 4bet; placeholder call until range engine is added."
    if node_type.startswith("fourbettor_vs_") and "5bet" in node_type:
        return "call", "Fourbettor facing 5bet; placeholder call until range engine is added."
    return "safe_fallback", "Unknown/all-in/unsupported preflop node in V0.3."


def solve_clear_json(data: dict[str, Any]) -> SolverDecision:
    try:
        frame = parse_clear_json_preflop(data)
        spot = classify_preflop_spot(frame)
        hand_class = hand_to_class(frame.hero_cards)

        raw_action, reason = _placeholder_action_for_node(spot.node_type, spot.to_call_bb)

        if raw_action == "safe_fallback":
            click_sequence = list(SAFE_FALLBACK_SEQUENCE)
            engine_action = "safe_fallback"
            size_pct = None
            status = "fallback"
        else:
            click_sequence = click_sequence_for_action(raw_action)
            engine_action = "raise" if raw_action in {"open_raise", "iso_raise", "3bet", "4bet", "5bet", "jam", "all_in"} else raw_action
            size_pct = size_pct_for_action(raw_action)
            status = "ok"

        solver_fingerprint, decision_id = _build_identity(
            frame.frame_id,
            spot.node_type,
            frame.hero_cards,
            hand_class,
            raw_action,
        )

        return SolverDecision(
            status=status,
            street="preflop",
            frame_id=frame.frame_id,
            hero_position=frame.hero_position,
            hero_hand=frame.hero_cards,
            hand_class=hand_class,
            node_type=spot.node_type,
            raw_action=raw_action,
            engine_action=engine_action,
            click_sequence=click_sequence,
            reason=reason,
            size_pct=size_pct,
            decision_id=decision_id,
            solver_fingerprint=solver_fingerprint,
            warnings=list(frame.warnings) + list(spot.notes),
            debug={
                "to_call_bb": spot.to_call_bb,
                "max_commitment_bb": spot.max_commitment_bb,
                "hero_commitment_bb": spot.hero_commitment_bb,
                "commitment_by_pos": dict(spot.commitment_by_pos),
                "raise_levels": list(spot.raise_levels),
                "limpers": list(spot.limpers),
                "all_in_players": list(spot.all_in_players),
                "opener_pos": spot.opener_pos,
                "three_bettor_pos": spot.three_bettor_pos,
                "four_bettor_pos": spot.four_bettor_pos,
                "last_aggressor_pos": spot.last_aggressor_pos,
                "previous_raise_size_bb": spot.previous_raise_size_bb,
                "facing_raise_size_bb": spot.facing_raise_size_bb,
                "sizing_ratio": spot.sizing_ratio,
                "sizing_category": spot.sizing_category,
            },
        )
    except Exception as exc:
        frame_id = str(data.get("frame_id") or "unknown_frame") if isinstance(data, dict) else "unknown_frame"
        return SolverDecision(
            status="fallback",
            street="preflop",
            frame_id=frame_id,
            hero_position="unknown",
            hero_hand=[],
            hand_class="unknown",
            node_type="solver_input_error",
            raw_action="safe_fallback",
            engine_action="safe_fallback",
            click_sequence=list(SAFE_FALLBACK_SEQUENCE),
            reason=f"Solver input error: {exc}",
            warnings=[str(exc)],
            debug={"exception_type": type(exc).__name__},
        )
