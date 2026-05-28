import json
import subprocess
import sys
from pathlib import Path


DISPLAY = (
    Path("external")
    / "PokerVisionFinalVersionNoSolver_snapshot"
    / "PokerVision V1_2"
    / "display_analysis_cycle.py"
)


def test_v2_0_runtime_source_switch_is_present_and_embedded():
    text = DISPLAY.read_text(encoding="utf-8")

    assert "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True" in text
    assert "V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True" in text
    assert "def _select_v20_runtime_action_decision_state(" in text

    assert "solver_preflop_bridge_contract: Optional[Dict[str, object]] = None" in text
    assert "action_decision_state=runtime_action_decision_state" in text
    assert '"v20_runtime_source_selection": dict(v20_runtime_source_selection)' in text
    assert "solver_preflop_bridge_contract=solver_preflop_bridge_contract" in text


def test_v2_0_runtime_source_switch_check_runs_without_nested_pytest():
    completed = subprocess.run(
        [sys.executable, "tools/run_v2_0_snapshot_runtime_source_switch_check.py"],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["schema"] == "pokervision_solver_preflop_v20_snapshot_runtime_source_switch_check_v1"
    assert payload["status"] == "ok"
    assert payload["real_project_touched"] is False
    assert payload["nested_pytest_executed"] is False
    assert payload["missing"] == []
    assert all(payload["checks"].values())
