import json
import subprocess
import sys


def test_snapshot_clear_json_bridge_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_snapshot_clear_json_bridge_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_snapshot_clear_json_bridge_check_v1"
    assert payload["status"] == "ok"
    assert payload["files_total"] >= 1
    assert payload["executable_preflop_count"] >= 1
    assert int(payload["status_counts"].get("error", 0)) == 0
    assert payload["input_source"] in {
        "snapshot_clear_json_pending",
        "snapshot_clear_json_final",
        "examples_clear_json",
        "custom",
    }

    assert any("preflop" in item["file"].lower() for item in payload["results"])
    assert any(item["status"] in {"ok", "fallback"} for item in payload["results"])


def test_snapshot_clear_json_bridge_check_all_streets_mode_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_snapshot_clear_json_bridge_check.py", "--all-streets"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["status"] == "ok"
    assert payload["files_total"] >= 1
    assert payload["executable_preflop_count"] >= 1
    assert int(payload["status_counts"].get("error", 0)) == 0
