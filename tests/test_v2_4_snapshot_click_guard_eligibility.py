import json
import subprocess
import sys


def test_v2_4_snapshot_click_guard_eligibility_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_4_snapshot_click_guard_eligibility_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v24_snapshot_click_guard_eligibility_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False
    assert payload["physical_click_executed"] is False

    assert payload["files_total"] >= 4
    assert payload["bad_count"] == 0
    assert payload["ok_count"] == payload["files_total"]

    assert payload["action_counts"].get("fold", 0) >= 1
    assert payload["action_counts"].get("check", 0) >= 1

    for item in payload["results"]:
        assert item["ok"] is True
        assert item["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection_reason"] == "v20_solver_preflop_selected"

        runtime = item["runtime_plan"]
        assert runtime["status"] == "preview_not_saved_pending_only"
        assert runtime["runtime_state_status"] == "ok"
        assert runtime["dry_run"] is True
        assert runtime["real_click_enabled"] is False
        assert runtime["target_sequence"]

        dry = item["dry_run_click_result"]
        assert dry["status"] == "dry_run"
        assert dry["reason"] == "all_click_execution_guards_passed"
        assert dry["guard_passed"] is True
        assert dry["dry_run"] is True
        assert dry["real_click_enabled"] is False
        assert dry["guards"]["plan_source_guard"] is True
        assert dry["guards"]["button_availability_guard"] is True
        assert dry["guards"]["slot_boundary_guard"] is True
        assert dry["guards"]["no_repeat_decision_guard"] is True
        assert dry["guards"]["dry_run_guard"] is True

        repeated = item["repeated_click_result"]
        assert repeated["status"] == "blocked"
        assert repeated["reason"] == "decision_id_already_executed"

        real = item["forced_real_click_result"]
        assert real["status"] == "blocked"
        assert real["reason"] == "real_click_master_not_armed"
        assert real["dry_run"] is False
        assert real["real_click_enabled"] is True

        assert item["checks"]["runtime_ok"] is True
        assert item["checks"]["dry_run_guard_ok"] is True
        assert item["checks"]["repeat_guard_ok"] is True
        assert item["checks"]["real_click_block_ok"] is True

        assert all(item["checks"].values())
