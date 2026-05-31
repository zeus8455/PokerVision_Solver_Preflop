from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = PROJECT_ROOT / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

for path in (PROJECT_ROOT, SNAPSHOT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import config
from runtime import trigger_ui_service_policy as policy


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", default="outputs/v2_50_remove_game_service_policy_audit.json")
    args = parser.parse_args()

    remove_table_only = {"Remove_Table": {"bbox_xyxy": [100, 100, 180, 150], "confidence": 0.99}}
    remove_game_only = {"Remove_Game": {"bbox_xyxy": [100, 100, 180, 150], "confidence": 0.99}}
    both = {
        "Remove_Table": {"bbox_xyxy": [100, 100, 180, 150], "confidence": 0.99},
        "Remove_Game": {"bbox_xyxy": [200, 100, 280, 150], "confidence": 0.99},
    }

    checks = {}
    checks["remove_table_not_in_runtime_service_config"] = "Remove_Table" not in list(getattr(config, "V11_TRIGGER_UI_SERVICE_CLASSES", []))
    checks["remove_table_not_in_service_priority"] = "Remove_Table" not in list(policy.SERVICE_CLICK_PRIORITY)
    checks["remove_table_hard_disabled_set"] = "Remove_Table" in set(getattr(policy, "DISABLED_SERVICE_CLASSES", set()))
    checks["remove_table_not_detected_only"] = "Remove_Table" not in set(policy.DETECTED_ONLY_SERVICE_CLASSES)
    checks["remove_table_not_terminal"] = "Remove_Table" not in set(policy.TERMINAL_DETECTED_ONLY_SERVICE_CLASSES)
    checks["remove_table_only_no_actionable_target"] = policy.first_detected_service_class(remove_table_only) is None
    checks["remove_table_only_no_detected_only"] = policy.detected_only_service_classes(remove_table_only) == []
    checks["remove_game_first_priority"] = list(policy.SERVICE_CLICK_PRIORITY)[0] == "Remove_Game"
    checks["remove_game_is_simple_service"] = policy.is_simple_service_class("Remove_Game") is True
    checks["remove_game_only_actionable"] = policy.first_detected_service_class(remove_game_only) == "Remove_Game"
    checks["remove_game_wins_over_remove_table"] = policy.first_detected_service_class(both) == "Remove_Game"
    description = policy.describe_service_class("Remove_Table")
    checks["remove_table_description_hard_disabled"] = "Hard-disabled" in description or "ignored" in description.lower()

    report = {
        "schema": "v2_50_remove_game_service_policy_audit_v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": {
            "service_priority": list(policy.SERVICE_CLICK_PRIORITY),
            "disabled_service_classes": sorted(list(getattr(policy, "DISABLED_SERVICE_CLASSES", set()))),
            "detected_only_service_classes": sorted(list(policy.DETECTED_ONLY_SERVICE_CLASSES)),
            "runtime_service_config": list(getattr(config, "V11_TRIGGER_UI_SERVICE_CLASSES", [])),
            "remove_table_description": description,
            "remove_game_description": policy.describe_service_class("Remove_Game"),
        },
    }

    print("V2.50 REMOVE_GAME SERVICE POLICY AUDIT")
    for key, value in checks.items():
        print(f"{key:58} {value}")
    print("-" * 100)
    print(f"V2.50_REMOVE_GAME_SERVICE_POLICY_AUDIT_OK = {report['ok']}")

    out = Path(args.report_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
