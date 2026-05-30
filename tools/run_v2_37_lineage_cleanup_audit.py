from __future__ import annotations
import sys

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "tmp_solver_outputs" / "v2_37_lineage_cleanup_audit"


def _import_v236_tool():
    import importlib.util
    path = ROOT / "tools" / "run_v2_36_synthetic_clear_json_runtime_chain.py"
    spec = importlib.util.spec_from_file_location("v236_chain", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V2.36 tool from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _synthetic_action_decision(raw_action: str, runtime_action: str, size_pct: int | None) -> Dict[str, Any]:
    """Build a builder-valid Action_Decision_JSON carrying Solver_Preflop lineage.

    Important:
    - Action_Decision_JSON contract is legacy-level and validates action='raise', not action='bet_raise'.
    - action_runtime_plan_builder.normalize_action('raise') later produces planned_action='bet_raise'.
    - Solver_Preflop raw action is carried through decision_context for V2.34/V2.37 lineage.
    """
    from logic.action_decision_stub import V06_ACTION_DECISION_SCHEMA_VERSION

    public_action = "raise" if runtime_action == "bet_raise" else runtime_action

    size_policy = None
    if size_pct is not None:
        size_policy = {"type": "preset_pct", "value": str(size_pct), "unit": "pct"}

    if public_action == "fold":
        target_buttons = ["FOLD"]
    elif public_action == "call":
        target_buttons = ["Call"]
    elif public_action == "check":
        target_buttons = ["Check"]
    elif public_action == "check_fold":
        target_buttons = ["Check", "Check/fold", "FOLD"]
    elif public_action in {"bet", "raise"}:
        target_buttons = []
        if size_pct is not None:
            target_buttons.append(f"{size_pct}%")
        target_buttons.append("Bet/Raise")
    else:
        target_buttons = ["FOLD"]

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": f"v237_{raw_action}",
        "decision_id": f"v237_decision_{raw_action}",
        "status": "ok",
        "action": public_action,
        "size_policy": size_policy,
        "target_button_classes": target_buttons,
        "reason": f"v237_lineage_probe:{raw_action}",
        "dry_run_safe": True,
        "solver_stub": True,
        "decision_context": {
            "street": "preflop",
            "source_frame_id": f"v237_{raw_action}",
            "solver_preflop_runtime_source": True,
            "solver_source": "PokerVision_Solver_Preflop",
            "solver_status": "ok",
            "solver_raw_action": raw_action,
            "solver_engine_action": "raise" if runtime_action == "bet_raise" else runtime_action,
            "solver_action": runtime_action,
            "solver_fingerprint": f"v237_fp_{raw_action}",
            "runtime_source_selection": "Solver_Preflop_Bridge",
        },
    }


def _runtime_plan_lineage_probe() -> List[Dict[str, Any]]:
    snapshot = ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
    if str(snapshot) not in sys.path:
        sys.path.insert(0, str(snapshot))
    from logic.action_runtime_plan_builder import build_action_runtime_plan_from_action_decision  # type: ignore

    cases = [
        ("open_raise", "bet_raise", None, ["Raise"]),
        ("iso_raise", "bet_raise", 98, ["98%", "Raise"]),
        ("4bet", "bet_raise", 50, ["50%", "Raise"]),
        ("5bet", "bet_raise", 50, ["50%", "Raise"]),
        ("fold", "fold", None, ["FOLD"]),
    ]
    out: List[Dict[str, Any]] = []
    for raw_action, runtime_action, size_pct, expected_sequence in cases:
        plan = build_action_runtime_plan_from_action_decision(_synthetic_action_decision(raw_action, runtime_action, size_pct))
        lineage = plan.get("lineage") if isinstance(plan.get("lineage"), dict) else {}
        ok = (
            plan.get("decision_id") == f"v237_decision_{raw_action}"
            and plan.get("solver_source") == "PokerVision_Solver_Preflop"
            and plan.get("solver_raw_action") == raw_action
            and lineage.get("selected_source") == "Solver_Preflop_Bridge"
            and lineage.get("runtime_action") == runtime_action
            and plan.get("target_sequence") == expected_sequence
        )
        out.append(
            {
                "raw_action": raw_action,
                "runtime_action": runtime_action,
                "expected_sequence": expected_sequence,
                "target_sequence": plan.get("target_sequence"),
                "decision_id": plan.get("decision_id"),
                "solver_source": plan.get("solver_source"),
                "solver_raw_action": plan.get("solver_raw_action"),
                "lineage_selected_source": lineage.get("selected_source"),
                "lineage_runtime_action": lineage.get("runtime_action"),
                "ok": ok,
            }
        )
    return out


