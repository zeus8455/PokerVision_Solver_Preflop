from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v234_enable_raise_branch_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY = SNAPSHOT_ROOT / "display_analysis_cycle.py"
V11_RUNTIME = SNAPSHOT_ROOT / "runtime" / "v11_stage1_runtime.py"
BUILDER = SNAPSHOT_ROOT / "logic" / "action_runtime_plan_builder.py"

EXPECTED_CLICK_SEQUENCES: dict[str, list[str]] = {
    "open_raise": ["Raise"],
    "iso_raise": ["98%", "Raise"],
    "3bet": ["98%", "Raise"],
    "4bet": ["50%", "Raise"],
    "all_in": ["98%", "Raise"],
}


def _set_full_live_env() -> None:
    os.environ["POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"] = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK"] = "V3_1_ONE_CLICK"
    os.environ["POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"] = "table_01,table_02,table_03,table_04,table_05,table_06"
    os.environ.pop("POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN", None)


def _load_module(name: str, path: Path):
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _contract(raw_action: str, click_sequence: list[str], status: str = "ok") -> dict[str, Any]:
    return {
        "status": status,
        "raw_action": raw_action,
        "bridge_payload": {
            "decision_id": f"v234_{raw_action}_decision",
            "solver_fingerprint": f"v234_{raw_action}_fingerprint",
            "action_decision": {
                "status": "ok",
                "source": "PokerVision_Solver_Preflop",
                "decision_id": f"v234_{raw_action}_decision",
                "solver_fingerprint": f"v234_{raw_action}_fingerprint",
                "source_frame_id": f"v234_{raw_action}_frame",
                "raw_action": raw_action,
                "action": raw_action,
                "engine_action": raw_action,
                "size_pct": None,
                "reason": f"V2.34 synthetic raise branch case: {raw_action}",
                "click_sequence": list(click_sequence),
            },
        },
    }


def _default_action_decision() -> dict[str, Any]:
    return {
        "schema": "action_decision_v1",
        "status": "ok",
        "source": "Decision_JSON",
        "decision_id": "legacy_default_should_not_be_selected",
        "action": "check_fold",
        "target_button_classes": ["Check", "Check/fold", "FOLD"],
        "reason": "legacy default should be replaced by Solver_Preflop_Bridge",
    }


