from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

CONFIG_PATH = SNAPSHOT_ROOT / "config.py"
DISPLAY_PATH = SNAPSHOT_ROOT / "display_analysis_cycle.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)

    if spec.loader is None:
        raise RuntimeError(f"Could not load module: {path}")

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def get_value(module: Any, name: str) -> Any:
    return getattr(module, name, None)


def main() -> int:
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))

    config = load_module("v217_config", CONFIG_PATH)
    display = load_module("v217_display_analysis_cycle", DISPLAY_PATH)

    effective = {
        "V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE": get_value(config, "V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE"),
        "V11_REAL_MOUSE_CLICK_ENABLED": get_value(config, "V11_REAL_MOUSE_CLICK_ENABLED"),
        "V11_CLICK_DRY_RUN": get_value(config, "V11_CLICK_DRY_RUN"),
        "V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED": get_value(config, "V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED"),
        "V11_TRIGGER_UI_SERVICE_DRY_RUN": get_value(config, "V11_TRIGGER_UI_SERVICE_DRY_RUN"),
        "V09_REAL_CLICK_MASTER_ARMED": get_value(config, "V09_REAL_CLICK_MASTER_ARMED"),

        "V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED": get_value(config, "V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED"),
        "V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED": get_value(config, "V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED"),
        "V03_TRANSACTION_RELEASE_ON_INACTIVE": get_value(config, "V03_TRANSACTION_RELEASE_ON_INACTIVE"),

        "V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT": get_value(config, "V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT"),
        "V07_ACTION_RUNTIME_PLAN_ENABLED": get_value(config, "V07_ACTION_RUNTIME_PLAN_ENABLED"),

        "V09_REQUIRE_SLOT_BOUNDARY_GUARD": get_value(config, "V09_REQUIRE_SLOT_BOUNDARY_GUARD"),
        "V09_REQUIRE_NO_REPEAT_DECISION_GUARD": get_value(config, "V09_REQUIRE_NO_REPEAT_DECISION_GUARD"),
        "V09_REQUIRE_BUTTON_AVAILABILITY_GUARD": get_value(config, "V09_REQUIRE_BUTTON_AVAILABILITY_GUARD"),
        "V09_ALLOW_DRY_RUN_COMPLETION": get_value(config, "V09_ALLOW_DRY_RUN_COMPLETION"),
        "V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK": get_value(config, "V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK"),

        "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE": get_value(display, "V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE"),
        "V20_SOLVER_PREFLOP_DRY_RUN_ONLY": get_value(display, "V20_SOLVER_PREFLOP_DRY_RUN_ONLY"),
    }

    checks = {
        "live_data_capture_no_click_mode_enabled": effective["V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE"] is True,
        "action_button_real_click_disabled": effective["V11_REAL_MOUSE_CLICK_ENABLED"] is False,
        "action_button_dry_run_enabled": effective["V11_CLICK_DRY_RUN"] is True,
        "service_real_click_disabled": effective["V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED"] is False,
        "service_dry_run_enabled": effective["V11_TRIGGER_UI_SERVICE_DRY_RUN"] is True,
        "real_click_master_not_armed": effective["V09_REAL_CLICK_MASTER_ARMED"] is False,

        "transaction_gate_enabled": effective["V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED"] is True,
        "dry_run_counts_as_completed": effective["V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED"] is True,
        "transaction_releases_on_inactive": effective["V03_TRANSACTION_RELEASE_ON_INACTIVE"] is True,

        "final_clear_requires_click_result": effective["V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT"] is True,
        "runtime_plan_enabled": effective["V07_ACTION_RUNTIME_PLAN_ENABLED"] is True,

        "slot_boundary_guard_required": effective["V09_REQUIRE_SLOT_BOUNDARY_GUARD"] is True,
        "no_repeat_guard_required": effective["V09_REQUIRE_NO_REPEAT_DECISION_GUARD"] is True,
        "button_availability_guard_required": effective["V09_REQUIRE_BUTTON_AVAILABILITY_GUARD"] is True,
        "dry_run_completion_allowed": effective["V09_ALLOW_DRY_RUN_COMPLETION"] is True,
        "real_click_blocked_when_live_capture_no_click": effective["V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK"] is True,

        "solver_preflop_runtime_source_enabled": effective["V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE"] is True,
        "solver_preflop_dry_run_only": effective["V20_SOLVER_PREFLOP_DRY_RUN_ONLY"] is True,
    }

    report = {
        "schema": "pokervision_solver_preflop_v217_pre_live_config_audit_v1",
        "status": "ok" if all(checks.values()) else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "effective_config": effective,
        "checks": checks,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
