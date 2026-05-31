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


def _clear_json(street: str = "flop") -> dict:
    board = {
        "flop": ["A_spades", "7_hearts", "2_clubs"],
        "turn": ["A_spades", "7_hearts", "2_clubs", "K_diamonds"],
        "river": ["A_spades", "7_hearts", "2_clubs", "K_diamonds", "3_spades"],
    }[street]
    return {
        "schema_version": "clear_json_v1",
        "table_id": "table_01",
        "frame_id": f"table_01_hand_v251_{street}",
        "hand_id": "hand_v251_postflop",
        "street": street,
        "board": board,
        "Total_pot": 9.5,
        "players": {
            "SB": {"hero": True, "cards": ["K_spades", "K_hearts"], "stack": 90.0, "chips": False, "fold": False},
            "BB": {"hero": False, "stack": 88.0, "chips": 4.0, "fold": False},
        },
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_51_postflop_runtime_fallback_audit.json")
    args = parser.parse_args()

    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    for street in ["flop", "turn", "river"]:
        clear_json = _clear_json(street)
        bridge = build_solver_preflop_dryrun_bridge_contract(
            clear_state=clear_json,
            cycle_dir=Path("outputs"),
            table_id="table_01",
            publish_files=False,
        )
        payload = bridge.get("bridge_payload") if isinstance(bridge, dict) else None
        action_decision = payload.get("action_decision") if isinstance(payload, dict) else None
        action_validation = validate_action_decision_contract(action_decision) if isinstance(action_decision, dict) else {"ok": False}
        runtime_plan = build_action_runtime_plan_from_action_decision(action_decision) if isinstance(action_decision, dict) else {}
        runtime_validation = validate_action_runtime_plan_contract(runtime_plan) if isinstance(runtime_plan, dict) else {"ok": False}

        prefix = f"{street}_"
        checks[prefix + "bridge_ok"] = isinstance(bridge, dict) and bridge.get("status") == "ok"
        checks[prefix + "node_postflop_solver_missing"] = bridge.get("node_type") == "postflop_solver_missing"
        checks[prefix + "raw_safe_runtime_fallback"] = bridge.get("raw_action") == "safe_runtime_fallback"
        checks[prefix + "action_decision_exists"] = isinstance(action_decision, dict)
        checks[prefix + "action_decision_valid"] = action_validation.get("ok") is True
        checks[prefix + "not_legacy_runtime_source"] = bool((action_decision.get("decision_context") or {}).get("solver_preflop_runtime_source")) is True
        checks[prefix + "context_postflop_solver_missing"] = bool((action_decision.get("decision_context") or {}).get("postflop_solver_missing")) is True
        checks[prefix + "runtime_plan_valid"] = runtime_validation.get("ok") is True
        checks[prefix + "runtime_target_sequence"] = list(runtime_plan.get("target_sequence") or []) == ["Check", "Check/fold", "FOLD"]
        checks[prefix + "runtime_status_ok"] = runtime_plan.get("status") == "ok"

        details[street] = {
            "bridge": bridge,
            "action_validation": action_validation,
            "runtime_plan": runtime_plan,
            "runtime_validation": runtime_validation,
        }

    report = {"schema": "v2_51_postflop_runtime_fallback_audit_v1", "ok": all(checks.values()), "checks": checks, "details": details}

    print("V2.51 POSTFLOP RUNTIME FALLBACK AUDIT")
    for key, value in checks.items():
        print(f"{key:62} {value}")
    print("-" * 100)
    print(f"V2.51_POSTFLOP_RUNTIME_FALLBACK_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
