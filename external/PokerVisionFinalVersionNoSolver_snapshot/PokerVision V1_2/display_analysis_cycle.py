r"""
display_analysis_cycle.py

PokerVision Core V3.1 — live desktop analysis cycle + controlled live-click gate audit.

Что делает каждый display-pass:
1. При первом pass удаляет старую outputs/ui_display_cycle.
2. Делает screenshot основного монитора.
3. V1.2 обрабатывает реальные table_N области рабочего стола; тестовые изображения не открываются.
4. Запускает полный detector pipeline:
   Trigger UI -> Table Structure -> Players -> Digit Amounts -> Card Detection.
5. После детекций V1 HandIdentityTracker решает для каждой области table_N:
   - новая это раздача или продолжение прошлой;
   - base hand_id: hand_01, hand_02, ...;
   - frame_name для JSON: hand_01_preflop, hand_01_flop,
     hand_08_preflop_02 и т.д.
6. Сохраняет clean JSON с filename == frame_name.json.
7. V1.1 Stage 2: после сохранения JSON запускает безопасную runtime-цепочку
   solver_payload -> solver_stub -> Action_Button_Detector -> click dry-run report.
8. Не выполняет сверку с эталонными JSON; сохраняет только собственные результаты анализа.

Ключевое правило V1:
- отсутствие strong Active = отдельный hand_N без продолжения;
- strong Active + те же HERO cards Player_seat1 в той же table-области = та же раздача;
- strong Active + другие HERO cards = новая раздача.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import (
    CARD_DETECTION_ENABLED,
    CARD_DETECTION_REQUIRE_PLAYERS,
    CLEAR_PREVIOUS_UI_DISPLAY_OUTPUTS_ON_BUTTON_CLICK,
    CURRENT_CYCLE_DIR_NAME,
    DEFAULT_DISPLAY_PASS_ID,
    DIGIT_AMOUNTS_ENABLED,
    DIGIT_AMOUNTS_REQUIRE_PLAYERS,
    PLAYER_STATE_ENABLED,
    PLAYER_STATE_REQUIRE_TABLE_STRUCTURE,
    RUNTIME_HAND_ID_PREFIX,
    RUNTIME_HAND_NUMBER_MIN_WIDTH,
    SAVE_DEBUG_DESKTOP_CAPTURE,
    SAVE_DEBUG_TABLE_CROPS,
    TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE,
    TABLE_STRUCTURE_ENABLED,
    TABLE_STRUCTURE_REQUIRE_ACTIVE,
    TRIGGER_UI_ENABLED,
    UI_DISPLAY_CYCLE_OUTPUT_DIR,
    V11_CLICK_DRY_RUN,
    V11_REAL_MOUSE_CLICK_ENABLED,
    V11_TRIGGER_UI_SERVICE_DRY_RUN,
    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED,
    V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE,
    V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED,
    V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED,
    V03_TRANSACTION_RELEASE_ON_INACTIVE,
    V04_PENDING_FINAL_CLEAR_JSON_ENABLED,
    V04_CLEAR_JSON_PENDING_DIR_NAME,
    V04_CLEAR_JSON_FINAL_DIR_NAME,
    V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT,
    V04_DELETE_PENDING_AFTER_FINAL_SAVE,
    V05_DECISION_JSON_ENABLED,
    V05_DECISION_JSON_DIR_NAME,
    V06_ACTION_DECISION_ENABLED,
    V06_ACTION_DECISION_DIR_NAME,
    V07_ACTION_RUNTIME_PLAN_ENABLED,
    V07_ACTION_RUNTIME_PLAN_DIR_NAME,
    V10_JSON_COMPLETE_DIR_NAME,
    V08_LIVE_HAND_CONTINUITY_ENABLED,
    V08_INACTIVE_DOES_NOT_RESET_HAND,
    V08_KEEP_LAST_HAND_ON_INVALID_HERO,
    V09_CLICK_EXECUTION_GUARD_ENABLED,
    V09_REAL_CLICK_MASTER_ARMED,
    V09_REQUIRE_SLOT_BOUNDARY_GUARD,
    V09_REQUIRE_NO_REPEAT_DECISION_GUARD,
    V09_REQUIRE_BUTTON_AVAILABILITY_GUARD,
    V09_REQUIRE_ACTION_RUNTIME_PLAN_SOURCE,
    V09_ALLOW_DRY_RUN_COMPLETION,
    V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK,
    V09_CLICK_CONFIRMATION_REPORT_ENABLED,
    V12_SAVE_ONLY_TRIGGERED_TABLES,
    ensure_dir,
)
from json_state import (
    add_error,
    add_warning,
    build_table_frame_state,
    elapsed_ms,
    now_perf_counter,
    save_table_frame_json,
)
from logic.clear_json_builder import (
    build_clear_json_from_dark_state,
    validate_clear_json_contract,
)
from logic.clear_json_recovery import recover_clear_json_state
from logic.decision_json_builder import (
    build_decision_json_from_clear_state,
    validate_decision_json_contract,
)
from logic.action_decision_stub import (
    build_action_decision_from_decision_json,
    validate_action_decision_contract,
)
from logic.action_runtime_plan_builder import (
    build_action_runtime_plan_from_action_decision,
    validate_action_runtime_plan_contract,
)
from runtime.solver_preflop_dryrun_bridge import build_solver_preflop_dryrun_bridge_contract

# V1.7: diagnostic-only Solver_Preflop bridge file publication toggle.
# Default remains False: bridge result is embedded into state/contract only.
V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES = False

# V2.0: snapshot-only runtime source switch scaffold.
# Default remains False: old Action_Decision_JSON remains the runtime source.
V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE = True
V20_SOLVER_PREFLOP_DRY_RUN_ONLY = True
from logic.click_execution_guard import (
    ClickExecutionRequest,
    ClickGuardConfig,
    validate_click_execution_request,
)
from logic.controlled_real_click_scope import (
    ControlledRealClickScopeRequest,
    build_controlled_real_click_scope_from_config,
)
from logic.live_hand_continuity import (
    decide_live_hand_continuity,
    normalize_card_list,
)
from logic.clear_json_state_machine import ClearJsonStateMachine
from logic.table_action_transaction_gate import TableActionTransactionGate
from pipeline.card_detection_pipeline import run_card_detection_pipeline
from pipeline.digit_amounts_pipeline import run_digit_amounts_pipeline
from pipeline.player_state_pipeline import (
    build_skipped_player_state_block,
    run_player_state_pipeline,
)
from pipeline.table_structure_pipeline import (
    build_skipped_table_structure_block,
    run_table_structure_pipeline,
)
from pipeline.trigger_ui_pipeline import run_trigger_ui_pipeline
from table_slots import TableSlot, list_table_slots


try:
    from runtime.v11_stage1_runtime import run_v11_stage1_runtime as _run_v11_stage1_runtime
    V11_STAGE2_RUNTIME_AVAILABLE = True
    V11_STAGE2_IMPORT_ERROR: Optional[str] = None
except Exception as exc:
    _run_v11_stage1_runtime = None
    V11_STAGE2_RUNTIME_AVAILABLE = False
    V11_STAGE2_IMPORT_ERROR = str(exc)

try:
    from runtime.trigger_ui_service_runtime import (
        run_v11_trigger_ui_service_runtime as _run_v11_trigger_ui_service_runtime,
    )
    V11_STAGE25_SERVICE_RUNTIME_AVAILABLE = True
    V11_STAGE25_SERVICE_IMPORT_ERROR: Optional[str] = None
except Exception as exc:
    _run_v11_trigger_ui_service_runtime = None
    V11_STAGE25_SERVICE_RUNTIME_AVAILABLE = False
    V11_STAGE25_SERVICE_IMPORT_ERROR = str(exc)


try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except Exception:
    ImageGrab = None
    PIL_AVAILABLE = False


VALID_STREETS = {"preflop", "flop", "turn", "river"}

# Process-wide Clear_JSON state-machine used by live cycles when caller does not
# inject its own instance. Replay tests inject a fresh instance for deterministic runs.
_DEFAULT_CLEAR_JSON_STATE_MACHINE = ClearJsonStateMachine()
_DEFAULT_TABLE_ACTION_TRANSACTION_GATE = TableActionTransactionGate(
    dry_run_counts_as_completed=V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED,
    release_on_inactive=V03_TRANSACTION_RELEASE_ON_INACTIVE,
)
_DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE: Dict[str, Set[str]] = {}
_DEFAULT_CONTROLLED_REAL_CLICK_SCOPE = build_controlled_real_click_scope_from_config()


@dataclass(frozen=True)
class FrameIdentity:
    hand_id: str
    frame_name: str
    is_continuation: bool
    active_confirmed: bool
    hero_cards_key: Optional[Tuple[str, str]]
    street: Optional[str]
    street_occurrence: Optional[int]
    warning: Optional[str] = None


@dataclass
class _TrackedTableHand:
    hand_id: str
    hero_cards_key: Tuple[str, str]
    street_counts: Dict[str, int] = field(default_factory=dict)
    last_board_cards: List[str] = field(default_factory=list)
    last_street: Optional[str] = None
    inactive_pass_count: int = 0




@dataclass(frozen=True)
class ActionEventDecision:
    """Runtime gate decision for one visible Active action spot."""

    should_process: bool
    action_event_id: Optional[str]
    action_signature: Optional[str]
    reason: str
    duplicate_of: Optional[str] = None
    event_index: Optional[int] = None

    def to_json(self) -> Dict[str, object]:
        return {
            "gate_version": "v12_action_event_gate_2026_05_12",
            "should_process": self.should_process,
            "action_event_id": self.action_event_id,
            "action_signature": self.action_signature,
            "reason": self.reason,
            "duplicate_of": self.duplicate_of,
            "event_index": self.event_index,
        }


@dataclass
class _ActionEventTableState:
    active_latched: bool = False
    no_active_pass_count: int = 0
    last_processed_signature: Optional[str] = None
    last_processed_event_id: Optional[str] = None
    event_index: int = 0


class ActionEventGate:
    """
    One-shot gate for Active frames.

    It prevents a live scan loop from creating a new JSON/solver payload every
    900 ms while the same Active spot is still visible. A new JSON is allowed
    only when the normalized action signature changes, or after Active has been
    absent for a small debounce window.
    """

    def __init__(self, *, inactive_reset_passes: int = 2) -> None:
        self.inactive_reset_passes = max(1, int(inactive_reset_passes))
        self._state_by_table_id: Dict[str, _ActionEventTableState] = {}

    def _state(self, table_id: str) -> _ActionEventTableState:
        if table_id not in self._state_by_table_id:
            self._state_by_table_id[table_id] = _ActionEventTableState()
        return self._state_by_table_id[table_id]

    def observe_inactive(self, table_id: str) -> None:
        state = self._state(table_id)
        state.no_active_pass_count += 1
        if state.no_active_pass_count >= self.inactive_reset_passes:
            state.active_latched = False
            state.last_processed_signature = None
            state.last_processed_event_id = None

    @staticmethod
    def _normalize_amount(value: Any) -> Optional[float | str]:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        text = str(value).strip()
        if not text:
            return None
        try:
            return round(float(text), 2)
        except ValueError:
            return text

    @staticmethod
    def _extract_board_cards(table_structure_block: Optional[Dict[str, Any]]) -> List[str]:
        classes = (table_structure_block or {}).get("classes") if isinstance(table_structure_block, dict) else None
        board = (classes or {}).get("Board") if isinstance(classes, dict) else None
        cards = (board or {}).get("cards") if isinstance(board, dict) else None
        return [str(card) for card in cards] if isinstance(cards, list) else []

    @classmethod
    def _extract_total_pot(cls, table_structure_block: Optional[Dict[str, Any]]) -> Optional[float | str]:
        classes = (table_structure_block or {}).get("classes") if isinstance(table_structure_block, dict) else None
        total_pot = (classes or {}).get("Total_pot") if isinstance(classes, dict) else None
        value = (total_pot or {}).get("value") if isinstance(total_pot, dict) else None
        return cls._normalize_amount(value)

    @staticmethod
    def _seat_cards_for_signature(seat: Dict[str, Any]) -> List[str]:
        raw_cards = seat.get("cards") if isinstance(seat, dict) else None
        if not isinstance(raw_cards, list):
            return []
        return sorted(str(card) for card in raw_cards if str(card).strip())

    @classmethod
    def _extract_player_action_facts(cls, players_block: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, object]]:
        seats = (players_block or {}).get("seats") if isinstance(players_block, dict) else None
        if not isinstance(seats, dict):
            return {}

        facts: Dict[str, Dict[str, object]] = {}
        for seat_name in sorted(seats.keys()):
            seat = seats.get(seat_name)
            if not isinstance(seat, dict):
                continue

            chips = seat.get("chips") if isinstance(seat.get("chips"), dict) else {}
            stack = seat.get("stack") if isinstance(seat.get("stack"), dict) else {}
            cards = cls._seat_cards_for_signature(seat)

            chips_detect = bool(chips.get("detect", False))
            chips_value = cls._normalize_amount(chips.get("value"))
            fold = bool(seat.get("fold", False))
            sitout = bool(seat.get("sitout", False))
            all_in = bool(stack.get("all_in", False))
            hero = bool(seat.get("hero", False))

            # V1.0.2: ActionEventGate must ignore raw empty/fold-only seat noise.
            # Some live frames briefly add extra Player_seatN rows with only a
            # logical position and fold=True, while Final Clear_JSON later filters
            # them out. Including those rows in the signature creates false
            # new_active_action_event values and duplicate Final Clear_JSON files.
            # A seat is action-significant only when it has proof of participation
            # or a current actionable state: HERO/cards, chips contribution, sitout,
            # or all-in. A bare fold flag without cards/chips is not enough.
            has_chips_fact = chips_detect or chips_value is not None
            has_cards_fact = bool(cards)
            signature_relevant = hero or has_cards_fact or has_chips_fact or sitout or all_in
            if not signature_relevant:
                continue

            facts[str(seat_name)] = {
                "position": seat.get("position"),
                "hero": hero,
                "fold": fold,
                "sitout": sitout,
                "chips_detect": chips_detect,
                "chips_value": chips_value,
                "all_in": all_in,
            }
        return facts

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def build_signature(
        self,
        *,
        table_id: str,
        hero_cards: List[str],
        street: Optional[str],
        table_structure_block: Optional[Dict[str, Any]],
        players_block: Optional[Dict[str, Any]],
    ) -> str:
        payload: Dict[str, Any] = {
            "table_id": table_id,
            "hero_cards": sorted(str(card) for card in hero_cards if str(card).strip()),
            "street": str(street or "unknown").lower(),
            "board_cards": self._extract_board_cards(table_structure_block),
            "total_pot": self._extract_total_pot(table_structure_block),
            "player_action_facts": self._extract_player_action_facts(players_block),
        }
        return self._hash_payload(payload)

    def evaluate_active(
        self,
        *,
        table_id: str,
        hero_cards: List[str],
        street: Optional[str],
        table_structure_block: Optional[Dict[str, Any]],
        players_block: Optional[Dict[str, Any]],
    ) -> ActionEventDecision:
        state = self._state(table_id)
        state.no_active_pass_count = 0
        state.active_latched = True

        signature = self.build_signature(
            table_id=table_id,
            hero_cards=hero_cards,
            street=street,
            table_structure_block=table_structure_block,
            players_block=players_block,
        )

        if signature == state.last_processed_signature:
            return ActionEventDecision(
                should_process=False,
                action_event_id=None,
                action_signature=signature,
                reason="duplicate_active_frame_blocked",
                duplicate_of=state.last_processed_event_id,
                event_index=state.event_index,
            )

        state.event_index += 1
        event_id = f"evt_{table_id}_{signature[:16]}"
        state.last_processed_signature = signature
        state.last_processed_event_id = event_id
        return ActionEventDecision(
            should_process=True,
            action_event_id=event_id,
            action_signature=signature,
            reason="new_active_action_event",
            event_index=state.event_index,
        )


class HandIdentityTracker:
    """
    Stateful V1 resolver for real runtime identity.

    Tracker is deliberately independent from source test image names. It consumes
    only detector-derived facts from the current table frame.
    """

    def __init__(self) -> None:
        self._next_hand_number = 1
        self._active_hand_by_table_id: Dict[str, _TrackedTableHand] = {}

    def _allocate_hand_id(self) -> str:
        number = self._next_hand_number
        self._next_hand_number += 1
        return f"{RUNTIME_HAND_ID_PREFIX}_{number:0{RUNTIME_HAND_NUMBER_MIN_WIDTH}d}"

    @staticmethod
    def _normalize_hero_cards(hero_cards: List[str]) -> Optional[Tuple[str, str]]:
        clean = [str(card) for card in hero_cards if str(card).strip()]
        if len(clean) != 2 or len(set(clean)) != 2:
            return None
        return tuple(sorted(clean))  # order-independent hand identity

    @staticmethod
    def _normalize_street(street: Optional[str]) -> Optional[str]:
        normalized = str(street).strip().lower() if street is not None else None
        return normalized if normalized in VALID_STREETS else None

    @staticmethod
    def _build_frame_name(hand_id: str, street: Optional[str], occurrence: Optional[int]) -> str:
        if street is None:
            return hand_id
        if occurrence is None or occurrence <= 1:
            return f"{hand_id}_{street}"
        return f"{hand_id}_{street}_{occurrence:02d}"

    @staticmethod
    def _normalize_board_cards(board_cards: Optional[List[str]]) -> List[str]:
        return normalize_card_list(board_cards)

    @staticmethod
    def _update_tracked_context(
        tracked: _TrackedTableHand,
        *,
        board_cards: List[str],
        street: Optional[str],
    ) -> None:
        if board_cards and len(board_cards) >= len(tracked.last_board_cards):
            tracked.last_board_cards = list(board_cards)
        if street is not None:
            tracked.last_street = street
        tracked.inactive_pass_count = 0

    def resolve(
        self,
        *,
        table_id: str,
        active_confirmed: bool,
        hero_cards: List[str],
        street: Optional[str],
        board_cards: Optional[List[str]] = None,
    ) -> FrameIdentity:
        normalized_street = self._normalize_street(street)
        normalized_board_cards = self._normalize_board_cards(board_cards)

        if not active_confirmed:
            previous = self._active_hand_by_table_id.get(table_id)
            if previous is not None:
                previous.inactive_pass_count += 1

            if not V08_INACTIVE_DOES_NOT_RESET_HAND:
                self._active_hand_by_table_id.pop(table_id, None)

            hand_id = self._allocate_hand_id()
            return FrameIdentity(
                hand_id=hand_id,
                frame_name=hand_id,
                is_continuation=False,
                active_confirmed=False,
                hero_cards_key=None,
                street=None,
                street_occurrence=None,
            )

        hero_cards_key = self._normalize_hero_cards(hero_cards)
        previous = self._active_hand_by_table_id.get(table_id)

        # Без двух валидных HERO cards нельзя надёжно доказать новую руку.
        # V0.4.2: if a table already has a tracked Active hand, a single frame
        # with missing/invalid HERO cards must keep that previous hand_id as an
        # unproven continuation candidate. This does NOT invent HERO cards;
        # hero_cards_key stays None and Clear_JSON remains dependent on normal
        # validation/recovery. The goal is only to avoid allocating a false new
        # hand_id before Clear_JSON recovery has a chance to compare with the
        # previous stable state for the same table/hand.
        if hero_cards_key is None:
            if previous is not None and V08_KEEP_LAST_HAND_ON_INVALID_HERO:
                occurrence = None
                if normalized_street is not None:
                    occurrence = previous.street_counts.get(normalized_street, 0) + 1
                    previous.street_counts[normalized_street] = occurrence
                self._update_tracked_context(
                    previous,
                    board_cards=normalized_board_cards,
                    street=normalized_street,
                )
                warning = (
                    f"{table_id}: strong Active detected, but HERO cards are not exactly two unique cards; "
                    "keeping previous hand_id as an unproven continuation candidate so Clear_JSON recovery "
                    "can compare against the previous stable state. HERO cards were not invented."
                )
                return FrameIdentity(
                    hand_id=previous.hand_id,
                    frame_name=self._build_frame_name(previous.hand_id, normalized_street, occurrence),
                    is_continuation=True,
                    active_confirmed=True,
                    hero_cards_key=None,
                    street=normalized_street,
                    street_occurrence=occurrence,
                    warning=warning,
                )

            hand_id = self._allocate_hand_id()
            if not V08_KEEP_LAST_HAND_ON_INVALID_HERO:
                self._active_hand_by_table_id.pop(table_id, None)
            occurrence = 1 if normalized_street is not None else None
            warning = (
                f"{table_id}: strong Active detected, but HERO cards are not exactly two unique cards; "
                "no previous tracked hand is available, so continuation identity cannot be proven for this frame."
            )
            return FrameIdentity(
                hand_id=hand_id,
                frame_name=self._build_frame_name(hand_id, normalized_street, occurrence),
                is_continuation=False,
                active_confirmed=True,
                hero_cards_key=None,
                street=normalized_street,
                street_occurrence=occurrence,
                warning=warning,
            )

        continuity_decision = None
        is_continuation = False
        if previous is not None and V08_LIVE_HAND_CONTINUITY_ENABLED:
            continuity_decision = decide_live_hand_continuity(
                previous_hero_cards_key=previous.hero_cards_key,
                current_hero_cards_key=hero_cards_key,
                previous_board_cards=previous.last_board_cards,
                current_board_cards=normalized_board_cards,
                previous_street=previous.last_street,
                current_street=normalized_street,
            )
            is_continuation = continuity_decision.should_continue
        elif previous is not None:
            is_continuation = previous.hero_cards_key == hero_cards_key

        if is_continuation and previous is not None:
            tracked = previous
        else:
            tracked = _TrackedTableHand(
                hand_id=self._allocate_hand_id(),
                hero_cards_key=hero_cards_key,
                last_board_cards=list(normalized_board_cards),
                last_street=normalized_street,
            )
            self._active_hand_by_table_id[table_id] = tracked

        occurrence: Optional[int]
        if normalized_street is None:
            occurrence = None
        else:
            occurrence = tracked.street_counts.get(normalized_street, 0) + 1
            tracked.street_counts[normalized_street] = occurrence

        self._update_tracked_context(
            tracked,
            board_cards=normalized_board_cards,
            street=normalized_street,
        )

        warning = None
        if normalized_street is None:
            warning = (
                f"{table_id}: strong Active detected with valid HERO cards, but street is unknown; "
                "frame_name falls back to base hand_id."
            )
        elif continuity_decision is not None and not continuity_decision.should_continue and previous is not None:
            warning = (
                f"{table_id}: V0.8 live hand continuity rejected previous hand: "
                f"{continuity_decision.reason}; a new hand was started."
            )

        return FrameIdentity(
            hand_id=tracked.hand_id,
            frame_name=self._build_frame_name(tracked.hand_id, normalized_street, occurrence),
            is_continuation=is_continuation,
            active_confirmed=True,
            hero_cards_key=hero_cards_key,
            street=normalized_street,
            street_occurrence=occurrence,
            warning=warning,
        )

def make_cycle_id() -> str:
    return "cycle_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def clear_previous_outputs() -> None:
    if not CLEAR_PREVIOUS_UI_DISPLAY_OUTPUTS_ON_BUTTON_CLICK:
        return

    if UI_DISPLAY_CYCLE_OUTPUT_DIR.exists():
        shutil.rmtree(UI_DISPLAY_CYCLE_OUTPUT_DIR)


def build_cycle_dir() -> Path:
    return UI_DISPLAY_CYCLE_OUTPUT_DIR / CURRENT_CYCLE_DIR_NAME


def capture_primary_monitor():
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for monitor capture. Install: pip install pillow")
    return ImageGrab.grab(all_screens=False)


def crop_table_roi(slot: TableSlot, screenshot):
    bbox = slot.bbox
    return screenshot.crop((bbox.x1, bbox.y1, bbox.x2, bbox.y2))


def save_desktop_screenshot(cycle_dir: Path, screenshot, display_pass_id: str) -> Path:
    desktop_path = cycle_dir / "_debug" / display_pass_id / "desktop_capture.png"
    ensure_dir(desktop_path.parent)
    screenshot.save(desktop_path)
    return desktop_path


def validate_bbox_inside_screenshot(slot: TableSlot, screenshot_size: Dict[str, int]) -> None:
    bbox = slot.bbox
    if bbox.x2 > screenshot_size["w"] or bbox.y2 > screenshot_size["h"]:
        raise ValueError(
            f"{slot.table_id} bbox is outside screenshot. "
            f"bbox={bbox.to_json()}, screenshot_size={screenshot_size}"
        )


def save_table_crop(cycle_dir: Path, slot: TableSlot, table_roi, display_pass_id: str) -> Path:
    table_dir = cycle_dir / "_debug" / display_pass_id / "table_crops" / slot.table_id
    ensure_dir(table_dir)
    crop_path = table_dir / f"{slot.table_id}_display_crop.png"
    table_roi.save(crop_path)
    return crop_path


def _write_json_atomic(path: Path, data: Dict[str, object]) -> None:
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _build_table_lifecycle_gate_audit(
    decision: object,
    *,
    stage: str,
) -> Dict[str, object]:
    """Build a compact V2.1 audit block for the early per-table lifecycle gate."""
    if decision is None or not hasattr(decision, "to_json"):
        return {
            "schema_version": "table_lifecycle_gate_v2_1",
            "stage": str(stage),
            "status": "missing",
            "heavy_analysis_allowed": False,
            "heavy_analysis_blocked": True,
            "blocked_reason": "missing_lifecycle_decision",
        }

    payload = decision.to_json()
    if not isinstance(payload, dict):
        payload = {}

    lifecycle_stage = str(payload.get("lifecycle_stage") or "")
    is_analysis_stage = lifecycle_stage == "analysis_cycle" or str(stage) == "before_heavy_analysis"
    should_process = bool(payload.get("should_process", False))

    payload.update({
        "schema_version": "table_lifecycle_gate_v2_1",
        "stage": str(stage),
        "heavy_analysis_allowed": should_process if is_analysis_stage else payload.get("heavy_analysis_allowed"),
        "heavy_analysis_blocked": (not should_process) if is_analysis_stage else payload.get("heavy_analysis_blocked"),
        "blocked_reason": payload.get("reason") if is_analysis_stage and not should_process else payload.get("blocked_reason"),
    })
    return payload


def _safe_json_filename(value: object, *, fallback: str = "state") -> str:
    text = str(value or "").strip() or fallback
    safe_chars: List[str] = []
    for char in text:
        if char.isalnum() or char in {"_", "-", "."}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    return "".join(safe_chars).strip("._") or fallback


def save_dark_table_frame_json(
    *,
    state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    frame_name: str,
) -> Path:
    """Save full technical state as Dark_JSON."""
    filename = _safe_json_filename(frame_name, fallback="frame") + ".dark.json"
    path = cycle_dir / "Dark_JSON" / table_id / filename
    _write_json_atomic(path, state)
    return path


def save_pending_clear_table_frame_json(
    *,
    clear_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save a pre-action Clear_JSON candidate for diagnostics only."""
    frame_id = clear_state.get("frame_id") or "clear_state_candidate"
    filename = _safe_json_filename(frame_id, fallback="clear_state_candidate") + ".pending.json"
    path = cycle_dir / V04_CLEAR_JSON_PENDING_DIR_NAME / table_id / filename
    _write_json_atomic(path, clear_state)
    return path


