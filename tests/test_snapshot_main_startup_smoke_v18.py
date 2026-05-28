import json
import subprocess
import sys


def test_snapshot_main_startup_smoke_runs_without_live_ui():
    completed = subprocess.run(
        [sys.executable, "tools/run_snapshot_main_startup_smoke.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_snapshot_main_startup_smoke_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False

    assert all(payload["display_checks"].values())
    assert all(payload["bridge_checks"].values())

    startup = payload["startup_audit"]
    assert startup["returncode"] == 0
    assert startup["startup_audit_only_seen"] is True
    assert startup["live_ui_skipped_seen"] is True
    assert startup["live_output_cleanup_seen"] is False
