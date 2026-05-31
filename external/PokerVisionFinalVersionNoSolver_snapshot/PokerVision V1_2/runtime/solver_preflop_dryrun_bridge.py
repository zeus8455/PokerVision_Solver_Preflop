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

# =============================================================================
# V2.51 POSTFLOP UNSUPPORTED EXPLICIT RUNTIME FALLBACK
# =============================================================================

_V251_ORIGINAL_BUILD_SOLVER_PREFLOP_DRYRUN_BRIDGE_CONTRACT = build_solver_preflop_dryrun_bridge_contract


def _v251_clear_street(clear_state: dict) -> str:
    return str((clear_state or {}).get("street") or "").strip().lower()


def _v251_hero_position(clear_state: dict) -> str:
    players = (clear_state or {}).get("players")
    if isinstance(players, dict):
        for position, player in players.items():
            if isinstance(player, dict) and bool(player.get("hero")):
                return str(position)
    return ""


def _v251_source_frame_id(clear_state: dict, table_id: str) -> str:
    return str((clear_state or {}).get("frame_id") or (clear_state or {}).get("source_frame_id") or table_id or "unknown_frame")


def _v251_build_postflop_unsupported_action_decision(*, clear_state: dict, table_id: str) -> dict:
    try:
        from config import V06_ACTION_DECISION_SCHEMA_VERSION
    except Exception:
        V06_ACTION_DECISION_SCHEMA_VERSION = "action_decision_v1"

    street = _v251_clear_street(clear_state)
    source_frame_id = _v251_source_frame_id(clear_state, table_id)
    hero_position = _v251_hero_position(clear_state)
    decision_id = f"v251_postflop_solver_missing:{table_id}:{source_frame_id}:{street}"

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": source_frame_id,
        "status": "ok",
        "action": "check_fold",
        "size_policy": {"type": "none", "value": None},
        "target_button_classes": ["Check", "Check/fold", "FOLD"],
        "reason": "v251_postflop_solver_missing_safe_runtime_fallback",
        "dry_run_safe": True,
        "solver_stub": True,
        "decision_context": {
            "street": street,
            "hero_position": hero_position,
            "source_frame_id": source_frame_id,
            "solver_preflop_runtime_source": True,
            "solver_stub_legacy_compat": True,
            "solver_decision_id": decision_id,
            "solver_fingerprint": decision_id,
            "solver_raw_action": "safe_runtime_fallback",
            "solver_engine_action": "check_fold",
            "node_type": "postflop_solver_missing",
            "postflop_solver_missing": True,
            "safe_runtime_fallback": True,
            "target_sequence": ["Check", "Check/fold", "FOLD"],
        },
    }


def _v251_build_postflop_unsupported_bridge_contract(*, clear_state: dict, table_id: str, upstream_contract: dict | None = None) -> dict:
    street = _v251_clear_street(clear_state)
    action_decision = _v251_build_postflop_unsupported_action_decision(clear_state=clear_state, table_id=table_id)
    return {
        "schema_version": "solver_preflop_dryrun_bridge_v2_51",
        "source": "PokerVision_Solver_Preflop",
        "status": "ok",
        "reason": "v251_postflop_solver_missing_safe_runtime_fallback",
        "table_id": str(table_id or ""),
        "street": street,
        "node_type": "postflop_solver_missing",
        "raw_action": "safe_runtime_fallback",
        "engine_action": "check_fold",
        "target_sequence": ["Check", "Check/fold", "FOLD"],
        "upstream_contract": dict(upstream_contract) if isinstance(upstream_contract, dict) else upstream_contract,
        "bridge_payload": {
            "action_decision": action_decision,
        },
    }


def build_solver_preflop_dryrun_bridge_contract(*args, **kwargs):  # type: ignore[no-redef]
    clear_state = kwargs.get("clear_state")
    table_id = str(kwargs.get("table_id") or "")
    result = _V251_ORIGINAL_BUILD_SOLVER_PREFLOP_DRYRUN_BRIDGE_CONTRACT(*args, **kwargs)

    if isinstance(clear_state, dict):
        street = _v251_clear_street(clear_state)
        if street in {"flop", "turn", "river"}:
            if not isinstance(result, dict):
                return _v251_build_postflop_unsupported_bridge_contract(
                    clear_state=clear_state,
                    table_id=table_id,
                    upstream_contract={"status": "unknown_non_dict_result", "raw": repr(result)},
                )

            status = str(result.get("status") or "").strip().lower()
            reason = str(result.get("reason") or result.get("skip_reason") or "").strip().lower()
            bridge_payload = result.get("bridge_payload")
            action_decision = bridge_payload.get("action_decision") if isinstance(bridge_payload, dict) else None

            if status != "ok" or not isinstance(action_decision, dict) or reason in {"street_is_not_preflop", "not_preflop"}:
                return _v251_build_postflop_unsupported_bridge_contract(
                    clear_state=clear_state,
                    table_id=table_id,
                    upstream_contract=result,
                )

    return result

# =============================================================================
# V2.52 ACTIVE INVALID HERO EXPLICIT RUNTIME FALLBACK
# =============================================================================

_V252_ORIGINAL_BUILD_SOLVER_PREFLOP_DRYRUN_BRIDGE_CONTRACT = build_solver_preflop_dryrun_bridge_contract


def _v252_validate_clear_state(clear_state: dict) -> dict:
    try:
        from logic.clear_json_builder import validate_clear_json_contract
        validation = validate_clear_json_contract(clear_state)
        return validation if isinstance(validation, dict) else {"ok": False, "errors": ["validation_not_dict"], "warnings": []}
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}


