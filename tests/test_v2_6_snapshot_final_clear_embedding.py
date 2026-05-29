import json
import subprocess
import sys


def test_v2_6_snapshot_final_clear_embedding_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_6_snapshot_final_clear_embedding_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v26_snapshot_final_clear_embedding_check_v1"
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
    assert payload["published_final_clear_files_count"] == payload["files_total"]

    assert payload["action_counts"].get("fold", 0) >= 1
    assert payload["action_counts"].get("check", 0) >= 1

    for item in payload["results"]:
        assert item["ok"] is True
        assert item["selected_source"] == "Solver_Preflop_Bridge"
        assert item["selection_reason"] == "v20_solver_preflop_selected"

        runtime = item["runtime_plan"]
        assert runtime["status"] == "saved"
        assert runtime["dry_run"] is True
        assert runtime["real_click_enabled"] is False
        assert runtime["target_sequence"]

        click = item["click_result"]
        assert click["status"] == "dry_run"
        assert click["reason"] == "all_click_execution_guards_passed"
        assert click["guard_passed"] is True
        assert click["click_completed_inferred"] is True
        assert click["dry_run"] is True
        assert click["real_click_enabled"] is False

        compact = item["compact_click_result"]
        assert set(compact.keys()) == {
            "status",
            "decision_id",
            "dry_run",
            "real_click_enabled",
        }
        assert "click_completed" not in compact
        assert compact["status"] == "dry_run"
        assert compact["dry_run"] is True
        assert compact["real_click_enabled"] is False

        final_clear = item["final_clear"]
        assert final_clear["validation"]["ok"] is True
        assert final_clear["exists"] is True
        assert final_clear["frame_id"] == item["source_frame_id"]
        assert final_clear["click_result"] == compact
        assert "click_completed" not in final_clear["click_result"]

        assert item["checks"]["runtime_ok"] is True
        assert item["checks"]["click_ok"] is True
        assert item["checks"]["compact_click_result_ok"] is True
        assert item["checks"]["final_validation_ok"] is True
        assert item["checks"]["final_saved_ok"] is True
        assert all(item["checks"].values())
