r"""
config.py

PokerVision Core V1.2 / V0.9 — live desktop runtime configuration.

Главные изменения V1:
- тестовый запуск больше не считает каждую batch-группу по 6 изображений одной общей раздачей;
- каждая область table_01 ... table_06 ведёт собственную runtime-историю;
- новая раздача определяется по факту: strong Active + HERO cards Player_seat1;
- продолжение раздачи определяется только внутри той же table-области по тем же HERO cards;
- если Active отсутствует, кадр получает отдельный hand_N и не может иметь продолжения;
- output JSON сохраняется по frame_name: hand_01_preflop, hand_01_flop,
  hand_08_preflop_02 и т.д.;
- V1.2 работает по реальному рабочему столу: анализирует 6 table-областей напрямую с monitor screenshot;
- тестовые PNG больше не открываются и не используются в основном runtime;
- solver пока остаётся временной заглушкой;
- real-click ветка включается через защитные флаги ниже.

Важно:
- UI/скриншоты/crop/test_image не записываются в clean JSON;
- raw bbox детекций не записываются в clean JSON;
- клики могут выполняться только через slot guard + anti-repeat + human-like mouse runtime.
"""

from __future__ import annotations

import os
from pathlib import Path


# =============================================================================
# 1. PYTHON / PROJECT INFO
# =============================================================================

PYTHON_EXE = Path(r"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe")
PYTHON_VERSION_TARGET = "3.12.8"

PROJECT_ROOT = Path(__file__).resolve().parent


# =============================================================================
# 2. UI SETTINGS
# =============================================================================

UI_WINDOW_WIDTH = 1920
UI_WINDOW_HEIGHT = 1080
UI_START_MAXIMIZED = True

UI_BOTTOM_BAR_HEIGHT = 96
UI_MONITOR_REFRESH_MS = 350

# Пауза между live-cycles. В V1.2 тестовые изображения не открываются.
DISPLAY_SETTLE_DELAY_MS = 500

UI_LAUNCH_DISPLAY_DIR = PROJECT_ROOT / "ui_launch_display"

# =============================================================================
# 2.0. V1.2 LIVE DESKTOP MODE
# =============================================================================

V12_LIVE_DESKTOP_MODE = True
V81_CONTROLLED_LIVE_READY_PROFILE_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_READY_PROFILE"
V81_CONTROLLED_LIVE_READY_PROFILE_VALUE = "V8_1_CONTROLLED_ACTION_BUTTON"
V81_CONTROLLED_LIVE_READY_PROFILE_ACTIVE = (
    os.environ.get(V81_CONTROLLED_LIVE_READY_PROFILE_ENV_VAR, "").strip()
    == V81_CONTROLLED_LIVE_READY_PROFILE_VALUE
)

# Safe live audit mode. When enabled, main.py/UI may run the live desktop
# detector pipeline and save Dark_JSON/Clear_JSON, but every real-click branch
# is forced into dry-run. This is the default mode for data verification.
V87_FULL_LIVE_CHAIN_SCOPE_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_TEST_SCOPE"
V87_FULL_LIVE_CHAIN_SCOPE_VALUE = "V8_7_FULL_LIVE_CHAIN_NO_LIMIT"
V87_FULL_LIVE_CHAIN_SCOPE_ACTIVE = (
    os.environ.get(V87_FULL_LIVE_CHAIN_SCOPE_ENV_VAR, "").strip()
    == V87_FULL_LIVE_CHAIN_SCOPE_VALUE
)

V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE = not V81_CONTROLLED_LIVE_READY_PROFILE_ACTIVE

# =============================================================================
# 2.0.1. V0.3 STRICT ACTIVE ACTION TRANSACTION GATE
# =============================================================================

# Включает строгую transaction-дисциплину для каждого table_N:
# Active -> table analysis -> Dark_JSON -> Clear_JSON candidate -> runtime action
# -> click/dry-run result -> только после этого table_N освобождается.
V03_TABLE_ACTION_TRANSACTION_GATE_ENABLED = True

# В no-click/live-data-capture/replay режиме dry-run считается завершённым click-cycle.
# Это нужно, чтобы regression мог проверять transaction gate без реального клика.
V03_TRANSACTION_DRY_RUN_COUNTS_AS_COMPLETED = True

# Если Active пропал до завершения action-cycle, transaction сбрасывается как aborted/released.
V03_TRANSACTION_RELEASE_ON_INACTIVE = True

# =============================================================================
# V0.4 PENDING -> FINAL CLEAR_JSON PUBLICATION
# =============================================================================

# Clear_JSON is first written as a pending candidate and becomes a final Clear_JSON
# only after the action transaction confirms a completed click/dry-run cycle.
V04_PENDING_FINAL_CLEAR_JSON_ENABLED = True
V04_CLEAR_JSON_PENDING_DIR_NAME = "Clear_JSON_Pending"
V04_CLEAR_JSON_FINAL_DIR_NAME = "Clear_JSON"
V04_FINAL_CLEAR_JSON_REQUIRES_CLICK_RESULT = True
V04_DELETE_PENDING_AFTER_FINAL_SAVE = False

# V0.5 Decision_JSON publication layer. Decision_JSON is built only from
# validated Clear_JSON candidate/final state, never from Dark_JSON/runtime debug.
V05_DECISION_JSON_ENABLED = True
V05_DECISION_JSON_DIR_NAME = "Decision_JSON"
V05_DECISION_JSON_SCHEMA_VERSION = "decision_json_v1"

