from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
DISPLAY_FILE = SNAPSHOT_ROOT / "display_analysis_cycle.py"
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
DEFAULT_OUT_DIR = PROJECT_ROOT / "tmp_solver_outputs" / "v17_publication_check"


def _load_bridge_module():
    spec = importlib.util.spec_from_file_location("solver_preflop_dryrun_bridge_publication_check", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load bridge module: {BRIDGE_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_dir(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_file():
            item.unlink()


def main() -> int:
    if not DISPLAY_FILE.exists():
        raise FileNotFoundError(DISPLAY_FILE)
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(BRIDGE_PATH)
    if not PENDING_CLEAR_JSON.exists():
        raise FileNotFoundError(PENDING_CLEAR_JSON)

    display_text = DISPLAY_FILE.read_text(encoding="utf-8")
    static_checks = {
        "toggle_present": "V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False" in display_text,
        "toggle_call_present": "publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES)" in display_text,
    }

    out_dir = DEFAULT_OUT_DIR
    _clean_dir(out_dir)

    bridge_module = _load_bridge_module()
    clear_state = _load_json(PENDING_CLEAR_JSON)
    contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=clear_state,
        cycle_dir=out_dir,
        table_id="table_02",
        publish_files=True,
    )

    path_text = contract.get("path")
    published_path = Path(path_text) if path_text else None
    published_exists = bool(published_path and published_path.exists())
    published_payload = _load_json(published_path) if published_exists and published_path is not None else None

    report = {
        "schema": "pokervision_solver_preflop_bridge_publication_check_v1",
        "status": "ok" if all(static_checks.values()) and published_exists else "error",
        "project_root": str(PROJECT_ROOT),
        "display_analysis_cycle": str(DISPLAY_FILE),
        "bridge_module": str(BRIDGE_PATH),
        "pending_clear_json": str(PENDING_CLEAR_JSON),
        "static_checks": static_checks,
        "runtime_publication_check": {
            "status": contract.get("status"),
            "source_frame_id": contract.get("source_frame_id"),
            "engine_action": contract.get("engine_action"),
            "click_sequence": contract.get("click_sequence"),
            "file_publication_enabled": contract.get("file_publication_enabled"),
            "path": path_text,
            "published_exists": published_exists,
            "published_schema": published_payload.get("schema") if isinstance(published_payload, dict) else None,
            "published_source_frame_id": published_payload.get("source_frame_id") if isinstance(published_payload, dict) else None,
        },
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
