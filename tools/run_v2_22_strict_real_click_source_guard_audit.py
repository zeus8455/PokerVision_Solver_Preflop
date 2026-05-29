from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
CLICK_RUNTIME = SNAPSHOT_ROOT / "runtime" / "action_click_stub.py"


def main() -> int:
    text = CLICK_RUNTIME.read_text(encoding="utf-8")

    checks = {
        "captures_solver_source": 'solver_source = str(solver_decision.get("source") or "")' in text,
        "captures_solver_status": 'solver_status = str(solver_decision.get("status") or "")' in text,
        "blocks_non_solver_preflop_source": 'controlled_live_click_solver_source_not_solver_preflop' in text,
        "blocks_non_ok_solver_status": 'controlled_live_click_solver_status_not_ok' in text,
        "blocks_v12_stub_decision": 'controlled_live_click_stub_decision_blocked' in text,
        "blocks_v12_fallback_decision": 'controlled_live_click_fallback_decision_blocked' in text,
        "reports_solver_source": '"solver_source": solver_source' in text,
        "reports_solver_status": '"solver_status": solver_status' in text,
    }

    report = {
        "schema": "pokervision_solver_preflop_v222_strict_real_click_source_guard_audit_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "checks": checks,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