# V0.6 Action_Decision_JSON stub layer. Action_Decision_JSON is built only from
# validated Decision_JSON and contains the action that runtime layers may execute.
V06_ACTION_DECISION_ENABLED = True
V06_ACTION_DECISION_DIR_NAME = "Action_Decision_JSON"
V06_ACTION_DECISION_SCHEMA_VERSION = "action_decision_v1"
V06_ACTION_DECISION_STUB_DEFAULT_ACTION = "check_fold"
V06_ACTION_DECISION_STUB_DEFAULT_SIZE_POLICY = None
V06_ACTION_DECISION_STUB_DEFAULT_REASON = "v62_stub_check_then_check_fold_then_fold"

# =============================================================================
# 2.0.4. V0.7 ACTION_RUNTIME_PLAN CONTRACT
# =============================================================================

# V0.7 connects Action_Decision_JSON to the runtime/action-button planning layer.
# It does not enable real clicks; it records an explicit dry-run-safe plan that
# Action_Button runtime must follow.
V07_ACTION_RUNTIME_PLAN_ENABLED = True
V07_ACTION_RUNTIME_PLAN_DIR_NAME = "Action_Runtime_Plan_JSON"
V07_ACTION_RUNTIME_PLAN_SCHEMA_VERSION = "action_runtime_plan_v1"
V07_RUNTIME_ACTION_SOURCE_REQUIRED = "Action_Decision_JSON"
V07_RUNTIME_PLAN_DRY_RUN_REQUIRED = True

# V10.1 completed-cycle publication layer.
# JSON_Complete is written only after Final Clear_JSON + action runtime completion.
V10_JSON_COMPLETE_DIR_NAME = "JSON_Complete"

V12_REAL_SCAN_INTERVAL_MS = 900
V12_PROCESS_ALL_TABLE_SLOTS = True
V12_SAVE_ONLY_TRIGGERED_TABLES = True
V12_CLEAR_OUTPUTS_ON_LIVE_START = True
V12_UI_BUTTON_TEXT_START = "V1.2: START LIVE DATA CAPTURE (NO CLICK)"
V12_UI_BUTTON_TEXT_STOP = "STOP LIVE ANALYSIS"

# Future solver timeout/failsafe layer. Stub returns immediately, but the contract is ready for a real solver.
V12_SOLVER_WAIT_TIMEOUT_SEC = 8.0
V12_BIG_POT_THRESHOLD_BB = 10.0
V12_BIG_POT_EXTRA_WAIT_SEC = 10.0
V12_SOLVER_FALLBACK_ACTION = "fold"
V12_SOLVER_FALLBACK_SIZE_PCT = None

# Human-like mouse runtime.
V12_MOUSE_STATIC_REQUIRED_SEC = 0.0
V12_MOUSE_OBSERVE_INTERVAL_SEC = 0.12
V12_MOUSE_MOVE_MIN_DURATION_SEC = 0.45
V12_MOUSE_MOVE_MAX_DURATION_SEC = 1.05
V12_MOUSE_STEPS_MIN = 22
V12_MOUSE_STEPS_MAX = 42
V12_MOUSE_JITTER_PX = 5
V12_MOUSE_CLICK_SETTLE_MIN_SEC = 0.08
V12_MOUSE_CLICK_SETTLE_MAX_SEC = 0.22
V12_MOUSE_BETWEEN_CLICKS_MIN_SEC = 0.12
V12_MOUSE_BETWEEN_CLICKS_MAX_SEC = 0.28



# =============================================================================
# 2.0.3. V0.8 LIVE HAND CONTINUITY RECONCILER
# =============================================================================

# Keeps the same hand_id across live Active gaps when continuity is proven by
# same HERO cards plus same/forward board progression (flop -> turn -> river).
V08_LIVE_HAND_CONTINUITY_ENABLED = True

# Inactive/service frames must not erase the last known hand immediately.
# They are treated as temporary visibility gaps until a future Active frame proves
# either continuation or a new hand.
V08_INACTIVE_DOES_NOT_RESET_HAND = True

# If HERO cards are missing on an Active frame, do not erase the previous tracked
# hand. The frame itself stays invalid for Clear_JSON, but future frames may still
# continue the last proven hand by HERO+board.
V08_KEEP_LAST_HAND_ON_INVALID_HERO = True


# =============================================================================
# 2.0.5. V0.8 LIVE OUTPUT CLEANUP GUARD
# =============================================================================

# Before each main.py live launch, remove outputs/ui_display_cycle/current_cycle
# so Explorer cannot show stale Dark/Clear/Decision JSON from previous runs.
V08_CLEAR_CURRENT_CYCLE_ON_MAIN_START = True
V08_CLEAR_CURRENT_CYCLE_DIR_NAME = "current_cycle"



# =============================================================================
# 2.0.6. V0.9 REAL-CLICK READINESS / CLICK EXECUTION GUARD
# =============================================================================

# V0.9 does NOT enable real clicks. It adds a final safety contract that must
# pass before any future mouse execution can happen. The default remains safe.
V09_CLICK_EXECUTION_GUARD_ENABLED = True

# Master arm switch. Real physical clicks are impossible while this is False,
# even if another config flag is accidentally changed.
V09_REAL_CLICK_MASTER_ARMED = bool(V81_CONTROLLED_LIVE_READY_PROFILE_ACTIVE)

