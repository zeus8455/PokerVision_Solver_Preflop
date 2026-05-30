from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

for path in (PROJECT_ROOT, SNAPSHOT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _build_report() -> dict[str, Any]:
    from solver_preflop.decision_engine import solve_clear_json
    from solver_preflop.pokervision_bridge import build_pokervision_bridge_payload
    from runtime.v11_stage1_runtime import _extract_solver_preflop_decision_from_state

    bad_clear_json: dict[str, Any] = {
        "frame_id": "v241_bad_input",
        "street": "preflop",
        "players": [],
    }

    decision = solve_clear_json(bad_clear_json)
    bridge_payload = build_pokervision_bridge_payload(decision)

    full_state = {
        "solver_preflop_bridge_contract": {
            "status": bridge_payload.get("status"),
            "bridge_payload": bridge_payload,
            "raw_action": decision.raw_action,
            "engine_action": decision.engine_action,
            "click_sequence": list(decision.click_sequence),
            "decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "source_frame_id": decision.source_frame_id,
        }
    }

    solver_payload = {
        "table_id": "table_01",
        "hand_id": "hand_v241",
        "frame_name": "frame_v241",
    }

    runtime_decision = _extract_solver_preflop_decision_from_state(
        full_state=full_state,
        solver_payload=solver_payload,
        solver_payload_path=Path("synthetic_v241_solver_payload.json"),
    )

    checks = {
        "solver_status_fallback": decision.status == "fallback",
        "solver_raw_action_preserved_safe_fallback": decision.raw_action == "safe_fallback",
        "solver_engine_action_fold": decision.engine_action == "fold",
        "solver_click_sequence_fold": list(decision.click_sequence) == ["FOLD"],
        "bridge_raw_action_preserved_safe_fallback": bridge_payload["action_decision"]["raw_action"] == "safe_fallback",
        "bridge_engine_action_fold": bridge_payload["action_decision"]["engine_action"] == "fold",
        "bridge_click_sequence_fold": bridge_payload["action_decision"]["click_sequence"] == ["FOLD"],
        "runtime_decision_exists": isinstance(runtime_decision, dict),
        "runtime_action_fold": isinstance(runtime_decision, dict) and runtime_decision.get("action") == "fold",
        "runtime_raw_action_still_safe_fallback_for_lineage": isinstance(runtime_decision, dict) and runtime_decision.get("raw_action") == "safe_fallback",
        "runtime_click_sequence_fold": isinstance(runtime_decision, dict) and runtime_decision.get("click_sequence") == ["FOLD"],
    }

    return {
        "schema": "v2_41_safe_fallback_runtime_fold_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "decision": decision.to_json_dict(),
        "bridge_action_decision": bridge_payload["action_decision"],
        "runtime_decision": runtime_decision,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_41_safe_fallback_runtime_fold_audit.json")
    args = parser.parse_args()

    report = _build_report()

    print("V2.41 SAFE_FALLBACK RUNTIME FOLD AUDIT")
    for key, value in report["checks"].items():
        print(f"{key:55} {value}")
    print("-" * 80)
    print(f"V2.41_SAFE_FALLBACK_RUNTIME_FOLD_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
