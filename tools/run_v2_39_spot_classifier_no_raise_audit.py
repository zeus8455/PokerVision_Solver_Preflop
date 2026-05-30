from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "v2_39_spot_classifier_no_raise" / "cases.json"


RANGE_DATA: dict[str, Any] = {
    "defaults": {
        "unopened": "fold",
        "sb_first_in": "fold",
        "bb_vs_sb_limp": "check",
        "bb_option_vs_limp": "check",
        "bb_unopened_option_no_raise": "check",
        "iso_vs_limp": "fold",
        "facing_open": "fold",
        "blind_vs_open": "fold",
        "opener_vs_3bet": "fold",
        "threebettor_vs_4bet": "fold",
        "cold_vs_3bet_or_higher": "fold",
    },
    "nodes": {
        "rfi": {
            "CO": {"open_raise": "AKo,AKs"},
            "BTN": {"open_raise": "AKo,AKs"},
            "SB": {"open_raise": "AKo,AKs"},
        },
        "sb_first_in": {
            "SB": {"open_raise": "AKo,AKs"},
        },
        "bb_vs_sb_limp": {
            "BB": {"iso_raise": "AKo,AKs"},
        },
        "iso_raise": {
            "BTN": {"iso_raise": "AKo,AKs"},
            "SB": {"iso_raise": "AKo,AKs"},
            "BB": {"iso_raise": "AKo,AKs"},
        },
        "vs_open": {
            "BTN|BB": {"3bet": "AKo,AKs", "call": "88+"},
            "UTG|BTN": {"3bet": "AKo,AKs", "call": "88+"},
        },
        "opener_vs_3bet": {
            "CO|BTN": {"4bet": "AKo,AKs", "call": "QQ+"},
        },
        "threebettor_vs_4bet": {
            "BTN|CO": {"5bet_jam": "AKo,AKs"},
        },
        "cold_4bet": {
            "UTG|CO|SB": {"4bet": "AKs"},
        },
    },
}


def _import_solver_modules():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from solver_preflop.cards import hand_to_class
    from solver_preflop.clear_json_adapter import parse_clear_json_preflop
    from solver_preflop.range_engine import decide_preflop_action_from_ranges
    from solver_preflop.sizing_policy import click_sequence_for_action, size_pct_for_action
    from solver_preflop.spot_classifier import classify_preflop_spot

    return {
        "hand_to_class": hand_to_class,
        "parse_clear_json_preflop": parse_clear_json_preflop,
        "classify_preflop_spot": classify_preflop_spot,
        "decide_preflop_action_from_ranges": decide_preflop_action_from_ranges,
        "click_sequence_for_action": click_sequence_for_action,
        "size_pct_for_action": size_pct_for_action,
    }


def _load_cases() -> list[dict[str, Any]]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"No cases in {FIXTURE_PATH}")
    return cases


def run_audit() -> dict[str, Any]:
    modules = _import_solver_modules()
    results: list[dict[str, Any]] = []

    for case in _load_cases():
        frame = modules["parse_clear_json_preflop"](case["clear_json"])
        spot = modules["classify_preflop_spot"](frame)
        hand_class = modules["hand_to_class"](frame.hero_cards)
        range_decision = modules["decide_preflop_action_from_ranges"](
            hand_class=hand_class,
            spot=spot,
            range_data=RANGE_DATA,
        )
        click_sequence = modules["click_sequence_for_action"](range_decision.action)
        size_pct = modules["size_pct_for_action"](range_decision.action)

        checks = {
            "node_type_ok": spot.node_type == case["expected_node_type"],
            "action_ok": range_decision.action == case["expected_action"],
            "to_call_ok": abs(float(spot.to_call_bb) - float(case["expected_to_call_bb"])) < 1e-9,
            "no_unknown_ok": (not case.get("expect_no_unknown")) or ("unknown" not in spot.node_type),
            "not_safe_fallback_ok": range_decision.action != "safe_fallback",
            "click_sequence_available_ok": bool(click_sequence),
        }
        ok = all(checks.values())

        results.append(
            {
                "case_id": case["case_id"],
                "hero_position": frame.hero_position,
                "hero_hand": frame.hero_cards,
                "hand_class": hand_class,
                "node_type": spot.node_type,
                "expected_node_type": case["expected_node_type"],
                "raw_action": range_decision.action,
                "expected_action": case["expected_action"],
                "range_source": range_decision.source,
                "fallback_used": range_decision.fallback_used,
                "to_call_bb": spot.to_call_bb,
                "expected_to_call_bb": case["expected_to_call_bb"],
                "max_commitment_bb": spot.max_commitment_bb,
                "hero_commitment_bb": spot.hero_commitment_bb,
                "limpers": list(spot.limpers),
                "opener_pos": spot.opener_pos,
                "three_bettor_pos": spot.three_bettor_pos,
                "four_bettor_pos": spot.four_bettor_pos,
                "last_aggressor_pos": spot.last_aggressor_pos,
                "click_sequence": click_sequence,
                "size_pct": size_pct,
                "notes": list(spot.notes) + list(range_decision.notes),
                "checks": checks,
                "ok": ok,
            }
        )

    return {
        "schema_version": "v2_39_spot_classifier_no_raise_audit_report_v1",
        "ok": all(item["ok"] for item in results),
        "project_root": str(ROOT),
        "real_project_touched": False,
        "full_live_ui_executed": False,
        "screen_capture_executed": False,
        "yolo_detector_executed": False,
        "physical_click_executed": False,
        "results": results,
    }


def _print_report(report: dict[str, Any]) -> None:
    print("V2.39 SPOT CLASSIFIER / NO-RAISE FALLBACK AUDIT")
    print(f"{'CASE':42} {'NODE':32} {'ACTION':12} {'TO_CALL':8} {'OK'}")
    print("-" * 112)
    for item in report["results"]:
        print(
            f"{item['case_id'][:42]:42} "
            f"{item['node_type'][:32]:32} "
            f"{item['raw_action'][:12]:12} "
            f"{str(item['to_call_bb'])[:8]:8} "
            f"{item['ok']}"
        )
        if not item["ok"]:
            print("  checks:", item["checks"])
            print("  notes:", item["notes"])
    print("-" * 112)
    print(f"V2.39_SPOT_CLASSIFIER_NO_RAISE_AUDIT_OK = {report['ok']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default=None)
    args = parser.parse_args()

    report = run_audit()
    _print_report(report)

    if args.report_json:
        path = Path(args.report_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report_json={path}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