def _v252_hero_entries(clear_state: dict) -> list:
    players = (clear_state or {}).get("players")
    if not isinstance(players, dict):
        return []
    return [
        (position, player)
        for position, player in players.items()
        if isinstance(player, dict) and bool(player.get("hero"))
    ]


def _v252_is_invalid_hero_clear_state(clear_state: dict) -> tuple[bool, str, dict]:
    if not isinstance(clear_state, dict):
        return False, "not_clear_state_dict", {"ok": False, "errors": ["not_clear_state_dict"], "warnings": []}

    validation = _v252_validate_clear_state(clear_state)
    errors = [str(item) for item in validation.get("errors", []) if str(item).strip()]
    joined = " | ".join(errors).lower()

    hero_entries = _v252_hero_entries(clear_state)
    hero_count_bad = len(hero_entries) != 1

    hero_cards_bad = False
    if len(hero_entries) == 1:
        _, hero_player = hero_entries[0]
        cards = hero_player.get("cards")
        clean_cards = [str(card).strip() for card in cards if str(card).strip()] if isinstance(cards, list) else []
        hero_cards_bad = len(clean_cards) != 2 or len(set(clean_cards)) != 2

    message_says_hero_bad = (
        "exactly one hero" in joined
        or "hero cards" in joined
        or "exactly 2 hero cards" in joined
        or "exactly two hero cards" in joined
    )

    if hero_count_bad:
        return True, f"invalid_hero_count_{len(hero_entries)}", validation
    if hero_cards_bad:
        return True, "invalid_hero_card_count", validation
    if message_says_hero_bad:
        return True, "invalid_hero_validation_error", validation
    return False, "hero_valid_or_unrelated_validation_error", validation


def _v252_clear_street(clear_state: dict) -> str:
    board = (clear_state or {}).get("board")
    if isinstance(board, dict):
        street = board.get("street")
    else:
        street = (clear_state or {}).get("street")
    return str(street or "unknown").strip().lower()


def _v252_source_frame_id(clear_state: dict, table_id: str) -> str:
    return str((clear_state or {}).get("frame_id") or (clear_state or {}).get("source_frame_id") or table_id or "unknown_frame")


def _v252_build_invalid_hero_action_decision(*, clear_state: dict, table_id: str, reason: str, validation: dict) -> dict:
    try:
        from config import V06_ACTION_DECISION_SCHEMA_VERSION
    except Exception:
        V06_ACTION_DECISION_SCHEMA_VERSION = "action_decision_v1"

    source_frame_id = _v252_source_frame_id(clear_state, table_id)
    street = _v252_clear_street(clear_state)
    decision_id = f"v252_active_invalid_hero_cards:{table_id}:{source_frame_id}:{street}:{reason}"

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": source_frame_id,
        "status": "ok",
        "action": "fold",
        "size_policy": {"type": "none", "value": None},
        "target_button_classes": ["FOLD"],
        "reason": f"v252_active_invalid_hero_cards_safe_runtime_fallback:{reason}",
        "dry_run_safe": True,
        "solver_stub": True,
        "decision_context": {
            "street": street,
            "hero_position": "",
            "source_frame_id": source_frame_id,
            "solver_preflop_runtime_source": True,
            "solver_stub_legacy_compat": True,
            "solver_decision_id": decision_id,
            "solver_fingerprint": decision_id,
            "solver_raw_action": "safe_runtime_fallback",
            "solver_engine_action": "fold",
            "node_type": "active_invalid_hero_cards",
            "active_invalid_hero_cards": True,
            "safe_runtime_fallback": True,
            "target_sequence": ["FOLD"],
            "clear_json_validation": dict(validation) if isinstance(validation, dict) else validation,
            "fallback_reason": reason,
        },
    }


def _v252_build_invalid_hero_bridge_contract(*, clear_state: dict, table_id: str, reason: str, validation: dict) -> dict:
    action_decision = _v252_build_invalid_hero_action_decision(
        clear_state=clear_state,
        table_id=table_id,
        reason=reason,
        validation=validation,
    )
    return {
        "schema_version": "solver_preflop_dryrun_bridge_v2_52",
        "source": "PokerVision_Solver_Preflop",
        "status": "ok",
        "reason": "v252_active_invalid_hero_cards_safe_runtime_fallback",
        "fallback_reason": reason,
        "table_id": str(table_id or ""),
        "street": _v252_clear_street(clear_state),
        "node_type": "active_invalid_hero_cards",
        "raw_action": "safe_runtime_fallback",
        "engine_action": "fold",
        "target_sequence": ["FOLD"],
        "clear_json_validation": dict(validation) if isinstance(validation, dict) else validation,
        "bridge_payload": {
            "action_decision": action_decision,
        },
    }


def build_solver_preflop_dryrun_bridge_contract(*args, **kwargs):  # type: ignore[no-redef]
    clear_state = kwargs.get("clear_state")
    table_id = str(kwargs.get("table_id") or "")

    invalid_hero, reason, validation = _v252_is_invalid_hero_clear_state(clear_state)
    if invalid_hero:
        return _v252_build_invalid_hero_bridge_contract(
            clear_state=clear_state,
            table_id=table_id,
            reason=reason,
            validation=validation,
        )

    try:
        return _V252_ORIGINAL_BUILD_SOLVER_PREFLOP_DRYRUN_BRIDGE_CONTRACT(*args, **kwargs)
    except Exception:
        invalid_hero_after_error, fallback_reason, fallback_validation = _v252_is_invalid_hero_clear_state(clear_state)
        if invalid_hero_after_error:
            return _v252_build_invalid_hero_bridge_contract(
                clear_state=clear_state,
                table_id=table_id,
                reason=f"{fallback_reason}_after_bridge_exception",
                validation=fallback_validation,
            )
        raise

