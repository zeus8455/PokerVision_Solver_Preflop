r"""
logic/table_action_transaction_gate.py

PokerVision V2.2 — early per-table transaction lifecycle gate + duplicate lifecycle lock fix.

Purpose:
- Keep a per-table transaction state after a strong Active table lifecycle starts.
- Block repeated heavy analysis while the same table is already in an unfinished
  analysis/action/click lifecycle.
- Keep detector/runtime details outside this module; display_analysis_cycle owns
  detector calls, JSON publication, and click runtime.

This gate is not a click executor. It decides whether a table may start analysis,
when it may enter action/click runtime, and whether the final click/dry-run result
is sufficient to publish Final Clear_JSON.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


_COMPLETED_STATUSES = {"clicked", "confirmed", "dry_run"}
_FAILED_STATUSES = {"blocked", "error", "timeout", "failed"}
_OPEN_PHASES = {
    "active_detected",
    "analyzing",
    "clear_json_saved",
    "clear_json_not_saved",
    "waiting_click",
    "click_pending",
    "click_failed",
}
_TERMINAL_PHASES = {"released", "click_done", "aborted"}


@dataclass(frozen=True)
class TableActionTransactionDecision:
    should_process: bool
    status: str
    reason: str
    table_id: str
    transaction_id: Optional[str] = None
    action_event_id: Optional[str] = None
    phase: str = "idle"
    locked_by_transaction_id: Optional[str] = None
    previous_action_event_id: Optional[str] = None
    lifecycle_stage: str = "action_cycle"

    def to_json(self) -> Dict[str, object]:
        analysis_stage = self.lifecycle_stage == "analysis_cycle"
        return {
            "gate_version": "v21_table_lifecycle_gate_audit_2026_05_17",
            "schema_version": "table_lifecycle_gate_v2_1",
            "should_process": self.should_process,
            "status": self.status,
            "reason": self.reason,
            "table_id": self.table_id,
            "transaction_id": self.transaction_id,
            "action_event_id": self.action_event_id,
            "phase": self.phase,
            "locked_by_transaction_id": self.locked_by_transaction_id,
            "previous_action_event_id": self.previous_action_event_id,
            "lifecycle_stage": self.lifecycle_stage,
            "heavy_analysis_allowed": bool(self.should_process) if analysis_stage else None,
            "heavy_analysis_blocked": (not bool(self.should_process)) if analysis_stage else None,
            "blocked_reason": self.reason if analysis_stage and not self.should_process else None,
        }


@dataclass
class _TableTransactionState:
    table_id: str
    transaction_id: str
    action_event_id: Optional[str]
    action_signature: Optional[str]
    phase: str = "active_detected"
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    clear_json_path: Optional[str] = None
    final_status: Optional[str] = None
    final_message: Optional[str] = None
    lifecycle_reason: Optional[str] = None


class TableActionTransactionGate:
    """Per-table lifecycle lock for Active -> analysis -> action -> click completion."""

    def __init__(self, *, dry_run_counts_as_completed: bool = True, release_on_inactive: bool = True) -> None:
        self.dry_run_counts_as_completed = bool(dry_run_counts_as_completed)
        self.release_on_inactive = bool(release_on_inactive)
        self._state_by_table_id: Dict[str, _TableTransactionState] = {}

    def reset_table(self, table_id: str) -> None:
        self._state_by_table_id.pop(str(table_id), None)

    def reset_all(self) -> None:
        self._state_by_table_id.clear()

    @staticmethod
    def _build_transaction_id(
        *,
        table_id: str,
        action_event_id: Optional[str],
        action_signature: Optional[str],
    ) -> str:
        base = str(action_event_id or action_signature or f"{table_id}_{int(time.time() * 1000)}")
        return f"tx_{table_id}_{base.replace('evt_', '')[:32]}"

    def begin_analysis_cycle(
        self,
        *,
        table_id: str,
        action_event_id: Optional[str] = None,
        action_signature: Optional[str] = None,
    ) -> TableActionTransactionDecision:
        """
        Start the early lifecycle lock before expensive table-analysis stages.

        This method intentionally does not require an action_signature because the
        full signature is only available after detector stages. It only prevents a
        second pass from entering heavy analysis while a previous lifecycle for the
        same table is still open.
        """
        table_id_clean = str(table_id)
        current = self._state_by_table_id.get(table_id_clean)
        if current is not None and current.phase in _OPEN_PHASES:
            return TableActionTransactionDecision(
                should_process=False,
                status="blocked",
                reason="table_lifecycle_already_open_before_analysis",
                table_id=table_id_clean,
                transaction_id=current.transaction_id,
                action_event_id=action_event_id,
                phase=current.phase,
                locked_by_transaction_id=current.transaction_id,
                previous_action_event_id=current.action_event_id,
                lifecycle_stage="analysis_cycle",
            )

        tx_id = self._build_transaction_id(
            table_id=table_id_clean,
            action_event_id=action_event_id,
            action_signature=action_signature,
        )
        self._state_by_table_id[table_id_clean] = _TableTransactionState(
            table_id=table_id_clean,
            transaction_id=tx_id,
            action_event_id=action_event_id,
            action_signature=action_signature,
            phase="analyzing",
            lifecycle_reason="early_analysis_cycle_started",
        )
        return TableActionTransactionDecision(
            should_process=True,
            status="started",
            reason="new_active_table_analysis_lifecycle_started",
            table_id=table_id_clean,
            transaction_id=tx_id,
            action_event_id=action_event_id,
            phase="analyzing",
            lifecycle_stage="analysis_cycle",
        )

    def begin_action_cycle(
        self,
        *,
        table_id: str,
        action_event_id: Optional[str],
        action_signature: Optional[str],
    ) -> TableActionTransactionDecision:
        """
        Enter action/click phase for an already-started lifecycle, or start one
        for legacy callers that still open the gate late.
        """
        table_id_clean = str(table_id)
        current = self._state_by_table_id.get(table_id_clean)

        if current is not None and current.phase in {"active_detected", "analyzing"}:
            current.phase = "waiting_click"
            current.updated_at = time.time()
            current.action_event_id = action_event_id or current.action_event_id
            current.action_signature = action_signature or current.action_signature
            current.lifecycle_reason = "analysis_lifecycle_entered_action_runtime"
            return TableActionTransactionDecision(
                should_process=True,
                status="continued",
                reason="active_table_lifecycle_entered_action_runtime",
                table_id=table_id_clean,
                transaction_id=current.transaction_id,
                action_event_id=current.action_event_id,
                phase=current.phase,
                lifecycle_stage="action_cycle",
            )

        if current is not None and current.phase not in _TERMINAL_PHASES:
            return TableActionTransactionDecision(
                should_process=False,
                status="blocked",
                reason="table_action_transaction_already_open",
                table_id=table_id_clean,
                transaction_id=current.transaction_id,
                action_event_id=action_event_id,
                phase=current.phase,
                locked_by_transaction_id=current.transaction_id,
                previous_action_event_id=current.action_event_id,
                lifecycle_stage="action_cycle",
            )

        tx_id = self._build_transaction_id(
            table_id=table_id_clean,
            action_event_id=action_event_id,
            action_signature=action_signature,
        )
        self._state_by_table_id[table_id_clean] = _TableTransactionState(
            table_id=table_id_clean,
            transaction_id=tx_id,
            action_event_id=action_event_id,
            action_signature=action_signature,
            phase="waiting_click",
            lifecycle_reason="late_action_cycle_started",
        )
        return TableActionTransactionDecision(
            should_process=True,
            status="started",
            reason="new_active_action_transaction_started",
            table_id=table_id_clean,
            transaction_id=tx_id,
            action_event_id=action_event_id,
            phase="waiting_click",
            lifecycle_stage="action_cycle",
        )

    def abort_analysis_cycle(self, *, table_id: str, reason: str, message: Optional[str] = None) -> Dict[str, object]:
        """Release an early lifecycle that never reached a completed action/click cycle."""
        table_id_clean = str(table_id)
        state = self._state_by_table_id.get(table_id_clean)
        if state is None:
            return {
                "gate_version": "v21_table_lifecycle_gate_audit_2026_05_17",
                "status": "skipped",
                "reason": "no_open_transaction",
                "table_id": table_id_clean,
                "click_completed": False,
            }
        report = self.snapshot(table_id_clean) or {}
        state.phase = "aborted"
        state.updated_at = time.time()
        state.final_status = "aborted"
        state.final_message = str(message or reason)
        report.update({
            "status": "aborted",
            "reason": str(reason),
            "message": str(message or reason),
            "click_completed": False,
        })
        self._state_by_table_id.pop(table_id_clean, None)
        return report


    def release_failed_active_finalization(
        self,
        *,
        table_id: str,
        reason: str,
        message: Optional[str] = None,
    ) -> Dict[str, object]:
        """Release an Active lifecycle that cannot reach click completion.

        V4.1: if a strong Active frame fails Clear_JSON/Decision/RuntimePlan
        finalization, the transaction must not remain in waiting_click or
        click_pending. This release path keeps the Dark_JSON audit but frees the
        table so later streets/new Active signatures are not blocked by an
        impossible click cycle.
        """
        return self.abort_analysis_cycle(
            table_id=table_id,
            reason=str(reason or "failed_active_finalization_released"),
            message=str(message or reason or "Failed Active finalization released the table lifecycle."),
        )

    def mark_clear_json_saved(self, *, table_id: str, clear_json_path: Optional[str]) -> Dict[str, object]:
        state = self._state_by_table_id.get(str(table_id))
        if state is None:
            return {"status": "skipped", "reason": "no_open_transaction"}
        state.phase = "clear_json_saved" if clear_json_path else "clear_json_not_saved"
        state.clear_json_path = str(clear_json_path) if clear_json_path else None
        state.updated_at = time.time()
        return self.snapshot(str(table_id)) or {"status": "missing"}

    @staticmethod
    def _extract_branch(runtime_action: Dict[str, Any]) -> Dict[str, Any]:
        service = runtime_action.get("service") if isinstance(runtime_action.get("service"), dict) else {}
        action = runtime_action.get("action_button") if isinstance(runtime_action.get("action_button"), dict) else {}
        service_status = str(service.get("status") or "skipped")
        action_status = str(action.get("status") or "skipped")
        if service_status in _COMPLETED_STATUSES or service_status in _FAILED_STATUSES:
            return {"branch": "service", **service}
        return {"branch": "action_button", **action}

    def runtime_allows_final_clear_json(self, runtime_action: Dict[str, Any]) -> bool:
        branch = self._extract_branch(runtime_action if isinstance(runtime_action, dict) else {})
        status = str(branch.get("status") or "skipped")
        if status == "dry_run" and not self.dry_run_counts_as_completed:
            return False
        return status in _COMPLETED_STATUSES

    def build_click_result(self, runtime_action: Dict[str, Any]) -> Dict[str, object]:
        branch = self._extract_branch(runtime_action if isinstance(runtime_action, dict) else {})
        status = str(branch.get("status") or "skipped")
        return {
            "status": status,
            "branch": str(branch.get("branch") or "unknown"),
            "action": branch.get("solver_action") or branch.get("action"),
            "size_pct": branch.get("size_pct"),
            "dry_run": bool(branch.get("dry_run", False)),
            "real_click_enabled": bool(branch.get("real_click_enabled", False)),
            "guard_passed": bool(branch.get("guard_passed", False)),
            "decision_id": branch.get("decision_id"),
            "message": branch.get("message"),
        }

    def finalize_from_runtime(self, *, table_id: str, runtime_action: Dict[str, Any]) -> Dict[str, object]:
        table_id_clean = str(table_id)
        state = self._state_by_table_id.get(table_id_clean)
        click_result = self.build_click_result(runtime_action)
        completed = self.runtime_allows_final_clear_json(runtime_action)
        status = str(click_result.get("status") or "skipped")

        if state is None:
            return {
                "gate_version": "v21_table_lifecycle_gate_audit_2026_05_17",
                "status": "skipped",
                "reason": "no_open_transaction",
                "table_id": table_id_clean,
                "click_completed": completed,
                "click_result": click_result,
            }

        state.updated_at = time.time()
        state.final_status = status
        state.final_message = str(click_result.get("message") or "")

        if completed:
            state.phase = "click_done"
            report = self.snapshot(table_id_clean) or {}
            report.update({
                "status": "completed",
                "reason": "click_cycle_completed",
                "click_completed": True,
                "click_result": click_result,
            })
            self._state_by_table_id.pop(table_id_clean, None)
            return report

        state.phase = "click_pending" if status == "skipped" else "click_failed"
        report = self.snapshot(table_id_clean) or {}
        report.update({
            "status": "pending" if status == "skipped" else "failed",
            "reason": "click_cycle_not_completed",
            "click_completed": False,
            "click_result": click_result,
        })
        return report

    def observe_inactive(self, table_id: str) -> Optional[Dict[str, object]]:
        table_id_clean = str(table_id)
        state = self._state_by_table_id.get(table_id_clean)
        if state is None:
            return None
        if self.release_on_inactive:
            report = self.snapshot(table_id_clean) or {}
            report.update({"status": "aborted", "reason": "active_disappeared_before_click_completion"})
            self._state_by_table_id.pop(table_id_clean, None)
            return report
        return self.snapshot(table_id_clean)

    def snapshot(self, table_id: str) -> Optional[Dict[str, object]]:
        state = self._state_by_table_id.get(str(table_id))
        if state is None:
            return None
        now = time.time()
        return {
            "gate_version": "v21_table_lifecycle_gate_audit_2026_05_17",
            "table_id": state.table_id,
            "transaction_id": state.transaction_id,
            "action_event_id": state.action_event_id,
            "action_signature": state.action_signature,
            "phase": state.phase,
            "age_sec": round(now - state.started_at, 3),
            "clear_json_path": state.clear_json_path,
            "final_status": state.final_status,
            "final_message": state.final_message,
            "lifecycle_reason": state.lifecycle_reason,
        }
