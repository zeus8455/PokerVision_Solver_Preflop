from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v226_live_no_click_probe_after_v225_v1"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("No JSON object found in subprocess stdout")


def _version_contains(project_root: Path, marker: str) -> bool:
    version_file = project_root / "VERSION.md"
    if not version_file.exists():
        return False
    return marker in version_file.read_text(encoding="utf-8", errors="replace")


def _run_v219_probe(project_root: Path) -> tuple[int, str, str, dict[str, Any]]:
    tool = project_root / "tools" / "run_v2_19_live_no_click_capture_probe.py"
    if not tool.exists():
        raise FileNotFoundError(f"Required V2.19 live no-click probe tool not found: {tool}")

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=180,
    )

    payload: dict[str, Any] = {}
    if proc.stdout.strip():
        payload = _extract_json_object(proc.stdout)

    return proc.returncode, proc.stdout, proc.stderr, payload


def build_report() -> dict[str, Any]:
    project_root = _project_root()
    snapshot_root = project_root / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

    returncode, stdout, stderr, v219 = _run_v219_probe(project_root)

    output_counts = v219.get("output_counts", {}) if isinstance(v219, dict) else {}
    saved_paths_count = int(v219.get("saved_paths_count") or 0)
    active_artifacts_count = saved_paths_count + sum(
        int(value or 0) for value in output_counts.values()
    )
    active_or_json_observed = active_artifacts_count > 0

    checks = {
        "v225_version_record_present": _version_contains(
            project_root,
            "V2.25.0 - real startup readiness after V2.24",
        ),
        "v219_tool_returncode_zero": returncode == 0,
        "v219_status_ok": v219.get("status") == "ok",
        "real_project_not_touched": v219.get("real_project_touched") is False,
        "live_cycle_executed": v219.get("live_cycle_executed") is True,
        "screen_capture_executed": v219.get("screen_capture_executed") is True,
        "yolo_detector_executed": v219.get("yolo_detector_executed") is True,
        "physical_click_not_executed": v219.get("physical_click_executed") is False,
        "current_cycle_restored_after_probe": v219.get("current_cycle_restored_after_probe") is True,
        "six_slots_available": v219.get("slots_total") == 6,
        "table_ids_detected": set(v219.get("opened_table_ids") or []) == {
            "table_01",
            "table_02",
            "table_03",
            "table_04",
            "table_05",
            "table_06",
        },
        "no_traceback": "Traceback" not in stdout and "Traceback" not in stderr,
    }

    report = {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(project_root),
        "snapshot_root": str(snapshot_root),
        "real_project_touched": v219.get("real_project_touched"),
        "live_cycle_executed": v219.get("live_cycle_executed"),
        "screen_capture_executed": v219.get("screen_capture_executed"),
        "yolo_detector_executed": v219.get("yolo_detector_executed"),
        "physical_click_executed": v219.get("physical_click_executed"),
        "current_cycle_restored_after_probe": v219.get("current_cycle_restored_after_probe"),
        "slots_total": v219.get("slots_total"),
        "opened_table_ids": v219.get("opened_table_ids"),
        "saved_paths_count": saved_paths_count,
        "output_counts": output_counts,
        "active_or_json_observed": active_or_json_observed,
        "solver_live_chain_validated": False,
        "solver_live_chain_validation_reason": (
            "active_or_json_artifacts_observed_but_v219_probe_does_not_validate_solver_bridge"
            if active_or_json_observed
            else "no_active_or_json_artifacts_observed_in_this_probe"
        ),
        "v226_scope": "safe_live_no_click_probe_only",
        "checks": checks,
        "v219_schema": v219.get("schema"),
        "v219_returncode": returncode,
        "stderr": stderr.strip(),
    }
    return report


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
