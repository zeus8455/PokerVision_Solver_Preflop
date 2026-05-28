from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY_FILE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
PENDING_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle" / "Clear_JSON_Pending"
DEFAULT_OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v19_snapshot_cycle_bridge_smoke"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_bridge_module():
    os.environ["POKERVISION_SOLVER_PREFLOP_ROOT"] = str(PROJECT_ROOT)
    spec = importlib.util.spec_from_file_location("snapshot_cycle_solver_preflop_bridge", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load bridge module: {BRIDGE_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _discover_pending_preflop_files() -> list[Path]:
    if not PENDING_ROOT.exists():
        return []
    return sorted(PENDING_ROOT.glob("table_*/*preflop*.json"))


def _table_id_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent if parent.startswith("table_") else "unknown_table"


def _static_display_checks() -> dict[str, bool]:
    text = DISPLAY_FILE.read_text(encoding="utf-8")
    return {
        "bridge_import": "from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract" in text,
        "publication_toggle": "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False" in text,
        "bridge_call": "solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(" in text,
        "toggle_call": "publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES)" in text,
        "contract_embedding": 'action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract' in text,
        "state_embedding": 'state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract' in text,
        "run_ui_display_analysis_cycle_exists": "def run_ui_display_analysis_cycle(" in text,
    }


def _clean_out_dir(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    for item in sorted(out_dir.rglob("*"), reverse=True):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            try:
                item.rmdir()
            except OSError:
                pass


def _run_one(bridge_module: Any, path: Path, *, out_dir: Path, publish_files: bool) -> dict[str, Any]:
    clear_state = _load_json(path)
    table_id = _table_id_from_path(path)

    contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_state,
        cycle_dir=out_dir,
        table_id=table_id,
        publish_files=publish_files,
    )

    bridge_payload = contract.get("bridge_payload") if isinstance(contract, dict) else None
    runtime_plan = contract.get("runtime_plan_candidate") if isinstance(contract, dict) else None
    action_decision = bridge_payload.get("action_decision") if isinstance(bridge_payload, dict) else None

    path_text = contract.get("path") if isinstance(contract, dict) else None
    published_exists = bool(path_text and Path(path_text).exists())

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "table_id": table_id,
        "status": contract.get("status"),
        "source_frame_id": contract.get("source_frame_id"),
        "raw_action": contract.get("raw_action"),
        "engine_action": contract.get("engine_action"),
        "click_sequence": contract.get("click_sequence"),
        "safe_fallback_used": contract.get("safe_fallback_used"),
        "has_bridge_payload": isinstance(bridge_payload, dict),
        "has_runtime_plan_candidate": isinstance(runtime_plan, dict),
        "has_action_decision": isinstance(action_decision, dict),
        "runtime_plan_schema": runtime_plan.get("schema") if isinstance(runtime_plan, dict) else None,
        "action_decision_schema": action_decision.get("schema") if isinstance(action_decision, dict) else None,
        "file_publication_enabled": contract.get("file_publication_enabled"),
        "path": path_text,
        "published_exists": published_exists,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot-only smoke for Pending Clear_JSON -> Solver_Preflop bridge cycle path.",
    )
    parser.add_argument(
        "--publish-files",
        action="store_true",
        help="Enable diagnostic bridge JSON publication during smoke.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for optional diagnostic publication.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if not SNAPSHOT_ROOT.exists():
        raise FileNotFoundError(SNAPSHOT_ROOT)
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)

    out_dir = Path(args.out_dir)
    _clean_out_dir(out_dir)

    static_checks = _static_display_checks()
    bridge_module = _load_bridge_module()
    files = _discover_pending_preflop_files()

    results = [
        _run_one(bridge_module, path, out_dir=out_dir, publish_files=bool(args.publish_files))
        for path in files
    ]

    executable = [r for r in results if r.get("status") in {"ok", "fallback"}]
    bad_results = [
        r for r in results
        if r.get("status") not in {"ok", "fallback"}
        or not r.get("has_bridge_payload")
        or not r.get("has_runtime_plan_candidate")
        or not r.get("has_action_decision")
    ]

    publication_ok = True
    if args.publish_files:
        publication_ok = all(bool(r.get("published_exists")) for r in executable)

    report = {
        "schema": "pokervision_solver_preflop_snapshot_cycle_bridge_smoke_v1",
        "status": "ok" if all(static_checks.values()) and files and executable and not bad_results and publication_ok else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "display_analysis_cycle": str(DISPLAY_FILE),
        "bridge_module": str(BRIDGE_PATH),
        "pending_root": str(PENDING_ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "publish_files": bool(args.publish_files),
        "out_dir": str(out_dir),
        "static_checks": static_checks,
        "files_total": len(files),
        "executable_count": len(executable),
        "bad_results_count": len(bad_results),
        "publication_ok": publication_ok,
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
