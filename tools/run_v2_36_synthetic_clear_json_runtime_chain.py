from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
FIXTURE = ROOT / "tests" / "fixtures" / "v2_36_synthetic_clear_json_chain" / "cases.json"
DEFAULT_OUT_DIR = ROOT / "tmp_solver_outputs" / "v2_36_synthetic_clear_json_runtime_chain"


def _configure_live_env() -> None:
    """Load config.py in the same guarded real-click profile used for V2.35.

    Mouse is still not used: execute_click_points_human_like is replaced with a spy.
    """
    os.environ["POKERVISION_CONTROLLED_LIVE_READY_PROFILE"] = "V8_1_CONTROLLED_ACTION_BUTTON"
    os.environ["POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"] = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK"] = "V3_1_ONE_CLICK"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"] = "table_01,table_02,table_03,table_04,table_05,table_06"
    os.environ.pop("POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN", None)


@dataclass
class _BBox:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class _Slot:
    table_id: str
    bbox: _BBox


class _FakeActionButtonResult:
    def __init__(self, best_by_class: Dict[str, Dict[str, Any]]) -> None:
        self.status = "ok"
        self.best_by_class = best_by_class
        self.detected_classes = list(best_by_class.keys())
        self.raw_detection_count = len(best_by_class)
        self.processing_time_ms = 1
        self.warnings: List[str] = []
        self.errors: List[str] = []


def _base_buttons() -> Dict[str, Dict[str, Any]]:
    return {
        "FOLD": {"bbox_xyxy": [80, 610, 185, 660], "confidence": 0.99},
        "33%": {"bbox_xyxy": [230, 560, 315, 605], "confidence": 0.99},
        "50%": {"bbox_xyxy": [330, 560, 415, 605], "confidence": 0.99},
        "70%": {"bbox_xyxy": [430, 560, 515, 605], "confidence": 0.99},
        "98%": {"bbox_xyxy": [530, 560, 615, 605], "confidence": 0.99},
        "Call": {"bbox_xyxy": [300, 610, 420, 660], "confidence": 0.99},
        "Check/fold": {"bbox_xyxy": [80, 555, 205, 600], "confidence": 0.99},
        "Check": {"bbox_xyxy": [300, 555, 420, 600], "confidence": 0.99},
        "Bet/Raise": {"bbox_xyxy": [625, 610, 785, 660], "confidence": 0.99},
    }


def _load_cases() -> List[Dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("V2.36 fixture must contain non-empty cases list.")
    return cases


def _import_runtime_modules():
    _configure_live_env()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(SNAPSHOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT))
    import runtime.action_click_stub as click_stub  # type: ignore
    import runtime.solver_preflop_dryrun_bridge as bridge_mod  # type: ignore
    import runtime.v11_stage1_runtime as v11_runtime  # type: ignore
    return click_stub, bridge_mod, v11_runtime


def _safe_name(value: Any, fallback: str = "v2_36_case") -> str:
    raw = str(value or fallback).strip() or fallback
    out = []
    for ch in raw:
        out.append(ch if ch.isalnum() or ch in {"_", "-", "."} else "_")
    return "".join(out).strip("._") or fallback


