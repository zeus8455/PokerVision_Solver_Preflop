r"""
logic/trigger_ui_policy.py

PokerVision Core V0.3 — политика классов Trigger_UI_Detector.

Этот файл НЕ запускает YOLO-модель и НЕ выполняет клики.
Его задача — быть единственным местом, где описано:
- что означает каждый класс Trigger_UI_Detector;
- что V0.3 должна записывать в JSON;
- можно ли в будущем рассматривать класс как кандидат для клика;
- запускает ли класс следующий stage pipeline.

Почему это вынесено отдельно:
Если писать правила классов прямо в detector/pipeline/display_analysis_cycle,
то код быстро смешает разные ответственности:
1) inference модели,
2) нормализацию confidence,
3) правила кликов,
4) запуск следующих stage,
5) JSON-контракт.

В V0.3 мы намеренно держим Trigger UI изолированным:
- клики НЕ выполняются;
- Table_Seat_BoardPot_Detector НЕ запускается;
- Action_Button_Detector НЕ запускается;
- solver НЕ запускается;
- все click-related поля являются только future intent.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class TriggerUIClassPolicy(TypedDict):
    meaning: str
    v03_action: str
    future_click_allowed: bool
    future_click_action_hint: Optional[str]
    allow_structure_pipeline_in_v03: bool
    next_stage_hint_if_confirmed: Optional[str]


TRIGGER_UI_CLASS_ORDER: List[str] = [
    "Active",
    "Remove_Table",
    "Remove_Game",
    "Exit_cashOut",
    "Bunny",
    "Non_active_fold",
    "True_active_fold",
    "1_roll_board",
]


# -----------------------------------------------------------------------------
# V0.3 IMPORTANT:
# Политика ниже специально запрещает реальные клики.
# Даже если future_click_allowed=True, это НЕ значит, что V0.3 будет кликать.
# Это только документация будущего намерения для отдельного click-runtime.
# Реальный click в будущем должен пройти:
# 1) config-флаг click_execution_enabled=True;
# 2) confirmed=True по классу;
# 3) slot_bbox guard;
# 4) local ROI bbox -> global monitor coords mapping;
# 5) anti-repeat protection;
# 6) отдельную click-policy.
# -----------------------------------------------------------------------------
TRIGGER_UI_POLICY: Dict[str, TriggerUIClassPolicy] = {
    "Remove_Table": {
        "meaning": "Служебная кнопка смены/закрытия/удаления стола.",
        "v03_action": "Hard-disabled: ignore for click/runtime policy. Do not plan or execute clicks.",
        "future_click_allowed": False,
        "future_click_action_hint": None,
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "Remove_Game": {
        "meaning": "Служебная кнопка возврата/изменения состояния игры.",
        "v03_action": "Записать detect/confirmed/confidence в JSON. Клик не выполнять.",
        "future_click_allowed": True,
        "future_click_action_hint": "future: safe click only inside slot_bbox after dedicated guard",
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "Exit_cashOut": {
        "meaning": "Кнопка закрытия cashout/служебного окна.",
        "v03_action": "Записать detect/confirmed/confidence в JSON. Клик не выполнять.",
        "future_click_allowed": True,
        "future_click_action_hint": "future: close cashout only after slot_bbox guard and one-shot protection",
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "1_roll_board": {
        "meaning": "Отдельное техническое состояние/кнопка одной прокрутки board.",
        "v03_action": "Записать отдельным ключом JSON. Не смешивать с Bunny. Клик не выполнять.",
        "future_click_allowed": True,
        "future_click_action_hint": "future: separate board interaction branch; do not merge with Bunny",
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "Bunny": {
        "meaning": "Отдельное техническое UI-состояние Bunny.",
        "v03_action": "Записать отдельным ключом JSON. Не считать это 1_roll_board. Клик не выполнять.",
        "future_click_allowed": True,
        "future_click_action_hint": "future: click only if class confirmed and explicit click-policy enabled",
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "Non_active_fold": {
        "meaning": "Fold-состояние/кнопка без активного хода HERO.",
        "v03_action": "Записать в JSON. НЕ запускать Table_Seat_BoardPot_Detector в V0.3.",
        "future_click_allowed": False,
        "future_click_action_hint": None,
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "True_active_fold": {
        "meaning": "Активное fold-состояние, связанное с действием HERO.",
        "v03_action": "Записать в JSON. Клик не выполнять. Action_Button_Detector не запускать.",
        "future_click_allowed": True,
        "future_click_action_hint": "future: participate in Action_Button/Autoclick guard only after decision layer",
        "allow_structure_pipeline_in_v03": False,
        "next_stage_hint_if_confirmed": None,
    },
    "Active": {
        "meaning": "Главный положительный триггер: HERO сейчас должен принять решение.",
        "v03_action": "Если confirmed=True, выставить table.status=ready_for_structure_pipeline. Structure model пока не запускать.",
        "future_click_allowed": False,
        "future_click_action_hint": None,
        "allow_structure_pipeline_in_v03": True,
        "next_stage_hint_if_confirmed": "ready_for_structure_pipeline",
    },
}


def get_trigger_ui_policy(class_name: str) -> TriggerUIClassPolicy:
    """
    Вернуть политику класса Trigger_UI_Detector.

    Если модель вернула неизвестный класс, это не должно ломать pipeline.
    Такой класс будет сохранён только в warnings/debug, но clean JSON V0.3
    строится по фиксированному списку известных классов.
    """
    if class_name not in TRIGGER_UI_POLICY:
        raise KeyError(f"Unknown Trigger_UI_Detector class: {class_name!r}")
    return TRIGGER_UI_POLICY[class_name]


def is_known_trigger_ui_class(class_name: str) -> bool:
    return class_name in TRIGGER_UI_POLICY
