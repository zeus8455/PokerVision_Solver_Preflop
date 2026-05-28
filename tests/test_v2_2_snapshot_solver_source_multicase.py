import json
import subprocess
import sys


def test_v2_2_snapshot_solver_source_multicase_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_2_snapshot_solver_source_multicase_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v22_snapshot_solver_source_multicase_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False

    assert payload["files_total"] >= 4
    assert payload["bad_count"] == 0
    assert payload["ok_count"] == payload["files_total"]

    assert payload["action_counts"].get("fold", 0) >= 1
    assert payload["action_counts"].get("check", 0) >= 1

    for item in payload["results"]:
        assert item["ok"] is True
        assert item["selection"]["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection"]["adapted_to_legacy_action_decision"] is True

        selected = item["selected_action_decision"]
        assert selected["source"] == "Decision_JSON"
        assert selected["solver_stub"] is True
        assert selected["decision_context"]["solver_preflop_runtime_source"] is True
        assert selected["decision_context"]["solver_stub_legacy_compat"] is True

        runtime = item["runtime_plan_contract"]
        assert runtime["status"] == "preview_not_saved_pending_only"
        assert runtime["file_publication_enabled"] is False
        assert runtime["dry_run"] is True
        assert runtime["real_click_enabled"] is False
        assert runtime["target_sequence"]
