import json
from pathlib import Path

from solver_preflop import solve_clear_json
from solver_preflop.pokervision_bridge import build_pokervision_bridge_payload


def _base():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_pokervision_bridge_payload_ok():
    decision = solve_clear_json(_base())
    payload = build_pokervision_bridge_payload(decision)

    assert payload["schema"] == "pokervision_solver_preflop_bridge_v1"
    assert payload["source_frame_id"] == "table_02_hand_29_preflop_01"
    assert payload["status"] == "ok"

    action = payload["action_decision"]
    assert action["schema"] == "pokervision_action_decision_from_solver_preflop_v1"
    assert action["decision_id"] == decision.decision_id
    assert action["solver_fingerprint"] == decision.solver_fingerprint
    assert action["raw_action"] == "check"
    assert action["engine_action"] == "check"
    assert action["click_sequence"] == ["Check"]

    plan = payload["runtime_plan_candidate"]
    assert plan["schema"] == "pokervision_action_runtime_plan_candidate_v1"
    assert plan["button_sequence"] == ["Check"]
    assert plan["target_buttons"] == ["Check"]
    assert plan["dry_run_recommended"] is True
    assert plan["real_click_must_be_guarded"] is True
    assert plan["requires_active_guard"] is True
    assert plan["requires_slot_roi_guard"] is True
    assert plan["requires_no_repeat_guard"] is True


def test_build_pokervision_bridge_payload_fallback():
    data = _base()
    data["click_result"] = {"status": "clicked"}

    decision = solve_clear_json(data)
    payload = build_pokervision_bridge_payload(decision)

    assert payload["status"] == "fallback"
    assert payload["action_decision"]["safe_fallback_used"] is True
    assert payload["runtime_plan_candidate"]["button_sequence"] == ["Check", "Check/fold", "FOLD"]
    assert payload["safety"]["must_not_execute_directly"] is True
