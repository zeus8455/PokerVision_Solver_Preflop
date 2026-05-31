from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

for path in (PROJECT_ROOT, SNAPSHOT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from logic.premium_fold_guard import evaluate_premium_fold_guard
import runtime.action_click_stub as click_stub
from runtime.action_click_stub import build_and_maybe_execute_click_plan


@dataclass
class FakeSlot:
    x1: int = 100
    y1: int = 100
    x2: int = 900
    y2: int = 700

    @property
    def bbox(self) -> "FakeSlot":
        return self


def _button(cls: str, x: int) -> dict[str, Any]:
    return {"class_name": cls, "bbox_xyxy": [x, 520, x + 110, 570], "confidence": 0.99}


def _action_buttons(*classes: str) -> dict[str, Any]:
    best = {cls: _button(cls, 100 + i * 130) for i, cls in enumerate(classes)}
    return {"best_by_class": best, "detected_classes": list(classes)}


def _decision(
    *,
    case_id: str,
    cards: list[str],
    hand_class: str | None,
    action: str = "fold",
    raw_action: str = "safe_fallback",
    engine_action: str = "fold",
    node_type: str = "hero_is_current_aggressor_no_decision",
    reason: str = "Range engine unsupported/unsafe node: hero_is_current_aggressor_no_decision; V2.41 runtime fallback action=fold",
    safe_fallback_used: bool = True,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "source": "PokerVision_Solver_Preflop",
        "decision_id": f"v244_{case_id}",
        "table_id": "table_01",
        "hand_id": "hand_v244",
        "frame_name": case_id,
        "action": action,
        "raw_action": raw_action,
        "engine_action": engine_action,
        "solver_raw_action": raw_action,
        "solver_engine_action": engine_action,
        "size_pct": None,
        "hero_hand": cards,
        "hand_class": hand_class,
        "node_type": node_type,
        "safe_fallback_used": safe_fallback_used,
        "reason": reason,
        "source_frame_id": case_id,
        "click_sequence": ["FOLD"] if action == "fold" else ["Raise"],
        "solver_fingerprint": f"fp_{case_id}",
    }


def _run_click(decision: dict[str, Any], buttons: dict[str, Any]) -> dict[str, Any]:
    old_dry = click_stub.V11_CLICK_DRY_RUN
    old_real = click_stub.V11_REAL_MOUSE_CLICK_ENABLED
    try:
        click_stub.V11_CLICK_DRY_RUN = True
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = False
        return build_and_maybe_execute_click_plan(
            solver_decision=decision,
            action_button_result=buttons,
            slot=FakeSlot(),
            active_confirmed=True,
        )
    finally:
        click_stub.V11_CLICK_DRY_RUN = old_dry
        click_stub.V11_REAL_MOUSE_CLICK_ENABLED = old_real


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_44_premium_fold_guard_e2e.json")
    args = parser.parse_args()

    cases: list[dict[str, Any]] = []

    def add(case_id: str, decision: dict[str, Any], buttons: dict[str, Any], expected_status: str, expected_sequence: list[str] | None, guard_active: bool) -> None:
        click = _run_click(decision, buttons)
        actual_seq = list(click.get("target_sequence") or [])
        ok = (
            click.get("status") == expected_status
            and bool((click.get("premium_fold_guard") or {}).get("active")) == guard_active
            and (expected_sequence is None or actual_seq == expected_sequence)
            and ("FOLD" not in actual_seq if guard_active else True)
        )
        cases.append(
            {
                "case_id": case_id,
                "ok": ok,
                "expected_status": expected_status,
                "actual_status": click.get("status"),
                "expected_sequence": expected_sequence,
                "actual_sequence": actual_seq,
                "guard_active": bool((click.get("premium_fold_guard") or {}).get("active")),
                "message": click.get("message"),
                "premium_fold_guard": click.get("premium_fold_guard"),
                "click_result": click,
            }
        )

    add(
        "kk_safe_fallback_fold_raise_visible",
        _decision(case_id="kk_raise", cards=["K_spades", "K_diamonds"], hand_class="KK"),
        _action_buttons("FOLD", "Bet/Raise", "Call"),
        "dry_run",
        ["Bet/Raise"],
        True,
    )
    add(
        "kk_safe_fallback_fold_call_fallback",
        _decision(case_id="kk_call", cards=["K_spades", "K_diamonds"], hand_class="KK"),
        _action_buttons("FOLD", "Call"),
        "dry_run",
        ["Call"],
        True,
    )
    add(
        "kk_safe_fallback_fold_only_fold_blocks",
        _decision(case_id="kk_block", cards=["K_spades", "K_diamonds"], hand_class="KK"),
        _action_buttons("FOLD"),
        "blocked",
        None,
        True,
    )
    add(
        "aa_unknown_no_decision_raise_visible",
        _decision(case_id="aa_raise", cards=["A_hearts", "A_clubs"], hand_class="AA", node_type="unknown_no_raise_preflop_spot"),
        _action_buttons("FOLD", "Bet/Raise"),
        "dry_run",
        ["Bet/Raise"],
        True,
    )
    add(
        "qq_fallback_call_visible",
        _decision(case_id="qq_call", cards=["Q_hearts", "Q_clubs"], hand_class="QQ"),
        _action_buttons("FOLD", "Call"),
        "dry_run",
        ["Call"],
        True,
    )
    add(
        "weak_72o_safe_fallback_still_folds",
        _decision(case_id="weak_fold", cards=["7_clubs", "2_diamonds"], hand_class="72o"),
        _action_buttons("FOLD", "Bet/Raise", "Call"),
        "dry_run",
        ["FOLD"],
        False,
    )
    add(
        "kk_clean_raise_not_interfered",
        _decision(
            case_id="kk_clean_raise",
            cards=["K_spades", "K_diamonds"],
            hand_class="KK",
            action="bet_raise",
            raw_action="open_raise",
            engine_action="raise",
            node_type="unopened",
            reason="range:unopened.SB:first_in_raise",
            safe_fallback_used=False,
        ),
        _action_buttons("Bet/Raise", "FOLD"),
        "dry_run",
        ["Bet/Raise"],
        False,
    )

    report = {
        "schema": "v2_44_premium_fold_guard_e2e_report_v1",
        "ok": all(c["ok"] for c in cases),
        "cases_total": len(cases),
        "cases_ok": sum(1 for c in cases if c["ok"]),
        "cases_failed": sum(1 for c in cases if not c["ok"]),
        "cases": cases,
    }

    print("V2.44 PREMIUM FOLD GUARD E2E")
    print(f"cases_total={report['cases_total']} cases_ok={report['cases_ok']} cases_failed={report['cases_failed']}")
    print("-" * 120)
    for c in cases:
        print(
            f"{c['case_id']:42} status={str(c['actual_status']):8} "
            f"seq={c['actual_sequence']} guard={c['guard_active']} ok={c['ok']}"
        )
        if not c["ok"]:
            print(f"  message={c['message']}")
            print(f"  guard={c['premium_fold_guard']}")
    print("-" * 120)
    print(f"V2.44_PREMIUM_FOLD_GUARD_E2E_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
