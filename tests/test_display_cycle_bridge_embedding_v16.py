import json
import subprocess
import sys


def test_display_cycle_bridge_embedding_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_display_cycle_bridge_embedding_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_display_cycle_bridge_embedding_check_v1"
    assert payload["status"] == "ok"
    assert payload["missing"] == []
    assert payload["order_ok"] is True

    checks = payload["snippet_checks"]
    assert checks["bridge_import"] is True
    assert checks["bridge_call"] is True
    assert checks["contract_embedding"] is True
    assert checks["state_embedding"] is True

    runtime = payload["bridge_runtime_check"]
    assert runtime["ok"] is True
    assert runtime["status"] in {"ok", "fallback"}
    assert runtime["source_frame_id"] == "table_02_hand_29_preflop"
    assert runtime["click_sequence"] == ["Check"]
    assert runtime["file_publication_enabled"] is False
    assert runtime["path"] is None
