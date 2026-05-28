from __future__ import annotations

from typing import Any

from .contracts import SOLVER_NAME, SOLVER_VERSION, SolverDecision


BRIDGE_SCHEMA = "pokervision_solver_preflop_bridge_v1"
ACTION_DECISION_SCHEMA = "pokervision_action_decision_from_solver_preflop_v1"
RUNTIME_PLAN_CANDIDATE_SCHEMA = "pokervision_action_runtime_plan_candidate_v1"


def build_pokervision_bridge_payload(decision: SolverDecision) -> dict[str, Any]:
    """Build a PokerVision-facing integration payload.

    This is a preview contract for the future PokerVisionFinalVersionNoSolver
    bridge. It does not execute clicks and must not bypass PokerVision runtime
    guards. PokerVision remains responsible for Active, slot ROI, no-repeat,
    dry-run/real-click flags and button availability.
    """
    action_runtime_hint = decision.to_json_dict()["action_runtime_hint"]

    action_decision = {
        "schema": ACTION_DECISION_SCHEMA,
        "source": SOLVER_NAME,
        "source_version": SOLVER_VERSION,
        "source_frame_id": decision.source_frame_id,
        "street": decision.street,
        "status": decision.status,
        "decision_id": decision.decision_id,
        "solver_decision_id": decision.decision_id,
        "solver_fingerprint": decision.solver_fingerprint,
        "hero_position": decision.hero_position,
        "hero_hand": list(decision.hero_hand),
        "hand_class": decision.hand_class,
        "node_type": decision.node_type,
        "raw_action": decision.raw_action,
        "engine_action": decision.engine_action,
        "size_pct": decision.size_pct,
        "amount_to_bb": decision.amount_to_bb,
        "click_sequence": list(decision.click_sequence),
        "target_buttons": list(decision.click_sequence),
        "safe_fallback_used": decision.safe_fallback_used,
        "reason": decision.reason,
        "warnings": list(decision.warnings),
    }

    runtime_plan_candidate = {
        "schema": RUNTIME_PLAN_CANDIDATE_SCHEMA,
        "source": SOLVER_NAME,
        "source_frame_id": decision.source_frame_id,
        "decision_id": decision.decision_id,
        "solver_fingerprint": decision.solver_fingerprint,
        "street": decision.street,
        "plan_name": decision.raw_action,
        "engine_action": decision.engine_action,
        "raw_action": decision.raw_action,
        "button_sequence": list(decision.click_sequence),
        "target_buttons": list(decision.click_sequence),
        "size_pct": decision.size_pct,
        "amount_to_bb": decision.amount_to_bb,
        "safe_fallback_used": decision.safe_fallback_used,
        "dry_run_recommended": True,
        "real_click_must_be_guarded": True,
        "requires_active_guard": True,
        "requires_slot_roi_guard": True,
        "requires_no_repeat_guard": True,
        "requires_button_availability_guard": True,
    }

    return {
        "schema": BRIDGE_SCHEMA,
        "source": SOLVER_NAME,
        "source_version": SOLVER_VERSION,
        "source_frame_id": decision.source_frame_id,
        "street": decision.street,
        "status": decision.status,
        "identity": {
            "decision_id": decision.decision_id,
            "solver_decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "source_frame_id": decision.source_frame_id,
        },
        "action_decision": action_decision,
        "action_runtime_hint": action_runtime_hint,
        "runtime_plan_candidate": runtime_plan_candidate,
        "safety": {
            "safe_fallback_used": decision.safe_fallback_used,
            "click_sequence": list(decision.click_sequence),
            "must_not_execute_directly": True,
            "must_pass_pokervision_guards": True,
            "integration_stage": "preview",
        },
        "debug": {
            "node_type": decision.node_type,
            "range_source": decision.debug.get("range_source"),
            "range_fallback_used": decision.debug.get("range_fallback_used"),
            "spot_debug": decision.to_json_dict()["spot_debug"],
        },
    }