# Required safety gates for every action execution attempt.
V09_REQUIRE_SLOT_BOUNDARY_GUARD = True
V09_REQUIRE_NO_REPEAT_DECISION_GUARD = True
V09_REQUIRE_BUTTON_AVAILABILITY_GUARD = True
V09_REQUIRE_ACTION_RUNTIME_PLAN_SOURCE = "Action_Runtime_Plan_JSON"

# Dry-run remains the only allowed execution mode in V0.9 default configuration.
V09_ALLOW_DRY_RUN_COMPLETION = True
V09_BLOCK_REAL_CLICK_WHEN_LIVE_CAPTURE_NO_CLICK = True

# Compact click confirmation report fields that can be copied into Final Clear_JSON.
V09_CLICK_CONFIRMATION_REPORT_ENABLED = True
V09_POST_CLICK_COOLDOWN_SEC = 1.2
V09_CLICK_RESULT_SCHEMA_VERSION = "click_result_v09"

# =============================================================================
# 2.0.7. V1.0 CONTROLLED REAL-CLICK READINESS VALIDATOR
# =============================================================================
# This validator does not click by itself. It only allows the program to start
# in real-click mode when all required safety switches are aligned.
V10_REAL_CLICK_READINESS_VALIDATOR_ENABLED = True
V10_REAL_CLICK_ABORT_ON_UNSAFE_CONFIG = True
V10_REAL_CLICK_ALLOW_ACTION_BUTTON_ONLY = True
V10_REAL_CLICK_REQUIRE_SERVICE_CLICKS_DISABLED = True
V10_REAL_CLICK_REQUIRE_LIVE_NO_CLICK_DISABLED = True
V10_REAL_CLICK_REQUIRE_MASTER_ARMED = True
V10_REAL_CLICK_REQUIRE_MOUSE_REAL_ENABLED = True
V10_REAL_CLICK_REQUIRE_MOUSE_DRY_RUN_DISABLED = True
V10_REAL_CLICK_READINESS_SCHEMA_VERSION = "real_click_readiness_v1"

# =============================================================================
# 2.0.8. V1.4 CONTROLLED REAL-CLICK CONFIG PRESET
# =============================================================================
# V1.4 does not click by itself and does not enable physical clicks by default.
# It defines a narrow, reviewable preset for the first manual live-click test.
# The actual switch to real-click mode is still guarded by:
# - V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE = False
# - V09_REAL_CLICK_MASTER_ARMED = True
# - V11_REAL_MOUSE_CLICK_ENABLED = True
# - V11_CLICK_DRY_RUN = False
# - V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = False
# - V11_TRIGGER_UI_SERVICE_DRY_RUN = True
V14_CONTROLLED_REAL_CLICK_PRESET_SCHEMA_VERSION = "controlled_real_click_preset_v1"
V14_CONTROLLED_REAL_CLICK_PRESET_AVAILABLE = True
V14_CONTROLLED_REAL_CLICK_TEST_MODE = False
V14_CONTROLLED_REAL_CLICK_TABLE_ID = "table_01"
V14_CONTROLLED_REAL_CLICK_MAX_CLICKS_PER_RUN = 1
V14_CONTROLLED_REAL_CLICK_ACTION_BUTTON_ONLY = True
V14_CONTROLLED_REAL_CLICK_SERVICE_BRANCH_DISABLED = True
V14_CONTROLLED_REAL_CLICK_RAISE_BRANCH_ENABLED = False
V14_CONTROLLED_REAL_CLICK_REQUIRE_SCOPE_AUDIT = True
V14_CONTROLLED_REAL_CLICK_STARTUP_ABORT_ON_UNSAFE_PRESET = True
V14_CONTROLLED_REAL_CLICK_ALLOWED_ACTIONS = (
    "fold",
    "check",
    "call",
    "check_fold",
)
V14_CONTROLLED_REAL_CLICK_ALLOWED_BUTTONS = (
    "FOLD",
    "Check",
    "Call",
    "Check/fold",
)


def get_v14_controlled_real_click_preset() -> dict:
    """Return a compact, serializable V1.4 preset snapshot for audits/tests."""
    return {
        "schema_version": V14_CONTROLLED_REAL_CLICK_PRESET_SCHEMA_VERSION,
        "preset_available": bool(V14_CONTROLLED_REAL_CLICK_PRESET_AVAILABLE),
        "test_mode": bool(V14_CONTROLLED_REAL_CLICK_TEST_MODE),
        "table_id": str(V14_CONTROLLED_REAL_CLICK_TABLE_ID),
        "max_clicks_per_run": int(V14_CONTROLLED_REAL_CLICK_MAX_CLICKS_PER_RUN),
        "action_button_only": bool(V14_CONTROLLED_REAL_CLICK_ACTION_BUTTON_ONLY),
        "service_branch_disabled": bool(V14_CONTROLLED_REAL_CLICK_SERVICE_BRANCH_DISABLED),
        "raise_branch_enabled": bool(V14_CONTROLLED_REAL_CLICK_RAISE_BRANCH_ENABLED),
        "require_scope_audit": bool(V14_CONTROLLED_REAL_CLICK_REQUIRE_SCOPE_AUDIT),
        "startup_abort_on_unsafe_preset": bool(V14_CONTROLLED_REAL_CLICK_STARTUP_ABORT_ON_UNSAFE_PRESET),
        "allowed_actions": list(V14_CONTROLLED_REAL_CLICK_ALLOWED_ACTIONS),
        "allowed_buttons": list(V14_CONTROLLED_REAL_CLICK_ALLOWED_BUTTONS),
        "effective_runtime_switches": {
            "V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE": bool(V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE),
            "V09_REAL_CLICK_MASTER_ARMED": bool(V09_REAL_CLICK_MASTER_ARMED),
            "V11_REAL_MOUSE_CLICK_ENABLED": bool(V11_REAL_MOUSE_CLICK_ENABLED),
            "V11_CLICK_DRY_RUN": bool(V11_CLICK_DRY_RUN),
            "V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED": bool(V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED),
            "V11_TRIGGER_UI_SERVICE_DRY_RUN": bool(V11_TRIGGER_UI_SERVICE_DRY_RUN),
        },
    }


