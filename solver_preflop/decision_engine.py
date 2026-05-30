from __future__ import annotations

import hashlib
import json
from typing import Any

from .cards import hand_to_class
from .clear_json_adapter import parse_clear_json_preflop
from .contracts import SolverDecision
from .range_engine import decide_preflop_action_from_ranges
from .sizing_policy import SAFE_FALLBACK_SEQUENCE, click_sequence_for_action, size_pct_for_action
from .spot_classifier import classify_preflop_spot


def _hash_payload(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1((prefix + "|" + raw).encode("utf-8")).hexdigest()


def _build_identity(frame_id: str, node_type: str, hero_hand: list[str], hand_class: str, action: str) -> tuple[str, str]:
    payload = {
        "source": "PokerVision_Solver_Preflop",
        "contract": "decision_identity_v1",
        "frame_id": frame_id,
        "source_frame_id": frame_id,
        "street": "preflop",
        "node_type": node_type,
        "hero_hand": hero_hand,
        "hand_class": hand_class,
        "action": action,
    }
    fp = _hash_payload("solver_fingerprint_v1", payload)
    decision_id = _hash_payload("solver_decision_id_v1", payload)[:24]
    return fp, decision_id


def _engine_action(raw_action: str) -> str:
    if raw_action in {"open_raise", "raise", "iso_raise", "3bet", "4bet", "5bet", "5bet_jam", "jam", "all_in"}:
        return "raise"
    if raw_action == "limp":
        return "call"
    return raw_action


def solve_clear_json(data: dict[str, Any]) -> SolverDecision:
    try:
        frame = parse_clear_json_preflop(data)
        spot = classify_preflop_spot(frame)
        hand_class = hand_to_class(frame.hero_cards)

        range_decision = decide_preflop_action_from_ranges(hand_class=hand_class, spot=spot)
        raw_action = range_decision.action

        if raw_action == "safe_fallback":
            # V2.41: unsupported/unsafe Solver_Preflop nodes must remain diagnostic
            # raw_action=safe_fallback, but runtime must receive a valid click action.
            # Use direct FOLD instead of Check/Check-fold chain for real live safety.
            click_sequence = ["FOLD"]
            engine_action = "fold"
            size_pct = None
            status = "fallback"
            reason = f"Range engine unsupported/unsafe node: {spot.node_type}; V2.41 runtime fallback action=fold"
        else:
            click_sequence = click_sequence_for_action(raw_action)
            engine_action = _engine_action(raw_action)
            size_pct = size_pct_for_action(raw_action)
            status = "ok"
            reason = (
                f"range:{range_decision.source}:{raw_action}"
                if not range_decision.fallback_used
                else f"range:{range_decision.source}:default_or_override:{raw_action}"
            )

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
            warnings=list(frame.warnings) + list(spot.notes) + list(range_decision.notes),
            debug={
                "to_call_bb": spot.to_call_bb,
                "max_commitment_bb": spot.max_commitment_bb,
                "hero_commitment_bb": spot.hero_commitment_bb,
                "commitment_by_pos": dict(spot.commitment_by_pos),
                "raise_levels": list(spot.raise_levels),
                "limpers": list(spot.limpers),
                "all_in_players": list(spot.all_in_players),
                "all_in_amount_bb": spot.all_in_amount_bb,
                "all_in_actor_pos": spot.all_in_actor_pos,
                "all_in_previous_level_bb": spot.all_in_previous_level_bb,
                "all_in_raise_delta_bb": spot.all_in_raise_delta_bb,
                "all_in_min_full_raise_delta_bb": spot.all_in_min_full_raise_delta_bb,
                "all_in_is_full_raise": spot.all_in_is_full_raise,
                "all_in_reopens_action": spot.all_in_reopens_action,
                "opener_pos": spot.opener_pos,
                "three_bettor_pos": spot.three_bettor_pos,
                "four_bettor_pos": spot.four_bettor_pos,
                "last_aggressor_pos": spot.last_aggressor_pos,
                "previous_raise_size_bb": spot.previous_raise_size_bb,
                "facing_raise_size_bb": spot.facing_raise_size_bb,
                "sizing_ratio": spot.sizing_ratio,
                "sizing_category": spot.sizing_category,
                "range_source": range_decision.source,
                "matched_range": range_decision.matched_range,
                "range_fallback_used": range_decision.fallback_used,
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
            engine_action="fold",
            click_sequence=["FOLD"],
            reason=f"Solver input error: {exc}; V2.41 runtime fallback action=fold",
            warnings=[str(exc)],
            debug={"exception_type": type(exc).__name__},
        )
