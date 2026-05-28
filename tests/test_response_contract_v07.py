import json
from pathlib import Path

from solver_preflop import solve_clear_json
from solver_preflop.contracts import SOLVER_VERSION


def _base():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_ok_response_contract_has_runtime_hint():
    data = _base()
    decision = solve_clear_json(data)
    payload = decision.to_json_dict()

    assert payload["solver"]["contract"] == "preflop_solver_response_v1"
    assert payload["solver"]["version"] == SOLVER_VERSION

    assert payload["source"]["source_frame_id"] == "table_02_hand_29_preflop_01"
    assert payload["identity"]["solver_decision_id"] == decision.decision_id
    assert payload["identity"]["source_frame_id"] == decision.source_frame_id

    hint = payload["action_runtime_hint"]
    assert hint["contract"] == "pokervision_action_runtime_hint_v1"
    assert hint["source"] == "solver_preflop"
    assert hint["source_frame_id"] == decision.source_frame_id
    assert hint["decision_id"] == decision.decision_id
    assert hint["solver_fingerprint"] == decision.solver_fingerprint
    assert hint["click_sequence"] == ["Check"]
    assert hint["target_buttons"] == ["Check"]
    assert hint["safe_fallback_used"] is False
    assert hint["runtime_action_allowed"] is True

    assert payload["safety"]["requires_pokervision_runtime_guards"] is True
    assert payload["safety"]["must_not_bypass_click_guards"] is True
    assert payload["input_summary"]["node_type"] == "bb_option_vs_1_limper"
    assert payload["spot_debug"]["to_call_bb"] == 0.0


def test_fallback_response_contract_has_safe_fallback_hint():
    data = _base()
    data["click_result"] = {"status": "clicked"}

    decision = solve_clear_json(data)
    payload = decision.to_json_dict()

    assert decision.status == "fallback"
    assert payload["decision"]["click_sequence"] == ["Check", "Check/fold", "FOLD"]
    assert payload["action_runtime_hint"]["safe_fallback_used"] is True
    assert payload["action_runtime_hint"]["target_buttons"] == ["Check", "Check/fold", "FOLD"]
    assert payload["safety"]["safe_fallback_used"] is True
    assert payload["safety"]["fallback_click_sequence"] == ["Check", "Check/fold", "FOLD"]
    assert payload["identity"]["solver_decision_id"] is None


def test_action_decision_bridge_payload():
    data = _base()
    decision = solve_clear_json(data)
    payload = decision.to_action_decision_dict()

    assert payload["schema"] == "pokervision_solver_action_decision_v1"
    assert payload["source"] == "PokerVision_Solver_Preflop"
    assert payload["source_frame_id"] == decision.source_frame_id
    assert payload["decision_id"] == decision.decision_id
    assert payload["solver_fingerprint"] == decision.solver_fingerprint
    assert payload["street"] == "preflop"
    assert payload["raw_action"] == "check"
    assert payload["engine_action"] == "check"
    assert payload["click_sequence"] == ["Check"]
    assert payload["safe_fallback_used"] is False