# =============================================================================
# 2.0.9. V3.1 CONTROLLED LIVE ONE-CLICK GATE
# =============================================================================
# V3.1 integrates the already-tested detected-button one-click rehearsal into
# the live action-button runtime. Defaults remain safe because live data-capture
# no-click mode still forces dry-run. When real-click mode is deliberately armed,
# this gate allows at most one simple Action_Button click on a deliberately
# configured table_N per process. Default target remains table_01. For staged
# six-slot testing, switch only the controlled target table via
# POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_ID=table_02 ... table_06; all other
# safety gates remain unchanged.
V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION = "controlled_live_click_gate_v3_1"
V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED = True
V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS = (
    "table_01",
    "table_02",
    "table_03",
    "table_04",
    "table_05",
    "table_06",
)
V31_CONTROLLED_LIVE_CLICK_TABLE_ID = "table_01"
V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_ID"
V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS"
V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN"
V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_DEFAULT = 1
V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ALLOWED_VALUES = (0, 1, 2, 3, 4, 5, 6)
V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN = 1
V31_CONTROLLED_LIVE_CLICK_ACTION_BUTTON_ONLY = True
V31_CONTROLLED_LIVE_CLICK_SIMPLE_ACTIONS_ONLY = True
V31_CONTROLLED_LIVE_CLICK_SERVICE_BRANCH_DISABLED = not V87_FULL_LIVE_CHAIN_SCOPE_ACTIVE
V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED = False
V31_CONTROLLED_LIVE_CLICK_REQUIRE_ROI_GUARD_OK = True
V31_CONTROLLED_LIVE_CLICK_REQUIRE_FULL_SCREEN_BLOCKED = True
V31_CONTROLLED_LIVE_CLICK_REQUIRE_INSIDE_SLOT = True
V31_CONTROLLED_LIVE_CLICK_REQUIRE_ENV_CONFIRM = True
V31_CONTROLLED_LIVE_CLICK_ENV_VAR = "POKERVISION_CONTROLLED_LIVE_CLICK"
V31_CONTROLLED_LIVE_CLICK_ENV_VALUE = "V3_1_ONE_CLICK"
V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS = ('fold', 'check', 'call', 'check_fold', 'raise', 'bet_raise', 'open_raise', 'iso_raise', '3bet', '4bet', '5bet', 'jam', 'all_in',)
V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS = ('FOLD', 'Check', 'Call', 'Check/fold', 'CALL', 'Raise', 'Bet/Raise', '33%', '50%', '70%', '98%',)


def _normalize_v31_controlled_live_click_table_id(value: object, *, default: str = "table_01") -> str:
    """Return a safe configured table_N id for the controlled live-click gate."""
    text = str(value or "").strip()
    if text in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS:
        return text
    return str(default if default in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS else "table_01")


def _normalize_v31_controlled_live_click_table_ids(value: object, *, default: object = ("table_01",)) -> tuple[str, ...]:
    """Return a safe, de-duplicated tuple of configured table_N ids.

    V5.4 keeps the old single-table target contract, but adds an optional
    comma-separated multi-target env override:
    POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS=table_01,table_02
    Invalid values are ignored and cannot broaden scope beyond table_01..table_06.
    """
    allowed = {str(x) for x in V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS}
    result: list[str] = []

    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item).strip() for item in value]
    else:
        raw_items = [item.strip() for item in str(value or "").split(",")]

    for item in raw_items:
        if item in allowed and item not in result:
            result.append(item)

    if result:
        return tuple(result)

    if isinstance(default, (list, tuple, set)):
        default_items = [str(item).strip() for item in default]
    else:
        default_items = [str(default or "").strip()]

    fallback: list[str] = []
    for item in default_items:
        if item in allowed and item not in fallback:
            fallback.append(item)

    return tuple(fallback or ["table_01"])


def get_v31_controlled_live_click_max_clicks_per_run() -> int:
    """Return safe effective max clicks per run for controlled live-click gate."""
    raw = os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ENV_VAR), "").strip()
    if V87_FULL_LIVE_CHAIN_SCOPE_ACTIVE and raw.upper() in {"", "0", "NO_LIMIT", "UNLIMITED"}:
        return 0
    default = int(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_DEFAULT)

    if not raw:
        return default

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default

    allowed = tuple(int(x) for x in V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ALLOWED_VALUES)
    if value in allowed:
        return value

    return default


V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN = get_v31_controlled_live_click_max_clicks_per_run()


