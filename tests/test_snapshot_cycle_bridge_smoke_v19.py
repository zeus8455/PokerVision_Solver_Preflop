import json
import subprocess
import sys


def test_snapshot_cycle_bridge_smoke_without_file_publication():
    completed = subprocess.run(
        [sys.executable, "tools/run_snapshot_cycle_bridge_smoke.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_snapshot_cycle_bridge_smoke_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False

    assert all(payload["static_checks"].values())
    assert payload["files_total"] >= 4
    assert payload["executable_count"] >= 4
    assert payload["bad_results_count"] == 0
    assert payload["publish_files"] is False

    for item in payload["results"]:
        assert item["has_bridge_payload"] is True
        assert item["has_runtime_plan_candidate"] is True
        assert item["has_action_decision"] is True
        assert item["runtime_plan_schema"] == "pokervision_action_runtime_plan_candidate_v1"
        assert item["action_decision_schema"] == "pokervision_action_decision_from_solver_preflop_v1"
        assert item["file_publication_enabled"] is False
        assert item["published_exists"] is False


def test_snapshot_cycle_bridge_smoke_with_file_publication():
    completed = subprocess.run(
        [sys.executable, "tools/run_snapshot_cycle_bridge_smoke.py", "--publish-files"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["status"] == "ok"
    assert payload["publish_files"] is True
    assert payload["publication_ok"] is True

    for item in payload["results"]:
        assert item["file_publication_enabled"] is True
        assert item["published_exists"] is True
        assert item["path"]
