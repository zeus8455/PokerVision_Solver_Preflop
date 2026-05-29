from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
V213_TOOL = PROJECT_ROOT / "tools" / "run_v2_13_snapshot_final_action_publication_regression.py"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(V213_TOOL)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode or 1

    source_report = json.loads(result.stdout)
    completed_reports = source_report.get("completed_reports", {})

    expected_names = {
        "dry_run_completed_final_saved",
        "clicked_completed_final_saved",
    }

    checks = {
        "source_report_ok": source_report.get("status") == "ok",
        "completed_reports_present": set(completed_reports) == expected_names,
    }

    final_source_reports = {}
    for name in sorted(expected_names):
        item = completed_reports.get(name, {})
        selection = item.get("runtime_source_selection", {})

        final_source_reports[name] = {
            "solver_bridge_status": item.get("solver_bridge_status"),
            "solver_bridge_reason": item.get("solver_bridge_reason"),
            "runtime_selected_source": selection.get("selected_source"),
            "runtime_selection_reason": selection.get("reason"),
            "solver_action_decision_available": selection.get("solver_action_decision_available"),
            "adapted_to_legacy_action_decision": selection.get("adapted_to_legacy_action_decision"),
            "decision_id": selection.get("decision_id"),
            "solver_fingerprint": selection.get("solver_fingerprint"),
            "source_frame_id": selection.get("source_frame_id"),
            "runtime_plan_status": item.get("runtime_plan_status"),
            "runtime_plan_publication_stage": item.get("runtime_plan_publication_stage"),
            "runtime_plan_file_publication_enabled": item.get("runtime_plan_file_publication_enabled"),
        }

        checks[f"{name}_solver_bridge_ok"] = item.get("solver_bridge_status") == "ok"
        checks[f"{name}_solver_bridge_not_skipped"] = item.get("solver_bridge_reason") != "clear_json_already_has_click_result"
        checks[f"{name}_runtime_selected_solver_preflop"] = selection.get("selected_source") == "Solver_Preflop_Bridge"
        checks[f"{name}_runtime_selection_reason"] = selection.get("reason") == "v20_solver_preflop_selected"
        checks[f"{name}_solver_action_decision_available"] = selection.get("solver_action_decision_available") is True
        checks[f"{name}_adapted_to_legacy_action_decision"] = selection.get("adapted_to_legacy_action_decision") is True
        checks[f"{name}_decision_id_present"] = bool(selection.get("decision_id"))
        checks[f"{name}_solver_fingerprint_present"] = bool(selection.get("solver_fingerprint"))
        checks[f"{name}_source_frame_id_present"] = bool(selection.get("source_frame_id"))
        checks[f"{name}_runtime_plan_saved"] = item.get("runtime_plan_status") == "saved"
        checks[f"{name}_runtime_plan_final"] = item.get("runtime_plan_publication_stage") == "final"
        checks[f"{name}_runtime_plan_file_enabled"] = item.get("runtime_plan_file_publication_enabled") is True

    report = {
        "schema": "pokervision_solver_preflop_v214_snapshot_final_solver_source_regression_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "source_tool": str(V213_TOOL),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "checks": checks,
        "final_source_reports": final_source_reports,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
