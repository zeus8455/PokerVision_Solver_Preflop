r"""
runtime/trigger_ui_service_policy.py

PokerVision Core V1.1 — policy for Trigger_UI service-click branch.

This is separate from Action_Button_Detector. It handles service classes detected
by Trigger_UI_Detector before/around the Active branch.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from config import V11_BUNNY_CLICK_ENABLED, V11_BUNNY_CLICK_PROBABILITY

# Only classes from this list may create a click plan.
# Important:
# - Remove_Table is hard-disabled. It must not plan/click, must not become detected_only,
#   and must not affect service/action branch selection.
# - True_active_fold is also detect-only: it confirms that Non_active_fold has already
#   been pressed by the poker client. It must never plan/click.
SERVICE_CLICK_PRIORITY: List[str] = [

    "Remove_Game",
    "Exit_cashOut",
    "1_roll_board",
    "Non_active_fold",
    "Bunny",
]

# Hard-disabled service classes are ignored completely by the service-click runtime.
DISABLED_SERVICE_CLASSES = {"Remove_Table"}

# Detect-only service classes are still reported, but never clicked.
DETECTED_ONLY_SERVICE_CLASSES = {"True_active_fold"}

# True_active_fold is terminal because it confirms a fold state and should stop
# the current frame from going into solver/action-button runtime.
TERMINAL_DETECTED_ONLY_SERVICE_CLASSES = {"True_active_fold"}

SIMPLE_SERVICE_CLASSES = {"Remove_Game", "Exit_cashOut", "1_roll_board"}


def is_disabled_service_class(class_name: str) -> bool:
    return class_name in DISABLED_SERVICE_CLASSES


def is_terminal_service_class(class_name: str) -> bool:
    return class_name in TERMINAL_DETECTED_ONLY_SERVICE_CLASSES


def is_detected_only_service_class(class_name: str) -> bool:
    return class_name in DETECTED_ONLY_SERVICE_CLASSES


def is_simple_service_class(class_name: str) -> bool:
    return class_name in SIMPLE_SERVICE_CLASSES


def is_bunny_service_enabled() -> bool:
    return bool(V11_BUNNY_CLICK_ENABLED) and float(V11_BUNNY_CLICK_PROBABILITY) > 0.0


def describe_service_class(class_name: str) -> str:
    descriptions: Dict[str, str] = {
        "True_active_fold": "Detect-only confirmation class: Non_active_fold has already been pressed; never click this class.",
        "Remove_Table": "Hard-disabled class: ignored by service-click runtime; never plan/click/detected-only.",
        "Remove_Game": "Service class for removing/changing game state.",
        "Exit_cashOut": "Service class for closing cashout/exit overlay.",
        "1_roll_board": "Service class for rolling board once.",
        "Non_active_fold": "Non-active fold branch; requires HERO cards and Data_death_card match.",
        "Bunny": "Optional click with configured probability.",
    }
    return descriptions.get(class_name, "Unknown Trigger_UI service class.")


def first_detected_service_class(best_by_class: Dict[str, Dict[str, object]]) -> Optional[str]:
    """Return the first actionable service class that may create a click plan."""
    for class_name in SERVICE_CLICK_PRIORITY:
        if class_name in DISABLED_SERVICE_CLASSES:
            continue
        if class_name in best_by_class:
            return class_name
    return None


def detected_only_service_classes(best_by_class: Dict[str, Dict[str, object]]) -> List[str]:
    return [
        class_name
        for class_name in sorted(DETECTED_ONLY_SERVICE_CLASSES)
        if class_name not in DISABLED_SERVICE_CLASSES and class_name in best_by_class
    ]