def get_v31_controlled_live_click_target_table_ids() -> tuple[str, ...]:
    """Return the effective controlled live-click target table set.

    Priority:
    1. POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_IDS comma-separated set.
    2. Legacy POKERVISION_CONTROLLED_LIVE_CLICK_TABLE_ID single target.
    3. Config default V31_CONTROLLED_LIVE_CLICK_TABLE_ID.
    """
    default_table = _normalize_v31_controlled_live_click_table_id(V31_CONTROLLED_LIVE_CLICK_TABLE_ID)
    legacy_override = os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR), "")
    legacy_target = _normalize_v31_controlled_live_click_table_id(legacy_override, default=default_table)
    multi_override = os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR), "")
    return _normalize_v31_controlled_live_click_table_ids(multi_override, default=(legacy_target,))


def get_v31_controlled_live_click_target_table_id() -> str:
    """Return the first effective controlled live-click table target.

    Backward-compatible alias for older single-table tests and audits.
    """
    return get_v31_controlled_live_click_target_table_ids()[0]


def get_v31_controlled_live_click_gate_snapshot() -> dict:
    """Return a compact V3.1/V5.4 gate snapshot for Dark_JSON/tests."""
    table_ids = get_v31_controlled_live_click_target_table_ids()
    return {
        "schema_version": V31_CONTROLLED_LIVE_CLICK_GATE_SCHEMA_VERSION,
        "enabled": bool(V31_CONTROLLED_LIVE_CLICK_GATE_ENABLED),
        "table_id": table_ids[0],
        "table_ids": list(table_ids),
        "configured_table_ids": list(table_ids),
        "configured_default_table_id": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID),
        "allowed_table_ids": list(V31_CONTROLLED_LIVE_CLICK_ALLOWED_TABLE_IDS),
        "table_id_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR),
        "table_id_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_ID_ENV_VAR), ""),
        "table_ids_env_var": str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR),
        "table_ids_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_TABLE_IDS_ENV_VAR), ""),
        "max_clicks_per_run": int(get_v31_controlled_live_click_max_clicks_per_run()),
        "max_clicks_per_run_env_var": str(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ENV_VAR),
        "max_clicks_per_run_env_value": os.environ.get(str(V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN_ENV_VAR), ""),
        "action_button_only": bool(V31_CONTROLLED_LIVE_CLICK_ACTION_BUTTON_ONLY),
        "simple_actions_only": bool(V31_CONTROLLED_LIVE_CLICK_SIMPLE_ACTIONS_ONLY),
        "service_branch_disabled": bool(V31_CONTROLLED_LIVE_CLICK_SERVICE_BRANCH_DISABLED),
        "raise_branch_enabled": bool(V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED),
        "require_roi_guard_ok": bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_ROI_GUARD_OK),
        "require_full_screen_blocked": bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_FULL_SCREEN_BLOCKED),
        "require_inside_slot": bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_INSIDE_SLOT),
        "require_env_confirm": bool(V31_CONTROLLED_LIVE_CLICK_REQUIRE_ENV_CONFIRM),
        "env_var": str(V31_CONTROLLED_LIVE_CLICK_ENV_VAR),
        "env_value": str(V31_CONTROLLED_LIVE_CLICK_ENV_VALUE),
        "allowed_actions": list(V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS),
        "allowed_buttons": list(V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS),
    }

# =============================================================================
# 2.1. V1 TEST REPLAY SETTINGS
# =============================================================================

# Тестовый replay всё ещё может одновременно показывать до 6 столов,
# но раздачи теперь живут отдельно по table_N, а не как один общий batch hand.
UI_MAX_VISIBLE_TABLES = 6
UI_PROCESS_ALL_IMAGES_IN_TEST_DIR = True
UI_CLOSE_WINDOWS_BETWEEN_PASSES = True

# Имена исходных тестовых файлов используются только для восстановления
# заранее подготовленного replay-порядка, чтобы в UI воспроизвести реальный таймлайн.
# Runtime identity/output naming ниже никогда не берутся из имени исходного файла.
TEST_REPLAY_USE_SOURCE_FILE_NAMES_FOR_ORDER_ONLY = True
TEST_REPLAY_REQUIRE_HAND_STYLE_FILE_NAMES = True

# Формат runtime hand numbering: hand_01, hand_02, ...
RUNTIME_HAND_ID_PREFIX = "hand"
RUNTIME_HAND_NUMBER_MIN_WIDTH = 2

# Оставлены как compatibility aliases для старых импортов.
UI_IMAGES_PER_HAND = UI_MAX_VISIBLE_TABLES
UI_TEST_HAND_ID_PREFIX = RUNTIME_HAND_ID_PREFIX
UI_REQUIRE_IMAGE_COUNT_DIVISIBLE_BY_SLOTS = False
UI_TEST_HAND_COUNT = 0
UI_REQUIRE_UNIQUE_IMAGES_ACROSS_TEST_HANDS = True
UI_OVERLAY_NEXT_HAND_WINDOWS = False
UI_CLOSE_WINDOWS_BETWEEN_BATCHES = UI_CLOSE_WINDOWS_BETWEEN_PASSES


# =============================================================================
# 3. INPUT TEST IMAGES
# =============================================================================

TEST_IMAGES_DIR = Path(
    r"C:\PokerVision\Script_Test_PokerVision_All_files\Test_image_6slot_display"
)

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
}


# =============================================================================
# 4. OUTPUT SETTINGS
# =============================================================================

SCHEMA_VERSION = "1.2"
DEFAULT_DISPLAY_PASS_ID = "pass_000001"

OUTPUT_ROOT_DIR = PROJECT_ROOT / "outputs"
UI_DISPLAY_CYCLE_OUTPUT_DIR = OUTPUT_ROOT_DIR / "ui_display_cycle"
CURRENT_CYCLE_DIR_NAME = "current_cycle"