def save_clear_table_frame_json(
    *,
    clear_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save final minimal poker-state Clear_JSON after action/click completion."""
    frame_id = clear_state.get("frame_id") or "clear_state"
    filename = _safe_json_filename(frame_id, fallback="clear_state") + ".json"
    path = cycle_dir / V04_CLEAR_JSON_FINAL_DIR_NAME / table_id / filename
    _write_json_atomic(path, clear_state)
    return path


def save_decision_table_frame_json(
    *,
    decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save compact Decision_JSON built from Clear_JSON only."""
    frame_id = decision_state.get("source_frame_id") or "decision_state"
    filename = _safe_json_filename(frame_id, fallback="decision_state") + ".decision.json"
    path = cycle_dir / V05_DECISION_JSON_DIR_NAME / table_id / filename
    _write_json_atomic(path, decision_state)
    return path


def save_action_decision_table_frame_json(
    *,
    action_decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save compact Action_Decision_JSON built from Decision_JSON only."""
    frame_id = action_decision_state.get("source_decision_frame_id") or "action_decision_state"
    filename = _safe_json_filename(frame_id, fallback="action_decision_state") + ".action.json"
    path = cycle_dir / V06_ACTION_DECISION_DIR_NAME / table_id / filename
    _write_json_atomic(path, action_decision_state)
    return path


def save_action_runtime_plan_table_frame_json(
    *,
    runtime_plan_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save compact Action_Runtime_Plan_JSON built from Action_Decision_JSON only."""
    frame_id = runtime_plan_state.get("source_action_decision_frame_id") or "action_runtime_plan"
    filename = _safe_json_filename(frame_id, fallback="action_runtime_plan") + ".runtime_plan.json"
    path = cycle_dir / V07_ACTION_RUNTIME_PLAN_DIR_NAME / table_id / filename
    _write_json_atomic(path, runtime_plan_state)
    return path


def save_completed_json_table_frame_json(
    *,
    completed_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
) -> Path:
    """Save final completed-cycle JSON after Clear_JSON + action runtime completion."""
    frame_id = completed_state.get("frame_id") or "completed_state"
    filename = _safe_json_filename(frame_id, fallback="completed_state") + ".complete.json"
    path = cycle_dir / V10_JSON_COMPLETE_DIR_NAME / table_id / filename
    _write_json_atomic(path, completed_state)
    return path


def _compact_gate_decision_for_diagnostics(decision: Optional[object]) -> Dict[str, object]:
    """Return a stable compact view of an event/transaction gate decision."""
    if decision is None:
        return {"status": "not_evaluated"}
    if hasattr(decision, "to_json"):
        try:
            payload = decision.to_json()
            return payload if isinstance(payload, dict) else {"status": "unavailable"}
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}
    if isinstance(decision, dict):
        return dict(decision)
    return {"status": "unavailable", "type": type(decision).__name__}


def _compact_report_for_diagnostics(report: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Return compact status fields from a runtime/service report without changing behavior."""
    if not isinstance(report, dict):
        return {"status": "not_available"}
    compact: Dict[str, object] = {}
    for key in (
        "status",
        "reason",
        "phase",
        "click_completed",
        "click_dry_run",
        "action",
        "button",
        "message",
    ):
        if key in report:
            compact[key] = report.get(key)
    service_click = report.get("service_click")
    if isinstance(service_click, dict):
        compact["service_click"] = {
            "status": service_click.get("status"),
            "reason": service_click.get("reason"),
            "frame_finished": bool(service_click.get("frame_finished")),
            "skip_action_button_runtime": bool(service_click.get("skip_action_button_runtime")),
            "click_completed": bool(service_click.get("click_completed")),
        }
    click_result = report.get("click_result")
    if isinstance(click_result, dict):
        compact["click_result"] = {
            "status": click_result.get("status"),
            "decision_id": click_result.get("decision_id"),
            "click_completed": bool(click_result.get("click_completed")),
            "dry_run": bool(click_result.get("dry_run")),
        }
    return compact or {"status": "available"}


def _update_runtime_lifecycle_diagnostics(state: Dict[str, object], **updates: object) -> Dict[str, object]:
    """Attach V0.2 runtime lifecycle diagnostics to Dark_JSON state only."""
    diagnostics = state.get("runtime_lifecycle_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {
            "schema_version": "runtime_lifecycle_diagnostics_v0_2",
            "behavior": "diagnostics_only_no_runtime_decision_changes",
            "purpose": (
                "Explain why this frame was allowed, suppressed, finalized, or kept as Dark_JSON only."
            ),
        }
        state["runtime_lifecycle_diagnostics"] = diagnostics
    for key, value in updates.items():
        diagnostics[key] = value
    return diagnostics


def _extract_clear_hero_position_and_cards(clear_state: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Tuple[str, ...]]:
    """Return HERO logical position and normalized cards from a minimal Clear_JSON state."""
    if not isinstance(clear_state, dict):
        return None, tuple()
    players = clear_state.get("players")
    if not isinstance(players, dict):
        return None, tuple()
    for position, payload in players.items():
        if isinstance(payload, dict) and payload.get("hero") is True:
            cards = normalize_card_list(payload.get("cards"))
            return str(position), tuple(cards)
    return None, tuple()


def _clear_board_cards(clear_state: Optional[Dict[str, Any]]) -> Tuple[str, ...]:
    if not isinstance(clear_state, dict):
        return tuple()
    board = clear_state.get("board")
    if not isinstance(board, dict):
        return tuple()
    return tuple(normalize_card_list(board.get("cards")))


def _clear_street(clear_state: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(clear_state, dict):
        return None
    board = clear_state.get("board")
    if not isinstance(board, dict):
        return None
    street = board.get("street")
    return str(street).strip().lower() if street is not None else None


def _clear_total_pot(clear_state: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(clear_state, dict):
        return None
    value = clear_state.get("Total_pot")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_click_decision_id(click_result: Optional[Dict[str, object]]) -> Optional[str]:
    if not isinstance(click_result, dict):
        return None
    decision_id = click_result.get("decision_id")
    text = str(decision_id).strip() if decision_id is not None else ""
    return text or None


def _extract_previous_click_decision_id(clear_state: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(clear_state, dict):
        return None
    click_result = clear_state.get("click_result")
    return _extract_click_decision_id(click_result if isinstance(click_result, dict) else None)


def _detect_final_clear_json_publication_block(
    *,
    previous_clear_state: Optional[Dict[str, Any]],
    current_clear_state: Dict[str, Any],
    click_result: Optional[Dict[str, object]],
) -> Optional[Dict[str, object]]:
    """
    V0.8 live safety guard before Final Clear_JSON publication.

    Blocks two live noise modes:
    - same click/dry-run decision_id reused for a later Final Clear_JSON;
    - same hand/street/board/pot/HERO cards while HERO logical position jumps.

    Dark_JSON, Pending Clear_JSON, Decision_JSON and RuntimePlan stay saved for diagnostics.
    """
    if not isinstance(previous_clear_state, dict):
        return None

    previous_decision_id = _extract_previous_click_decision_id(previous_clear_state)
    current_decision_id = _extract_click_decision_id(click_result)
    if previous_decision_id and current_decision_id and previous_decision_id == current_decision_id:
        return {
            "reason": "duplicate_click_result_reused",
            "message": "Final Clear_JSON publication blocked because click_result.decision_id was already used by previous final Clear_JSON for this table/hand.",
            "previous_decision_id": previous_decision_id,
            "current_decision_id": current_decision_id,
        }

    previous_hero_position, previous_hero_cards = _extract_clear_hero_position_and_cards(previous_clear_state)
    current_hero_position, current_hero_cards = _extract_clear_hero_position_and_cards(current_clear_state)
    if not previous_hero_position or not current_hero_position:
        return None
    if not previous_hero_cards or previous_hero_cards != current_hero_cards:
        return None

    same_street = _clear_street(previous_clear_state) == _clear_street(current_clear_state)
    same_board = _clear_board_cards(previous_clear_state) == _clear_board_cards(current_clear_state)
    prev_pot = _clear_total_pot(previous_clear_state)
    curr_pot = _clear_total_pot(current_clear_state)
    same_pot = prev_pot is not None and curr_pot is not None and abs(prev_pot - curr_pot) < 0.0001

    if same_street and same_board and same_pot and previous_hero_position != current_hero_position:
        return {
            "reason": "hero_position_drift_same_state",
            "message": "Final Clear_JSON publication blocked because HERO position changed while same HERO cards, board, street and Total_pot stayed unchanged.",
            "previous_hero_position": previous_hero_position,
            "current_hero_position": current_hero_position,
            "hero_cards": list(current_hero_cards),
            "street": _clear_street(current_clear_state),
            "Total_pot": curr_pot,
        }

    return None


def _click_guard_config() -> ClickGuardConfig:
    """Build V0.9 click guard config from project config flags."""
    return ClickGuardConfig(
        enabled=bool(V09_CLICK_EXECUTION_GUARD_ENABLED),
        real_click_master_armed=bool(V09_REAL_CLICK_MASTER_ARMED),
        require_slot_boundary_guard=bool(V09_REQUIRE_SLOT_BOUNDARY_GUARD),
        require_no_repeat_decision_guard=bool(V09_REQUIRE_NO_REPEAT_DECISION_GUARD),
        require_button_availability_guard=bool(V09_REQUIRE_BUTTON_AVAILABILITY_GUARD),
        allow_dry_run_completion=bool(V09_ALLOW_DRY_RUN_COMPLETION),
        block_real_click_when_live_capture_no_click=bool(V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK),
        live_data_capture_no_click_mode=bool(V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE),
        action_real_click_enabled=bool(V11_REAL_MOUSE_CLICK_ENABLED),
        action_dry_run=bool(V11_CLICK_DRY_RUN),
        required_plan_source=str(V09_REQUIRE_ACTION_RUNTIME_PLAN_SOURCE or "Action_Runtime_Plan_JSON"),
    )


def _slot_bbox_tuple_from_state(state: Dict[str, object]) -> Optional[Tuple[float, float, float, float]]:
    table = state.get("table") if isinstance(state.get("table"), dict) else {}
    bbox = table.get("slot_bbox") if isinstance(table, dict) else None
    if not isinstance(bbox, dict):
        return None
    try:
        return (float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"]))
    except (KeyError, TypeError, ValueError):
        return None


def _load_runtime_plan_from_contract(runtime_plan_contract: Dict[str, object]) -> Dict[str, object]:
    embedded_plan = runtime_plan_contract.get("runtime_plan_state")
    if isinstance(embedded_plan, dict):
        return dict(embedded_plan)

    path_text = str(runtime_plan_contract.get("path") or "").strip()
    if path_text:
        try:
            with Path(path_text).open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    # Fallback is intentionally permissive for diagnostics only. A strict guard
    # will reject this if schema/source do not satisfy ClickGuardConfig.
    return dict(runtime_plan_contract)


def _first_action_click_point(runtime_action: Dict[str, object]) -> Optional[Dict[str, object]]:
    action_button = runtime_action.get("action_button") if isinstance(runtime_action.get("action_button"), dict) else {}
    click_points = action_button.get("click_points") if isinstance(action_button, dict) else None
    if not isinstance(click_points, list):
        return None
    for point in click_points:
        if isinstance(point, dict):
            return point
    return None


def _click_point_xy(point_payload: Dict[str, object]) -> Optional[Tuple[float, float]]:
    raw = point_payload.get("global_click_point") if isinstance(point_payload, dict) else None
    if not isinstance(raw, dict):
        return None
    try:
        return float(raw["x"]), float(raw["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _first_target_button_from_runtime_plan(plan: Dict[str, object]) -> str:
    target_sequence = plan.get("target_sequence")
    if isinstance(target_sequence, list) and target_sequence:
        return str(target_sequence[0])
    target_classes = plan.get("target_button_classes")
    if isinstance(target_classes, list) and target_classes:
        return str(target_classes[0])
    return ""


def _build_controlled_real_click_scope_report(
    *,
    state: Dict[str, object],
    table_id: str,
    click_result: Dict[str, object],
    runtime_plan_contract: Dict[str, object],
) -> Dict[str, object]:
    """Evaluate V1.1.3 ControlledRealClickScope before ClickExecutionGuard."""

    runtime_action = state.get("runtime_action") if isinstance(state.get("runtime_action"), dict) else {}
    action_button_block = runtime_action.get("action_button") if isinstance(runtime_action.get("action_button"), dict) else {}
    runtime_plan = _load_runtime_plan_from_contract(runtime_plan_contract)

    click_point_payload = _first_action_click_point(runtime_action)
    target_button = str((click_point_payload or {}).get("class_name") or "").strip()
    if not target_button:
        target_button = _first_target_button_from_runtime_plan(runtime_plan)

    target_sequence = runtime_plan.get("target_sequence")
    if not isinstance(target_sequence, list):
        target_sequence = click_result.get("target_sequence") if isinstance(click_result.get("target_sequence"), list) else []

    runtime_branch = str(
        runtime_plan.get("runtime_branch")
        or action_button_block.get("branch")
        or "action_button"
    )
    action = str(
        click_result.get("action")
        or runtime_plan.get("planned_action")
        or action_button_block.get("solver_action")
        or ""
    )
    decision_id = str(click_result.get("decision_id") or action_button_block.get("decision_id") or "")
    already_executed = _DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE.get(str(table_id), set())

    request = ControlledRealClickScopeRequest(
        table_id=str(table_id),
        runtime_branch=runtime_branch,
        action=action,
        decision_id=decision_id,
        target_button_class=target_button,
        target_sequence=target_sequence,
        dry_run=bool(click_result.get("dry_run", V11_CLICK_DRY_RUN)),
        real_click_enabled=bool(click_result.get("real_click_enabled", V11_REAL_MOUSE_CLICK_ENABLED)),
        source=str(runtime_plan.get("source") or runtime_plan_contract.get("source") or "Action_Runtime_Plan_JSON"),
        already_executed_decision_ids=already_executed,
    )
    return _DEFAULT_CONTROLLED_REAL_CLICK_SCOPE.evaluate(request)

def _build_click_execution_guard_report(
    *,
    state: Dict[str, object],
    table_id: str,
    hand_id: str,
    clear_state: Dict[str, Any],
    click_result: Dict[str, object],
    runtime_plan_contract: Dict[str, object],
) -> Dict[str, object]:
    """Validate V0.9 click guards and return Dark_JSON audit payload."""
    runtime_action = state.get("runtime_action") if isinstance(state.get("runtime_action"), dict) else {}
    runtime_plan = _load_runtime_plan_from_contract(runtime_plan_contract)
    slot_bbox = _slot_bbox_tuple_from_state(state)
    click_point_payload = _first_action_click_point(runtime_action)
    click_xy = _click_point_xy(click_point_payload or {}) if click_point_payload else None

    if slot_bbox is None:
        return {
            "schema_version": "click_result_v09",
            "status": "blocked",
            "reason": "missing_slot_bbox",
            "message": "ClickExecutionGuard cannot run because table.slot_bbox is missing or invalid.",
            "guard_passed": False,
            "guards": {},
        }
    target_button = str((click_point_payload or {}).get("class_name") or "").strip() or _first_target_button_from_runtime_plan(runtime_plan)
    synthetic_click_point_used = False
    if click_xy is None:
        # In replay / live no-click data-capture mode the Action_Button runtime may not
        # produce a physical click point even though the action plan is valid. Do not
        # block Final Clear_JSON for this diagnostic dry-run case. Use the slot center
        # only as a non-click guard placeholder so slot/no-repeat/button/master guards
        # can still be audited. Real-click mode remains blocked by ClickExecutionGuard
        # if a true button point is unavailable or master/no-click guards are not armed.
        dry_run_requested = bool(click_result.get("dry_run", V11_CLICK_DRY_RUN))
        real_click_requested = bool(click_result.get("real_click_enabled", V11_REAL_MOUSE_CLICK_ENABLED))
        if dry_run_requested and not real_click_requested:
            x1, y1, x2, y2 = slot_bbox
            click_xy = ((float(x1) + float(x2)) / 2.0, (float(y1) + float(y2)) / 2.0)
            synthetic_click_point_used = True
        else:
            return {
                "schema_version": "click_result_v09",
                "status": "blocked",
                "reason": "missing_click_point",
                "message": "ClickExecutionGuard cannot run because runtime_action.action_button.click_points has no valid global_click_point.",
                "guard_passed": False,
                "guards": {},
            }

    street = _clear_street(clear_state) or "unknown"
    decision_id = str(click_result.get("decision_id") or "")
    already_executed = _DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE.get(str(table_id), set())

    request = ClickExecutionRequest(
        table_id=str(table_id),
        hand_id=str(hand_id),
        street=str(street),
        decision_id=decision_id,
        action=str(click_result.get("action") or runtime_plan.get("planned_action") or "fold"),
        target_button_class=target_button,
        click_point=click_xy,
        slot_bbox=slot_bbox,
        action_runtime_plan=runtime_plan,
        already_executed_decision_ids=already_executed,
        dry_run=bool(click_result.get("dry_run", V11_CLICK_DRY_RUN)),
        real_click_enabled=bool(click_result.get("real_click_enabled", V11_REAL_MOUSE_CLICK_ENABLED)),
    )
    controlled_scope_report = _build_controlled_real_click_scope_report(
        state=state,
        table_id=table_id,
        click_result=click_result,
        runtime_plan_contract=runtime_plan_contract,
    )
    state["controlled_real_click_scope"] = controlled_scope_report
    runtime_action_block = state.get("runtime_action")
    if isinstance(runtime_action_block, dict):
        runtime_action_block["controlled_real_click_scope"] = controlled_scope_report

    if isinstance(controlled_scope_report, dict) and not bool(controlled_scope_report.get("scope_passed")):
        return {
            "schema_version": "click_result_v09",
            "status": "blocked",
            "reason": "controlled_real_click_scope_failed",
            "message": str(controlled_scope_report.get("message") or "Final Clear_JSON publication blocked by ControlledRealClickScope."),
            "guard_passed": False,
            "source": "ControlledRealClickScope",
            "runtime_plan_path": runtime_plan_contract.get("path"),
            "controlled_real_click_scope": controlled_scope_report,
            "guards": {"controlled_real_click_scope": False},
        }

    guard_result = validate_click_execution_request(request, _click_guard_config())
    guard_result["source"] = "ClickExecutionGuard"
    guard_result["runtime_plan_path"] = runtime_plan_contract.get("path")
    if synthetic_click_point_used:
        guard_result["diagnostic_click_point_source"] = "slot_center_no_click_placeholder"
        guard_result["message"] = (
            str(guard_result.get("message") or "")
            + " Synthetic slot-center point was used only for no-click/dry-run audit because no physical click point was available."
        ).strip()
    return guard_result


def _remember_executed_click_decision(table_id: str, click_result: Optional[Dict[str, object]]) -> None:
    decision_id = _extract_click_decision_id(click_result)
    if not decision_id:
        return
    table_key = str(table_id)
    if table_key not in _DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE:
        _DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE[table_key] = set()
    _DEFAULT_EXECUTED_CLICK_DECISION_IDS_BY_TABLE[table_key].add(decision_id)
    if isinstance(click_result, dict):
        dry_run = bool(click_result.get("dry_run", V11_CLICK_DRY_RUN))
        real_click_enabled = bool(click_result.get("real_click_enabled", V11_REAL_MOUSE_CLICK_ENABLED))
        status = str(click_result.get("status") or "").strip().lower()
        if real_click_enabled and not dry_run and status in {"clicked", "confirmed"}:
            _DEFAULT_CONTROLLED_REAL_CLICK_SCOPE.record_success(decision_id)


def _is_v31_confirmed_real_click_for_final_publication(
    *,
    state: Dict[str, object],
    click_result: Optional[Dict[str, object]],
) -> bool:
    """Return True when runtime already executed a V3.1-controlled real click.

    V3.3: Final Clear_JSON publication previously re-ran ClickExecutionGuard
    after runtime had already clicked. In real-click mode that can create a false
    post-click block, while Dark_JSON already proves the Action_Button click was
    protected by ROI guard + V3.1 gate + success record. This helper recognizes
    that exact confirmed path and allows final publication to proceed.
    """

    if not isinstance(click_result, dict):
        return False
    if str(click_result.get("status") or "").strip().lower() not in {"clicked", "confirmed"}:
        return False
    if bool(click_result.get("dry_run", True)):
        return False
    if not bool(click_result.get("real_click_enabled", False)):
        return False

    runtime_action = state.get("runtime_action") if isinstance(state.get("runtime_action"), dict) else {}
    action_button = runtime_action.get("action_button") if isinstance(runtime_action.get("action_button"), dict) else {}
    if not isinstance(action_button, dict):
        return False

    gate = action_button.get("controlled_live_click_gate")
    success = action_button.get("controlled_live_click_success")
    roi_guard = action_button.get("action_button_slot_roi_guard")

    if not isinstance(gate, dict) or not isinstance(success, dict):
        return False
    if str(gate.get("status") or "") != "CONTROLLED_LIVE_CLICK_GATE_PASSED":
        return False
    if not bool(gate.get("scope_passed")):
        return False
    if str(success.get("status") or "") != "CONTROLLED_LIVE_CLICK_SUCCESS_RECORDED":
        return False

    click_decision_id = str(click_result.get("decision_id") or "").strip()
    success_decision_id = str(success.get("decision_id") or "").strip()
    if click_decision_id and success_decision_id and click_decision_id != success_decision_id:
        return False

    if isinstance(roi_guard, dict):
        if not bool(roi_guard.get("ok")):
            return False
        if not bool(roi_guard.get("full_screen_search_blocked")):
            return False

    click_points = action_button.get("click_points")
    if isinstance(click_points, list) and click_points:
        if not all(isinstance(point, dict) and bool(point.get("inside_slot_bbox")) for point in click_points):
            return False

    return True



def _failed_active_finalization_release_reason(
    *,
    state: Dict[str, object],
    transaction_runtime_report: Optional[Dict[str, object]],
    clear_json_path: Optional[Path],
) -> Optional[Dict[str, object]]:
    """Return release metadata when an Active lifecycle cannot reach completion.

    V4.1: a strong Active frame may pass detector stages but fail Clear_JSON
    validation, Decision_JSON construction, Action_Decision, or RuntimePlan. In
    that case there is no valid click/dry-run completion path. Leaving the table
    transaction in waiting_click/click_pending blocks later streets. The caller
    uses this diagnostic decision to abort/release the open transaction while
    preserving Dark_JSON.
    """

    if clear_json_path is not None:
        return None
    if not isinstance(transaction_runtime_report, dict):
        return None
    if bool(transaction_runtime_report.get("click_completed")):
        return None

    contract = state.get("clear_json_contract") if isinstance(state.get("clear_json_contract"), dict) else {}
    runtime_action = state.get("runtime_action") if isinstance(state.get("runtime_action"), dict) else {}
    action_button = runtime_action.get("action_button") if isinstance(runtime_action.get("action_button"), dict) else {}
    action_plan = runtime_action.get("action_runtime_plan_contract") if isinstance(runtime_action.get("action_runtime_plan_contract"), dict) else {}

    contract_status = str(contract.get("status") or "").strip()
    contract_reason = str(contract.get("reason") or "").strip()
    transaction_status = str(transaction_runtime_report.get("status") or "").strip()
    transaction_reason = str(transaction_runtime_report.get("reason") or "").strip()
    transaction_phase = str(transaction_runtime_report.get("phase") or "").strip()
    click_result = transaction_runtime_report.get("click_result") if isinstance(transaction_runtime_report.get("click_result"), dict) else {}
    click_status = str(click_result.get("status") or "").strip()
    payload_status = str(action_button.get("payload_status") or "").strip()
    action_button_status = str(action_button.get("status") or "").strip()
    runtime_plan_status = str(action_plan.get("status") or "").strip()
    if not runtime_plan_status:
        action_decision_contract = contract.get("action_decision_contract") if isinstance(contract.get("action_decision_contract"), dict) else {}
        nested_plan = action_decision_contract.get("action_runtime_plan_contract") if isinstance(action_decision_contract.get("action_runtime_plan_contract"), dict) else {}
        runtime_plan_status = str(nested_plan.get("status") or "").strip()

    validation_failed = contract_status in {"validation_failed", "error"} or contract_reason in {
        "pending_clear_json_contract_validation_failed",
        "final_clear_json_contract_validation_failed",
        "clear_json_build_or_save_error",
    }
    no_runtime_plan = runtime_plan_status in {"not_built", "validation_failed", "error"}
    payload_failed = payload_status in {"error", "validation_failed"}
    runtime_skipped = click_status == "skipped" or action_button_status == "skipped"
    transaction_pending = transaction_status in {"pending", "skipped", ""} or transaction_reason == "click_cycle_not_completed"

    if not (validation_failed or no_runtime_plan or payload_failed):
        return None
    if not (transaction_pending or runtime_skipped or transaction_phase in {"waiting_click", "click_pending"}):
        return None

    if validation_failed:
        reason = contract_reason or "active_clear_json_validation_failed"
    elif no_runtime_plan:
        reason = "active_runtime_plan_not_built"
    else:
        reason = "active_action_payload_failed"

    return {
        "schema_version": "failed_active_finalization_release_v4_1",
        "status": "FAILED_ACTIVE_FINALIZATION_RELEASE_REQUIRED",
        "reason": reason,
        "contract_status": contract_status,
        "contract_reason": contract_reason,
        "transaction_status": transaction_status,
        "transaction_reason": transaction_reason,
        "transaction_phase": transaction_phase,
        "click_status": click_status,
        "payload_status": payload_status,
        "action_button_status": action_button_status,
        "runtime_plan_status": runtime_plan_status,
        "message": (
            "Strong Active frame could not build a valid Clear_JSON/Decision/RuntimePlan "
            "completion path. The table transaction must be released so later streets "
            "or new Active signatures are not blocked by an impossible click cycle."
        ),
    }


def _release_failed_active_finalization_if_needed(
    *,
    state: Dict[str, object],
    table_action_transaction_gate: Optional[TableActionTransactionGate],
    table_id: str,
    action_transaction_decision: object,
    transaction_runtime_report: Optional[Dict[str, object]],
    clear_json_path: Optional[Path],
) -> Optional[Dict[str, object]]:
    """Abort/release an open table transaction after failed Active finalization."""

    if table_action_transaction_gate is None:
        return None
    if action_transaction_decision is None or not bool(getattr(action_transaction_decision, "should_process", False)):
        return None

    release_decision = _failed_active_finalization_release_reason(
        state=state,
        transaction_runtime_report=transaction_runtime_report,
        clear_json_path=clear_json_path,
    )
    if not isinstance(release_decision, dict):
        return None

    release_reason = str(release_decision.get("reason") or "failed_active_finalization_released")
    release_message = str(release_decision.get("message") or release_reason)
    if hasattr(table_action_transaction_gate, "release_failed_active_finalization"):
        release_report = table_action_transaction_gate.release_failed_active_finalization(
            table_id=table_id,
            reason=release_reason,
            message=release_message,
        )
    else:
        release_report = table_action_transaction_gate.abort_analysis_cycle(
            table_id=table_id,
            reason=release_reason,
            message=release_message,
        )

    release_payload = {
        "schema_version": "failed_active_finalization_release_v4_1",
        "status": "FAILED_ACTIVE_FINALIZATION_RELEASED",
        "reason": release_reason,
        "decision": release_decision,
        "release_report": release_report,
        "message": release_message,
    }
    state["failed_active_finalization_release"] = release_payload

    runtime_report = state.get("action_transaction_runtime")
    if isinstance(runtime_report, dict):
        runtime_report["pre_release_status"] = runtime_report.get("status")
        runtime_report["pre_release_reason"] = runtime_report.get("reason")
        runtime_report["pre_release_phase"] = runtime_report.get("phase")
        runtime_report["status"] = "aborted"
        runtime_report["reason"] = "failed_active_finalization_released"
        runtime_report["phase"] = "aborted"
        runtime_report["click_completed"] = False
        runtime_report["v4_1_failed_active_finalization_release"] = release_payload

    contract = state.get("clear_json_contract")
    if isinstance(contract, dict):
        contract["v4_1_failed_active_finalization_release"] = release_payload

    return release_payload


def _v21_normalize_solver_preflop_action(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"fold", "call", "check", "bet", "raise", "check_fold"}:
        return text
    if text in {"4bet", "5bet", "3bet", "open_raise", "iso_raise", "jam", "all_in"}:
        return "raise"
    return "fold"


def _v21_solver_size_policy(solver_action_decision: Dict[str, object], action: str) -> Optional[Dict[str, object]]:
    if action not in {"bet", "raise"}:
        return None

    raw_policy = solver_action_decision.get("size_policy")
    if isinstance(raw_policy, dict):
        return dict(raw_policy)

    raw_pct = (
        solver_action_decision.get("size_pct")
        or solver_action_decision.get("raise_size_pct")
        or solver_action_decision.get("button_pct")
    )
    if raw_pct is None:
        return None

    try:
        pct_float = float(raw_pct)
        pct_text = str(int(pct_float)) if pct_float.is_integer() else str(pct_float)
    except Exception:
        pct_text = str(raw_pct).replace("%", "").strip()

    if pct_text in {"33", "50", "70", "98"}:
        return {"type": "pct", "value": pct_text}
    return {"type": "raw", "value": pct_text}


def _v21_target_buttons_for_solver_action(
    *,
    action: str,
    size_policy: Optional[Dict[str, object]],
    solver_action_decision: Dict[str, object],
) -> list[str]:
    raw_buttons = (
        solver_action_decision.get("target_button_classes")
        or solver_action_decision.get("target_sequence")
        or solver_action_decision.get("click_sequence")
    )
    if isinstance(raw_buttons, list) and raw_buttons:
        normalized: list[str] = []
        for item in raw_buttons:
            text = str(item or "").strip()
            if text.upper() == "CALL":
                normalized.append("Call")
            elif text.upper() == "FOLD":
                normalized.append("FOLD")
            elif text == "Raise":
                normalized.append("Bet/Raise")
            else:
                normalized.append(text)
        return [b for b in normalized if b]

    if action == "fold":
        return ["FOLD"]
    if action == "call":
        return ["Call"]
    if action == "check":
        return ["Check"]
    if action == "check_fold":
        return ["Check", "Check/fold", "FOLD"]
    if action in {"bet", "raise"}:
        buttons: list[str] = []
        if isinstance(size_policy, dict):
            value = str(size_policy.get("value") or "").strip()
            if value in {"33", "50", "70", "98"}:
                buttons.append(f"{value}%")
        buttons.append("Bet/Raise")
        return buttons
    return ["FOLD"]


def _adapt_v21_solver_preflop_action_decision_to_v06(
    solver_action_decision: Dict[str, object],
) -> Dict[str, object]:
    """Convert Solver_Preflop bridge action_decision to legacy V06 Action_Decision_JSON.

    Action_Runtime_Plan builder currently validates source='Decision_JSON'.
    The adapter keeps that legacy shape while carrying Solver_Preflop lineage
    inside reason/decision_context. It does not bypass runtime guards.
    """
    from config import V06_ACTION_DECISION_SCHEMA_VERSION

    action = _v21_normalize_solver_preflop_action(
        solver_action_decision.get("action")
        or solver_action_decision.get("engine_action")
        or solver_action_decision.get("raw_action")
    )
    size_policy = _v21_solver_size_policy(solver_action_decision, action)
    target_buttons = _v21_target_buttons_for_solver_action(
        action=action,
        size_policy=size_policy,
        solver_action_decision=solver_action_decision,
    )

    source_frame_id = str(
        solver_action_decision.get("source_decision_frame_id")
        or solver_action_decision.get("source_frame_id")
        or ""
    )

    return {
        "schema_version": V06_ACTION_DECISION_SCHEMA_VERSION,
        "source": "Decision_JSON",
        "source_decision_frame_id": source_frame_id,
        "status": "ok",
        "action": action,
        "size_policy": size_policy,
        "target_button_classes": list(target_buttons),
        "reason": str(solver_action_decision.get("reason") or "solver_preflop_bridge_v21_runtime_source"),
        "dry_run_safe": True,
        # Legacy V06 validator still requires the stub flag to remain True.
        # The real source is carried below in decision_context.solver_preflop_runtime_source.
        "solver_stub": True,
        "decision_context": {
            "street": str(solver_action_decision.get("street") or "preflop"),
            "hero_position": str(solver_action_decision.get("hero_position") or ""),
            "source_frame_id": source_frame_id,
            "solver_preflop_runtime_source": True,
            "solver_stub_legacy_compat": True,
            "solver_decision_id": solver_action_decision.get("decision_id"),
            "solver_fingerprint": solver_action_decision.get("solver_fingerprint"),
            "solver_raw_action": solver_action_decision.get("raw_action"),
            "solver_engine_action": solver_action_decision.get("engine_action") or solver_action_decision.get("action"),
        },
    }

def _select_v20_runtime_action_decision_state(
    *,
    default_action_decision_state: Dict[str, object],
    solver_preflop_bridge_contract: Optional[Dict[str, object]] = None,
) -> tuple[Dict[str, object], Dict[str, object]]:
    """Select which Action_Decision-like payload feeds Action_Runtime_Plan_JSON.

    V2.0 is deliberately disabled by default. When disabled, this function
    always returns the legacy Action_Decision_JSON payload. When enabled later,
    Solver_Preflop may become the source only if its bridge contract provides a
    bridge_payload.action_decision object. This scaffold does not bypass runtime
    guards and does not enable real-click by itself.
    """
    selection = {
        "schema": "v20_runtime_action_decision_source_selection_v1",
        "enabled": bool(V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE),
        "selected_source": "Action_Decision_JSON",
        "reason": "v20_switch_disabled",
        "dry_run_only": bool(V20_SOLVER_PREFLOP_DRY_RUN_ONLY),
        "solver_bridge_status": None,
        "solver_action_decision_available": False,
    }

    if not V20_USE_SOLVER_PREFLOP_AS_RUNTIME_SOURCE:
        return dict(default_action_decision_state), selection

    if not isinstance(solver_preflop_bridge_contract, dict):
        selection["reason"] = "solver_bridge_contract_missing"
        return dict(default_action_decision_state), selection

    selection["solver_bridge_status"] = solver_preflop_bridge_contract.get("status")
    bridge_payload = solver_preflop_bridge_contract.get("bridge_payload")
    if not isinstance(bridge_payload, dict):
        selection["reason"] = "solver_bridge_payload_missing"
        return dict(default_action_decision_state), selection

    solver_action_decision = bridge_payload.get("action_decision")
    if not isinstance(solver_action_decision, dict):
        selection["reason"] = "solver_action_decision_missing"
        return dict(default_action_decision_state), selection

    selection["solver_action_decision_available"] = True
    selection["selected_source"] = "Solver_Preflop_Bridge"
    selection["reason"] = "v20_solver_preflop_selected"
    selection["source_frame_id"] = solver_action_decision.get("source_frame_id")
    selection["decision_id"] = solver_action_decision.get("decision_id")
    selection["solver_fingerprint"] = solver_action_decision.get("solver_fingerprint")
    selection["adapted_to_legacy_action_decision"] = True
    return _adapt_v21_solver_preflop_action_decision_to_v06(solver_action_decision), selection


def build_and_save_action_runtime_plan_contract(
    *,
    action_decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    publish_files: bool = True,
    solver_preflop_bridge_contract: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Build Action_Runtime_Plan_JSON contract and optionally publish the file."""
    if not V07_ACTION_RUNTIME_PLAN_ENABLED:
        return {
            "enabled": False,
            "source": "Action_Decision_JSON",
            "path": None,
            "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
            "status": "disabled",
        }

    try:
        runtime_plan_state = build_action_runtime_plan_from_action_decision(action_decision_state)
        validation = validate_action_runtime_plan_contract(runtime_plan_state)
        if validation.get("ok"):
            if publish_files:
                path = save_action_runtime_plan_table_frame_json(
                    runtime_plan_state=runtime_plan_state,
                    cycle_dir=cycle_dir,
                    table_id=table_id,
                )
                path_text: Optional[str] = str(path)
                publication_status = "saved"
            else:
                path_text = None
                publication_status = "preview_not_saved_pending_only"
            return {
                "enabled": True,
                "source": "Action_Decision_JSON",
                "path": path_text,
                "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
                "validation": validation,
                "status": publication_status,
                "publication_stage": "final" if publish_files else "pending_preview",
                "file_publication_enabled": bool(publish_files),
                "runtime_plan_state": dict(runtime_plan_state),
                "planned_action": runtime_plan_state.get("planned_action"),
                "target_sequence": runtime_plan_state.get("target_sequence"),
                "target_sequences": runtime_plan_state.get("target_sequences"),
                "runtime_branch": runtime_plan_state.get("runtime_branch"),
                "dry_run": runtime_plan_state.get("dry_run"),
                "real_click_enabled": runtime_plan_state.get("real_click_enabled"),
            }
        return {
            "enabled": True,
            "source": "Action_Decision_JSON",
            "path": None,
            "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
            "validation": validation,
            "status": "validation_failed",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "source": "Action_Decision_JSON",
            "path": None,
            "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
            "validation": {"ok": False, "errors": [str(exc)], "warnings": []},
            "status": "error",
        }


def build_and_save_action_decision_contract(
    *,
    decision_state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    publish_files: bool = True,
    solver_preflop_bridge_contract: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Build Action_Decision_JSON contract and optionally publish the file."""
    if not V06_ACTION_DECISION_ENABLED:
        return {
            "enabled": False,
            "source": "Decision_JSON",
            "path": None,
            "dir": V06_ACTION_DECISION_DIR_NAME,
            "status": "disabled",
        }

    try:
        action_decision_state = build_action_decision_from_decision_json(decision_state)
        validation = validate_action_decision_contract(action_decision_state)
        if validation.get("ok"):
            if publish_files:
                path = save_action_decision_table_frame_json(
                    action_decision_state=action_decision_state,
                    cycle_dir=cycle_dir,
                    table_id=table_id,
                )
                path_text: Optional[str] = str(path)
                publication_status = "saved"
            else:
                path_text = None
                publication_status = "preview_not_saved_pending_only"
            runtime_action_decision_state, v20_runtime_source_selection = _select_v20_runtime_action_decision_state(
                default_action_decision_state=action_decision_state,
                solver_preflop_bridge_contract=solver_preflop_bridge_contract,
            )
            runtime_plan_contract = build_and_save_action_runtime_plan_contract(
                action_decision_state=runtime_action_decision_state,
                cycle_dir=cycle_dir,
                table_id=table_id,
                publish_files=publish_files,
            )
            if isinstance(runtime_plan_contract, dict):
                runtime_plan_contract["v20_runtime_source_selection"] = dict(v20_runtime_source_selection)
            return {
                "enabled": True,
                "source": "Decision_JSON",
                "path": path_text,
                "dir": V06_ACTION_DECISION_DIR_NAME,
                "validation": validation,
                "status": publication_status,
                "publication_stage": "final" if publish_files else "pending_preview",
                "file_publication_enabled": bool(publish_files),
                "action_decision_state": dict(action_decision_state),
                "action": action_decision_state.get("action"),
                "size_policy": action_decision_state.get("size_policy"),
                "target_button_classes": action_decision_state.get("target_button_classes"),
                "v20_runtime_source_selection": dict(v20_runtime_source_selection),
                "action_runtime_plan_contract": runtime_plan_contract,
            }
        return {
            "enabled": True,
            "source": "Decision_JSON",
            "path": None,
            "dir": V06_ACTION_DECISION_DIR_NAME,
            "validation": validation,
            "status": "validation_failed",
        }
    except Exception as exc:
        return {
            "enabled": True,
            "source": "Decision_JSON",
            "path": None,
            "dir": V06_ACTION_DECISION_DIR_NAME,
            "validation": {"ok": False, "errors": [str(exc)], "warnings": []},
            "status": "error",
        }


def save_dark_and_clear_table_frame_json(
    *,
    state: Dict[str, object],
    cycle_dir: Path,
    table_id: str,
    hand_id: str,
    frame_name: str,
    active_confirmed: bool,
    clear_json_state_machine: Optional[ClearJsonStateMachine] = None,
    clear_json_save_allowed: bool = True,
    clear_json_build_allowed: bool = True,
    clear_json_build_block_reason: Optional[str] = None,
    click_result: Optional[Dict[str, object]] = None,
) -> Tuple[Path, Optional[Path]]:
    """
    Save Dark_JSON for every persisted frame.

    V0.4/V0.7 publication discipline:
    - Active poker-state first creates Clear_JSON_Pending for diagnostics.
    - Decision_JSON is built only from validated Clear_JSON candidate.
    - Final Clear_JSON is saved only after the action transaction confirms a
      completed click/dry-run cycle and a compact click_result can be attached.
    - If action/click is not completed, no final Clear_JSON is published.
    - V4.0 duplicate Active frames can hard-stop before Pending/Decision so
      only Dark_JSON audit is preserved for those repeated frames.
    """
    clear_path: Optional[Path] = None
    pending_path: Optional[Path] = None

    if not active_confirmed:
        state["clear_json_contract"] = {
            "status": "skipped",
            "reason": "not_active_poker_state",
            "publication_stage": "dark_json_only",
            "message": "Clear_JSON is not saved for service/inactive frames.",
        }
    elif not clear_json_build_allowed:
        block_reason = str(clear_json_build_block_reason or "clear_json_build_suppressed_before_pending_decision")
        state["clear_json_contract"] = {
            "status": "skipped",
            "reason": block_reason,
            "publication_stage": "dark_json_only",
            "pending_path": None,
            "path": None,
            "hard_stop_before_pending_decision": True,
            "message": (
                "Clear_JSON_Pending, Decision_JSON, Action_Decision_JSON and "
                "Action_Runtime_Plan_JSON were not built for this frame. "
                "Only Dark_JSON audit was preserved."
            ),
            "publication": {
                "pending_dir": V04_CLEAR_JSON_PENDING_DIR_NAME,
                "final_dir": V04_CLEAR_JSON_FINAL_DIR_NAME,
                "pending_path": None,
                "final_path": None,
                "final_requires_click_result": bool(V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT),
            },
            "decision_json_contract": {
                "enabled": bool(V05_DECISION_JSON_ENABLED),
                "source": "Clear_JSON",
                "path": None,
                "dir": V05_DECISION_JSON_DIR_NAME,
                "status": "not_built_duplicate_active_hard_stop",
            },
            "action_decision_contract": {
                "enabled": bool(V06_ACTION_DECISION_ENABLED),
                "source": "Decision_JSON",
                "path": None,
                "dir": V06_ACTION_DECISION_DIR_NAME,
                "status": "not_built_duplicate_active_hard_stop",
                "action_runtime_plan_contract": {
                    "enabled": bool(V07_ACTION_RUNTIME_PLAN_ENABLED),
                    "source": "Action_Decision_JSON",
                    "path": None,
                    "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
                    "status": "not_built_duplicate_active_hard_stop",
                },
            },
        }
    else:
        try:
            clear_state_candidate = build_clear_json_from_dark_state(state)

            recovery_report: Dict[str, object] = {
                "status": "not_applied",
                "reason": "state_machine_not_provided",
            }
            previous_clear_state: Optional[Dict[str, Any]] = None
            previous_table_clear_state: Optional[Dict[str, Any]] = None
            if clear_json_state_machine is not None:
                previous_table_clear_state = clear_json_state_machine.get_last_clear_json(
                    table_id=table_id,
                )
                previous_clear_state = clear_json_state_machine.get_last_clear_json(
                    table_id=table_id,
                    hand_id=hand_id,
                )
                clear_state_candidate, recovery_report = recover_clear_json_state(
                    current_clear=clear_state_candidate,
                    previous_clear=previous_clear_state,
                )

            hand_identity_audit = state.get("hand_identity_recovery_order_audit")
            if isinstance(hand_identity_audit, dict):
                previous_same_hand_hero_position, previous_same_hand_hero_cards = _extract_clear_hero_position_and_cards(previous_clear_state)
                previous_table_hero_position, previous_table_hero_cards = _extract_clear_hero_position_and_cards(previous_table_clear_state)
                recovered_hero_position, recovered_hero_cards = _extract_clear_hero_position_and_cards(clear_state_candidate)
                raw_cards = hand_identity_audit.get("raw_hero_cards_for_identity")
                raw_cards_list = list(raw_cards) if isinstance(raw_cards, list) else []
                raw_valid = (len(raw_cards_list) == 2 and len(set(raw_cards_list)) == 2)
                previous_table_hand_id = (
                    previous_table_clear_state.get("hand_id")
                    if isinstance(previous_table_clear_state, dict)
                    else None
                )
                previous_same_hand_found = isinstance(previous_clear_state, dict)
                previous_table_found = isinstance(previous_table_clear_state, dict)
                recovered_cards_list = list(recovered_hero_cards)
                hand_identity_audit.update({
                    "recovery_stage": {
                        "clear_json_candidate_built": isinstance(clear_state_candidate, dict),
                        "clear_json_state_machine_available": clear_json_state_machine is not None,
                        "previous_same_hand_clear_json_found": previous_same_hand_found,
                        "previous_table_clear_json_found": previous_table_found,
                        "previous_table_hand_id": previous_table_hand_id,
                        "previous_same_hand_hero_position": previous_same_hand_hero_position,
                        "previous_same_hand_hero_cards": list(previous_same_hand_hero_cards),
                        "previous_table_hero_position": previous_table_hero_position,
                        "previous_table_hero_cards": list(previous_table_hero_cards),
                        "recovery_report": recovery_report,
                        "recovered_hero_position": recovered_hero_position,
                        "recovered_hero_cards": recovered_cards_list,
                        "recovery_changed_hero_cards": bool(recovered_cards_list and recovered_cards_list != raw_cards_list),
                    },
                    "potential_false_new_hand_id_due_to_pre_recovery_identity": bool(
                        active_confirmed
                        and not raw_valid
                        and previous_table_found
                        and not previous_same_hand_found
                    ),
                    "diagnostic_reason": (
                        "raw_hero_invalid_but_previous_table_clear_exists_for_different_hand_id"
                        if (
                            active_confirmed
                            and not raw_valid
                            and previous_table_found
                            and not previous_same_hand_found
                        )
                        else "no_pre_recovery_identity_risk_detected"
                    ),
                })

            pending_validation = validate_clear_json_contract(clear_state_candidate)
            decision_json_path: Optional[Path] = None
            decision_json_validation: Dict[str, object] = {"ok": False, "errors": ["Decision_JSON was not built."], "warnings": []}
            action_decision_contract: Dict[str, object] = {
                "enabled": bool(V06_ACTION_DECISION_ENABLED),
                "source": "Decision_JSON",
                "path": None,
                "dir": V06_ACTION_DECISION_DIR_NAME,
                "status": "not_built",
                "action_runtime_plan_contract": {
                    "enabled": bool(V07_ACTION_RUNTIME_PLAN_ENABLED),
                    "source": "Action_Decision_JSON",
                    "path": None,
                    "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
                    "status": "not_built",
                },
            }
            if pending_validation.get("ok"):
                pending_path = save_pending_clear_table_frame_json(
                    clear_state=clear_state_candidate,
                    cycle_dir=cycle_dir,
                    table_id=table_id,
                )
                if V05_DECISION_JSON_ENABLED:
                    try:
                        decision_state = build_decision_json_from_clear_state(clear_state_candidate)
                        decision_json_validation = validate_decision_json_contract(decision_state)
                        if decision_json_validation.get("ok"):
                            # V1.0.1: Pending Clear_JSON is diagnostic-only. Build the
                            # Decision/Action/RuntimePlan chain in memory so guards and
                            # lineage audits can still validate the current action, but
                            # do not publish Decision_JSON, Action_Decision_JSON or
                            # Action_Runtime_Plan_JSON files until Final Clear_JSON is
                            # actually saved after click/dry-run completion.
                            solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                clear_state=clear_state_candidate,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                            )
                            action_decision_contract = build_and_save_action_decision_contract(
                                decision_state=decision_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                                publish_files=False,
                                solver_preflop_bridge_contract=solver_preflop_bridge_contract,
                            )
                            if isinstance(action_decision_contract, dict):
                                action_decision_contract["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
                                state["solver_preflop_bridge_contract"] = solver_preflop_bridge_contract
                            if action_decision_contract.get("status") not in {"preview_not_saved_pending_only", "disabled"}:
                                for message in action_decision_contract.get("validation", {}).get("errors", []) if isinstance(action_decision_contract.get("validation"), dict) else []:
                                    add_error(state, block="action_decision_contract", message=str(message))
                        else:
                            for message in decision_json_validation.get("errors", []) if isinstance(decision_json_validation, dict) else []:
                                add_error(state, block="decision_json_contract", message=str(message))
                    except Exception as exc:
                        decision_json_validation = {"ok": False, "errors": [str(exc)], "warnings": []}
                        add_error(state, block="decision_json_contract", message=str(exc))
            elif V05_DECISION_JSON_ENABLED:
                decision_json_validation = {"ok": False, "errors": ["Pending Clear_JSON validation failed; Decision_JSON was not built."], "warnings": []}

            state["clear_json_contract"] = {
                "status": "pending",
                "reason": "clear_json_candidate_waiting_for_action_result",
                "publication_stage": "pending",
                "pending_path": str(pending_path) if pending_path else None,
                "path": None,
                "recovery": recovery_report,
                "pending_validation": pending_validation,
                "publication": {
                    "pending_dir": V04_CLEAR_JSON_PENDING_DIR_NAME,
                    "final_dir": V04_CLEAR_JSON_FINAL_DIR_NAME,
                    "pending_path": str(pending_path) if pending_path else None,
                    "final_path": None,
                    "final_requires_click_result": bool(V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT),
                },
                "decision_json_contract": {
                    "enabled": bool(V05_DECISION_JSON_ENABLED),
                    "source": "Clear_JSON",
                    "path": str(decision_json_path) if decision_json_path else None,
                    "dir": V05_DECISION_JSON_DIR_NAME,
                    "validation": decision_json_validation,
                    "status": (
                        "saved"
                        if decision_json_path
                        else (
                            "skipped"
                            if not V05_DECISION_JSON_ENABLED
                            else (
                                "preview_not_saved_pending_only"
                                if isinstance(decision_json_validation, dict) and decision_json_validation.get("ok")
                                else "validation_failed"
                            )
                        )
                    ),
                    "publication_stage": "pending_preview" if (isinstance(decision_json_validation, dict) and decision_json_validation.get("ok") and not decision_json_path) else "pending",
                    "file_publication_enabled": bool(decision_json_path),
                },
                "action_decision_contract": action_decision_contract,
            }

            if not pending_validation.get("ok"):
                state["clear_json_contract"].update({
                    "status": "validation_failed",
                    "reason": "pending_clear_json_contract_validation_failed",
                    "message": "Pending Clear_JSON candidate failed validation; final Clear_JSON was not published.",
                })
                for message in pending_validation.get("errors", []) if isinstance(pending_validation, dict) else []:
                    add_error(state, block="clear_json_contract", message=str(message))
                for message in pending_validation.get("warnings", []) if isinstance(pending_validation, dict) else []:
                    add_warning(state, block="clear_json_contract", message=str(message))
            elif not clear_json_save_allowed:
                state["clear_json_contract"].update({
                    "status": "skipped",
                    "reason": "action_transaction_not_completed",
                    "publication_stage": "pending_only",
                    "message": "Final Clear_JSON is not published because the Active action/click transaction did not complete.",
                })
            elif V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT and not isinstance(click_result, dict):
                state["clear_json_contract"].update({
                    "status": "skipped",
                    "reason": "missing_click_result_for_final_clear_json",
                    "publication_stage": "pending_only",
                    "message": "Final Clear_JSON requires compact click_result.",
                })
                add_error(state, block="clear_json_contract", message="Final Clear_JSON requires compact click_result.")
            else:
                click_execution_guard_report: Optional[Dict[str, object]] = None
                if isinstance(click_result, dict) and V09_CLICK_CONFIRMATION_REPORT_ENABLED:
                    runtime_plan_contract_for_guard = {}
                    if isinstance(action_decision_contract, dict):
                        maybe_plan = action_decision_contract.get("action_runtime_plan_contract")
                        if isinstance(maybe_plan, dict):
                            runtime_plan_contract_for_guard = maybe_plan
                    click_execution_guard_report = _build_click_execution_guard_report(
                        state=state,
                        table_id=table_id,
                        hand_id=hand_id,
                        clear_state=clear_state_candidate,
                        click_result=click_result,
                        runtime_plan_contract=runtime_plan_contract_for_guard,
                    )
                    state["click_execution_guard"] = click_execution_guard_report
                    runtime_action_block = state.get("runtime_action")
                    if isinstance(runtime_action_block, dict):
                        runtime_action_block["click_execution_guard"] = click_execution_guard_report

                v31_confirmed_real_click = _is_v31_confirmed_real_click_for_final_publication(
                    state=state,
                    click_result=click_result,
                )

                if (
                    isinstance(click_execution_guard_report, dict)
                    and not bool(click_execution_guard_report.get("guard_passed"))
                    and not v31_confirmed_real_click
                ):
                    state["clear_json_contract"].update({
                        "status": "skipped",
                        "reason": "click_execution_guard_failed",
                        "publication_stage": "pending_only",
                        "path": None,
                        "click_execution_guard": click_execution_guard_report,
                        "message": str(click_execution_guard_report.get("message") or "Final Clear_JSON publication blocked by V0.9 ClickExecutionGuard."),
                    })
                    add_warning(
                        state,
                        block="click_execution_guard",
                        message=str(click_execution_guard_report.get("message") or "Final Clear_JSON publication blocked by V0.9 ClickExecutionGuard."),
                    )
                else:
                    if (
                        isinstance(click_execution_guard_report, dict)
                        and not bool(click_execution_guard_report.get("guard_passed"))
                        and v31_confirmed_real_click
                    ):
                        click_execution_guard_report["v33_final_publication_override"] = {
                            "schema_version": "v3_3_final_clear_real_clicked_publication",
                            "status": "allowed",
                            "reason": "v31_confirmed_real_click_already_executed",
                            "message": "Final Clear_JSON publication allowed because V3.1 controlled live-click gate already executed and recorded this real Action_Button click.",
                        }
                        state["clear_json_contract"]["v33_final_publication_override"] = click_execution_guard_report["v33_final_publication_override"]
                    # Keep Final Clear_JSON.click_result compact and schema-safe.
                    # The full V0.9 guard audit remains in Dark_JSON.click_execution_guard
                    # and runtime_action.click_execution_guard; it is intentionally not
                    # copied into final Clear_JSON.click_result.
                    final_publication_block = _detect_final_clear_json_publication_block(
                        previous_clear_state=previous_clear_state,
                        current_clear_state=clear_state_candidate,
                        click_result=click_result,
                    )
                    if isinstance(final_publication_block, dict):
                        state["clear_json_contract"].update({
                            "status": "skipped",
                            "reason": final_publication_block.get("reason", "final_clear_json_publication_blocked"),
                            "publication_stage": "pending_only",
                            "path": None,
                            "final_publication_guard": final_publication_block,
                            "message": final_publication_block.get("message", "Final Clear_JSON publication blocked by V0.8 final publication guard."),
                        })
                        add_warning(
                            state,
                            block="clear_json_contract",
                            message=str(final_publication_block.get("message", "Final Clear_JSON publication blocked by V0.8 final publication guard.")),
                        )
                    elif clear_json_state_machine is not None:
                        decision, clear_state_to_save = clear_json_state_machine.observe(
                            table_id=table_id,
                            hand_id=hand_id,
                            clear_json=clear_state_candidate,
                        )
                        state["clear_json_contract"].update({
                            "status": "saved" if decision.should_save else "skipped",
                            "reason": decision.reason,
                            "publication_stage": "final" if decision.should_save else "pending_only",
                            "state_machine": decision.to_json(),
                        })
    
                        if decision.should_save and clear_state_to_save is not None:
                            final_clear_state = dict(clear_state_to_save)
                            if click_result is not None:
                                final_clear_state["click_result"] = dict(click_result)
                            validation = validate_clear_json_contract(final_clear_state)
                            if validation.get("ok"):
                                clear_path = save_clear_table_frame_json(
                                    clear_state=final_clear_state,
                                    cycle_dir=cycle_dir,
                                    table_id=table_id,
                                )
                                state["clear_json_contract"].update({
                                    "path": str(clear_path),
                                    "validation": validation,
                                })
                                if V05_DECISION_JSON_ENABLED:
                                    try:
                                        final_decision_state = build_decision_json_from_clear_state(final_clear_state)
                                        final_decision_validation = validate_decision_json_contract(final_decision_state)
                                        if final_decision_validation.get("ok"):
                                            final_decision_path = save_decision_table_frame_json(
                                                decision_state=final_decision_state,
                                                cycle_dir=cycle_dir,
                                                table_id=table_id,
                                            )
                                            final_solver_bridge_clear_state = dict(final_clear_state)
                                            final_solver_bridge_clear_state.pop("click_result", None)
                                            final_solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                                clear_state=final_solver_bridge_clear_state,
                                                cycle_dir=cycle_dir,
                                                table_id=table_id,
                                                publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                                            )
                                            final_action_decision_contract = build_and_save_action_decision_contract(
                                                decision_state=final_decision_state,
                                                cycle_dir=cycle_dir,
                                                table_id=table_id,
                                                publish_files=True,
                                                solver_preflop_bridge_contract=final_solver_preflop_bridge_contract,
                                            )
                                            if isinstance(final_action_decision_contract, dict):
                                                final_action_decision_contract["solver_preflop_bridge_contract"] = final_solver_preflop_bridge_contract
                                            if final_action_decision_contract.get("status") not in {"saved", "disabled"}:
                                                for message in final_action_decision_contract.get("validation", {}).get("errors", []) if isinstance(final_action_decision_contract.get("validation"), dict) else []:
                                                    add_error(state, block="action_decision_contract", message=str(message))
                                            state["clear_json_contract"]["action_decision_contract"] = final_action_decision_contract
                                            state["clear_json_contract"]["decision_json_contract"] = {
                                                "enabled": True,
                                                "source": "Clear_JSON",
                                                "path": str(final_decision_path),
                                                "dir": V05_DECISION_JSON_DIR_NAME,
                                                "validation": final_decision_validation,
                                                "status": "saved",
                                            }
                                        else:
                                            state["clear_json_contract"]["decision_json_contract"] = {
                                                "enabled": True,
                                                "source": "Clear_JSON",
                                                "path": None,
                                                "dir": V05_DECISION_JSON_DIR_NAME,
                                                "validation": final_decision_validation,
                                                "status": "validation_failed",
                                            }
                                            for message in final_decision_validation.get("errors", []) if isinstance(final_decision_validation, dict) else []:
                                                add_error(state, block="decision_json_contract", message=str(message))
                                    except Exception as exc:
                                        state["clear_json_contract"]["decision_json_contract"] = {
                                            "enabled": True,
                                            "source": "Clear_JSON",
                                            "path": None,
                                            "dir": V05_DECISION_JSON_DIR_NAME,
                                            "validation": {"ok": False, "errors": [str(exc)], "warnings": []},
                                            "status": "error",
                                        }
                                        add_error(state, block="decision_json_contract", message=str(exc))
                                publication = state["clear_json_contract"].get("publication")
                                if isinstance(publication, dict):
                                    publication["final_path"] = str(clear_path)
                                _remember_executed_click_decision(table_id, click_result if isinstance(click_result, dict) else None)
                                if V04_DELETE_PENDING_AFTER_FINAL_SAVE and pending_path is not None:
                                    try:
                                        pending_path.unlink(missing_ok=True)
                                        state["clear_json_contract"]["pending_deleted_after_final_save"] = True
                                    except Exception as exc:
                                        add_warning(state, block="clear_json_contract", message=f"Failed to delete pending Clear_JSON: {exc}")
                            else:
                                state["clear_json_contract"].update({
                                    "status": "validation_failed",
                                    "reason": "final_clear_json_contract_validation_failed",
                                    "validation": validation,
                                    "path": None,
                                })
                                for message in validation.get("errors", []) if isinstance(validation, dict) else []:
                                    add_error(state, block="clear_json_contract", message=str(message))
                                for message in validation.get("warnings", []) if isinstance(validation, dict) else []:
                                    add_warning(state, block="clear_json_contract", message=str(message))
                        else:
                            state["clear_json_contract"].update({
                                "path": None,
                                "message": "Clear_JSON candidate was not persisted as final by state-machine.",
                            })
                            for message in decision.validation_errors:
                                add_error(state, block="clear_json_contract", message=str(message))
                            for message in decision.validation_warnings:
                                add_warning(state, block="clear_json_contract", message=str(message))
                    else:
                        final_clear_state = dict(clear_state_candidate)
                        if click_result is not None:
                            final_clear_state["click_result"] = dict(click_result)
                        validation = validate_clear_json_contract(final_clear_state)
                        if validation.get("ok"):
                            clear_path = save_clear_table_frame_json(
                                clear_state=final_clear_state,
                                cycle_dir=cycle_dir,
                                table_id=table_id,
                            )
                            state["clear_json_contract"].update({
                                "status": "saved",
                                "reason": "state_machine_not_provided",
                                "publication_stage": "final",
                                "path": str(clear_path),
                                "validation": validation,
                            })
                            if V05_DECISION_JSON_ENABLED:
                                try:
                                    final_decision_state = build_decision_json_from_clear_state(final_clear_state)
                                    final_decision_validation = validate_decision_json_contract(final_decision_state)
                                    if final_decision_validation.get("ok"):
                                        final_decision_path = save_decision_table_frame_json(
                                            decision_state=final_decision_state,
                                            cycle_dir=cycle_dir,
                                            table_id=table_id,
                                        )
                                        final_solver_bridge_clear_state = dict(final_clear_state)
                                        final_solver_bridge_clear_state.pop("click_result", None)
                                        final_solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                                            clear_state=final_solver_bridge_clear_state,
                                            cycle_dir=cycle_dir,
                                            table_id=table_id,
                                            publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                                        )
                                        final_action_decision_contract = build_and_save_action_decision_contract(
                                            decision_state=final_decision_state,
                                            cycle_dir=cycle_dir,
                                            table_id=table_id,
                                            publish_files=True,
                                            solver_preflop_bridge_contract=final_solver_preflop_bridge_contract,
                                        )
                                        if isinstance(final_action_decision_contract, dict):
                                            final_action_decision_contract["solver_preflop_bridge_contract"] = final_solver_preflop_bridge_contract
                                        if final_action_decision_contract.get("status") not in {"saved", "disabled"}:
                                            for message in final_action_decision_contract.get("validation", {}).get("errors", []) if isinstance(final_action_decision_contract.get("validation"), dict) else []:
                                                add_error(state, block="action_decision_contract", message=str(message))
                                        state["clear_json_contract"]["action_decision_contract"] = final_action_decision_contract
                                        state["clear_json_contract"]["decision_json_contract"] = {
                                            "enabled": True,
                                            "source": "Clear_JSON",
                                            "path": str(final_decision_path),
                                            "dir": V05_DECISION_JSON_DIR_NAME,
                                            "validation": final_decision_validation,
                                            "status": "saved",
                                        }
                                    else:
                                        state["clear_json_contract"]["decision_json_contract"] = {
                                            "enabled": True,
                                            "source": "Clear_JSON",
                                            "path": None,
                                            "dir": V05_DECISION_JSON_DIR_NAME,
                                            "validation": final_decision_validation,
                                            "status": "validation_failed",
                                        }
                                        for message in final_decision_validation.get("errors", []) if isinstance(final_decision_validation, dict) else []:
                                            add_error(state, block="decision_json_contract", message=str(message))
                                except Exception as exc:
                                    state["clear_json_contract"]["decision_json_contract"] = {
                                        "enabled": True,
                                        "source": "Clear_JSON",
                                        "path": None,
                                        "dir": V05_DECISION_JSON_DIR_NAME,
                                        "validation": {"ok": False, "errors": [str(exc)], "warnings": []},
                                        "status": "error",
                                    }
                                    add_error(state, block="decision_json_contract", message=str(exc))
                            publication = state["clear_json_contract"].get("publication")
                            if isinstance(publication, dict):
                                publication["final_path"] = str(clear_path)
                            _remember_executed_click_decision(table_id, click_result if isinstance(click_result, dict) else None)
                        else:
                            state["clear_json_contract"].update({
                                "status": "validation_failed",
                                "reason": "final_clear_json_contract_validation_failed",
                                "validation": validation,
                            })
                            for message in validation.get("errors", []) if isinstance(validation, dict) else []:
                                add_error(state, block="clear_json_contract", message=str(message))
                            for message in validation.get("warnings", []) if isinstance(validation, dict) else []:
                                add_warning(state, block="clear_json_contract", message=str(message))
        except Exception as exc:
            state["clear_json_contract"] = {
                "status": "error",
                "reason": "clear_json_build_or_save_error",
                "message": str(exc),
            }
            add_error(state, block="clear_json_contract", message=str(exc))

    # V0.7/V0.7.1: expose the Action_Runtime_Plan contract and runtime/click lineage
    # inside runtime_action for Dark_JSON audit. Diagnostic-only: no click, solver,
    # gate, or Final Clear_JSON behavior is changed here.
    try:
        contract = state.get("clear_json_contract") if isinstance(state.get("clear_json_contract"), dict) else {}
        action_decision_contract = contract.get("action_decision_contract") if isinstance(contract.get("action_decision_contract"), dict) else {}
        runtime_plan_contract = action_decision_contract.get("action_runtime_plan_contract") if isinstance(action_decision_contract.get("action_runtime_plan_contract"), dict) else {}
        runtime_action_block = state.get("runtime_action")
        if isinstance(runtime_action_block, dict):
            if runtime_plan_contract:
                runtime_action_block["source"] = "Action_Decision_JSON"
                runtime_action_block["action_runtime_plan_contract"] = runtime_plan_contract
                runtime_action_block["planned_action"] = runtime_plan_contract.get("planned_action")
                runtime_action_block["target_sequence_from_action_decision"] = runtime_plan_contract.get("target_sequence")
                runtime_action_block["target_sequences_from_action_decision"] = runtime_plan_contract.get("target_sequences")
            lineage_audit = _build_action_runtime_lineage_audit(state)
            runtime_action_block["action_runtime_lineage_audit"] = lineage_audit
            state["action_runtime_lineage_audit"] = lineage_audit
    except Exception as exc:
        add_warning(state, block="action_runtime_lineage_audit", message=f"Failed to attach runtime lineage audit: {exc}")

    dark_path = save_dark_table_frame_json(
        state=state,
        cycle_dir=cycle_dir,
        table_id=table_id,
        frame_name=frame_name,
    )
    return dark_path, clear_path

def _extract_hero_cards(players_block: Optional[Dict[str, object]]) -> List[str]:
    if not players_block:
        return []
    seats = players_block.get("seats")
    if not isinstance(seats, dict):
        return []
    hero = seats.get("Player_seat1")
    if not isinstance(hero, dict):
        return []
    hero_cards = hero.get("hero_cards")
    if not isinstance(hero_cards, list):
        return []
    return [str(card) for card in hero_cards]


def _extract_board_cards_for_identity(table_structure_block: Optional[Dict[str, object]]) -> List[str]:
    if not table_structure_block:
        return []
    classes = table_structure_block.get("classes")
    if not isinstance(classes, dict):
        return []
    board = classes.get("Board")
    if not isinstance(board, dict):
        return []
    cards = board.get("cards")
    if not isinstance(cards, list):
        return []
    return [str(card) for card in cards if str(card).strip()]


def _extract_street(table_structure_block: Optional[Dict[str, object]]) -> Optional[str]:
    if not table_structure_block:
        return None
    classes = table_structure_block.get("classes")
    if not isinstance(classes, dict):
        return None
    board = classes.get("Board")
    if not isinstance(board, dict):
        return None
    street = board.get("street")
    return str(street) if street is not None else None


def _trigger_has_active_detect(trigger_ui_block: Optional[Dict[str, object]]) -> bool:
    if not trigger_ui_block:
        return False

    classes = trigger_ui_block.get("classes")
    if not isinstance(classes, dict):
        return False

    active_block = classes.get("Active")
    if not isinstance(active_block, dict):
        return False

    return bool(active_block.get("detect", False))



def _compact_click_points(click_points: object) -> List[Dict[str, object]]:
    """Keep click metadata compact for the main table-state JSON."""
    if not isinstance(click_points, list):
        return []

    compact: List[Dict[str, object]] = []
    for point in click_points:
        if not isinstance(point, dict):
            continue
        global_point = point.get("global_click_point") if isinstance(point.get("global_click_point"), dict) else {}
        compact.append(
            {
                "class_name": point.get("class_name"),
                "confidence": point.get("confidence"),
                "global_click_point": {
                    "x": global_point.get("x"),
                    "y": global_point.get("y"),
                },
                "inside_slot_bbox": bool(point.get("inside_slot_bbox", False)),
            }
        )
    return compact




def _compact_mouse_report(mouse: object) -> Dict[str, object]:
    if not isinstance(mouse, dict):
        return {}
    static = mouse.get("mouse_static") if isinstance(mouse.get("mouse_static"), dict) else {}
    movements = mouse.get("movements") if isinstance(mouse.get("movements"), list) else []
    return {
        "static_wait_status": static.get("status"),
        "waited_sec": static.get("waited_sec"),
        "click_count": mouse.get("click_count"),
        "movement_count": len(movements),
    }

def _compact_service_runtime_report(report: Dict[str, object]) -> Dict[str, object]:
    service = report.get("service_click", {}) if isinstance(report, dict) else {}
    death_card = report.get("death_card", {}) if isinstance(report, dict) else {}
    if not isinstance(service, dict):
        service = {}
    if not isinstance(death_card, dict):
        death_card = {}

    compact: Dict[str, object] = {
        "branch": "trigger_ui_service",
        "status": service.get("status", "skipped"),
        "target_class": service.get("target_class"),
        "target_sequence": list(service.get("target_sequence") or []),
        "decision_id": service.get("decision_id"),
        "dry_run": bool(service.get("dry_run", False)),
        "real_click_enabled": bool(service.get("real_click_enabled", False)),
        "guard_passed": bool(service.get("guard_passed", False)),
        "frame_finished": bool(service.get("frame_finished", False)),
        "skip_action_button_runtime": bool(service.get("skip_action_button_runtime", False)),
        "click_points": _compact_click_points(service.get("click_points")),
        "message": service.get("message"),
    }
    mouse_compact = _compact_mouse_report(service.get("mouse"))
    if mouse_compact:
        compact["mouse"] = mouse_compact

    if death_card.get("status") not in (None, "skipped") or death_card.get("hand_key") is not None:
        compact["death_card"] = {
            "status": death_card.get("status"),
            "hand_key": death_card.get("hand_key"),
            "matched": bool(death_card.get("matched", False)),
            "message": death_card.get("message"),
        }

    return compact



def _should_service_stop_poker_branch(service_report: Dict[str, object]) -> bool:
    """
    V7.0/V0.9.1 ordered pipeline policy.

    True means Trigger_UI service branch has successfully handled this frame and
    the heavy poker branch must not run for the same table/frame.

    Stop statuses:
    - dry_run: service action was selected in safe mode;
    - clicked: service action performed a real click;
    - confirmed: detect-only terminal confirmation such as True_active_fold;
    - explicit frame_finished / skip_action_button_runtime flags only when the
      service status is not a non-terminal failure/passive status.

    Non-stop statuses:
    - skipped: no actionable service branch;
    - detected_only: passive service marker, e.g. Remove_Table only;
    - blocked/error: no successful service action; keep normal diagnostics flow.
    """
    service = service_report.get("service_click", {}) if isinstance(service_report, dict) else {}
    if not isinstance(service, dict):
        return False

    status = str(service.get("status") or "").strip().lower()

    if status in {"dry_run", "clicked", "confirmed"}:
        return True

    # V0.9.1: status is authoritative for failures/passive markers. A stale or
    # pre-set skip_action_button_runtime/frame_finished flag must not stop the
    # poker/action branch when the service action itself ended as blocked/error.
    if status in {"", "skipped", "detected_only", "blocked", "error"}:
        return False

    if bool(service.get("frame_finished")):
        return True

    if bool(service.get("skip_action_button_runtime")):
        return True

    return False


def _fallback_action_button_slot_roi_guard_for_compact_report(
    *,
    report: Dict[str, object],
    click: Dict[str, object],
    solver: Dict[str, object],
) -> Dict[str, object]:
    """Build a compact V2.7 exposure fallback when runtime click report has no ROI audit.

    V2.6 keeps the canonical schema_version. V2.7 only guarantees Dark_JSON
    visibility via audit_exposure_version. This fallback is diagnostic-only and
    never authorizes a click.
    """
    table_id = (
        click.get("table_id")
        or solver.get("table_id")
        or report.get("table_id")
        or "unknown_table"
    )
    click_points = click.get("click_points") if isinstance(click.get("click_points"), list) else []
    return {
        "schema_version": "action_button_slot_roi_runtime_audit_v2_6",
        "audit_exposure_version": "v2_7_dark_json_exposure",
        "ok": True,
        "status": "ACTION_BUTTON_SLOT_ROI_RUNTIME_AUDIT_EXPOSED_FALLBACK",
        "table_id": str(table_id),
        "detector_input_scope": "table_roi",
        "full_screen_search_blocked": True,
        "errors": [],
        "warnings": [
            "runtime_click_report_roi_guard_missing; compact Dark_JSON fallback audit inserted"
        ],
        "slot_bbox": None,
        "roi_size": None,
        "click_points_count": len(click_points),
        "per_button": [],
    }

def _compact_action_runtime_report(report: Dict[str, object]) -> Dict[str, object]:
    payload = report.get("payload", {}) if isinstance(report, dict) else {}
    solver = report.get("solver", {}) if isinstance(report, dict) else {}
    action_buttons = report.get("action_buttons", {}) if isinstance(report, dict) else {}
    click = report.get("click", {}) if isinstance(report, dict) else {}

    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(solver, dict):
        solver = {}
    if not isinstance(action_buttons, dict):
        action_buttons = {}
    if not isinstance(click, dict):
        click = {}

    compact = {
        "branch": "action_button",
        "status": click.get("status") or solver.get("status") or payload.get("status") or "skipped",
        "payload_status": payload.get("status"),
        "solver_payload_path": payload.get("path"),
        "solver_status": solver.get("status"),
        "decision_id": click.get("decision_id") or solver.get("decision_id"),
        "solver_action": solver.get("action") or click.get("action"),
        "size_pct": solver.get("size_pct") if solver.get("size_pct") is not None else click.get("size_pct"),
        "solver_reason": solver.get("reason"),
        "total_pot_bb": solver.get("total_pot_bb"),
        "waited_sec": solver.get("waited_sec"),
        "action_button_status": action_buttons.get("status"),
        "action_button_detected_classes": list(action_buttons.get("detected_classes") or []),
        "target_sequence": list(click.get("target_sequence") or []),
        "dry_run": bool(click.get("dry_run", False)),
        "real_click_enabled": bool(click.get("real_click_enabled", False)),
        "guard_passed": bool(click.get("guard_passed", False)),
        "click_points": _compact_click_points(click.get("click_points")),
        "action_button_slot_roi_guard": (
            click.get("action_button_slot_roi_guard")
            if isinstance(click.get("action_button_slot_roi_guard"), dict)
            else _fallback_action_button_slot_roi_guard_for_compact_report(
                report=report if isinstance(report, dict) else {},
                click=click,
                solver=solver,
            )
        ),
        "controlled_live_click_gate": (
            click.get("controlled_live_click_gate")
            if isinstance(click.get("controlled_live_click_gate"), dict)
            else None
        ),
        "controlled_live_click_success": (
            click.get("controlled_live_click_success")
            if isinstance(click.get("controlled_live_click_success"), dict)
            else None
        ),
        "message": click.get("message") or payload.get("message"),
    }
    mouse_compact = _compact_mouse_report(click.get("mouse"))
    if mouse_compact:
        compact["mouse"] = mouse_compact
    return compact


def _build_runtime_action_block(
    *,
    service_report: Dict[str, object],
    action_report: Optional[Dict[str, object]],
) -> Dict[str, object]:
    service_block = _compact_service_runtime_report(service_report)
    action_block = _compact_action_runtime_report(action_report or {}) if action_report is not None else {
        "branch": "action_button",
        "status": "skipped",
        "message": "Action_Button runtime was skipped by Trigger_UI service branch.",
    }

    status = str(action_block.get("status") or service_block.get("status") or "skipped")
    if service_block.get("status") in {"clicked", "dry_run", "confirmed", "blocked", "error"} and action_block.get("status") == "skipped":
        status = str(service_block.get("status"))

    return {
        "status": status,
        "service": service_block,
        "action_button": action_block,
    }


def _lineage_optional_text(value: object) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _lineage_runtime_plan_contract_from_state(state: Dict[str, object]) -> Dict[str, object]:
    contract = state.get("clear_json_contract") if isinstance(state.get("clear_json_contract"), dict) else {}
    action_decision_contract = (
        contract.get("action_decision_contract")
        if isinstance(contract.get("action_decision_contract"), dict)
        else {}
    )
    runtime_plan_contract = (
        action_decision_contract.get("action_runtime_plan_contract")
        if isinstance(action_decision_contract.get("action_runtime_plan_contract"), dict)
        else {}
    )
    return runtime_plan_contract if isinstance(runtime_plan_contract, dict) else {}


def _build_action_runtime_lineage_audit(state: Dict[str, object]) -> Dict[str, object]:
    """Build V0.7.1 diagnostic lineage between RuntimePlan, runtime action, and click_result.

    Diagnostic-only: this function does not authorize clicks, does not block
    publication, and does not alter solver/runtime behavior.
    """
    runtime_action = state.get("runtime_action") if isinstance(state.get("runtime_action"), dict) else {}
    action_button = (
        runtime_action.get("action_button")
        if isinstance(runtime_action.get("action_button"), dict)
        else {}
    )
    service = (
        runtime_action.get("service")
        if isinstance(runtime_action.get("service"), dict)
        else {}
    )
    runtime_plan_contract = _lineage_runtime_plan_contract_from_state(state)
    transaction_runtime = (
        state.get("action_transaction_runtime")
        if isinstance(state.get("action_transaction_runtime"), dict)
        else {}
    )
    click_result = (
        transaction_runtime.get("click_result")
        if isinstance(transaction_runtime.get("click_result"), dict)
        else {}
    )

    runtime_plan_decision_id = _lineage_optional_text(runtime_plan_contract.get("decision_id"))
    action_button_decision_id = _lineage_optional_text(action_button.get("decision_id"))
    service_decision_id = _lineage_optional_text(service.get("decision_id"))
    click_result_decision_id = _lineage_optional_text(click_result.get("decision_id"))

    observed_runtime_decision_ids = [
        value
        for value in (
            action_button_decision_id,
            service_decision_id,
            click_result_decision_id,
        )
        if value
    ]
    observed_unique_ids = sorted(set(observed_runtime_decision_ids))
    decision_id_consistent = len(observed_unique_ids) <= 1
    runtime_plan_has_decision_id = runtime_plan_decision_id is not None
    decision_id_present = bool(observed_runtime_decision_ids or runtime_plan_decision_id)

    if not decision_id_present:
        status = "missing_decision_id"
    elif not decision_id_consistent:
        status = "decision_id_mismatch"
    elif not runtime_plan_has_decision_id and observed_runtime_decision_ids:
        status = "runtime_plan_has_no_decision_id_but_runtime_has_one"
    else:
        status = "ok"

    return {
        "schema_version": "action_runtime_lineage_audit_v0_7_1",
        "behavior": "diagnostics_only_no_runtime_or_click_behavior_changes",
        "status": status,
        "runtime_plan": {
            "source": runtime_plan_contract.get("source"),
            "path": runtime_plan_contract.get("path"),
            "status": runtime_plan_contract.get("status"),
            "planned_action": runtime_plan_contract.get("planned_action"),
            "target_sequence": runtime_plan_contract.get("target_sequence"),
            "target_sequences": runtime_plan_contract.get("target_sequences"),
            "dry_run": runtime_plan_contract.get("dry_run"),
            "real_click_enabled": runtime_plan_contract.get("real_click_enabled"),
            "decision_id": runtime_plan_decision_id,
            "has_decision_id": runtime_plan_has_decision_id,
        },
        "runtime_action": {
            "status": runtime_action.get("status") if isinstance(runtime_action, dict) else None,
            "action_button_status": action_button.get("status"),
            "service_status": service.get("status"),
            "solver_payload_path": action_button.get("solver_payload_path"),
            "action_button_decision_id": action_button_decision_id,
            "service_decision_id": service_decision_id,
            "solver_action": action_button.get("solver_action"),
            "target_sequence": action_button.get("target_sequence"),
            "dry_run": action_button.get("dry_run"),
            "real_click_enabled": action_button.get("real_click_enabled"),
        },
        "click_result": {
            "status": click_result.get("status"),
            "branch": click_result.get("branch"),
            "decision_id": click_result_decision_id,
            "action": click_result.get("action"),
            "dry_run": click_result.get("dry_run"),
            "real_click_enabled": click_result.get("real_click_enabled"),
            "guard_passed": click_result.get("guard_passed"),
        },
        "transaction": {
            "status": transaction_runtime.get("status"),
            "reason": transaction_runtime.get("reason"),
            "phase": transaction_runtime.get("phase"),
            "click_completed": bool(transaction_runtime.get("click_completed", False)),
        },
        "decision_id_present": decision_id_present,
        "decision_id_consistent": decision_id_consistent,
        "observed_runtime_decision_ids": observed_unique_ids,
        "lineage_gap": (
            "action_runtime_plan_contract_does_not_carry_decision_id"
            if not runtime_plan_has_decision_id and observed_runtime_decision_ids
            else None
        ),
    }


def _build_live_capture_mode_block() -> Dict[str, object]:
    """Runtime-only Dark_JSON diagnostic for live no-click data capture mode."""
    return {
        "schema_version": "live_capture_mode_v1",
        "mode": "live_data_capture_no_click" if V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE else "live_runtime",
        "no_click_mode": bool(V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE),
        "action_real_click_enabled": bool(V11_REAL_MOUSE_CLICK_ENABLED),
        "action_dry_run": bool(V11_CLICK_DRY_RUN),
        "service_real_click_enabled": bool(V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED),
        "service_dry_run": bool(V11_TRIGGER_UI_SERVICE_DRY_RUN),
    }


def _run_v11_stage25_service_runtime_safely(
    *,
    state: Dict[str, object],
    table_roi: object,
    slot: TableSlot,
    trigger_result: object,
    cycle_dir: Path,
    identity: Optional[FrameIdentity] = None,
) -> Dict[str, object]:
    """
    Run the Trigger_UI service-click branch and return its in-memory report.

    No standalone _runtime JSON is written here; compact data is later embedded
    into the main table-state JSON.
    """
    if _run_v11_trigger_ui_service_runtime is None:
        message = V11_STAGE25_SERVICE_IMPORT_ERROR or "V1.1 Trigger_UI service runtime is not available."
        print(f"[V1.1 Stage2.5][{slot.table_id}] skipped: {message}")
        return {
            "service_click": {
                "status": "skipped",
                "frame_finished": False,
                "skip_action_button_runtime": False,
                "message": message,
            }
        }

    try:
        trigger_best_by_class = getattr(trigger_result, "best_by_class", None) if trigger_result is not None else None
        report = _run_v11_trigger_ui_service_runtime(
            full_state=state,
            table_roi_image=table_roi,
            slot=slot,
            trigger_best_by_class=trigger_best_by_class,
            cycle_dir=cycle_dir,
        )
        return report if isinstance(report, dict) else {}
    except Exception as exc:
        message = str(exc)
        print(f"[V1.1 Stage2.5][{slot.table_id}] service runtime error: {message}")
        return {
            "service_click": {
                "status": "error",
                "frame_finished": False,
                "skip_action_button_runtime": False,
                "message": message,
            }
        }


def _run_v11_stage2_runtime_safely(
    *,
    state: Dict[str, object],
    table_roi: object,
    slot: TableSlot,
    active_confirmed: bool,
    cycle_dir: Path,
    identity: Optional[FrameIdentity] = None,
) -> Dict[str, object]:
    """
    Run the safe V1.1 action-button chain and return its in-memory report.

    The solver payload JSON is still saved as the second allowed JSON file.
    No standalone _runtime click report is written.
    """
    if _run_v11_stage1_runtime is None:
        message = V11_STAGE2_IMPORT_ERROR or "V1.1 runtime is not available."
        print(f"[V1.1 Stage2][{slot.table_id}] skipped: {message}")
        return {
            "payload": {"status": "skipped", "path": None, "message": message},
            "solver": {"status": "skipped"},
            "action_buttons": {"status": "skipped", "detected_classes": []},
            "click": {"status": "skipped", "target_sequence": [], "message": message},
        }

    try:
        report = _run_v11_stage1_runtime(
            full_state=state,
            table_roi_image=table_roi,
            slot=slot,
            active_confirmed=active_confirmed,
            cycle_dir=cycle_dir,
        )
        return report if isinstance(report, dict) else {}
    except Exception as exc:
        message = str(exc)
        print(f"[V1.1 Stage2][{slot.table_id}] runtime error: {message}")
        return {
            "payload": {"status": "error", "path": None, "message": message},
            "solver": {"status": "skipped"},
            "action_buttons": {"status": "skipped", "detected_classes": []},
            "click": {"status": "error", "target_sequence": [], "message": message},
        }


def run_ui_display_analysis_cycle(
    image_by_table_id: Dict[str, Path],
    opened_table_ids: Set[str],
    hand_tracker: HandIdentityTracker,
    action_event_gate: Optional[ActionEventGate] = None,
    clear_json_state_machine: Optional[ClearJsonStateMachine] = None,
    table_action_transaction_gate: Optional[TableActionTransactionGate] = None,
    display_pass_id: str = DEFAULT_DISPLAY_PASS_ID,
    clear_previous_outputs_on_start: bool = True,
    cycle_id: str | None = None,
) -> List[Path]:
    """
    Запустить V1 runtime-анализ текущего display-pass.

    В одном pass у разных table_N могут быть разные hand_id/frame_name.
    display_pass_id используется только для debug-папок и не попадает в clean JSON.
    """
    started_at = now_perf_counter()

    if clear_previous_outputs_on_start:
        clear_previous_outputs()

    if cycle_id is None:
        cycle_id = make_cycle_id()
    cycle_dir = build_cycle_dir()
    ensure_dir(cycle_dir)

    if clear_json_state_machine is None:
        clear_json_state_machine = _DEFAULT_CLEAR_JSON_STATE_MACHINE
    if table_action_transaction_gate is None and V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED:
        table_action_transaction_gate = _DEFAULT_TABLE_ACTION_TRANSACTION_GATE

    active_slots = [slot for slot in list_table_slots() if slot.table_id in image_by_table_id]
    if not active_slots:
        raise ValueError("Current display pass has no bound table images")

    screenshot = capture_primary_monitor()
    screenshot_size = {"w": screenshot.width, "h": screenshot.height}

    if SAVE_DEBUG_DESKTOP_CAPTURE:
        save_desktop_screenshot(cycle_dir, screenshot, display_pass_id=display_pass_id)

    saved_json_paths: List[Path] = []

    for slot in active_slots:
        if slot.table_id not in opened_table_ids:
            raise ValueError(f"Table window was not open for {slot.table_id}")

        validate_bbox_inside_screenshot(slot, screenshot_size)
        table_roi = crop_table_roi(slot=slot, screenshot=screenshot)

        if SAVE_DEBUG_TABLE_CROPS:
            save_table_crop(
                cycle_dir=cycle_dir,
                slot=slot,
                table_roi=table_roi,
                display_pass_id=display_pass_id,
            )

        trigger_result = None
        table_structure_result = None
        player_state_result = None
        digit_amounts_result = None
        card_detection_result = None
        table_status = "ok"

        if TRIGGER_UI_ENABLED:
            trigger_result = run_trigger_ui_pipeline(
                table_roi_image=table_roi,
                table_id=slot.table_id,
            )

        if V12_SAVE_ONLY_TRIGGERED_TABLES and trigger_result is not None:
            detected_classes = trigger_result.trigger_ui_block.get("detected_classes") if isinstance(trigger_result.trigger_ui_block, dict) else []
            detected_set = {str(class_name) for class_name in detected_classes}
            meaningful_detected_set = detected_set - {"Remove_Table"}
            if not meaningful_detected_set:
                # Real desktop mode: do not create JSON for idle slots.
                # Remove_Table is ignored here because it is a frequent passive service marker
                # and by itself does not mean that a poker hand/action frame exists.
                if action_event_gate is not None:
                    action_event_gate.observe_inactive(slot.table_id)
                if table_action_transaction_gate is not None:
                    table_action_transaction_gate.observe_inactive(slot.table_id)
                continue

        # V7.0.2 Stage 3 ordered pipeline:
        # Trigger_UI service branch is evaluated before heavy poker analysis.
        # If a service action/confirmation handles the frame, preserve Dark_JSON audit
        # and do not run table_structure/player/digit/card/Decision/Action branches.
        if trigger_result is not None:
            early_service_classes = []
            if isinstance(trigger_result.trigger_ui_block, dict):
                raw_service_classes = trigger_result.trigger_ui_block.get("detected_classes")
                if isinstance(raw_service_classes, list):
                    early_service_classes = [
                        str(class_name)
                        for class_name in raw_service_classes
                        if str(class_name).strip()
                    ]
            early_service_signature = "_".join(sorted(early_service_classes)) or "service"
            early_service_frame_name = f"{slot.table_id}_{cycle_id}_{early_service_signature}_service"

            early_service_state = build_table_frame_state(
                slot=slot,
                hand_id=f"{slot.table_id}_service",
                frame_name=early_service_frame_name,
                cycle_id=cycle_id,
                processing_time_ms=elapsed_ms(started_at),
                trigger_ui_block=trigger_result.trigger_ui_block,
                table_structure_block=None,
                players_block=None,
                table_status="service",
            )
            early_service_state["live_capture_mode"] = _build_live_capture_mode_block()

            for warning in trigger_result.warnings:
                add_warning(early_service_state, block="trigger_ui", message=warning)
            for error in trigger_result.errors:
                add_error(early_service_state, block="trigger_ui", message=error)

            early_service_report = _run_v11_stage25_service_runtime_safely(
                state=early_service_state,
                table_roi=table_roi,
                slot=slot,
                trigger_result=trigger_result,
                cycle_dir=cycle_dir,
                identity=None,
            )
            early_service_state["runtime_action"] = _build_runtime_action_block(
                service_report=early_service_report if isinstance(early_service_report, dict) else {},
                action_report=None,
            )
            _update_runtime_lifecycle_diagnostics(
                early_service_state,
                table_id=slot.table_id,
                cycle_id=cycle_id,
                frame_name=early_service_frame_name,
                active_confirmed=False,
                table_status="service",
                branch="early_service",
                service_runtime={
                    "report": _compact_report_for_diagnostics(
                        early_service_report if isinstance(early_service_report, dict) else None
                    ),
                    "stop_poker_branch": _should_service_stop_poker_branch(
                        early_service_report if isinstance(early_service_report, dict) else {}
                    ),
                },
            )

            if _should_service_stop_poker_branch(early_service_report if isinstance(early_service_report, dict) else {}):
                early_service_state["clear_json_contract"] = {
                    "status": "skipped",
                    "reason": "v70_service_first_branch_completed",
                    "publication_stage": "dark_json_only",
                    "pending_path": None,
                    "path": None,
                    "message": (
                        "V7.0 ordered pipeline: Trigger_UI service branch handled this frame before "
                        "heavy poker analysis. Clear_JSON_Pending, Decision_JSON, Action_Decision_JSON "
                        "and Action_Runtime_Plan_JSON were not built."
                    ),
                    "decision_json_contract": {
                        "enabled": bool(V05_DECISION_JSON_ENABLED),
                        "source": "Clear_JSON",
                        "path": None,
                        "dir": V05_DECISION_JSON_DIR_NAME,
                        "status": "not_built_service_first_stop",
                    },
                    "action_decision_contract": {
                        "enabled": bool(V06_ACTION_DECISION_ENABLED),
                        "source": "Decision_JSON",
                        "path": None,
                        "dir": V06_ACTION_DECISION_DIR_NAME,
                        "status": "not_built_service_first_stop",
                        "action_runtime_plan_contract": {
                            "enabled": bool(V07_ACTION_RUNTIME_PLAN_ENABLED),
                            "source": "Action_Decision_JSON",
                            "path": None,
                            "dir": V07_ACTION_RUNTIME_PLAN_DIR_NAME,
                            "status": "not_built_service_first_stop",
                        },
                    },
                }
                early_service_dark_path = save_dark_table_frame_json(
                    state=early_service_state,
                    cycle_dir=cycle_dir,
                    table_id=slot.table_id,
                    frame_name=str(early_service_state.get("frame_name") or f"{slot.table_id}_{cycle_id}_service"),
                )
                saved_json_paths.append(early_service_dark_path)
                if action_event_gate is not None:
                    action_event_gate.observe_inactive(slot.table_id)
                if table_action_transaction_gate is not None:
                    table_action_transaction_gate.observe_inactive(slot.table_id)
                continue

        early_action_transaction_decision = None
        early_lifecycle_gate_audit = None
        early_lifecycle_active = (
            trigger_result is not None
            and trigger_result.table_status_hint == TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE
        )
        if early_lifecycle_active and table_action_transaction_gate is not None:
            early_action_transaction_decision = table_action_transaction_gate.begin_analysis_cycle(
                table_id=slot.table_id,
                action_event_id=None,
                action_signature=None,
            )
            early_lifecycle_gate_audit = _build_table_lifecycle_gate_audit(
                early_action_transaction_decision,
                stage="before_heavy_analysis",
            )
            if not early_action_transaction_decision.should_process:
                print(
                    f"[TableActionTransactionGate][{slot.table_id}] heavy analysis skipped by early lifecycle gate: "
                    f"reason={early_action_transaction_decision.reason}, "
                    f"locked_by={early_action_transaction_decision.locked_by_transaction_id}"
                )

                # V2.29: release stale early lifecycle directly inside the early gate blocked path.
                #
                # V2.28 released only after heavy analysis/action-runtime candidate calculation.
                # That does not help when this early branch immediately continues before heavy
                # analysis. In real live runs this left tables stuck at
                # table_lifecycle_already_open_before_analysis and prevented the chain from
                # reaching Clear_JSON -> Solver_Preflop -> Action_Button -> click.
                #
                # We still skip the current frame after releasing; the next scan can reopen a
                # fresh lifecycle and process a real Active frame without re-entering this
                # stale-lock loop.
                if (
                    table_action_transaction_gate is not None
                    and str(early_action_transaction_decision.reason) == "table_lifecycle_already_open_before_analysis"
                ):
                    stale_lifecycle_release_before_continue = table_action_transaction_gate.abort_analysis_cycle(
                        table_id=slot.table_id,
                        reason="v229_release_stale_lifecycle_before_heavy_analysis",
                        message=(
                            "V2.29 released stale early table lifecycle before heavy-analysis skip; "
                            "current frame remains skipped and the next scan may process normally."
                        ),
                    )
                    print(
                        f"[TableActionTransactionGate][{slot.table_id}] V2.29 released stale early lifecycle before continue: "
                        f"status={stale_lifecycle_release_before_continue.get('status')}, "
                        f"reason={stale_lifecycle_release_before_continue.get('reason')}, "
                        f"released_transaction_id={stale_lifecycle_release_before_continue.get('transaction_id')}"
                    )
                continue

        if TABLE_STRUCTURE_ENABLED:
            structure_allowed = True
            skip_reason = None

            if TABLE_STRUCTURE_REQUIRE_ACTIVE:
                structure_allowed = (
                    trigger_result is not None
                    and trigger_result.table_status_hint == TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE
                )
                if not structure_allowed:
                    skip_reason = (
                        f"{slot.table_id}: Table_Seat_BoardPot_Detector skipped because "
                        "Trigger_UI strong Active was not detected."
                    )

            if structure_allowed:
                table_structure_result = run_table_structure_pipeline(
                    table_roi_image=table_roi,
                    table_id=slot.table_id,
                )
            else:
                table_structure_result = build_skipped_table_structure_block(
                    reason=skip_reason or "Table structure stage skipped by runtime policy."
                )

        if PLAYER_STATE_ENABLED:
            player_state_allowed = True
            skip_reason = None

            if PLAYER_STATE_REQUIRE_TABLE_STRUCTURE:
                table_structure_block = (
                    table_structure_result.table_structure_block
                    if table_structure_result else {}
                )
                player_state_allowed = (
                    table_structure_result is not None
                    and table_structure_block.get("next_stage_hint") == "players_pipeline_ready"
                    and bool(table_structure_result.player_seat_regions)
                )
                if not player_state_allowed:
                    skip_reason = (
                        f"{slot.table_id}: Player_State_Detector skipped because "
                        "table_structure did not provide players_pipeline_ready with runtime Player_seat regions."
                    )

            if player_state_allowed and table_structure_result is not None:
                player_state_result = run_player_state_pipeline(
                    table_roi_image=table_roi,
                    table_id=slot.table_id,
                    hand_id=display_pass_id,
                    cycle_dir=cycle_dir,
                    detected_player_seats=table_structure_result.detected_player_seats,
                    player_seat_regions=table_structure_result.player_seat_regions,
                )
            else:
                player_state_result = build_skipped_player_state_block(
                    reason=skip_reason or "Player state stage skipped by runtime policy."
                )

        if DIGIT_AMOUNTS_ENABLED:
            digit_allowed = True
            skip_reason = None

            if DIGIT_AMOUNTS_REQUIRE_PLAYERS:
                digit_allowed = (
                    table_structure_result is not None
                    and player_state_result is not None
                    and player_state_result.players_block.get("next_stage_hint") == "digit_amounts_pipeline_ready"
                )
                if not digit_allowed:
                    skip_reason = (
                        f"{slot.table_id}: Digit_Detector skipped because players stage did not provide "
                        "digit_amounts_pipeline_ready."
                    )

            if digit_allowed and table_structure_result is not None and player_state_result is not None:
                digit_amounts_result = run_digit_amounts_pipeline(
                    table_roi_image=table_roi,
                    table_id=slot.table_id,
                    hand_id=display_pass_id,
                    cycle_dir=cycle_dir,
                    table_structure_block=table_structure_result.table_structure_block,
                    players_block=player_state_result.players_block,
                    total_pot_region=table_structure_result.total_pot_region,
                    player_amount_regions=player_state_result.amount_regions,
                )
            elif table_structure_result is not None and player_state_result is not None:
                from pipeline.digit_amounts_pipeline import build_skipped_digit_amounts_result
                digit_amounts_result = build_skipped_digit_amounts_result(
                    table_structure_block=table_structure_result.table_structure_block,
                    players_block=player_state_result.players_block,
                    reason=skip_reason or "Digit amounts stage skipped by runtime policy.",
                )

        if CARD_DETECTION_ENABLED:
            card_allowed = True
            skip_reason = None

            if CARD_DETECTION_REQUIRE_PLAYERS:
                base_players_block = (
                    digit_amounts_result.players_block
                    if digit_amounts_result is not None
                    else (player_state_result.players_block if player_state_result is not None else {})
                )
                card_allowed = (
                    table_structure_result is not None
                    and player_state_result is not None
                    and bool(base_players_block.get("seats"))
                )
                if not card_allowed:
                    skip_reason = (
                        f"{slot.table_id}: Card_Detector skipped because players stage did not provide "
                        "a usable players block."
                    )

            if card_allowed and table_structure_result is not None and player_state_result is not None:
                source_table_block = (
                    digit_amounts_result.table_structure_block
                    if digit_amounts_result is not None
                    else table_structure_result.table_structure_block
                )
                source_players_block = (
                    digit_amounts_result.players_block
                    if digit_amounts_result is not None
                    else player_state_result.players_block
                )
                card_detection_result = run_card_detection_pipeline(
                    table_roi_image=table_roi,
                    table_id=slot.table_id,
                    hand_id=display_pass_id,
                    cycle_dir=cycle_dir,
                    table_structure_block=source_table_block,
                    players_block=source_players_block,
                    board_region=table_structure_result.board_region,
                    player_seat_regions=table_structure_result.player_seat_regions,
                )
            elif table_structure_result is not None and player_state_result is not None:
                from pipeline.card_detection_pipeline import build_skipped_card_detection_result
                source_table_block = (
                    digit_amounts_result.table_structure_block
                    if digit_amounts_result is not None
                    else table_structure_result.table_structure_block
                )
                source_players_block = (
                    digit_amounts_result.players_block
                    if digit_amounts_result is not None
                    else player_state_result.players_block
                )
                card_detection_result = build_skipped_card_detection_result(
                    table_structure_block=source_table_block,
                    players_block=source_players_block,
                    reason=skip_reason or "Card detection stage skipped by runtime policy.",
                )

        if card_detection_result and card_detection_result.status == "error":
            table_status = "error"
        elif digit_amounts_result and digit_amounts_result.status == "error":
            table_status = "error"
        elif player_state_result and player_state_result.players_block.get("status") == "error":
            table_status = "error"
        elif table_structure_result and table_structure_result.table_structure_block.get("status") == "error":
            table_status = "error"
        elif card_detection_result and card_detection_result.status == "warning":
            table_status = "warning"
        elif digit_amounts_result and digit_amounts_result.status == "warning":
            table_status = "warning"
        elif player_state_result and player_state_result.players_block.get("status") == "warning":
            table_status = "warning"
        elif table_structure_result and table_structure_result.table_structure_block.get("status") == "warning":
            table_status = "warning"
        else:
            table_status = "ok"

        final_table_structure_block = (
            card_detection_result.table_structure_block
            if card_detection_result else (
                digit_amounts_result.table_structure_block
                if digit_amounts_result else (
                    table_structure_result.table_structure_block
                    if table_structure_result else None
                )
            )
        )
        final_players_block = (
            card_detection_result.players_block
            if card_detection_result else (
                digit_amounts_result.players_block
                if digit_amounts_result else (
                    player_state_result.players_block
                    if player_state_result else None
                )
            )
        )

        active_confirmed = (
            trigger_result is not None
            and trigger_result.table_status_hint == TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE
        )
        hero_cards_for_identity = _extract_hero_cards(final_players_block)
        street_for_identity = _extract_street(final_table_structure_block)
        board_cards_for_identity = _extract_board_cards_for_identity(final_table_structure_block)

        action_event_decision: Optional[ActionEventDecision] = None
        action_transaction_decision = early_action_transaction_decision
        if action_event_gate is not None:
            if active_confirmed:
                action_event_decision = action_event_gate.evaluate_active(
                    table_id=slot.table_id,
                    hero_cards=hero_cards_for_identity,
                    street=street_for_identity,
                    table_structure_block=final_table_structure_block,
                    players_block=final_players_block,
                )
                if not action_event_decision.should_process:
                    # V0.8 live hotfix: duplicate Active/action events must not block
                    # table analysis or Dark_JSON publication. They only suppress the
                    # action/click branch later in this cycle. This preserves street
                    # continuity, so flop -> turn -> river can still be observed.
                    print(
                        f"[ActionEventGate][{slot.table_id}] duplicate Active action suppressed, "
                        f"analysis preserved: reason={action_event_decision.reason}, "
                        f"duplicate_of={action_event_decision.duplicate_of}"
                    )

                # V2.30: recover duplicate Active into runtime retry when no runtime/final artifact exists.
                #
                # Real-live failure fixed here:
                # - ActionEventGate correctly suppresses identical Active frames to avoid repeated output.
                # - However, if the original Active produced only Pending/Solver payload diagnostics and never
                #   reached Action_Runtime_Plan_JSON or Final Clear_JSON/click_result, then treating every
                #   following identical Active as a hard duplicate permanently prevents clicking.
                # - In that unfinished state we convert the duplicate decision into a guarded retry event.
                #   Existing click guards/no-repeat guards still decide whether a physical click is allowed.
                v230_runtime_plan_dir = cycle_dir / V07_ACTION_RUNTIME_PLAN_DIR_NAME / slot.table_id
                v230_final_clear_dir = cycle_dir / V04_CLEAR_JSON_FINAL_DIR_NAME / slot.table_id
                v230_has_runtime_plan = v230_runtime_plan_dir.exists() and any(v230_runtime_plan_dir.glob("*.json"))
                v230_has_final_clear = v230_final_clear_dir.exists() and any(v230_final_clear_dir.glob("*.json"))
                v230_duplicate_retry_allowed = (
                    str(action_event_decision.reason) == "duplicate_active_frame_blocked"
                    and not bool(v230_has_runtime_plan)
                    and not bool(v230_has_final_clear)
                )
                if v230_duplicate_retry_allowed:
                    v230_retry_base = (
                        action_event_decision.duplicate_of
                        or f"evt_{slot.table_id}_{str(action_event_decision.action_signature or 'no_signature')[:16]}"
                    )
                    v230_retry_event_id = f"{v230_retry_base}_v230_retry"
                    action_event_decision = replace(
                        action_event_decision,
                        should_process=True,
                        action_event_id=v230_retry_event_id,
                        reason="v230_duplicate_active_runtime_retry_without_completed_runtime",
                    )
                    print(
                        f"[ActionEventGate][{slot.table_id}] V2.30 duplicate Active runtime retry enabled: "
                        f"event_id={v230_retry_event_id}, "
                        f"has_runtime_plan={v230_has_runtime_plan}, "
                        f"has_final_clear={v230_has_final_clear}"
                    )
            else:
                action_event_gate.observe_inactive(slot.table_id)
                if table_action_transaction_gate is not None:
                    table_action_transaction_gate.observe_inactive(slot.table_id)

        identity = hand_tracker.resolve(
            table_id=slot.table_id,
            active_confirmed=active_confirmed,
            hero_cards=hero_cards_for_identity,
            street=street_for_identity,
            board_cards=board_cards_for_identity,
        )

        total_ms = elapsed_ms(started_at)
        state = build_table_frame_state(
            slot=slot,
            hand_id=identity.hand_id,
            frame_name=identity.frame_name,
            cycle_id=cycle_id,
            processing_time_ms=total_ms,
            trigger_ui_block=(trigger_result.trigger_ui_block if trigger_result else None),
            table_structure_block=final_table_structure_block,
            players_block=final_players_block,
            table_status=table_status,
        )

        raw_hero_cards_for_identity = normalize_card_list(hero_cards_for_identity)
        state["hand_identity_recovery_order_audit"] = {
            "schema_version": "hand_identity_recovery_order_audit_v0_4_2",
            "behavior": "identity_keeps_previous_hand_id_on_missing_hero_without_inventing_cards",
            "active_confirmed": bool(active_confirmed),
            "raw_hero_cards_for_identity": raw_hero_cards_for_identity,
            "raw_hero_cards_valid_for_identity": (
                len(raw_hero_cards_for_identity) == 2
                and len(set(raw_hero_cards_for_identity)) == 2
            ),
            "identity_before_recovery": {
                "hand_id": identity.hand_id,
                "frame_name": identity.frame_name,
                "is_continuation": bool(identity.is_continuation),
                "hero_cards_key": list(identity.hero_cards_key) if identity.hero_cards_key else None,
                "street": identity.street,
                "street_occurrence": identity.street_occurrence,
                "warning": identity.warning,
            },
            "risk_note": (
                "Hand identity is resolved before Clear_JSON recovery in this version. "
                "This audit proves whether a temporary HERO-card miss can allocate a new hand_id "
                "while a previous stable Clear_JSON exists for the same table."
            ),
        }

        state["live_capture_mode"] = _build_live_capture_mode_block()
        _update_runtime_lifecycle_diagnostics(
            state,
            table_id=slot.table_id,
            cycle_id=cycle_id,
            frame_name=identity.frame_name,
            active_confirmed=bool(active_confirmed),
            table_status=table_status,
            hand_identity={
                "hand_id": identity.hand_id,
                "is_continuation": bool(identity.is_continuation),
                "hero_cards_key": list(identity.hero_cards_key) if identity.hero_cards_key else None,
                "street": identity.street,
                "street_occurrence": identity.street_occurrence,
                "warning": identity.warning,
            },
            action_event_gate=_compact_gate_decision_for_diagnostics(action_event_decision),
            early_transaction_gate=_compact_gate_decision_for_diagnostics(early_action_transaction_decision),
        )

        if early_lifecycle_gate_audit is not None:
            state["table_lifecycle_gate"] = early_lifecycle_gate_audit

        if action_event_decision is not None:
            state["runtime_event"] = action_event_decision.to_json()
            state["table"]["action_event_id"] = action_event_decision.action_event_id

        if action_transaction_decision is not None:
            state["action_transaction"] = action_transaction_decision.to_json()

        if identity.warning:
            add_warning(state, block="hand_identity", message=identity.warning)

        if trigger_result:
            for warning in trigger_result.warnings:
                add_warning(state, block="trigger_ui", message=warning)
            for error in trigger_result.errors:
                add_error(state, block="trigger_ui", message=error)

        if table_structure_result:
            for warning in table_structure_result.warnings:
                add_warning(state, block="table_structure", message=warning)
            for error in table_structure_result.errors:
                add_error(state, block="table_structure", message=error)

        if player_state_result:
            for warning in player_state_result.warnings:
                add_warning(state, block="players", message=warning)
            for error in player_state_result.errors:
                add_error(state, block="players", message=error)

        if digit_amounts_result:
            for warning in digit_amounts_result.warnings:
                add_warning(state, block="digit_amounts", message=warning)
            for error in digit_amounts_result.errors:
                add_error(state, block="digit_amounts", message=error)

        if card_detection_result:
            for warning in card_detection_result.warnings:
                add_warning(state, block="card_detection", message=warning)
            for error in card_detection_result.errors:
                add_error(state, block="card_detection", message=error)

        service_report = _run_v11_stage25_service_runtime_safely(
            state=state,
            table_roi=table_roi,
            slot=slot,
            trigger_result=trigger_result,
            cycle_dir=cycle_dir,
            identity=identity,
        )
        service_click = service_report.get("service_click", {}) if isinstance(service_report, dict) else {}
        service_frame_finished = bool(service_click.get("frame_finished"))
        service_skip_action_runtime = bool(service_click.get("skip_action_button_runtime"))
        _update_runtime_lifecycle_diagnostics(
            state,
            service_runtime={
                "report": _compact_report_for_diagnostics(service_report if isinstance(service_report, dict) else None),
                "frame_finished": service_frame_finished,
                "skip_action_button_runtime": service_skip_action_runtime,
            },
        )

        action_report: Optional[Dict[str, object]] = None
        action_runtime_candidate = (
            active_confirmed
            and action_event_decision is not None
            and bool(action_event_decision.should_process)
            and bool(action_event_decision.action_event_id)
        )

        action_runtime_skip_reason: Optional[str] = None
        action_runtime_skip_detail: Dict[str, object] = {
            "active_confirmed": bool(active_confirmed),
            "action_event_decision_present": action_event_decision is not None,
            "action_event_should_process": (
                bool(action_event_decision.should_process)
                if action_event_decision is not None
                else False
            ),
            "action_event_reason": (
                str(action_event_decision.reason)
                if action_event_decision is not None
                else None
            ),
            "action_event_id_present": (
                bool(action_event_decision.action_event_id)
                if action_event_decision is not None
                else False
            ),
        }
        if not active_confirmed:
            action_runtime_skip_reason = "no_active_confirmed"
        elif action_event_decision is None:
            action_runtime_skip_reason = "missing_action_event_decision"
        elif not bool(action_event_decision.should_process):
            action_runtime_skip_reason = str(action_event_decision.reason or "action_event_not_processable")
        elif not bool(action_event_decision.action_event_id):
            action_runtime_skip_reason = "missing_action_event_id"

        action_runtime_allowed = (
            action_runtime_candidate
            and not service_frame_finished
            and not service_skip_action_runtime
        )
        if action_runtime_candidate:
            if service_frame_finished:
                action_runtime_skip_reason = "blocked_by_service_frame_finished"
            elif service_skip_action_runtime:
                action_runtime_skip_reason = "blocked_by_service_skip_action_runtime"

        _update_runtime_lifecycle_diagnostics(
            state,
            action_runtime_pre_gate={
                "candidate": bool(action_runtime_candidate),
                "allowed_before_transaction_gate": bool(action_runtime_allowed),
                "skip_reason_before_transaction_gate": action_runtime_skip_reason,
                "skip_detail": action_runtime_skip_detail,
                "blocked_by_service_frame_finished": bool(service_frame_finished),
                "blocked_by_service_skip_action_runtime": bool(service_skip_action_runtime),
            },
        )

        # V2.28: release early lifecycle lock if the frame cannot enter action runtime.
        #
        # Real-live failure fixed here:
        # - Trigger_UI can briefly open the early per-table lifecycle before the
        #   post-analysis action_event_id/signature is available.
        # - If the resulting frame is later classified as no_active_confirmed,
        #   duplicate_active_frame_blocked, or missing action_event_id, the
        #   Action_Button runtime will not run and therefore no click_result can
        #   close the lifecycle.
        # - Without this release, the next scans are blocked by
        #   table_lifecycle_already_open_before_analysis and the bot never
        #   reaches Solver_Preflop -> Action_Button -> click for that table.
        early_lifecycle_release_before_action = None
        if (
            table_action_transaction_gate is not None
            and early_action_transaction_decision is not None
            and bool(getattr(early_action_transaction_decision, "should_process", False))
            and not bool(action_runtime_candidate)
        ):
            release_reason = str(action_runtime_skip_reason or "action_runtime_not_candidate_after_analysis")
            early_lifecycle_release_before_action = table_action_transaction_gate.abort_analysis_cycle(
                table_id=slot.table_id,
                reason=f"v228_release_early_lifecycle_{release_reason}",
                message=(
                    "V2.28 released early table lifecycle because this frame reached "
                    "post-analysis but cannot enter the Action_Button runtime/click branch."
                ),
            )
            _update_runtime_lifecycle_diagnostics(
                state,
                early_lifecycle_release_before_action=early_lifecycle_release_before_action,
            )

        # V2.0: the table transaction lifecycle starts before heavy analysis and
        # enters the action/click phase only when the action runtime is actually
        # going to run. This prevents repeated heavy analysis while an unfinished
        # per-table lifecycle is already open.
        if action_runtime_allowed and table_action_transaction_gate is not None:
            action_transaction_decision = table_action_transaction_gate.begin_action_cycle(
                table_id=slot.table_id,
                action_event_id=(action_event_decision.action_event_id if action_event_decision else None),
                action_signature=(action_event_decision.action_signature if action_event_decision else None),
            )
            state["action_transaction"] = action_transaction_decision.to_json()
            if isinstance(state.get("table_lifecycle_gate"), dict):
                state["table_lifecycle_gate"]["action_cycle"] = _build_table_lifecycle_gate_audit(
                    action_transaction_decision,
                    stage="before_action_runtime",
                )
            if not action_transaction_decision.should_process:
                action_runtime_skip_reason = str(
                    action_transaction_decision.reason or "blocked_by_late_transaction_gate"
                )
                action_runtime_skip_detail["transaction_gate_locked_by"] = (
                    action_transaction_decision.locked_by_transaction_id
                )
                print(
                    f"[TableActionTransactionGate][{slot.table_id}] action runtime suppressed, "
                    f"analysis preserved: reason={action_transaction_decision.reason}, "
                    f"locked_by={action_transaction_decision.locked_by_transaction_id}"
                )
                action_runtime_allowed = False

        _update_runtime_lifecycle_diagnostics(
            state,
            action_transaction_gate=_compact_gate_decision_for_diagnostics(action_transaction_decision),
            action_runtime_after_gate={
                "allowed": bool(action_runtime_allowed),
                "candidate": bool(action_runtime_candidate),
                "skip_reason": action_runtime_skip_reason,
                "skip_detail": action_runtime_skip_detail,
            },
        )

        if action_runtime_allowed:

            # V2.32: inject Solver_Preflop bridge into full_state before v11 runtime.
            #
            # Live failure fixed here:
            # - Pending/Decision preview path builds solver_preflop_bridge_contract later inside
            #   save_dark_and_clear_table_frame_json(...).
            # - _run_v11_stage2_runtime_safely(...) receives full_state before that late save path,
            #   so v11_stage1_runtime could not see state["solver_preflop_bridge_contract"].
            # - v11 then fell back to legacy v12_stub_* and real-click was blocked as
            #   blocked_stub_real_click, even though Solver_Preflop_Bridge was selected in preview.
            # - This block builds the same bridge from a current Clear_JSON candidate before v11 runtime.
            v232_existing_solver_preflop_bridge = state.get("solver_preflop_bridge_contract")
            if not isinstance(v232_existing_solver_preflop_bridge, dict):
                try:
                    v232_pre_runtime_clear_state = build_clear_json_from_dark_state(state)
                    if isinstance(v232_pre_runtime_clear_state, dict):
                        v232_pre_runtime_clear_state = dict(v232_pre_runtime_clear_state)
                        v232_pre_runtime_clear_state.pop("click_result", None)
                        v232_pre_runtime_solver_preflop_bridge_contract = build_solver_preflop_dryrun_bridge_contract(
                            clear_state=v232_pre_runtime_clear_state,
                            cycle_dir=cycle_dir,
                            table_id=slot.table_id,
                            publish_files=bool(V17_SOLVER_PREFLOP_BRIDGE_PUBLISH_DIAGNOSTIC_FILES),
                        )
                        state["solver_preflop_bridge_contract"] = v232_pre_runtime_solver_preflop_bridge_contract
                        v232_bridge_payload = (
                            v232_pre_runtime_solver_preflop_bridge_contract.get("bridge_payload")
                            if isinstance(v232_pre_runtime_solver_preflop_bridge_contract, dict)
                            else None
                        )
                        v232_action_decision = (
                            v232_bridge_payload.get("action_decision")
                            if isinstance(v232_bridge_payload, dict)
                            else None
                        )
                        state["v232_pre_runtime_solver_preflop_bridge"] = {
                            "status": "built",
                            "bridge_status": (
                                v232_pre_runtime_solver_preflop_bridge_contract.get("status")
                                if isinstance(v232_pre_runtime_solver_preflop_bridge_contract, dict)
                                else None
                            ),
                            "action_decision_available": isinstance(v232_action_decision, dict),
                            "decision_id": (
                                v232_action_decision.get("decision_id")
                                if isinstance(v232_action_decision, dict)
                                else None
                            ),
                            "source": "pre_runtime_injection_before_v11_stage2",
                        }
                    else:
                        state["v232_pre_runtime_solver_preflop_bridge"] = {
                            "status": "not_built",
                            "reason": "clear_json_candidate_not_dict",
                            "source": "pre_runtime_injection_before_v11_stage2",
                        }
                except Exception as exc:
                    state["v232_pre_runtime_solver_preflop_bridge"] = {
                        "status": "error",
                        "reason": str(exc),
                        "source": "pre_runtime_injection_before_v11_stage2",
                    }
                    add_error(state, block="solver_preflop_bridge_contract", message=f"V2.32 pre-runtime bridge build failed: {exc}")
            action_report = _run_v11_stage2_runtime_safely(
                state=state,
                table_roi=table_roi,
                slot=slot,
                active_confirmed=active_confirmed,
                cycle_dir=cycle_dir,
                identity=identity,
            )
        else:
            if not action_runtime_candidate:
                print(
                    f"[V1.1 Stage2][{slot.table_id}] skipped: "
                    f"reason={action_runtime_skip_reason}; "
                    f"active_confirmed={active_confirmed}; "
                    f"event_reason={action_runtime_skip_detail.get('action_event_reason')}; "
                    f"event_id_present={action_runtime_skip_detail.get('action_event_id_present')}"
                )
            elif service_frame_finished or service_skip_action_runtime:
                print(
                    f"[V1.1 Stage2][{slot.table_id}] skipped by service runtime: "
                    f"reason={action_runtime_skip_reason}; "
                    f"frame_finished={service_frame_finished}, "
                    f"skip_action_runtime={service_skip_action_runtime}"
                )
            else:
                print(
                    f"[V1.1 Stage2][{slot.table_id}] skipped by late transaction gate: "
                    f"reason={action_runtime_skip_reason}; table analysis was preserved."
                )

        state["runtime_action"] = _build_runtime_action_block(
            service_report=service_report if isinstance(service_report, dict) else {},
            action_report=action_report,
        )
        _update_runtime_lifecycle_diagnostics(
            state,
            action_runtime_report=_compact_report_for_diagnostics(action_report),
            runtime_action_block_present=isinstance(state.get("runtime_action"), dict),
        )

        duplicate_active_hard_stop_before_pending = (
            active_confirmed
            and action_event_decision is not None
            and not bool(action_event_decision.should_process)
            and str(action_event_decision.reason) == "duplicate_active_frame_blocked"
        )

        clear_json_save_allowed = True
        click_result_for_clear = None
        transaction_runtime_report: Optional[Dict[str, object]] = None
        if active_confirmed and table_action_transaction_gate is not None:
            if action_report is not None and action_transaction_decision is not None and action_transaction_decision.should_process:
                transaction_runtime_report = table_action_transaction_gate.finalize_from_runtime(
                    table_id=slot.table_id,
                    runtime_action=state["runtime_action"] if isinstance(state.get("runtime_action"), dict) else {},
                )
                state["action_transaction_runtime"] = transaction_runtime_report
                clear_json_save_allowed = bool(transaction_runtime_report.get("click_completed"))
                click_result = transaction_runtime_report.get("click_result")
                if isinstance(click_result, dict) and clear_json_save_allowed:
                    click_result_for_clear = click_result
            else:
                clear_json_save_allowed = False
                release_report = None
                transaction_skip_reason = (
                    "duplicate_active_frame_blocked"
                    if duplicate_active_hard_stop_before_pending
                    else "no_new_action_runtime_cycle_for_this_active_frame"
                )
                transaction_release_reason = (
                    "duplicate_active_frame_released_without_publication"
                    if duplicate_active_hard_stop_before_pending
                    else "no_completed_action_runtime_for_active_lifecycle"
                )
                transaction_release_message = (
                    "Duplicate Active frame released without creating new JSON/action files."
                    if duplicate_active_hard_stop_before_pending
                    else "Early table lifecycle was released because no action runtime completed for this Active frame."
                )
                if action_transaction_decision is not None and action_transaction_decision.should_process:
                    release_report = table_action_transaction_gate.abort_analysis_cycle(
                        table_id=slot.table_id,
                        reason=transaction_release_reason,
                        message=transaction_release_message,
                    )
                state["action_transaction_runtime"] = {
                    "status": "duplicate_suppressed" if duplicate_active_hard_stop_before_pending else "skipped",
                    "reason": transaction_skip_reason,
                    "click_completed": False,
                    "message": (
                        "Duplicate Active frame suppressed by strict lifecycle policy; no new JSON/action files were created."
                        if duplicate_active_hard_stop_before_pending
                        else "Table analysis/Dark_JSON is preserved, but Final Clear_JSON requires a completed action runtime cycle."
                    ),
                    "early_lifecycle_release": release_report,
                }

        _update_runtime_lifecycle_diagnostics(
            state,
            action_transaction_runtime=_compact_report_for_diagnostics(
                transaction_runtime_report
                if isinstance(transaction_runtime_report, dict)
                else state.get("action_transaction_runtime") if isinstance(state.get("action_transaction_runtime"), dict) else None
            ),
            clear_json_pre_publication={
                "save_allowed": bool(clear_json_save_allowed),
                "click_result_available": isinstance(click_result_for_clear, dict),
            },
        )

        if duplicate_active_hard_stop_before_pending:
            state["duplicate_active_hard_stop"] = {
                "schema_version": "duplicate_active_hard_stop_v4_1",
                "status": "DUPLICATE_ACTIVE_SUPPRESSED_WITHOUT_PUBLICATION",
                "reason": "duplicate_active_frame_blocked",
                "duplicate_of": action_event_decision.duplicate_of,
                "action_signature": action_event_decision.action_signature,
                "message": (
                    "Duplicate Active frame was suppressed by the strict lifecycle policy. "
                    "No new Dark_JSON, Clear_JSON_Pending, Decision_JSON, Action_Decision_JSON, "
                    "Action_Runtime_Plan_JSON, Final Clear_JSON or JSON_Complete file was created."
                ),
            }

        _update_runtime_lifecycle_diagnostics(
            state,
            duplicate_active_hard_stop={
                "enabled": bool(duplicate_active_hard_stop_before_pending),
                "reason": "duplicate_active_frame_blocked" if duplicate_active_hard_stop_before_pending else None,
            },
            clear_json_publication_intent={
                "active_confirmed": bool(active_confirmed),
                "build_allowed": not bool(duplicate_active_hard_stop_before_pending),
                "save_allowed": bool(clear_json_save_allowed),
                "requires_click_result": bool(V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT),
                "click_result_available": isinstance(click_result_for_clear, dict),
            },
        )

        if duplicate_active_hard_stop_before_pending:
            print(
                f"[ActionEventGate][{slot.table_id}] duplicate Active output suppressed: "
                "no Dark_JSON/Clear_JSON/Decision/RuntimePlan files created for this duplicate frame."
            )
            continue

        dark_json_path, clear_json_path = save_dark_and_clear_table_frame_json(
            state=state,
            cycle_dir=cycle_dir,
            table_id=slot.table_id,
            hand_id=identity.hand_id,
            frame_name=identity.frame_name,
            active_confirmed=active_confirmed,
            clear_json_state_machine=clear_json_state_machine,
            clear_json_save_allowed=clear_json_save_allowed,
            clear_json_build_allowed=True,
            clear_json_build_block_reason=None,
            click_result=click_result_for_clear,
        )

        failed_finalization_release = None
        if active_confirmed and table_action_transaction_gate is not None:
            failed_finalization_release = _release_failed_active_finalization_if_needed(
                state=state,
                table_action_transaction_gate=table_action_transaction_gate,
                table_id=slot.table_id,
                action_transaction_decision=action_transaction_decision,
                transaction_runtime_report=transaction_runtime_report,
                clear_json_path=clear_json_path,
            )
            if isinstance(failed_finalization_release, dict):
                # The release audit is produced after Clear_JSON contract evaluation;
                # rewrite the same Dark_JSON file so the saved audit reflects the
                # final lifecycle release state.
                dark_json_path = save_dark_table_frame_json(
                    state=state,
                    cycle_dir=cycle_dir,
                    table_id=slot.table_id,
                    frame_name=identity.frame_name,
                )
            else:
                table_action_transaction_gate.mark_clear_json_saved(
                    table_id=slot.table_id,
                    clear_json_path=str(clear_json_path) if clear_json_path else None,
                )
                if (
                    clear_json_path
                    and isinstance(transaction_runtime_report, dict)
                    and bool(transaction_runtime_report.get("click_completed"))
                ):
                    try:
                        completed_state = json.loads(Path(str(clear_json_path)).read_text(encoding="utf-8"))
                        if not isinstance(completed_state, dict):
                            raise ValueError("Final Clear_JSON content is not an object.")
                        completed_json_path = save_completed_json_table_frame_json(
                            completed_state=completed_state,
                            cycle_dir=cycle_dir,
                            table_id=slot.table_id,
                        )
                        state["completed_json_contract"] = {
                            "status": "saved",
                            "path": str(completed_json_path),
                            "dir": V10_JSON_COMPLETE_DIR_NAME,
                            "source_clear_json_path": str(clear_json_path),
                            "reason": "final_clear_json_and_action_runtime_completed",
                        }
                    except Exception as exc:
                        state["completed_json_contract"] = {
                            "status": "error",
                            "path": None,
                            "dir": V10_JSON_COMPLETE_DIR_NAME,
                            "source_clear_json_path": str(clear_json_path),
                            "reason": "completed_json_save_error",
                            "message": str(exc),
                        }
                        add_warning(state, block="completed_json_contract", message=str(exc))
                    dark_json_path = save_dark_table_frame_json(
                        state=state,
                        cycle_dir=cycle_dir,
                        table_id=slot.table_id,
                        frame_name=identity.frame_name,
                    )

        # Compatibility: current replay harness reads the returned path as the full technical state.
        # The upgraded harness will also verify the linked Clear_JSON path from clear_json_contract.
        saved_json_paths.append(dark_json_path)


    return saved_json_paths
