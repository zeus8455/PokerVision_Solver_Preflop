from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"
CURRENT_CYCLE_ROOT = SNAPSHOT_ROOT / "outputs" / "ui_display_cycle" / "current_cycle"

# Solver_Preflop must receive pre-click Clear_JSON. Prefer Clear_JSON_Pending.
# Final Clear_JSON usually already contains click_result and is intentionally skipped
# by the dry-run bridge.
CLEAR_JSON_PENDING_ROOT = CURRENT_CYCLE_ROOT / "Clear_JSON_Pending"
CLEAR_JSON_FINAL_ROOT = CURRENT_CYCLE_ROOT / "Clear_JSON"
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "clear_json"

BRIDGE_PATH = SNAPSHOT_ROOT / "runtime" / "solver_preflop_dryrun_bridge.py"
DEFAULT_OUT_DIR = PROJECT_ROOT / "tmp_snapshot_bridge_outputs"


def _load_bridge_module():
    if not BRIDGE_PATH.exists():
        raise FileNotFoundError(f"Bridge module not found: {BRIDGE_PATH}")

    spec = importlib.util.spec_from_file_location("solver_preflop_dryrun_bridge_snapshot_check", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load bridge module spec: {BRIDGE_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _glob_clear_json_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    nested = sorted(root.glob("table_*/*.json"))
    flat = sorted(root.glob("*.json"))
    return nested + flat


def _discover_clear_json_files(root: Path | None, *, preflop_only: bool = True) -> tuple[list[Path], str]:
    """Discover inputs for the snapshot bridge check.

    Default behavior:
    1. Use Clear_JSON_Pending from the NoSolver snapshot if present.
    2. Fall back to final Clear_JSON if explicitly available.
    3. Fall back to repository examples so the test suite stays reproducible
       even if snapshot runtime outputs are ignored by git.
    """
    candidates: list[tuple[Path, str]] = []
    if root is not None:
        candidates.append((root, "custom"))
    else:
        candidates.extend([
            (CLEAR_JSON_PENDING_ROOT, "snapshot_clear_json_pending"),
            (CLEAR_JSON_FINAL_ROOT, "snapshot_clear_json_final"),
            (EXAMPLES_ROOT, "examples_clear_json"),
        ])

    for candidate_root, source_kind in candidates:
        files = _glob_clear_json_files(candidate_root)
        if preflop_only:
            files = [p for p in files if "preflop" in p.name.lower()]
        if files:
            return files, source_kind

    return [], "none"


def _table_id_from_path(path: Path) -> str:
    parent = path.parent.name.strip()
    if parent.startswith("table_"):
        return parent
    name = path.name.lower()
    for part in name.replace(".", "_").split("_"):
        pass
    if "table_01" in name:
        return "table_01"
    if "table_02" in name:
        return "table_02"
    if "table_03" in name:
        return "table_03"
    return parent or "unknown_table"


def _run_one(bridge_module: Any, path: Path, *, publish_files: bool, out_dir: Path) -> dict[str, Any]:
    data = _load_json(path)
    table_id = _table_id_from_path(path)
    contract = bridge_module.build_solver_preflop_dryrun_bridge_contract(
        clear_state=data,
        cycle_dir=out_dir,
        table_id=table_id,
        publish_files=publish_files,
    )

    try:
        rel_file = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        rel_file = str(path)

    return {
        "file": rel_file,
        "table_id": table_id,
        "status": contract.get("status"),
        "reason": contract.get("reason"),
        "street": contract.get("street"),
        "source_frame_id": contract.get("source_frame_id") or data.get("frame_id"),
        "decision_id": contract.get("decision_id"),
        "solver_fingerprint": contract.get("solver_fingerprint"),
        "raw_action": contract.get("raw_action"),
        "engine_action": contract.get("engine_action"),
        "click_sequence": contract.get("click_sequence"),
        "safe_fallback_used": contract.get("safe_fallback_used"),
        "path": contract.get("path"),
        "message": contract.get("message"),
        "exception_type": contract.get("exception_type"),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Solver_Preflop dry-run bridge against PokerVision NoSolver snapshot pre-click Clear_JSON files.",
    )
    parser.add_argument(
        "--clear-json-root",
        default=None,
        help=(
            "Custom root containing table_*/Clear_JSON files. "
            "Default: Clear_JSON_Pending, then final Clear_JSON, then examples fallback."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Diagnostic output dir used when --publish-files is enabled.",
    )
    parser.add_argument(
        "--publish-files",
        action="store_true",
        help="Ask bridge to publish diagnostic bridge payload JSON files.",
    )
    parser.add_argument(
        "--all-streets",
        action="store_true",
        help="Scan all Clear_JSON files instead of only names containing preflop.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    custom_root = Path(args.clear_json_root) if args.clear_json_root else None
    out_dir = Path(args.out_dir)

    bridge_module = _load_bridge_module()
    files, input_source = _discover_clear_json_files(custom_root, preflop_only=not args.all_streets)

    results = []
    for path in files:
        try:
            results.append(_run_one(bridge_module, path, publish_files=bool(args.publish_files), out_dir=out_dir))
        except Exception as exc:
            try:
                rel_file = str(path.relative_to(PROJECT_ROOT))
            except ValueError:
                rel_file = str(path)
            results.append({
                "file": rel_file,
                "table_id": _table_id_from_path(path),
                "status": "error",
                "reason": "snapshot_bridge_check_exception",
                "message": str(exc),
                "exception_type": type(exc).__name__,
            })

    status_counts = Counter(str(item.get("status") or "unknown") for item in results)
    error_count = int(status_counts.get("error", 0))
    executable_count = int(status_counts.get("ok", 0) + status_counts.get("fallback", 0))
    skipped_count = int(status_counts.get("skipped", 0))

    report = {
        "schema": "pokervision_solver_preflop_snapshot_clear_json_bridge_check_v1",
        "status": "ok" if files and error_count == 0 and executable_count > 0 else "error",
        "project_root": str(PROJECT_ROOT),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "current_cycle_root": str(CURRENT_CYCLE_ROOT),
        "input_source": input_source,
        "clear_json_pending_root": str(CLEAR_JSON_PENDING_ROOT),
        "clear_json_final_root": str(CLEAR_JSON_FINAL_ROOT),
        "examples_root": str(EXAMPLES_ROOT),
        "bridge_module": str(BRIDGE_PATH),
        "preflop_only": not args.all_streets,
        "publish_files": bool(args.publish_files),
        "files_total": len(files),
        "executable_preflop_count": executable_count,
        "skipped_count": skipped_count,
        "status_counts": dict(sorted(status_counts.items())),
        "results": results,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not files:
        return 2
    if error_count or executable_count <= 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
