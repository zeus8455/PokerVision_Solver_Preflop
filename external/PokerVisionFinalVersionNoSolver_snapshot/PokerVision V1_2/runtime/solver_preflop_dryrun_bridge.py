from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


BRIDGE_CONTRACT_SCHEMA = "pokervision_display_cycle_solver_preflop_bridge_preview_v1"
BRIDGE_STATUS_SKIPPED = "skipped"
BRIDGE_STATUS_OK = "ok"
BRIDGE_STATUS_FALLBACK = "fallback"
BRIDGE_STATUS_ERROR = "error"


def _find_solver_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Find C:/PokerVision_Solver_Preflop style project root from this snapshot file."""
    current = (start or Path(__file__).resolve()).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "solver_preflop").is_dir() and (parent / "pyproject.toml").exists():
            return parent
    for parent in current.parents:
        candidate = parent
        if (candidate / "solver_preflop").is_dir():
            return candidate
    return None


def _ensure_solver_importable() -> Optional[str]:
    project_root = _find_solver_project_root()
    if project_root is None:
        return "PokerVision_Solver_Preflop project root was not found from snapshot runtime path."
    root_text = str(project_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return None


def _safe_json_filename(value: object, fallback: str = "solver_preflop_bridge") -> str:
    raw = str(value or fallback).strip() or fallback
    out = []
    for ch in raw:
        if ch.isalnum() or ch in {"_", "-", "."}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("._") or fallback


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _normalize_street(value: object) -> str:
    return str(value or "").strip().lower()


def _clear_json_street(clear_state: Dict[str, Any]) -> str:
    """Infer street from PokerVision Clear_JSON variants.

    PokerVision Final/Clear JSON may carry street in different places:
    - top-level street/current_street
    - meta.street/current_street
    - board.street
    - frame_id/hand_id containing "_preflop"
    V1.2 bridge needs this tolerant inference because current NoSolver Clear_JSON
    examples use board.street and frame_id, not top-level street.
    """
    for key in ("street", "current_street"):
        street = _normalize_street(clear_state.get(key))
        if street:
            return street

    meta = clear_state.get("meta")
    if isinstance(meta, dict):
        for key in ("street", "current_street"):
            street = _normalize_street(meta.get(key))
            if street:
                return street

    board = clear_state.get("board")
    if isinstance(board, dict):
        street = _normalize_street(board.get("street") or board.get("current_street"))
        if street:
            return street

    for key in ("frame_id", "hand_id", "source_frame_id"):
        text = _normalize_street(clear_state.get(key))
        if "_preflop" in text or text.endswith("preflop"):
            return "preflop"
        if "_flop" in text or text.endswith("flop"):
            return "flop"
        if "_turn" in text or text.endswith("turn"):
            return "turn"
        if "_river" in text or text.endswith("river"):
            return "river"

    return ""


def is_preflop_clear_json_without_click(clear_state: object) -> bool:
    if not isinstance(clear_state, dict):
        return False
    if isinstance(clear_state.get("click_result"), dict):
        return False
    return _clear_json_street(clear_state) == "preflop"


def build_solver_preflop_dryrun_bridge_contract(
    *,
    clear_state: Dict[str, Any],
    cycle_dir: Path,
    table_id: str,
    publish_files: bool = False,
) -> Dict[str, Any]:
    """Build a dry-run Solver_Preflop bridge contract for PokerVision display cycle.

    This function never clicks and never replaces PokerVision's existing runtime
    plan by itself. It only runs the standalone Solver_Preflop against a valid
    preflop Clear_JSON candidate and returns a diagnostic contract that can be
    embedded into action_decision_contract.
    """
    if not isinstance(clear_state, dict):
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": BRIDGE_STATUS_SKIPPED,
            "reason": "clear_state_is_not_dict",
            "source": "Clear_JSON_Pending",
            "path": None,
        }

    if isinstance(clear_state.get("click_result"), dict):
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": BRIDGE_STATUS_SKIPPED,
            "reason": "clear_json_already_has_click_result",
            "source": "Clear_JSON_Pending",
            "path": None,
        }

    street = _clear_json_street(clear_state)
    if street != "preflop":
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": BRIDGE_STATUS_SKIPPED,
            "reason": "street_is_not_preflop",
            "street": street,
            "source": "Clear_JSON_Pending",
            "path": None,
        }

    import_error = _ensure_solver_importable()
    if import_error:
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": BRIDGE_STATUS_ERROR,
            "reason": "solver_import_path_error",
            "message": import_error,
            "source": "Clear_JSON_Pending",
            "path": None,
        }

    try:
        from solver_preflop import solve_clear_json
        from solver_preflop.pokervision_bridge import build_pokervision_bridge_payload

        decision = solve_clear_json(clear_state)
        bridge_payload = build_pokervision_bridge_payload(decision)
        frame_id = str(bridge_payload.get("source_frame_id") or clear_state.get("frame_id") or "solver_preflop_bridge")
        path: Optional[Path] = None

        if publish_files:
            filename = _safe_json_filename(frame_id) + ".solver_preflop_bridge_preview.json"
            path = cycle_dir / "Solver_Preflop_Bridge_JSON" / str(table_id) / filename
            _write_json_atomic(path, bridge_payload)

        status = BRIDGE_STATUS_OK if decision.status == "ok" else BRIDGE_STATUS_FALLBACK
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": status,
            "source": "Clear_JSON_Pending",
            "publication_stage": "pending_preview",
            "file_publication_enabled": bool(publish_files),
            "path": str(path) if path else None,
            "dir": "Solver_Preflop_Bridge_JSON",
            "street": "preflop",
            "source_frame_id": decision.source_frame_id,
            "decision_id": decision.decision_id,
            "solver_fingerprint": decision.solver_fingerprint,
            "raw_action": decision.raw_action,
            "engine_action": decision.engine_action,
            "click_sequence": list(decision.click_sequence),
            "safe_fallback_used": decision.safe_fallback_used,
            "bridge_payload": bridge_payload,
            "runtime_plan_candidate": bridge_payload.get("runtime_plan_candidate"),
            "safety": bridge_payload.get("safety"),
            "warnings": list(decision.warnings),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "schema": BRIDGE_CONTRACT_SCHEMA,
            "status": BRIDGE_STATUS_ERROR,
            "reason": "solver_preflop_bridge_exception",
            "message": str(exc),
            "exception_type": type(exc).__name__,
            "source": "Clear_JSON_Pending",
            "path": None,
        }
