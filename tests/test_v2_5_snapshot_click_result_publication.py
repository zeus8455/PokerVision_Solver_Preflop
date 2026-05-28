import json
import subprocess
import sys


def test_v2_5_snapshot_click_result_publication_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_5_snapshot_click_result_publication_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v25_snapshot_click_result_publication_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["full_live_ui_executed"] is False
    assert payload["screen_capture_executed"] is False
    assert payload["yolo_detector_executed"] is False
    assert payload["physical_click_executed"] is False

    assert payload["files_total"] >= 4
    assert payload["bad_count"] == 0
    assert payload["ok_count"] == payload["files_total"]
    assert payload["published_runtime_files_count"] == payload["files_total"]
    assert payload["published_click_files_count"] == payload["files_total"]

    assert payload["action_counts"].get("fold", 0) >= 1
    assert payload["action_counts"].get("check", 0) >= 1

    for item in payload["results"]:
        assert item["ok"] is True
        assert item["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection_reason"] == "v20_solver_preflop_selected"

        runtime = item["runtime_plan"]
        assert runtime["status"] == "saved"
        assert runtime["exists"] is True
        assert runtime["dry_run"] is True
        assert runtime["real_click_enabled"] is False
        assert runtime["target_sequence"]

        click = item["click_result"]
        assert click["status"] == "dry_run"
        assert click["reason"] == "all_click_execution_guards_passed"
        assert click["exists"] is True
        assert click["guard_passed"] is True
        assert click["dry_run"] is True
        assert click["real_click_enabled"] is False
        assert click["published_status"] == "dry_run"
        assert click["published_reason"] == "all_click_execution_guards_passed"
        assert click["published_guard_passed"] is True

        real = item["forced_real_click_result"]
        assert real["status"] == "blocked"
        assert real["reason"] == "real_click_master_not_armed"
        assert real["guard_passed"] is False

        assert item["checks"]["runtime_ok"] is True
        assert item["checks"]["dry_run_guard_ok"] is True
        assert item["checks"]["click_published_ok"] is True
        assert item["checks"]["real_click_block_ok"] is True
        assert all(item["checks"].values())