CLEAR_PREVIOUS_UI_DISPLAY_OUTPUTS_ON_BUTTON_CLICK = True
SAVE_DEBUG_DESKTOP_CAPTURE = False
SAVE_DEBUG_TABLE_CROPS = False
SAVE_DEBUG_PLAYER_SEAT_CROPS = False
SAVE_DEBUG_AMOUNT_CROPS = False
SAVE_DEBUG_CARD_CROPS = False

# Дополнительный итоговый JSON для кадров, где найден класс Active.
# Создаётся после обычного clean JSON:
# outputs/ui_display_cycle/current_cycle/active_frames/table_N/frame_name.json
ACTIVE_FRAME_EXPORT_ENABLED = False
ACTIVE_FRAME_OUTPUT_DIR_NAME = "active_frames"
ACTIVE_FRAME_EXPORT_ONLY_FOR_ACTIVE = True


# =============================================================================
# 5. PIPELINE STATUS VALUES
# =============================================================================

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

STATUS_VALUES = [
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_OK,
    STATUS_WARNING,
    STATUS_ERROR,
    STATUS_SKIPPED,
]

TABLE_STATUS_READY_FOR_STRUCTURE_PIPELINE = "ready_for_structure_pipeline"


# =============================================================================
# 6. CURRENT STAGE FLAGS
# =============================================================================

RUN_ANALYSIS_ON_UI_START = False
CREATE_JSON_ON_UI_START = False

RUN_ANALYSIS_AFTER_IMAGE_DISPLAY = True
CREATE_JSON_AFTER_IMAGE_DISPLAY = True


# =============================================================================
# 7. TRIGGER UI DETECTOR
# =============================================================================

TRIGGER_UI_ENABLED = True
TRIGGER_UI_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Trigger_UI_Detector\weights")
TRIGGER_UI_MODEL_FILE_NAME = "best.pt"

TRIGGER_UI_DETECT_THRESHOLD = 0.70
TRIGGER_UI_CONFIRM_THRESHOLD = 0.78

TRIGGER_UI_INFERENCE_CONF = 0.25
TRIGGER_UI_INFERENCE_IOU = 0.45
TRIGGER_UI_INFERENCE_IMGSZ = 832
TRIGGER_UI_DEVICE = None

TRIGGER_UI_CLASSES = [
    "Active",
    "Remove_Table",
    "Remove_Game",
    "Exit_cashOut",
    "Bunny",
    "Non_active_fold",
    "True_active_fold",
    "1_roll_board",
]

TRIGGER_UI_CLICK_EXECUTION_ENABLED = False
TRIGGER_UI_WRITE_RAW_DETECTIONS_TO_CLEAN_JSON = False


# =============================================================================
# 7.1. TABLE STRUCTURE DETECTOR
# =============================================================================

TABLE_STRUCTURE_ENABLED = True
TABLE_STRUCTURE_REQUIRE_ACTIVE = True

TABLE_STRUCTURE_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Table_Seat_BoardPot_Detector\weights")
TABLE_STRUCTURE_MODEL_FILE_NAME = "best.pt"

TABLE_STRUCTURE_DETECT_THRESHOLD = 0.65
TABLE_STRUCTURE_INFERENCE_CONF = 0.25
TABLE_STRUCTURE_INFERENCE_IOU = 0.45
TABLE_STRUCTURE_INFERENCE_IMGSZ = 832
TABLE_STRUCTURE_DEVICE = None

TABLE_STRUCTURE_CLASSES = [
    "Player_seat1",
    "Player_seat2",
    "Player_seat3",
    "Player_seat4",
    "Player_seat5",
    "Player_seat6",
    "Board",
    "Total_pot",
]

# BBox используется runtime-слоем для crop следующего stage, но в clean JSON не пишется.
TABLE_STRUCTURE_WRITE_BBOX_TO_CLEAN_JSON = False


# =============================================================================
# 7.2. PLAYER STATE DETECTOR
# =============================================================================

PLAYER_STATE_ENABLED = True
PLAYER_STATE_REQUIRE_TABLE_STRUCTURE = True

PLAYER_STATE_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Player_State_Detector\weights")
PLAYER_STATE_MODEL_FILE_NAME = "best.pt"

PLAYER_STATE_DETECT_THRESHOLD = 0.65
PLAYER_STATE_INFERENCE_CONF = 0.25
PLAYER_STATE_INFERENCE_IOU = 0.45
PLAYER_STATE_INFERENCE_IMGSZ = 640
PLAYER_STATE_DEVICE = None

PLAYER_STATE_CLASSES = [
    "Stack",
    "Chips",
    "Fold",
    "SitOut",
    "BTN",
]

PLAYER_STATE_WRITE_RAW_DETECTIONS_TO_CLEAN_JSON = False
PLAYER_STATE_BTN_MISSING_IS_ERROR = False


# =============================================================================
# 7.3. DIGIT DETECTOR / AMOUNT READING
# =============================================================================

DIGIT_AMOUNTS_ENABLED = True
DIGIT_AMOUNTS_REQUIRE_PLAYERS = True

DIGIT_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Digit_Detector\weights")
DIGIT_MODEL_FILE_NAME = "best.pt"

DIGIT_DETECT_THRESHOLD = 0.65
DIGIT_INFERENCE_CONF = 0.25
DIGIT_INFERENCE_IOU = 0.45
DIGIT_INFERENCE_IMGSZ = 640
DIGIT_DEVICE = None

