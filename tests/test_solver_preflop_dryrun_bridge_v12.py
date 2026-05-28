import importlib.util
import json
from pathlib import Path


def _load_bridge_module():
    path = (
        Path("external")
        / "PokerVisionFinalVersionNoSolver_snapshot"
        / "PokerVision V1_2"
        / "runtime"
        / "solver_preflop_dryrun_bridge.py"
    )
    spec = importlib.util.spec_from_file_location("solver_preflop_dryrun_bridge_v12", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _base_clear_json():
    path = Path("examples/clear_json/table_02_hand_29_preflop_01_preclick.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_bridge_skips_non_preflop():
    module = _load_bridge_module()
    data = _base_clear_json()
    data["street"] = "flop"

    contract = module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=data,
        cycle_dir=Path("tmp_test_cycle"),
        table_id="table_02",
        publish_files=False,
    )

    assert contract["status"] == "skipped"
    assert contract["reason"] == "street_is_not_preflop"


def test_bridge_runs_preflop_without_publishing_files(tmp_path):
    module = _load_bridge_module()
    data = _base_clear_json()

    contract = module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=data,
        cycle_dir=tmp_path,
        table_id="table_02",
        publish_files=False,
    )

    assert contract["status"] == "ok"
    assert contract["street"] == "preflop"
    assert contract["source_frame_id"] == "table_02_hand_29_preflop_01"
    assert contract["engine_action"] == "check"
    assert contract["click_sequence"] == ["Check"]
    assert contract["file_publication_enabled"] is False
    assert contract["path"] is None
    assert contract["bridge_payload"]["schema"] == "pokervision_solver_preflop_bridge_v1"
    assert contract["runtime_plan_candidate"]["requires_active_guard"] is True
    assert contract["safety"]["must_not_execute_directly"] is True


def test_bridge_skips_clear_json_with_click_result(tmp_path):
    module = _load_bridge_module()
    data = _base_clear_json()
    data["click_result"] = {"status": "clicked"}

    contract = module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=data,
        cycle_dir=tmp_path,
        table_id="table_02",
        publish_files=False,
    )

    assert contract["status"] == "skipped"
    assert contract["reason"] == "clear_json_already_has_click_result"
