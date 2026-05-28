r"""
logic/real_click_readiness.py

PokerVision V1.0 controlled real-click readiness validator.

Purpose:
- Do not execute clicks.
- Validate startup configuration before a future real-click run.
- Keep default V0.9/V1.0 no-click data capture mode safe.
- Permit real-click readiness only when every required safety switch is aligned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class RealClickReadinessResult:
    schema_version: str
    ok: bool
    status: str
    reason: str
    real_click_ready: bool
    abort_startup: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "real_click_ready": self.real_click_ready,
            "abort_startup": self.abort_startup,
            "checks": dict(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "config_snapshot": dict(self.config_snapshot),
        }


_FIELD_DEFAULTS: Dict[str, Any] = {
    "V10_REAL_CLICK_READINESS_SCHEMA_VERSION": "real_click_readiness_v1",
    "V10_REAL_CLICK_READINESS_VALIDATOR_ENABLED": True,
    "V10_REAL_CLICK_ABORT_ON_UNSAFE_CONFIG": True,
    "V10_REAL_CLICK_ALLOW_ACTION_BUTTON_ONLY": True,
    "V10_REAL_CLICK_REQUIRE_SERVICE_CLICKS_DISABLED": True,
    "V10_REAL_CLICK_REQUIRE_LIVE_NO_CLICK_DISABLED": True,
    "V10_REAL_CLICK_REQUIRE_MASTER_ARMED": True,
    "V10_REAL_CLICK_REQUIRE_MOUSE_REAL_ENABLED": True,
    "V10_REAL_CLICK_REQUIRE_MOUSE_DRY_RUN_DISABLED": True,
    "V09_CLICK_EXECUTION_GUARD_ENABLED": True,
    "V09_REAL_CLICK_MASTER_ARMED": False,
    "V09_REQUIRE_SLOT_BOUNDARY_GUARD": True,
    "V09_REQUIRE_NO_REPEAT_DECISION_GUARD": True,
    "V09_REQUIRE_BUTTON_AVAILABILITY_GUARD": True,
    "V09_REQUIRE_ACTION_RUNTIME_PLAN_SOURCE": "Action_Runtime_Plan_JSON",
    "V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK": True,
    "V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE": True,
    "V11_REAL_MOUSE_CLICK_ENABLED": False,
    "V11_CLICK_DRY_RUN": True,
    "V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED": False,
    "V11_TRIGGER_UI_SERVICE_DRY_RUN": True,
}


def _read(config: Any, name: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(name, _FIELD_DEFAULTS.get(name))
    return getattr(config, name, _FIELD_DEFAULTS.get(name))


def _snapshot(config: Any) -> Dict[str, Any]:
    return {name: _read(config, name) for name in _FIELD_DEFAULTS}


def _is_any_real_click_requested(snapshot: Mapping[str, Any]) -> bool:
    return bool(
        snapshot.get("V09_REAL_CLICK_MASTER_ARMED")
        or snapshot.get("V11_REAL_MOUSE_CLICK_ENABLED")
        or snapshot.get("V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED")
        or snapshot.get("V11_CLICK_DRY_RUN") is False
        or snapshot.get("V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE") is False
    )


def validate_real_click_readiness(config: Any) -> RealClickReadinessResult:
    """Validate whether the current config may proceed.

    Default no-click data capture mode returns ok=True, real_click_ready=False.
    Any partially enabled real-click mode must satisfy all safety requirements.
    """

    snap = _snapshot(config)
    schema = str(snap.get("V10_REAL_CLICK_READINESS_SCHEMA_VERSION") or "real_click_readiness_v1")
    enabled = bool(snap.get("V10_REAL_CLICK_READINESS_VALIDATOR_ENABLED"))
    abort_on_unsafe = bool(snap.get("V10_REAL_CLICK_ABORT_ON_UNSAFE_CONFIG"))

    if not enabled:
        return RealClickReadinessResult(
            schema_version=schema,
            ok=True,
            status="disabled",
            reason="real_click_readiness_validator_disabled",
            real_click_ready=False,
            abort_startup=False,
            checks={},
            warnings=["V10 real-click readiness validator is disabled."],
            config_snapshot=snap,
        )

    any_real_click_requested = _is_any_real_click_requested(snap)

    service_clicks_must_be_disabled = bool(snap.get("V10_REAL_CLICK_REQUIRE_SERVICE_CLICKS_DISABLED"))

    checks: Dict[str, bool] = {
        "click_execution_guard_enabled": bool(snap.get("V09_CLICK_EXECUTION_GUARD_ENABLED")),
        "slot_boundary_guard_required": bool(snap.get("V09_REQUIRE_SLOT_BOUNDARY_GUARD")),
        "no_repeat_decision_guard_required": bool(snap.get("V09_REQUIRE_NO_REPEAT_DECISION_GUARD")),
        "button_availability_guard_required": bool(snap.get("V09_REQUIRE_BUTTON_AVAILABILITY_GUARD")),
        "runtime_plan_source_required": snap.get("V09_REQUIRE_ACTION_RUNTIME_PLAN_SOURCE") == "Action_Runtime_Plan_JSON",
        "service_real_click_disabled": (
            not service_clicks_must_be_disabled
            or not bool(snap.get("V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED"))
        ),
        "service_dry_run_enabled": (
            not service_clicks_must_be_disabled
            or bool(snap.get("V11_TRIGGER_UI_SERVICE_DRY_RUN"))
        ),
        "service_clicks_must_be_disabled": True,
    }

    # Safe default: no physical click mode. This is allowed, but not real-click ready.
    if not any_real_click_requested:
        errors = [name for name, ok in checks.items() if not ok]
        return RealClickReadinessResult(
            schema_version=schema,
            ok=not errors,
            status="safe_no_click" if not errors else "unsafe_no_click_config",
            reason="live_data_capture_no_click_mode" if not errors else "required_safety_guards_missing",
            real_click_ready=False,
            abort_startup=bool(errors and abort_on_unsafe),
            checks=checks,
            errors=errors,
            config_snapshot=snap,
        )

    # Controlled real-click mode: all action-click guards must be explicitly aligned.
    real_checks: Dict[str, bool] = {
        **checks,
        "master_armed": bool(snap.get("V09_REAL_CLICK_MASTER_ARMED")),
        "action_mouse_real_enabled": bool(snap.get("V11_REAL_MOUSE_CLICK_ENABLED")),
        "action_mouse_dry_run_disabled": snap.get("V11_CLICK_DRY_RUN") is False,
        "live_no_click_mode_disabled": snap.get("V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE") is False,
        "live_no_click_real_block_configured": bool(snap.get("V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK")),
        "action_button_only_mode": bool(snap.get("V10_REAL_CLICK_ALLOW_ACTION_BUTTON_ONLY")),
        "service_clicks_disabled_for_v10": (
            not service_clicks_must_be_disabled
            or (
                not bool(snap.get("V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED"))
                and bool(snap.get("V11_TRIGGER_UI_SERVICE_DRY_RUN"))
            )
        ),
    }

    errors = [name for name, ok in real_checks.items() if not ok]
    ok = not errors
    return RealClickReadinessResult(
        schema_version=schema,
        ok=ok,
        status="ready_for_controlled_real_click" if ok else "unsafe_real_click_config",
        reason="all_real_click_readiness_checks_passed" if ok else "real_click_readiness_checks_failed",
        real_click_ready=ok,
        abort_startup=bool((not ok) and abort_on_unsafe),
        checks=real_checks,
        errors=errors,
        config_snapshot=snap,
    )


def format_readiness_for_console(result: RealClickReadinessResult) -> List[str]:
    """Return stable console lines for main.py startup diagnostics."""
    lines = [
        f"[V10_REAL_CLICK_READINESS] status={result.status} ok={result.ok} real_click_ready={result.real_click_ready}",
        f"[V10_REAL_CLICK_READINESS] reason={result.reason} abort_startup={result.abort_startup}",
    ]
    if result.errors:
        lines.append(f"[V10_REAL_CLICK_READINESS] errors={','.join(result.errors)}")
    return lines
