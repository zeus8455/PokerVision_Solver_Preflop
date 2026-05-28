import json
import subprocess
import sys


def test_v2_3_snapshot_runtime_publication_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_3_snapshot_runtime_publication_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v23_snapshot_runtime_publication_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False

    assert payload["files_total"] >= 4
    assert payload["bad_count"] == 0
    assert payload["ok_count"] == payload["files_total"]
    assert payload["published_files_count"] >= payload["files_total"]

    assert payload["action_counts"].get("fold", 0) >= 1
    assert payload["action_counts"].get("check", 0) >= 1

    for item in payload["results"]:
        assert item["ok"] is True
        assert item["selection"]["selected_source"] == "Solver_Preflop_Bridge"

        runtime = item["runtime_plan_contract"]
        assert runtime["status"] == "saved"
        assert runtime["file_publication_enabled"] is True
        assert runtime["dry_run"] is True
        assert runtime["real_click_enabled"] is False
        assert runtime["path"]

        published = item["published"]
        assert published["exists"] is True
        assert published["schema_version"] == "action_runtime_plan_v1"
        assert published["source_action_decision_frame_id"] == runtime["source_action_decision_frame_id"]
        assert published["planned_action"] == runtime["planned_action"]
        assert published["target_sequence"] == runtime["target_sequence"]
        assert published["dry_run"] is True
        assert published["real_click_enabled"] is False