DIGIT_CLASSES = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    ".",
    "All-in",
]

DIGIT_WRITE_RAW_DETECTIONS_TO_CLEAN_JSON = False


# =============================================================================
# 7.4. CARD DETECTOR
# =============================================================================

CARD_DETECTION_ENABLED = True
CARD_DETECTION_REQUIRE_PLAYERS = True

CARD_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Card_Detector\weights")
CARD_MODEL_FILE_NAME = "best.pt"

CARD_DETECT_THRESHOLD = 0.65
CARD_INFERENCE_CONF = 0.25
CARD_INFERENCE_IOU = 0.45
CARD_INFERENCE_IMGSZ = 640
CARD_DEVICE = None

# В текущем контракте проекта Player_seat1 всегда HERO.
CARD_HERO_SEAT_NAME = "Player_seat1"

CARD_CLASSES = [
    "A_spades", "A_hearts", "A_diamonds", "A_clubs",
    "2_spades", "2_hearts", "2_diamonds", "2_clubs",
    "3_spades", "3_hearts", "3_diamonds", "3_clubs",
    "4_spades", "4_hearts", "4_diamonds", "4_clubs",
    "5_spades", "5_hearts", "5_diamonds", "5_clubs",
    "6_spades", "6_hearts", "6_diamonds", "6_clubs",
    "7_spades", "7_hearts", "7_diamonds", "7_clubs",
    "8_spades", "8_hearts", "8_diamonds", "8_clubs",
    "9_spades", "9_hearts", "9_diamonds", "9_clubs",
    "10_spades", "10_hearts", "10_diamonds", "10_clubs",
    "J_spades", "J_hearts", "J_diamonds", "J_clubs",
    "Q_spades", "Q_hearts", "Q_diamonds", "Q_clubs",
    "K_spades", "K_hearts", "K_diamonds", "K_clubs",
]

CARD_WRITE_RAW_DETECTIONS_TO_CLEAN_JSON = False


# =============================================================================
# 8. DATA ISOLATION / SAFETY
# =============================================================================

ENFORCE_UNIQUE_IMAGES_PER_TABLE = True
ENFORCE_PER_TABLE_OUTPUT_DIR = True
PREVENT_OUTPUT_PATH_ESCAPE = True
ATOMIC_JSON_WRITE = True
VALIDATE_JSON_IDENTITY_BEFORE_SAVE = True




# =============================================================================
# 10. V1.1 SOLVER PAYLOAD / SOLVER STUB / ACTION BUTTON / CLICK
# =============================================================================

# V1.1 keeps the current full runtime table-status JSON unchanged and builds
# a separate compact solver payload JSON before any solver/click logic.
V11_SOLVER_PAYLOAD_ENABLED = True
V11_SOLVER_PAYLOAD_OUTPUT_DIR_NAME = "solver_payloads"
V11_SOLVER_PAYLOAD_SCHEMA_VERSION = "1.1-solver-payload"

# Temporary decision source. TODO V1.2: replace with real solver/engine bridge.
V11_SOLVER_STUB_ENABLED = True
V11_SOLVER_STUB_DEFAULT_ACTION = "fold"      # fold / call / check / check_fold / bet_raise
V11_SOLVER_STUB_DEFAULT_SIZE_PCT = None       # 33 / 50 / 70 / 98 / None
V11_SOLVER_STUB_TIMEOUT_SEC = 8.0

ACTION_BUTTON_DETECTOR_ENABLED = True
ACTION_BUTTON_MODEL_PATH = Path(r"C:\PokerVision\AI_detect\Action_Button_Detector\weights")
ACTION_BUTTON_MODEL_FILE_NAME = "best.pt"
ACTION_BUTTON_DETECT_THRESHOLD = 0.65
ACTION_BUTTON_INFERENCE_CONF = 0.25
ACTION_BUTTON_INFERENCE_IOU = 0.45
ACTION_BUTTON_INFERENCE_IMGSZ = 832
ACTION_BUTTON_DEVICE = None

ACTION_BUTTON_CLASSES = [
    "FOLD",
    "33%",
    "50%",
    "70%",
    "98%",
    "Call",
    "Check/fold",
    "Check",
    "Bet/Raise",
]

# Action-button click branch. Final effective values may be overridden by
# V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE below.
V11_CLICK_STUB_ENABLED = True
V11_REAL_MOUSE_CLICK_ENABLED = True
V11_CLICK_DRY_RUN = False
V11_CLICK_REQUIRE_ACTIVE = True
V11_CLICK_REQUIRE_BUTTON_DETECTION = True
V11_CLICK_SLOT_GUARD_ENABLED = True
V11_CLICK_SAFE_INNER_BBOX_RATIO = 0.10
V11_CLICK_ANTI_REPEAT_SEC = 2.0

V11_RUNTIME_REPORT_ENABLED = False
V11_RUNTIME_REPORT_OUTPUT_DIR_NAME = "_runtime"

# Prepared for Stage 3 overlay. Stage 1 only fills the status model.
V11_OVERLAY_ENABLED = True
V11_OVERLAY_UPDATE_MS = 150
V11_OVERLAY_TOP_LEFT_X = 6
V11_OVERLAY_TOP_LEFT_Y = 6
V11_OVERLAY_WIDTH = 252
V11_OVERLAY_HEIGHT = 86
V11_OVERLAY_TRANSPARENT_BACKGROUND = True
V11_OVERLAY_TRANSPARENT_COLOR = "#010203"
V11_OVERLAY_TEXT_FONT_SIZE = 8
V11_OVERLAY_COLOR_COMPILE = "#22C55E"
V11_OVERLAY_COLOR_PROCESS = "#FACC15"
V11_OVERLAY_COLOR_WARNING = "#EF4444"
V11_OVERLAY_COLOR_IDLE = "#9CA3AF"