def _fake_solver_payload_builder(out_dir: Path):
    def _build_and_save_solver_payload(full_state: Dict[str, Any], cycle_dir: Path | None = None) -> Tuple[Dict[str, Any], Path]:
        table = full_state.get("table") if isinstance(full_state, dict) else {}
        if not isinstance(table, dict):
            table = {}
        table_id = str(table.get("table_id") or "table_01")
        frame_name = str(table.get("frame_name") or table.get("hand_id") or "v2_36_unknown_preflop")
        hand_id = str(table.get("hand_id") or frame_name)
        payload = {
            "schema_version": "v2_36_synthetic_solver_payload_stub",
            "table_id": table_id,
            "hand_id": hand_id,
            "frame_name": frame_name,
            "street": "preflop",
            "source": "v2_36_synthetic_clear_json_runtime_chain",
        }
        root = cycle_dir or out_dir
        path = root / "Solver_Payload_JSON" / table_id / (_safe_name(frame_name) + ".solver_payload.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload, path

    return _build_and_save_solver_payload


def _fake_action_button_pipeline(buttons: Dict[str, Dict[str, Any]]):
    def _run_action_button_pipeline(*, table_roi_image: Any, active_confirmed: bool) -> _FakeActionButtonResult:
        return _FakeActionButtonResult(buttons)

    return _run_action_button_pipeline


def _reset_click_runtime_state(click_stub: Any) -> None:
    if hasattr(click_stub, "_EXECUTED_DECISION_AT"):
        click_stub._EXECUTED_DECISION_AT.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_DECISION_IDS.clear()
    if hasattr(click_stub, "_CONTROLLED_LIVE_CLICK_EXECUTED_COUNT"):
        click_stub._CONTROLLED_LIVE_CLICK_EXECUTED_COUNT = 0


def _compact_click_result(click: Dict[str, Any]) -> Dict[str, Any]:
    gate = click.get("controlled_live_click_gate") if isinstance(click.get("controlled_live_click_gate"), dict) else {}
    return {
        "status": click.get("status"),
        "reason": click.get("reason"),
        "message": click.get("message"),
        "action": click.get("action"),
        "target_sequence": list(click.get("target_sequence") or []),
        "decision_id": click.get("decision_id"),
        "guard_passed": bool(click.get("guard_passed")),
        "dry_run": bool(click.get("dry_run")),
        "real_click_enabled": bool(click.get("real_click_enabled")),
        "controlled_live_click_gate_status": gate.get("status"),
    }


def _write_final_publication_candidate(*, out_dir: Path, table_id: str, clear_state: Dict[str, Any], runtime_report: Dict[str, Any]) -> Dict[str, Any]:
    click = runtime_report.get("click") if isinstance(runtime_report.get("click"), dict) else {}
    if click.get("status") != "clicked" or not bool(click.get("guard_passed")):
        return {
            "status": "skipped",
            "reason": "click_not_completed",
            "saved_final_clear": False,
            "saved_json_complete": False,
            "click_status": click.get("status"),
        }

    frame_id = str(clear_state.get("frame_id") or runtime_report.get("frame_name") or "v2_36_unknown_preflop")
    final_clear = copy.deepcopy(clear_state)
    final_clear["click_result"] = _compact_click_result(click)
    final_clear["v2_36_synthetic_publication"] = {
        "source": "v2_36_synthetic_clear_json_runtime_chain",
        "runtime_schema_version": runtime_report.get("schema_version"),
        "solver_source": (runtime_report.get("solver") or {}).get("source") if isinstance(runtime_report.get("solver"), dict) else None,
        "solver_action": (runtime_report.get("solver") or {}).get("action") if isinstance(runtime_report.get("solver"), dict) else None,
    }

    final_path = out_dir / "Final_Clear_JSON" / table_id / (_safe_name(frame_id) + ".json")
    complete_path = out_dir / "JSON_Complete" / table_id / (_safe_name(frame_id) + ".json")
    for path in (final_path, complete_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(final_clear, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": "saved",
        "saved_final_clear": final_path.exists(),
        "saved_json_complete": complete_path.exists(),
        "final_clear_path": str(final_path),
        "json_complete_path": str(complete_path),
        "click_status": click.get("status"),
        "saved_click_result_status": final_clear["click_result"].get("status"),
        "saved_target_sequence": final_clear["click_result"].get("target_sequence"),
    }


def _run_case(case: Dict[str, Any], *, out_dir: Path, click_stub: Any, bridge_mod: Any, v11_runtime: Any) -> Dict[str, Any]:
    case_id = str(case.get("case_id") or "unknown_case")
    table_id = str(case.get("table_id") or "table_01")
    clear_state = copy.deepcopy(case.get("clear_json") or {})
    frame_id = str(clear_state.get("frame_id") or case_id)

    case_dir = out_dir / "cases" / _safe_name(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)

    bridge = bridge_mod.build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_state,
        cycle_dir=case_dir,
        table_id=table_id,
        publish_files=True,
    )

    result: Dict[str, Any] = {
        "case_id": case_id,
        "kind": case.get("kind"),
        "table_id": table_id,
        "frame_id": frame_id,
        "bridge_status": bridge.get("status"),
        "bridge_reason": bridge.get("reason"),
        "bridge_raw_action": bridge.get("raw_action"),
        "bridge_engine_action": bridge.get("engine_action"),
        "bridge_click_sequence": bridge.get("click_sequence"),
        "bridge_decision_id": bridge.get("decision_id"),
        "runtime_called": False,
        "runtime": None,
        "final_publication": None,
    }

    if case.get("expect_runtime_called") is False or bridge.get("status") == "skipped":
        result["ok"] = _case_ok(case, result)
        return result

    buttons = _base_buttons()
    for missing in case.get("missing_buttons", []) or []:
        buttons.pop(str(missing), None)

    slot = _Slot(table_id=table_id, bbox=_BBox(0, 0, 900, 700))
    mouse_calls: List[List[Dict[str, Any]]] = []

    def _mouse_spy(click_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        mouse_calls.append(click_points)
        return {
            "status": "executed_by_v2_36_test_spy",
            "physical_mouse_was_not_used": True,
            "click_points_count": len(click_points),
        }

    full_state = {
        "table": {
            "table_id": table_id,
            "hand_id": frame_id,
            "frame_name": frame_id,
            "processing_time_ms": 1,
        },
        "pipeline_meta": {
            "status": "ok",
            "processing_time_ms": 1,
        },
        "solver_preflop_bridge_contract": bridge,
        "v2_36_synthetic_clear_json": clear_state,
    }

    original_mouse = click_stub.execute_click_points_human_like
    original_payload = v11_runtime.build_and_save_solver_payload
    original_button_pipeline = v11_runtime.run_action_button_pipeline
    original_status_update = v11_runtime.update_table_runtime_status

    _reset_click_runtime_state(click_stub)
    click_stub.execute_click_points_human_like = _mouse_spy
    v11_runtime.build_and_save_solver_payload = _fake_solver_payload_builder(case_dir)
    v11_runtime.run_action_button_pipeline = _fake_action_button_pipeline(buttons)
    v11_runtime.update_table_runtime_status = lambda *args, **kwargs: None
    try:
        runtime_report = v11_runtime.run_v11_stage1_runtime(
            full_state=full_state,
            table_roi_image=None,
            slot=slot,
            active_confirmed=True,
            cycle_dir=case_dir,
        )
    finally:
        click_stub.execute_click_points_human_like = original_mouse
        v11_runtime.build_and_save_solver_payload = original_payload
        v11_runtime.run_action_button_pipeline = original_button_pipeline
        v11_runtime.update_table_runtime_status = original_status_update

    click = runtime_report.get("click") if isinstance(runtime_report.get("click"), dict) else {}
    solver = runtime_report.get("solver") if isinstance(runtime_report.get("solver"), dict) else {}
    gate = click.get("controlled_live_click_gate") if isinstance(click.get("controlled_live_click_gate"), dict) else {}
    final_publication = _write_final_publication_candidate(
        out_dir=case_dir,
        table_id=table_id,
        clear_state=clear_state,
        runtime_report=runtime_report,
    )

    result.update(
        {
            "runtime_called": True,
            "runtime": {
                "schema_version": runtime_report.get("schema_version"),
                "solver_source": solver.get("source"),
                "solver_status": solver.get("status"),
                "solver_action": solver.get("action"),
                "solver_raw_action": solver.get("raw_action"),
                "solver_size_pct": solver.get("size_pct"),
                "solver_decision_id": solver.get("decision_id"),
                "action_button_status": (runtime_report.get("action_buttons") or {}).get("status") if isinstance(runtime_report.get("action_buttons"), dict) else None,
                "detected_classes": (runtime_report.get("action_buttons") or {}).get("detected_classes") if isinstance(runtime_report.get("action_buttons"), dict) else [],
                "click_status": click.get("status"),
                "click_message": click.get("message"),
                "click_target_sequence": click.get("target_sequence"),
                "click_guard_passed": bool(click.get("guard_passed")),
                "gate_status": gate.get("status"),
                "gate_blockers": gate.get("blockers", []),
                "mouse_spy_called": bool(mouse_calls),
                "mouse_spy_call_count": len(mouse_calls),
            },
            "final_publication": final_publication,
        }
    )
    result["ok"] = _case_ok(case, result)
    return result


def _case_ok(case: Dict[str, Any], result: Dict[str, Any]) -> bool:
    expected_bridge_status = case.get("expected_bridge_status")
    if expected_bridge_status and result.get("bridge_status") != expected_bridge_status:
        return False

    expected_bridge_reason = case.get("expected_bridge_reason")
    if expected_bridge_reason and result.get("bridge_reason") != expected_bridge_reason:
        return False

    if case.get("expect_runtime_called") is False:
        return result.get("runtime_called") is False

    runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
    final_publication = result.get("final_publication") if isinstance(result.get("final_publication"), dict) else {}

    expected_raw = case.get("expected_raw_action")
    if expected_raw and result.get("bridge_raw_action") != expected_raw:
        return False

    expected_runtime_action = case.get("expected_runtime_action")
    if expected_runtime_action and runtime.get("solver_action") != expected_runtime_action:
        return False

    expected_click_status = case.get("expected_click_status")
    if expected_click_status and runtime.get("click_status") != expected_click_status:
        return False

    expected_sequence = case.get("expected_target_sequence")
    if expected_sequence is not None and runtime.get("click_target_sequence") != expected_sequence:
        return False

    if bool(runtime.get("mouse_spy_called")) != bool(case.get("expect_mouse_spy_called", False)):
        return False

    if bool(final_publication.get("saved_final_clear")) != bool(case.get("expect_final_clear_saved", False)):
        return False

    if case.get("expect_final_clear_saved") and final_publication.get("saved_click_result_status") != "clicked":
        return False

    if case.get("kind") == "positive":
        if runtime.get("solver_source") != "PokerVision_Solver_Preflop":
            return False
        if runtime.get("gate_status") != "CONTROLLED_LIVE_CLICK_GATE_PASSED":
            return False
        if runtime.get("click_guard_passed") is not True:
            return False

    return True


def run_audit(out_dir: Path = DEFAULT_OUT_DIR) -> Dict[str, Any]:
    click_stub, bridge_mod, v11_runtime = _import_runtime_modules()
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [
        _run_case(case, out_dir=out_dir, click_stub=click_stub, bridge_mod=bridge_mod, v11_runtime=v11_runtime)
        for case in _load_cases()
    ]
    return {
        "schema_version": "v2_36_synthetic_clear_json_runtime_chain_report",
        "ok": all(bool(item.get("ok")) for item in results),
        "project_root": str(ROOT),
        "snapshot_root": str(SNAPSHOT),
        "out_dir": str(out_dir),
        "cases_total": len(results),
        "cases_passed": sum(1 for item in results if item.get("ok")),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "results": results,
    }


def _print_table(report: Dict[str, Any]) -> None:
    print("CASE                              BRIDGE   RAW_ACTION   RUNTIME     CLICK    SEQUENCE                 FINAL  SPY  OK")
    print("-" * 132)
    for item in report["results"]:
        runtime = item.get("runtime") if isinstance(item.get("runtime"), dict) else {}
        final = item.get("final_publication") if isinstance(item.get("final_publication"), dict) else {}
        seq = " -> ".join(str(x) for x in runtime.get("click_target_sequence") or [])
        print(
            f"{item['case_id']:<33} {str(item.get('bridge_status')):<8} {str(item.get('bridge_raw_action')):<12} "
            f"{str(runtime.get('solver_action')):<11} {str(runtime.get('click_status')):<8} {seq:<24} "
            f"{str(final.get('status')):<6} {str(runtime.get('mouse_spy_called')):<4} {item.get('ok')}"
        )
        blockers = runtime.get("gate_blockers") or []
        if blockers:
            print(f"  blockers: {blockers}")
        if runtime.get("click_message") and runtime.get("click_status") != "clicked":
            print(f"  message: {runtime.get('click_message')}")
    print("-" * 132)
    print(f"V2.36_SYNTHETIC_CLEAR_JSON_RUNTIME_CHAIN_OK = {bool(report.get('ok'))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="V2.36 synthetic Clear_JSON -> Solver_Preflop bridge -> v11 runtime -> click spy E2E.")
    parser.add_argument("--report-json", default="", help="Optional path to write full JSON report.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Synthetic output directory.")
    args = parser.parse_args()

    report = run_audit(out_dir=Path(args.out_dir))
    _print_table(report)

    if args.report_json:
        path = Path(args.report_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report_json={path}")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
