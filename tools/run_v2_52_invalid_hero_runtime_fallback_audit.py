from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

for path in (PROJECT_ROOT, SNAPSHOT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract
from logic.action_decision_stub import validate_action_decision_contract
from logic.action_runtime_plan_builder import build_action_runtime_plan_from_action_decision, validate_action_runtime_plan_contract


def _base_clear() -> dict:
    return {
        "schema_version": "clear_json_v1",
        "frame_id": "table_01_hand_v252_preflop_01",
        "board": {"cards": [], "street": "preflop"},
        "Total_pot": 1.5,
        "players": {
            "SB": {"hero": False, "stack": 99.5, "chips": 0.5, "fold": False},
            "BB": {"hero": False, "stack": 99.0, "chips": 1.0, "fold": False},
        },
    }


def _case_no_hero() -> dict:
    return _base_clear()


def _case_one_hero_one_card() -> dict:
    clear = _base_clear()
    clear["players"]["SB"]["hero"] = True
    clear["players"]["SB"]["cards"] = ["A_spades"]
    clear["players"]["SB"]["chips"] = False
    return clear


def _case_duplicate_hero_cards() -> dict:
    clear = _base_clear()
    clear["players"]["SB"]["hero"] = True
    clear["players"]["SB"]["cards"] = ["K_spades", "K_spades"]
    clear["players"]["SB"]["chips"] = False
    return clear


def _case_two_heroes() -> dict:
    clear = _base_clear()
    clear["players"]["SB"]["hero"] = True
    clear["players"]["SB"]["cards"] = ["Q_spades", "Q_hearts"]
    clear["players"]["BB"]["hero"] = True
    clear["players"]["BB"]["cards"] = ["2_spades", "2_hearts"]
    return clear


def _run_case(clear_json: dict, table_id: str = "table_01") -> dict:
    bridge = build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_json,
        cycle_dir=Path("outputs"),
        table_id=table_id,
        publish_files=False,
    )
    payload = bridge.get("bridge_payload") if isinstance(bridge, dict) else None
    action_decision = payload.get("action_decision") if isinstance(payload, dict) else None
    action_validation = validate_action_decision_contract(action_decision) if isinstance(action_decision, dict) else {"ok": False}
    runtime_plan = build_action_runtime_plan_from_action_decision(action_decision) if isinstance(action_decision, dict) else {}
    runtime_validation = validate_action_runtime_plan_contract(runtime_plan) if isinstance(runtime_plan, dict) else {"ok": False}
    return {
        "bridge": bridge,
        "action_decision": action_decision,
        "action_validation": action_validation,
        "runtime_plan": runtime_plan,
        "runtime_validation": runtime_validation,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_52_invalid_hero_runtime_fallback_audit.json")
    args = parser.parse_args()

    cases = {
        "no_hero": _case_no_hero(),
        "one_hero_one_card": _case_one_hero_one_card(),
        "duplicate_hero_cards": _case_duplicate_hero_cards(),
        "two_heroes": _case_two_heroes(),
    }

    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    for name, clear_json in cases.items():
        result = _run_case(clear_json)
        bridge = result["bridge"]
        action_decision = result["action_decision"]
        runtime_plan = result["runtime_plan"]

        context = action_decision.get("decision_context") if isinstance(action_decision, dict) else {}

        prefix = f"{name}_"
        checks[prefix + "bridge_ok"] = isinstance(bridge, dict) and bridge.get("status") == "ok"
        checks[prefix + "node_active_invalid_hero_cards"] = bridge.get("node_type") == "active_invalid_hero_cards"
        checks[prefix + "raw_safe_runtime_fallback"] = bridge.get("raw_action") == "safe_runtime_fallback"
        checks[prefix + "engine_fold"] = bridge.get("engine_action") == "fold"
        checks[prefix + "target_fold"] = list(bridge.get("target_sequence") or []) == ["FOLD"]
        checks[prefix + "action_decision_valid"] = result["action_validation"].get("ok") is True
        checks[prefix + "runtime_plan_valid"] = result["runtime_validation"].get("ok") is True
        checks[prefix + "runtime_status_ok"] = runtime_plan.get("status") == "ok"
        checks[prefix + "runtime_target_fold"] = list(runtime_plan.get("target_sequence") or []) == ["FOLD"]
        checks[prefix + "not_legacy_runtime_source"] = bool((context or {}).get("solver_preflop_runtime_source")) is True
        checks[prefix + "context_marks_invalid_hero"] = bool((context or {}).get("active_invalid_hero_cards")) is True

        details[name] = result

    report = {
        "schema": "v2_52_invalid_hero_runtime_fallback_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
    }

    print("V2.52 INVALID HERO RUNTIME FALLBACK AUDIT")
    for key, value in checks.items():
        print(f"{key:64} {value}")
    print("-" * 100)
    print(f"V2.52_INVALID_HERO_RUNTIME_FALLBACK_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
