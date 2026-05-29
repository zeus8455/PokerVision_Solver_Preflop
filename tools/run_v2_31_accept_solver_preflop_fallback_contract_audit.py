from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v231_accept_solver_preflop_fallback_contract_audit_v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
TARGET = SNAPSHOT_ROOT / "runtime" / "v11_stage1_runtime.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _line_no(text: str, needle: str) -> int:
    idx = text.find(needle)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def _load_module():
    if str(SNAPSHOT_ROOT) not in sys.path:
        sys.path.insert(0, str(SNAPSHOT_ROOT))
    spec = importlib.util.spec_from_file_location("v231_runtime_audit", TARGET)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Cannot load v11_stage1_runtime.py")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_state(contract_status: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    full_state = {
        "solver_preflop_bridge_contract": {
            "status": contract_status,
            "raw_action": "fold",
            "bridge_payload": {
                "decision_id": "bridge_payload_decision",
                "solver_fingerprint": "fp_payload",
                "action_decision": {
                    "decision_id": "solver_preflop_decision_123",
                    "solver_fingerprint": "solver_fp_123",
                    "source": "PokerVision_Solver_Preflop",
                    "source_frame_id": "table_02_hand_12_preflop_03",
                    "raw_action": "fold",
                    "action": "fold",
                    "engine_action": "fold",
                    "reason": "Range engine unsupported/unsafe node: multi_raise_unknown",
                    "click_sequence": ["FOLD"],
                },
            },
        },
        "Total_pot": 9.5,
    }
    solver_payload = {
        "table_id": "table_02",
        "hand_id": "hand_12",
        "frame_name": "table_02_hand_12_preflop_03",
    }
    return full_state, solver_payload, Path("solver_payloads/table_02/hand_12_preflop_03.json")


def build_report() -> dict[str, Any]:
    text = _read(TARGET)
    module = _load_module()

    fallback_state, payload, path = _sample_state("fallback")
    ok_state, ok_payload, ok_path = _sample_state("ok")
    bad_state, bad_payload, bad_path = _sample_state("error")

    fallback_decision = module._extract_solver_preflop_decision_from_state(
        full_state=fallback_state,
        solver_payload=payload,
        solver_payload_path=path,
    )
    ok_decision = module._extract_solver_preflop_decision_from_state(
        full_state=ok_state,
        solver_payload=ok_payload,
        solver_payload_path=ok_path,
    )
    bad_decision = module._extract_solver_preflop_decision_from_state(
        full_state=bad_state,
        solver_payload=bad_payload,
        solver_payload_path=bad_path,
    )

    marker = "V2.31: accept Solver_Preflop fallback bridge when action_decision is available"
    strict_old = 'if str(contract.get("status") or "") != "ok":'
    accepted_set = 'if contract_status not in {"ok", "fallback"}:'

    checks = {
        "target_exists": TARGET.exists(),
        "marker_present": marker in text,
        "old_strict_ok_check_removed": strict_old not in text,
        "accepted_status_set_present": accepted_set in text,
        "fallback_decision_returned": isinstance(fallback_decision, dict),
        "fallback_decision_status_ok": isinstance(fallback_decision, dict) and fallback_decision.get("status") == "ok",
        "fallback_decision_source_solver_preflop": isinstance(fallback_decision, dict) and fallback_decision.get("source") == "PokerVision_Solver_Preflop",
        "fallback_decision_id_not_stub": isinstance(fallback_decision, dict) and not str(fallback_decision.get("decision_id") or "").startswith("v12_stub_"),
        "fallback_decision_action_fold": isinstance(fallback_decision, dict) and fallback_decision.get("action") == "fold",
        "fallback_runtime_selection_bridge": isinstance(fallback_decision, dict)
        and (fallback_decision.get("runtime_source_selection") or {}).get("selected_source") == "Solver_Preflop_Bridge",
        "ok_decision_still_returned": isinstance(ok_decision, dict) and ok_decision.get("status") == "ok",
        "bad_status_still_rejected": bad_decision is None,
    }

    return {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "target": str(TARGET),
        "real_project_touched": False,
        "line_positions": {
            "marker": _line_no(text, marker),
            "contract_status": _line_no(text, "contract_status = str(contract.get"),
            "accepted_status_set": _line_no(text, accepted_set),
            "bridge_payload": _line_no(text, "bridge_payload = contract.get"),
        },
        "checks": checks,
        "fallback_decision": fallback_decision,
        "ok_decision": ok_decision,
        "bad_decision": bad_decision,
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
