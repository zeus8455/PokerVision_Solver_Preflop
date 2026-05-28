from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY_ANALYSIS_CYCLE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
PENDING_CLEAR_JSON = (
    SNAPSHOT_ROOT
    / "outputs"
    / "ui_display_cycle"
    / "current_cycle"
    / "Clear_JSON_Pending"
    / "table_02"
    / "table_02_hand_29_preflop.pending.json"
)


REQUIRED_SNIPPETS = {
    "bridge_import": "from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract",
    "bridge_call": "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(",
    "clear_state_arg": "clear_state=clear_state_candidate",
    "publish_files_false": "publish_files=False",
    "contract_embedding": 'action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract',
    "state_embedding": 'state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract',
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("solver_preflop_dryrun_bridge_embedding_check", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load bridge module: {BRIDGE_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _line_number(text: str, needle: str) -> int | None:
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return idx
    return None


def main() -> int:
    if not DISPLAY_ANALYSIS_CYCLE.exists():
        raise FileNotFoundError(DISPLAY_ANALYSIS_CYCLE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)
    if not PENDING_CLEAR_JSON.exists():
        raise FileNotFoundError(PENDING_CLEAR_JSON)

    text = DISPLAY_ANALYSIS_CYCLE.read_text(encoding="utf-8")

    snippet_checks = {}
    line_numbers = {}
    for key, snippet in REQUIRED_SNIPPETS.items():
        present = snippet in text
        snippet_checks[key] = present
        line_numbers[key] = _line_number(text, snippet)

    missing = [key for key, present in snippet_checks.items() if not present]

    order_ok = False
    if not missing:
        order_ok = (
            int(line_numbers["bridge_call"]) < int(line_numbers["contract_embedding"]) < int(line_numbers["state_embedding"])
        )

    bridge_module = _load_bridge_module()
    clear_state = _load_json(PENDING_CLEAR_JSON)
    bridge_contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_state,
        cycle_dir=PROJECT_ROOT / "tmp_display_cycle_bridge_embedding_check",
        table_id="table_02",
        publish_files=False,
    )

    bridge_runtime_ok = bridge_contract.get("status") in {"ok", "fallback"}

    report = {
        "schema": "pokervision_solver_preflop_display_cycle_bridge_embedding_check_v1",
        "status": "ok" if not missing and order_ok and bridge_runtime_ok else "error",
        "project_root": str(PROJECT_ROOT),
        "display_analysis_cycle": str(DISPLAY_ANALYSIS_CYCLE),
        "bridge_module": str(BRIDGE_PATH),
        "pending_clear_json": str(PENDING_CLEAR_JSON),
        "snippet_checks": snippet_checks,
        "line_numbers": line_numbers,
        "missing": missing,
        "order_ok": order_ok,
        "bridge_runtime_check": {
            "ok": bridge_runtime_ok,
            "status": bridge_contract.get("status"),
            "source_frame_id": bridge_contract.get("source_frame_id"),
            "raw_action": bridge_contract.get("raw_action"),
            "engine_action": bridge_contract.get("engine_action"),
            "click_sequence": bridge_contract.get("click_sequence"),
            "safe_fallback_used": bridge_contract.get("safe_fallback_used"),
            "file_publication_enabled": bridge_contract.get("file_publication_enabled"),
            "path": bridge_contract.get("path"),
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
