from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.run_v2_42_full_preflop_spot_matrix_e2e import run_matrix


TARGETS = {
    "caller_vs_3bet_or_higher_btn_88": "caller_vs_3bet_or_higher",
    "facing_5bet_jam_fourbettor_kk": "fourbettor_vs_small_5bet_jam",
    "call_vs_5bet_jam_aa": "fourbettor_vs_small_5bet_jam",
    "fold_vs_5bet_jam_72o": "fourbettor_vs_small_5bet_jam",
    "fourbet_jam_threebettor_vs": "threebettor_vs_4bet_jam",
    "fivebet_jam_fourbettor_vs": "fourbettor_vs_small_5bet_jam",
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_43_allin_semantic_cleanup_audit.json")
    args = parser.parse_args()

    matrix = run_matrix()
    by_id = {r["case_id"]: r for r in matrix["results"]}

    focused = []
    checks = {
        "matrix_ok": matrix["ok"] is True,
        "runtime_chain_ok": matrix["runtime_chain_ok"] is True,
        "semantic_exact_ok": matrix["semantic_exact_ok"] is True,
        "known_semantic_gaps_zero": matrix["known_semantic_gaps_total"] == 0,
        "unexpected_semantic_failed_zero": matrix["unexpected_semantic_failed_total"] == 0,
    }

    for case_id, expected_node in TARGETS.items():
        item = by_id.get(case_id)
        actual = item.get("actual_node_type") if item else None
        raw = item.get("actual_raw_action") if item else None
        ok = bool(item and actual == expected_node and item.get("runtime_chain_ok") is True)
        checks[f"{case_id}_node_ok"] = ok
        focused.append({
            "case_id": case_id,
            "expected_node": expected_node,
            "actual_node": actual,
            "raw_action": raw,
            "planned_action": item.get("planned_action") if item else None,
            "target_sequence": item.get("target_sequence") if item else None,
            "runtime_chain_ok": item.get("runtime_chain_ok") if item else None,
            "ok": ok,
        })

    report = {
        "schema": "v2_43_allin_semantic_cleanup_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "focused_cases": focused,
        "matrix_summary": {
            "cases_total": matrix["cases_total"],
            "cases_ok": matrix["cases_ok"],
            "cases_failed": matrix["cases_failed"],
            "runtime_chain_ok": matrix["runtime_chain_ok"],
            "semantic_exact_ok": matrix["semantic_exact_ok"],
            "known_semantic_gaps_total": matrix["known_semantic_gaps_total"],
            "unexpected_semantic_failed_total": matrix["unexpected_semantic_failed_total"],
        },
    }

    print("V2.43 ALL-IN / HIGH-ORDER SEMANTIC CLEANUP AUDIT")
    for item in focused:
        print(
            f"{item['case_id']:40} expected={item['expected_node']:34} "
            f"actual={str(item['actual_node']):34} raw={str(item['raw_action']):14} "
            f"plan={str(item['planned_action']):10} ok={item['ok']}"
        )
    print("-" * 120)
    print(f"V2.43_ALLIN_SEMANTIC_CLEANUP_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