# =============================================================================
# 10.1. V1.1 TRIGGER UI SERVICE CLICK / DEATH CARD RANGE
# =============================================================================

# Separate dry-run service-click layer for Trigger_UI_Detector classes.
# This is NOT Action_Button_Detector and must run as an isolated runtime branch.
V11_TRIGGER_UI_SERVICE_CLICK_ENABLED = True
V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = True
V11_TRIGGER_UI_SERVICE_DRY_RUN = False

if V81_CONTROLLED_LIVE_READY_PROFILE_ACTIVE:
    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = False
    V11_TRIGGER_UI_SERVICE_DRY_RUN = True
V11_TRIGGER_UI_SERVICE_REQUIRE_BUTTON_DETECTION = True
V11_TRIGGER_UI_SERVICE_SLOT_GUARD_ENABLED = True
V11_TRIGGER_UI_SERVICE_SAFE_INNER_BBOX_RATIO = 0.10
V11_TRIGGER_UI_SERVICE_ANTI_REPEAT_SEC = 2.0

# Simple service classes from the left Trigger_UI chain.
# True_active_fold is terminal for the current frame.
V11_TRIGGER_UI_SERVICE_CLASSES = [
    "True_active_fold",
    "Remove_Game",
    "Exit_cashOut",
    "1_roll_board",
    "Bunny",
]

V11_BUNNY_CLICK_ENABLED = True
V11_BUNNY_CLICK_PROBABILITY = 0.30

# Non_active_fold branch: HERO cards -> Data_death_card -> fold/no-fold.
V11_NON_ACTIVE_FOLD_ENABLED = True
V11_DEATH_CARD_DIR = Path(r"C:\PokerVision\Data_death_card")
V11_DEATH_CARD_FILE_NAME = "data_death_card.json"
V11_DEATH_CARD_STRICT_ENABLED_REQUIRED = True

# Runtime-only report for Trigger_UI service-click branch.
V11_SERVICE_RUNTIME_REPORT_ENABLED = False
V11_SERVICE_RUNTIME_REPORT_SUFFIX = "service_click_report"




# =============================================================================
# 10.2. V1.2 LIVE DATA CAPTURE NO-CLICK OVERRIDE
# =============================================================================

if V12_LIVE_DATA_CAPTURE_NO_CLICK_MODE:
    # Hard runtime guard for live data validation. The UI may analyze real desktop
    # tables and save JSON, but it cannot execute real mouse clicks while this
    # mode is enabled.
    V11_REAL_MOUSE_CLICK_ENABLED = False
    V11_CLICK_DRY_RUN = True
    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = False
    V11_TRIGGER_UI_SERVICE_DRY_RUN = True

# =============================================================================
# 9. HELPERS
# =============================================================================

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_status(status: str) -> str:
    if status not in STATUS_VALUES:
        raise ValueError(f"Unknown status={status!r}. Allowed: {STATUS_VALUES}")
    return status


def safe_resolve(path: Path) -> Path:
    return path.resolve(strict=False)


def assert_path_inside(child_path: Path, parent_dir: Path) -> None:
    child = safe_resolve(child_path)
    parent = safe_resolve(parent_dir)

    try:
        child.relative_to(parent)
    except ValueError as exc:
        raise ValueError(
            f"Output path escaped parent dir. child={child}, parent={parent}"
        ) from exc


# =============================================================================
# V8.7 FULL LIVE CHAIN OVERRIDES
# =============================================================================
# Explicit opt-in mode:
#   POKERVISION_CONTROLLED_LIVE_TEST_SCOPE=V8_7_FULL_LIVE_CHAIN_NO_LIMIT
# Enables service real-click branch and removes max-click run limit.
# Slot/no-repeat/button guards remain enforced by runtime click layers.
if V87_FULL_LIVE_CHAIN_SCOPE_ACTIVE:
    V10_REAL_CLICK_REQUIRE_SERVICE_CLICKS_DISABLED = False

    V11_TRIGGER_UI_SERVICE_REAL_CLICK_ENABLED = True
    V11_TRIGGER_UI_SERVICE_DRY_RUN = False

    V31_CONTROLLED_LIVE_CLICK_ACTION_BUTTON_ONLY = False
    V31_CONTROLLED_LIVE_CLICK_SIMPLE_ACTIONS_ONLY = False
    V31_CONTROLLED_LIVE_CLICK_SERVICE_BRANCH_DISABLED = False
    V31_CONTROLLED_LIVE_CLICK_RAISE_BRANCH_ENABLED = True
    V31_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN = 0

    V31_CONTROLLED_LIVE_CLICK_ALLOWED_ACTIONS = ( "fold", "check", "call", "check_fold", "raise", "bet_raise", "open_raise", "iso_raise", "3bet", "4bet", "5bet", "jam", "all_in", )
    V31_CONTROLLED_LIVE_CLICK_ALLOWED_BUTTONS = ( "FOLD", "Check", "CALL", "Call", "Check/fold", "Raise", "Bet/Raise", "33%", "50%", "70%", "98%", )
