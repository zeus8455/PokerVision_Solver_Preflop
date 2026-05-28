import json
import subprocess
import sys


def test_v2_1_snapshot_solver_source_dryrun_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_1_snapshot_solver_source_dryrun_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v21_snapshot_solver_source_dryrun_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False

    assert payload["selection"]["selected_source"] == "Solver_Preflop_Bridge"
    assert payload["selection"]["adapted_to_legacy_action_decision"] is True

    selected = payload["selected_action_decision_state"]
    assert selected["source"] == "Decision_JSON"
    assert selected["action"] == "check"
    assert selected["target_button_classes"] == ["Check"]
    assert selected["solver_stub"] is True
    assert selected["decision_context"]["solver_preflop_runtime_source"] is True
    assert selected["decision_context"]["solver_stub_legacy_compat"] is True

    runtime = payload["runtime_plan_contract"]
    assert runtime["status"] == "preview_not_saved_pending_only"
    assert runtime["planned_action"] == "check"
    assert runtime["target_sequence"] == ["Check"]

    assert all(payload["checks"].values())