def _run_runtime_lineage_probe(out_dir: Path) -> List[Dict[str, Any]]:
    v236 = _import_v236_tool()
    click_stub, bridge_mod, v11_runtime = v236._import_runtime_modules()
    cases = [c for c in v236._load_cases() if c.get("kind") == "positive"]
    results: List[Dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id"))
        table_id = str(case.get("table_id") or "table_01")
        clear_state = copy.deepcopy(case.get("clear_json") or {})
        frame_id = str(clear_state.get("frame_id") or case_id)
        case_dir = out_dir / "runtime_cases" / v236._safe_name(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        bridge = bridge_mod.build_solver_preflop_dryrun_bridge_contract(
            clear_state=clear_state,
            cycle_dir=case_dir,
            table_id=table_id,
            publish_files=True,
        )
        buttons = v236._base_buttons()
        slot = v236._Slot(table_id=table_id, bbox=v236._BBox(0, 0, 900, 700))
        mouse_calls: List[List[Dict[str, Any]]] = []

        def _mouse_spy(click_points: List[Dict[str, Any]]) -> Dict[str, Any]:
            mouse_calls.append(click_points)
            return {"status": "executed_by_v2_37_test_spy", "click_points_count": len(click_points)}

        full_state = {
            "table": {"table_id": table_id, "hand_id": frame_id, "frame_name": frame_id, "processing_time_ms": 1},
            "pipeline_meta": {"status": "ok", "processing_time_ms": 1},
            "solver_preflop_bridge_contract": bridge,
            "v2_37_synthetic_lineage_probe": clear_state,
        }

        original_mouse = click_stub.execute_click_points_human_like
        original_payload = v11_runtime.build_and_save_solver_payload
        original_button_pipeline = v11_runtime.run_action_button_pipeline
        original_status_update = v11_runtime.update_table_runtime_status
        v236._reset_click_runtime_state(click_stub)
        click_stub.execute_click_points_human_like = _mouse_spy
        v11_runtime.build_and_save_solver_payload = v236._fake_solver_payload_builder(case_dir)
        v11_runtime.run_action_button_pipeline = v236._fake_action_button_pipeline(buttons)
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

        solver = runtime_report.get("solver") if isinstance(runtime_report.get("solver"), dict) else {}
        click = runtime_report.get("click") if isinstance(runtime_report.get("click"), dict) else {}
        lineage = runtime_report.get("runtime_lineage") if isinstance(runtime_report.get("runtime_lineage"), dict) else {}
        ok = (
            runtime_report.get("runtime_lineage") is not None
            and lineage.get("source") == "PokerVision_Solver_Preflop"
            and lineage.get("selected_source") == "Solver_Preflop_Bridge"
            and lineage.get("decision_id") == solver.get("decision_id") == click.get("decision_id")
            and lineage.get("solver_raw_action") == solver.get("raw_action") == bridge.get("raw_action")
            and lineage.get("runtime_action") == solver.get("action")
            and lineage.get("click_status") == "clicked"
            and lineage.get("click_completed") is True
            and click.get("solver_source") == "PokerVision_Solver_Preflop"
            and click.get("solver_raw_action") == solver.get("raw_action")
            and bool(mouse_calls)
        )
        results.append(
            {
                "case_id": case_id,
                "raw_action": bridge.get("raw_action"),
                "runtime_action": solver.get("action"),
                "click_status": click.get("status"),
                "target_sequence": click.get("target_sequence"),
                "decision_id": solver.get("decision_id"),
                "runtime_lineage": lineage,
                "click_lineage": {
                    "solver_source": click.get("solver_source"),
                    "solver_raw_action": click.get("solver_raw_action"),
                    "solver_engine_action": click.get("solver_engine_action"),
                    "solver_fingerprint": click.get("solver_fingerprint"),
                    "source_frame_id": click.get("source_frame_id"),
                },
                "mouse_spy_called": bool(mouse_calls),
                "ok": ok,
            }
        )
    return results


def run_audit(out_dir: Path = DEFAULT_OUT_DIR) -> Dict[str, Any]:
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime_results = _run_runtime_lineage_probe(out_dir)
    plan_results = _runtime_plan_lineage_probe()
    return {
        "schema_version": "v2_37_lineage_cleanup_audit_report_v1",
        "ok": all(bool(x.get("ok")) for x in runtime_results) and all(bool(x.get("ok")) for x in plan_results),
        "project_root": str(ROOT),
        "out_dir": str(out_dir),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "runtime_lineage_results": runtime_results,
        "runtime_plan_lineage_results": plan_results,
    }


def _print_table(report: Dict[str, Any]) -> None:
    print("RUNTIME LINEAGE")
    print("CASE                              RAW_ACTION   RUNTIME     CLICK    LINEAGE_SOURCE             DECISION_LINK  OK")
    print("-" * 122)
    for item in report["runtime_lineage_results"]:
        lin = item.get("runtime_lineage") if isinstance(item.get("runtime_lineage"), dict) else {}
        decision_link = item.get("decision_id") == lin.get("decision_id")
        print(
            f"{item['case_id']:<33} {str(item.get('raw_action')):<12} {str(item.get('runtime_action')):<11} "
            f"{str(item.get('click_status')):<8} {str(lin.get('source')):<26} {str(decision_link):<13} {item.get('ok')}"
        )
    print("\nRUNTIME PLAN LINEAGE")
    print("RAW_ACTION   RUNTIME     SEQUENCE                 SOURCE                    OK")
    print("-" * 90)
    for item in report["runtime_plan_lineage_results"]:
        seq = " -> ".join(str(x) for x in item.get("target_sequence") or [])
        print(
            f"{str(item.get('raw_action')):<12} {str(item.get('runtime_action')):<11} {seq:<24} "
            f"{str(item.get('solver_source')):<25} {item.get('ok')}"
        )
    print("-" * 122)
    print(f"V2.37_LINEAGE_CLEANUP_AUDIT_OK = {bool(report.get('ok'))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="V2.37 Solver_Preflop lineage cleanup audit.")
    parser.add_argument("--report-json", default="", help="Optional path to write report JSON.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Synthetic output directory.")
    args = parser.parse_args()
    report = run_audit(Path(args.out_dir))
    _print_table(report)
    if args.report_json:
        p = Path(args.report_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report_json={p}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
