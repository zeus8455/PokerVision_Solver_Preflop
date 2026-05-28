from __future__ import annotations

import json
import os
from typing import Any

import config
from logic.real_click_readiness import validate_real_click_readiness


SCHEMA_VERSION = "controlled_live_preflight_v8_0"
READY_STATUS = "CONTROLLED_LIVE_PREFLIGHT_READY"
BLOCKED_STATUS = "CONTROLLED_LIVE_PREFLIGHT_BLOCKED"
EXPECTED_ENV_VALUE = str(config.V31_CONTROLLED_LIVE_CLICK_ENV_VALUE)
EXPECTED_TABLES = ("table_01", "table_02", "table_03", "table_04", "table_05", "table_06")
ALLOWED_ACTIONS = ["fold", "check", "call", "check_fold"]
TEST_SCOPE_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"
SINGLE_TABLE_FIRST_CLICK_SCOPE = "V8_5_SINGLE_TABLE_FIRST_CLICK"
FULL_LIVE_CHAIN_SCOPE = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"


def _csv(items: list[str] | tuple[str, ...]) -> str:
    return ",".join(str(x) for x in items)


def _build_report() -> dict[str, Any]:
    gate = config.get_v31_controlled_live_click_gate_snapshot()
    readiness = validate_real_click_readiness(config).to_dict()

    blockers: list[str] = []

    env_value = os.environ.get(str(config.V31_CONTROLLED_LIVE_CLICK_ENV_VAR), "")
    if env_value != EXPECTED_ENV_VALUE:
        blockers.append("missing_controlled_live_click_env")

    table_ids = tuple(str(x) for x in gate.get("table_ids", []))

    max_clicks = int(gate.get("max_clicks_per_run", 0))
    test_scope = os.environ.get(TEST_SCOPE_ENV_VAR, "").strip()
    single_table_first_click_scope = test_scope == SINGLE_TABLE_FIRST_CLICK_SCOPE
    full_live_chain_scope = test_scope == FULL_LIVE_CHAIN_SCOPE

    if full_live_chain_scope:
        if table_ids != EXPECTED_TABLES:
            blockers.append("full_live_chain_scope_requires_table_01_to_table_06")
        if max_clicks != 0:
            blockers.append("full_live_chain_scope_requires_no_limit_max_clicks_0")
    elif single_table_first_click_scope:
        allowed_tables = set(str(x) for x in gate.get("allowed_table_ids", []))
        if len(table_ids) != 1:
            blockers.append("single_table_first_click_scope_requires_exactly_one_table")
        elif table_ids[0] not in allowed_tables:
            blockers.append("single_table_first_click_scope_requires_allowed_table_id")
        if max_clicks != 1:
            blockers.append("single_table_first_click_scope_requires_one_click")
    else:
        if table_ids != EXPECTED_TABLES:
            blockers.append("table_ids_must_be_table_01_to_table_06")
        if max_clicks < 4 or max_clicks > 6:
            blockers.append("max_clicks_must_be_4_to_6_for_multi_table_live")

    if not bool(gate.get("action_button_only")):
        blockers.append("action_button_only_required")

    if not bool(gate.get("simple_actions_only")):
        blockers.append("simple_actions_only_required")

    if not full_live_chain_scope and not bool(gate.get("service_branch_disabled")):
        blockers.append("service_branch_must_be_disabled")

    if bool(gate.get("raise_branch_enabled")):
        blockers.append("raise_branch_must_be_blocked")

    if list(gate.get("allowed_actions") or []) != ALLOWED_ACTIONS:
        blockers.append("allowed_actions_must_be_fold_check_call_check_fold")

    if not bool(gate.get("require_roi_guard_ok")):
        blockers.append("roi_guard_required")

    if not bool(gate.get("require_full_screen_blocked")):
        blockers.append("full_screen_action_button_search_must_be_blocked")

    if not bool(gate.get("require_inside_slot")):
        blockers.append("inside_slot_required")

    service_real_click_disabled = not bool(getattr(config, "V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED", False))
    if not full_live_chain_scope and not service_real_click_disabled:
        blockers.append("service_real_click_must_be_disabled")

    if not bool(readiness.get("real_click_ready")):
        blockers.append("real_click_readiness_not_ready")

    raise_branch_enabled = bool(gate.get("raise_branch_enabled"))

    ready = not blockers
    status = READY_STATUS if ready else BLOCKED_STATUS

    return {
        "schema_version": SCHEMA_VERSION,
        "ready": ready,
        "status": status,
        "blockers": blockers,
        "controlled_env_value": env_value,
        "test_scope": test_scope,
        "test_scope_env_var": TEST_SCOPE_ENV_VAR,
        "table_ids": list(table_ids),
        "table_ids_csv": _csv(table_ids),
        "max_clicks_per_run": max_clicks,
        "service_real_click_disabled": service_real_click_disabled,
        "raise_branch_enabled": raise_branch_enabled,
        "allowed_actions": list(gate.get("allowed_actions") or []),
        "gate": gate,
        "readiness": readiness,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(report["status"])
    print("schema_version=" + str(report["schema_version"]))
    print("ready=" + str(bool(report["ready"])))
    print("table_ids=" + str(report["table_ids_csv"]))
    print("max_clicks_per_run=" + str(report["max_clicks_per_run"]))
    print("service_real_click_disabled=" + str(report["service_real_click_disabled"]))
    print("raise_branch_enabled=" + str(report["raise_branch_enabled"]))
    print("allowed_actions=" + ",".join(str(x) for x in report["allowed_actions"]))
    print("test_scope=" + str(report.get("test_scope") or ""))

    blockers = list(report.get("blockers") or [])
    if blockers:
        print("blockers=" + ",".join(blockers))
    else:
        print("blockers=none")

    print("json=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


def main() -> int:
    report = _build_report()
    _print_report(report)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
