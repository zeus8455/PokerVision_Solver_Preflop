"""
logic/controlled_real_click_scope.py
PokerVision V1.1.3 — controlled one-shot real-click scope.

Purpose:
- Add a narrow runtime scope in front of ClickExecutionGuard.
- Allow first live real-click testing only for Action_Button_Detector branch.
- Block Trigger_UI/service branch from real-clicks.
- Block raise/bet/size buttons during the first controlled live-click stage.
- Limit real physical clicks per process/run.

This module does not move the mouse and does not import pyautogui.
It only returns a compact audit dict that can be written to Dark_JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, Iterable, Optional, Set


_SIMPLE_ACTIONS = {"fold", "check", "call", "check_fold"}
_RAISE_OR_SIZE_BUTTONS = {"33%", "50%", "70%", "98%", "Bet", "Raise", "Bet/Raise"}
_SERVICE_BRANCHES = {"trigger_ui", "trigger_ui_service", "service", "service_click"}
_ACTION_BUTTON_BRANCH = "action_button"


@dataclass(frozen=True)
class ControlledRealClickScopeConfig:
    """Static safety policy for first controlled real-click tests."""

    enabled: bool = True
    test_mode: bool = True
    table_id: str = "table_01"
    allowed_table_ids: Iterable[str] = ("table_01", "table_02", "table_03", "table_04", "table_05", "table_06")
    max_real_clicks_per_run: int = 1
    action_button_only: bool = True
    service_branch_disabled: bool = True
    simple_actions_only: bool = True
    raise_branch_enabled: bool = False


@dataclass(frozen=True)
class ControlledRealClickScopeRequest:
    """Minimal normalized data needed before click guard/runtime execution."""

    table_id: str
    runtime_branch: str
    action: str
    decision_id: str
    target_button_class: str
    dry_run: bool
    real_click_enabled: bool
    source: str = "Action_Runtime_Plan_JSON"
    target_sequence: Iterable[str] = field(default_factory=tuple)
    already_executed_decision_ids: Iterable[str] = field(default_factory=tuple)


@dataclass
class ControlledRealClickScope:
    """Process-local one-shot scope for controlled live-click testing."""

    config: ControlledRealClickScopeConfig = field(default_factory=ControlledRealClickScopeConfig)
    executed_real_click_decision_ids: Set[str] = field(default_factory=set)
    executed_real_clicks_count: int = 0

    def evaluate(self, request: ControlledRealClickScopeRequest) -> Dict[str, Any]:
        cfg = self.config
        wants_real_click = bool(request.real_click_enabled) and not bool(request.dry_run)
        action = _normalize_action(request.action)
        branch = str(request.runtime_branch or "").strip().lower()
        target_button = str(request.target_button_class or "").strip()
        decision_id = str(request.decision_id or "").strip()
        table_id = str(request.table_id or "").strip()
        target_sequence = [str(x).strip() for x in request.target_sequence if str(x).strip()]

        audit_base: Dict[str, Any] = {
            "schema_version": "controlled_real_click_scope_v1",
            "enabled": bool(cfg.enabled),
            "test_mode": bool(cfg.test_mode),
            "table_id": table_id,
            "configured_table_id": cfg.table_id,
            "allowed_table_ids": [str(x) for x in cfg.allowed_table_ids],
            "runtime_branch": branch,
            "action": action,
            "decision_id": decision_id,
            "target_button_class": target_button,
            "target_sequence": target_sequence,
            "dry_run": bool(request.dry_run),
            "real_click_enabled": bool(request.real_click_enabled),
            "wants_real_click": wants_real_click,
            "executed_real_clicks_count": int(self.executed_real_clicks_count),
            "max_real_clicks_per_run": int(cfg.max_real_clicks_per_run),
            "raise_branch_enabled": bool(cfg.raise_branch_enabled),
            "service_branch_disabled": bool(cfg.service_branch_disabled),
            "action_button_only": bool(cfg.action_button_only),
            "simple_actions_only": bool(cfg.simple_actions_only),
        }

        if not cfg.enabled:
            return _allowed(audit_base, "scope_disabled", "ControlledRealClickScope is disabled by config.")

        if not wants_real_click:
            return _allowed(audit_base, "dry_run_or_no_real_click_requested", "Dry-run/no-click path is allowed by scope.")

        if cfg.test_mode and cfg.table_id and table_id != cfg.table_id:
            return _blocked(
                audit_base,
                "wrong_table_id",
                f"Controlled real-click is allowed only for {cfg.table_id}; got {table_id}.",
            )

        if cfg.action_button_only and branch != _ACTION_BUTTON_BRANCH:
            return _blocked(
                audit_base,
                "non_action_button_branch",
                "Controlled real-click allows only Action_Button_Detector/action_button branch.",
            )

        if cfg.service_branch_disabled and branch in _SERVICE_BRANCHES:
            return _blocked(
                audit_base,
                "service_branch_disabled",
                "Trigger_UI/service real-click branch is disabled for this stage.",
            )

        if cfg.simple_actions_only and action not in _SIMPLE_ACTIONS:
            return _blocked(
                audit_base,
                "non_simple_action_blocked",
                "Only fold/check/call/check_fold are allowed in the first controlled real-click stage.",
            )

        sequence_buttons = set(target_sequence + ([target_button] if target_button else []))
        if not cfg.raise_branch_enabled and sequence_buttons.intersection(_RAISE_OR_SIZE_BUTTONS):
            return _blocked(
                audit_base,
                "raise_or_size_branch_blocked",
                "Raise/Bet/33/50/70/98 branch is disabled for the first controlled real-click stage.",
            )

        if not decision_id:
            return _blocked(audit_base, "missing_decision_id", "Real-click scope requires non-empty decision_id.")

        previous_ids = {str(x).strip() for x in request.already_executed_decision_ids if str(x).strip()}
        previous_ids.update(self.executed_real_click_decision_ids)
        if decision_id in previous_ids:
            return _blocked(
                audit_base,
                "decision_id_already_executed_in_scope",
                "This decision_id was already executed in current controlled scope.",
            )

        if self.executed_real_clicks_count >= int(cfg.max_real_clicks_per_run):
            return _blocked(
                audit_base,
                "max_real_clicks_per_run_reached",
                "Controlled real-click limit for this run has already been reached.",
            )

        return _allowed(audit_base, "controlled_scope_passed", "Controlled real-click scope passed.")

    def record_success(self, decision_id: str) -> Dict[str, Any]:
        """Record a confirmed real-click after the mouse runtime reports success."""

        clean_decision_id = str(decision_id or "").strip()
        if clean_decision_id:
            self.executed_real_click_decision_ids.add(clean_decision_id)
            self.executed_real_clicks_count += 1
        return {
            "schema_version": "controlled_real_click_scope_v1",
            "status": "recorded",
            "decision_id": clean_decision_id,
            "executed_real_clicks_count": int(self.executed_real_clicks_count),
            "max_real_clicks_per_run": int(self.config.max_real_clicks_per_run),
        }


def build_controlled_real_click_scope_from_config() -> ControlledRealClickScope:
    """
    Build scope from config.py when flags exist.
    Defaults are safe and keep the project compatible before config.py is updated.
    """

    try:
        import config as project_config  # type: ignore
    except Exception:
        project_config = None

    def get(name: str, default: Any) -> Any:
        return getattr(project_config, name, default) if project_config is not None else default

    allowed_table_ids = tuple(str(x) for x in get(
        "V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS",
        ("table_01", "table_02", "table_03", "table_04", "table_05", "table_06"),
    ))

    def _effective_table_id() -> str:
        explicit_v11 = get("V11_CONTROLLED_REAL_CLICK_TABLE_ID", None)
        if explicit_v11:
            return str(explicit_v11)
        helper = getattr(project_config, "get_v31_controlled_live_click_target_table_id", None) if project_config is not None else None
        if callable(helper):
            return str(helper())
        env_var = str(get("V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR", "POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_ID"))
        default_table = str(get("V31_CONTROLLED_LIVE_CLICK_TABLE_ID", "table_01"))
        env_table = os.environ.get(env_var, "")
        return env_table if env_table in allowed_table_ids else default_table

    cfg = ControlledRealClickScopeConfig(
        enabled=bool(get("V11_CONTROLLED_REAL_CLICK_SCOPE_ENABLED", True)),
        test_mode=bool(get("V11_CONTROLLED_REAL_CLICK_TEST_MODE", True)),
        table_id=_effective_table_id(),
        allowed_table_ids=allowed_table_ids,
        max_real_clicks_per_run=int(get("V11_CONTROLLED_REAL_CLICK_MAX_CLICKS_PER_RUN", 1)),
        action_button_only=bool(get("V11_CONTROLLED_REAL_CLICK_ACTION_BUTTON_ONLY", True)),
        service_branch_disabled=bool(get("V11_CONTROLLED_REAL_CLICK_SERVICE_BRANCH_DISABLED", True)),
        simple_actions_only=bool(get("V11_CONTROLLED_REAL_CLICK_SIMPLE_ACTIONS_ONLY", True)),
        raise_branch_enabled=bool(get("V11_CONTROLLED_REAL_CLICK_RAISE_BRANCH_ENABLED", False)),
    )
    return ControlledRealClickScope(cfg)


def _normalize_action(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace("/", "_")
    aliases = {
        "checkfold": "check_fold",
        "check_fold": "check_fold",
        "fold": "fold",
        "check": "check",
        "call": "call",
        "bet": "bet",
        "raise": "raise",
        "bet_raise": "raise",
        "betraise": "raise",
    }
    return aliases.get(text, text)


def _allowed(base: Dict[str, Any], reason: str, message: str) -> Dict[str, Any]:
    out = dict(base)
    out.update({"status": "allowed", "scope_passed": True, "reason": reason, "message": message})
    return out


def _blocked(base: Dict[str, Any], reason: str, message: str) -> Dict[str, Any]:
    out = dict(base)
    out.update({"status": "blocked", "scope_passed": False, "reason": reason, "message": message})
    return out
