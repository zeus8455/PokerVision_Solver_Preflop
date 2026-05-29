from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

CONFIG_PATH = SNAPSHOT_ROOT / "config.py"
RUNTIME_PATH = SNAPSHOT_ROOT / "runtime" / "v11_stage1_runtime.py"
V219_TOOL_PATH = PROJECT_ROOT / "tools" / "run_v2_19_live_no_click_capture_probe.py"
V220_TOOL_PATH = PROJECT_ROOT / "tools" / "run_v2_20_real_live_startup_readiness.py"


def main() -> int:
    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    runtime_text = RUNTIME_PATH.read_text(encoding="utf-8")
    v219_text = V219_TOOL_PATH.read_text(encoding="utf-8")
    v220_text = V220_TOOL_PATH.read_text(encoding="utf-8")

    checks = {
        "v87_full_scope_sets_action_button_only_false": "V31_CONTROLLED_LIVE_CLICK_ACTION_BUTTON_ONLY = False" in config_text,
        "v87_full_scope_sets_simple_actions_only_false": "V31_CONTROLLED_LIVE_CLICK_SIMPLE_ACTIONS_ONLY = False" in config_text,
        "v87_full_scope_enables_raise_branch": "V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED = True" in config_text,
        "v87_full_scope_no_limit_clicks": "V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN = 0" in config_text,
        "v87_full_scope_allows_raise_actions": '"open_raise"' in config_text and '"3bet"' in config_text and '"4bet"' in config_text and '"all_in"' in config_text,
        "v87_full_scope_allows_raise_buttons": '"Raise"' in config_text and '"98%"' in config_text and '"50%"' in config_text,

        "runtime_imports_real_click_flags": "V09_REAL_CLICK_MASTER_ARMED" in runtime_text and "V11_REAL_MOUSE_CLICK_ENABLED" in runtime_text and "V11_CLICK_DRY_RUN" in runtime_text,
        "runtime_detects_real_click_mode": "real_click_mode = (" in runtime_text,
        "runtime_blocks_stub_status": 'stub_status == "stub"' in runtime_text,
        "runtime_blocks_v12_stub_decision_id": 'stub_decision_id.startswith("v12_stub_")' in runtime_text,
        "runtime_block_reason_present": "v21_stub_decision_cannot_execute_real_click" in runtime_text,
        "runtime_block_returns_no_click_completed": '"click_completed": False' in runtime_text,
        "runtime_block_returns_guard_failed": '"guard_passed": False' in runtime_text,

        "v219_redirects_probe_stdout": "contextlib.redirect_stdout(probe_stdout)" in v219_text,
        "v219_exposes_probe_stdout_lines": "probe_stdout_lines" in v219_text,

        "v220_real_live_readiness_tool_exists": V220_TOOL_PATH.exists(),
        "v220_checks_real_click_ready": "real_click_ready" in v220_text,
    }

    report = {
        "schema": "pokervision_solver_preflop_v221_real_click_stub_blocker_audit_v1",
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