def build_report() -> dict[str, Any]:
    _set_full_live_env()

    display = _load_module("v234_display_analysis_cycle", DISPLAY)
    v11 = _load_module("v234_v11_stage1_runtime", V11_RUNTIME)

    cases: list[dict[str, Any]] = []
    for raw_action, expected_sequence in EXPECTED_CLICK_SEQUENCES.items():
        contract = _contract(raw_action, expected_sequence)
        selected_action_decision, selection = display._select_v20_runtime_action_decision_state(
            default_action_decision_state=_default_action_decision(),
            solver_preflop_bridge_contract=contract,
        )

        runtime_plan = display.build_action_runtime_plan_from_action_decision(selected_action_decision)
        runtime_plan_validation = display.validate_action_runtime_plan_contract(runtime_plan)

        extracted = v11._extract_solver_preflop_decision_from_state(
            full_state={
                "solver_preflop_bridge_contract": contract,
                "Total_pot": 10.0,
            },
            solver_payload={
                "table_id": "table_01",
                "hand_id": f"v234_{raw_action}",
                "frame_name": f"v234_{raw_action}_frame",
            },
            solver_payload_path=Path(f"solver_payloads/table_01/v234_{raw_action}.json"),
        )

        policy = runtime_plan.get("action_button_policy") if isinstance(runtime_plan.get("action_button_policy"), dict) else {}

        checks = {
            "selection_uses_solver_preflop": selection.get("selected_source") == "Solver_Preflop_Bridge",
            "selection_action_available": selection.get("solver_action_decision_available") is True,
            "v11_extracts_solver_decision": isinstance(extracted, dict) and extracted.get("source") == "PokerVision_Solver_Preflop",
            "v11_decision_id_not_stub": isinstance(extracted, dict) and not str(extracted.get("decision_id") or "").startswith("v12_stub_"),
            "runtime_plan_status_ok": runtime_plan.get("status") == "ok",
            "runtime_plan_validation_ok": bool(runtime_plan_validation.get("ok")),
            "planned_action_bet_raise": runtime_plan.get("planned_action") == "bet_raise",
            "raise_branch_enabled_true": runtime_plan.get("raise_branch_enabled") is True,
            "target_sequence_expected": runtime_plan.get("target_sequence") == expected_sequence,
            "target_button_classes_expected": runtime_plan.get("target_button_classes") == expected_sequence,
            "policy_ok_true": policy.get("ok") is True,
            "policy_selected_sequence_expected": policy.get("selected_sequence") == expected_sequence,
            "policy_no_blocked_reason": policy.get("blocked_reason") in (None, "", "None"),
            "plan_not_blocked_by_v1_1": runtime_plan.get("blocked_reason") in (None, "", "None"),
        }

        cases.append({
            "raw_action": raw_action,
            "expected_sequence": expected_sequence,
            "status": "ok" if all(checks.values()) else "failed",
            "selection": selection,
            "selected_action_decision": selected_action_decision,
            "runtime_plan": runtime_plan,
            "runtime_plan_validation": runtime_plan_validation,
            "v11_extracted_decision": extracted,
            "checks": checks,
        })

    text = BUILDER.read_text(encoding="utf-8", errors="replace")
    checks = {
        "builder_file_exists": BUILDER.exists(),
        "v234_marker_present": "V2.34: enable Solver_Preflop controlled bet_raise branch" in text,
        "all_cases_select_solver_preflop": all(c["checks"]["selection_uses_solver_preflop"] for c in cases),
        "all_cases_v11_extract_solver_decision": all(c["checks"]["v11_extracts_solver_decision"] for c in cases),
        "all_cases_v11_not_stub": all(c["checks"]["v11_decision_id_not_stub"] for c in cases),
        "all_cases_runtime_plan_ok": all(c["checks"]["runtime_plan_status_ok"] for c in cases),
        "all_cases_runtime_plan_validation_ok": all(c["checks"]["runtime_plan_validation_ok"] for c in cases),
        "all_cases_raise_branch_enabled": all(c["checks"]["raise_branch_enabled_true"] for c in cases),
        "all_cases_expected_sequence": all(c["checks"]["target_sequence_expected"] for c in cases),
        "all_cases_policy_ok": all(c["checks"]["policy_ok_true"] for c in cases),
        "no_case_blocked_by_v1_1": all(c["checks"]["plan_not_blocked_by_v1_1"] for c in cases),
    }

    return {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "real_project_touched": False,
        "physical_click_executed": False,
        "live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "checks": checks,
        "summary": [
            {
                "raw_action": c["raw_action"],
                "status": c["status"],
                "expected_sequence": c["expected_sequence"],
                "runtime_plan_status": c["runtime_plan"].get("status"),
                "planned_action": c["runtime_plan"].get("planned_action"),
                "raise_branch_enabled": c["runtime_plan"].get("raise_branch_enabled"),
                "target_sequence": c["runtime_plan"].get("target_sequence"),
                "blocked_reason": c["runtime_plan"].get("blocked_reason"),
                "policy_ok": (c["runtime_plan"].get("action_button_policy") or {}).get("ok")
                if isinstance(c["runtime_plan"].get("action_button_policy"), dict)
                else None,
                "policy_selected_sequence": (c["runtime_plan"].get("action_button_policy") or {}).get("selected_sequence")
                if isinstance(c["runtime_plan"].get("action_button_policy"), dict)
                else None,
                "v11_decision_id": (c["v11_extracted_decision"] or {}).get("decision_id")
                if isinstance(c["v11_extracted_decision"], dict)
                else None,
            }
            for c in cases
        ],
        "cases": cases,
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
