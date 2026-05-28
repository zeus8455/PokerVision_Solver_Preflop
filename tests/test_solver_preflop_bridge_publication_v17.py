import json
import subprocess
import sys
from pathlib import Path


DISPLAY_FILE = (
    Path("external")
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "display_analysis_cycle.py"
)


def test_display_cycle_has_publication_toggle():
    text = DISPLAY_FILE.read_text(encoding="utf-8")

    assert "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False" in text
    assert "publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES)" in text
    assert "publish_files=False,\n                            )\n                            if isinstance(action_decision_contract, dict):" not in text


def test_solver_preflop_bridge_publication_check_runs():
    completed = subprocess.run(
        [sys.executable, "tools/run_solver_preflop_bridge_publication_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_bridge_publication_check_v1"
    assert payload["status"] == "ok"
    assert payload["static_checks"]["toggle_present"] is True
    assert payload["static_checks"]["toggle_call_present"] is True

    runtime = payload["runtime_publication_check"]
    assert runtime["status"] == "ok"
    assert runtime["source_frame_id"] == "table_02_hand_29_preflop"
    assert runtime["engine_action"] == "check"
    assert runtime["click_sequence"] == ["Check"]
    assert runtime["file_publication_enabled"] is True
    assert runtime["published_exists"] is True
    assert runtime["published_schema"] == "pokervision_solver_preflop_bridge_v1"
    assert runtime["published_source_frame_id"] == "table_02_hand_29_preflop"
