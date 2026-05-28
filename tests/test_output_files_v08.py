import json
import subprocess
import sys
from pathlib import Path

from solver_preflop import solve_clear_json
from solver_preflop.contracts import SOLVER_VERSION
from solver_preflop.output_files import write_solver_output_files


def _base_path() -> Path:
    return Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")


def _base_data():
    return json.loads(_base_path().read_text(encoding="utf-8"))


def test_write_solver_output_files(tmp_path):
    decision = solve_clear_json(_base_data())
    manifest = write_solver_output_files(decision, output_dir=tmp_path)

    decision_path = Path(manifest.solver_decision_json)
    action_path = Path(manifest.solver_action_decision_json)
    runtime_path = Path(manifest.solver_runtime_hint_json)
    bridge_path = Path(manifest.pokervision_bridge_json)

    assert decision_path.exists()
    assert action_path.exists()
    assert runtime_path.exists()
    assert bridge_path.exists()

    full = json.loads(decision_path.read_text(encoding="utf-8"))
    action = json.loads(action_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))

    assert full["solver"]["contract"] == "preflop_solver_response_v1"
    assert full["solver"]["version"] == SOLVER_VERSION

    assert action["schema"] == "pokervision_solver_action_decision_v1"
    assert action["source_frame_id"] == "table_02_hand_29_preflop_01"
    assert action["click_sequence"] == ["Check"]

    assert runtime["schema"] == "pokervision_solver_runtime_hint_json_v1"
    assert runtime["action_runtime_hint"]["target_buttons"] == ["Check"]
    assert runtime["safety"]["requires_pokervision_runtime_guards"] is True

    assert bridge["schema"] == "pokervision_solver_preflop_bridge_v1"
    assert bridge["runtime_plan_candidate"]["target_buttons"] == ["Check"]
    assert bridge["safety"]["must_pass_pokervision_guards"] is True


def test_cli_write_files(tmp_path):
    cmd = [
        sys.executable,
        "tools/solve_clear_json.py",
        str(_base_path()),
        "--write-files",
        "--out-dir",
        str(tmp_path),
    ]
    completed = subprocess.run(cmd, check=True, text=True, capture_output=True)
    payload = json.loads(completed.stdout)

    assert payload["status"] == "ok"
    files = payload["manifest"]["files"]
    assert Path(files["solver_decision_json"]).exists()
    assert Path(files["solver_action_decision_json"]).exists()
    assert Path(files["solver_runtime_hint_json"]).exists()
    assert Path(files["pokervision_bridge_json"]).exists()
