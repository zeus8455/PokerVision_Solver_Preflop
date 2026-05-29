from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
V212_TOOL = PROJECT_ROOT / "tools" / "run_v2_12_snapshot_display_transaction_integration_audit.py"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(V212_TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode or 1

    report = json.loads(result.stdout)
    scenarios = {item["scenario"]: item for item in report["scenarios"]}

    completed_names = [
        "dry_run_completed_final_saved",
        "clicked_completed_final_saved",
    ]

    checks = {
        "v212_report_ok": report.get("status") == "ok",
        "completed_scenarios_present": all(name in scenarios for name in completed_names),
    }

    completed_reports = {}
    for name in completed_names:
        scenario = scenarios.get(name, {})
        contract = (
            scenario.get("dark_json", {})
            .get("clear_json_contract", {})
        )
        decision_contract = contract.get("decision_json_contract", {})
        action_contract = contract.get("action_decision_contract", {})
        runtime_contract = action_contract.get("action_runtime_plan_contract", {})

        error_text = json.dumps(contract, ensure_ascii=False)

        completed_reports[name] = {
            "final_clear_saved": scenario.get("final_clear_json", {}).get("exists") is True,
            "decision_json_status": decision_contract.get("status"),
            "decision_json_path": decision_contract.get("path"),
            "action_decision_status": action_contract.get("status"),
            "action_decision_path": action_contract.get("path"),
            "runtime_plan_status": runtime_contract.get("status"),
            "runtime_plan_path": runtime_contract.get("path"),
            "runtime_plan_publication_stage": runtime_contract.get("publication_stage"),
            "runtime_plan_file_publication_enabled": runtime_contract.get("file_publication_enabled"),
            "unexpected_keyword_error_absent": "unexpected keyword argument" not in error_text,
            "name_error_absent": "name 'solver_preflop_bridge_contract' is not defined" not in error_text,
            "solver_bridge_status": action_contract.get("solver_preflop_bridge_contract", {}).get("status"),
            "solver_bridge_reason": action_contract.get("solver_preflop_bridge_contract", {}).get("reason"),
            "runtime_source_selection": runtime_contract.get("v20_runtime_source_selection", {}),
        }

        checks[f"{name}_final_clear_saved"] = completed_reports[name]["final_clear_saved"]
        checks[f"{name}_decision_json_saved"] = completed_reports[name]["decision_json_status"] == "saved" and bool(completed_reports[name]["decision_json_path"])
        checks[f"{name}_action_decision_saved"] = completed_reports[name]["action_decision_status"] == "saved" and bool(completed_reports[name]["action_decision_path"])
        checks[f"{name}_runtime_plan_saved"] = completed_reports[name]["runtime_plan_status"] == "saved" and bool(completed_reports[name]["runtime_plan_path"])
        checks[f"{name}_runtime_plan_final_publication"] = completed_reports[name]["runtime_plan_publication_stage"] == "final"
        checks[f"{name}_runtime_plan_file_publication_enabled"] = completed_reports[name]["runtime_plan_file_publication_enabled"] is True
        checks[f"{name}_unexpected_keyword_error_absent"] = completed_reports[name]["unexpected_keyword_error_absent"]
        checks[f"{name}_name_error_absent"] = completed_reports[name]["name_error_absent"]

    report_out = {
        "schema": "pokervision_solver_preflop_v213_snapshot_final_action_publication_regression_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "source_tool": str(V212_TOOL),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "checks": checks,
        "completed_reports": completed_reports,
        "next_known_gap": {
            "status": "known_gap_for_v214",
            "reason": "Final Action_Runtime_Plan is now published, but final Solver_Preflop bridge may be skipped when Final Clear_JSON already contains click_result.",
        },
    }

    print(json.dumps(report_out, ensure_ascii=False, indent=2))
    return 0 if report_out["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
