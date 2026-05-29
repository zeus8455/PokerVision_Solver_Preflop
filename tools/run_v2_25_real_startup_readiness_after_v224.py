from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA = "pokervision_solver_preflop_v225_real_startup_readiness_after_v224_v1"


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


def _run_v220_readiness(project_root: Path) -> tuple[int, str, str, dict[str, Any]]:
    tool = project_root / "tools" / "run_v2_20_real_live_startup_readiness.py"
    if not tool.exists():
        raise FileNotFoundError(f"Required V2.20 readiness tool not found: {tool}")

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=90,
    )

    payload: dict[str, Any] = {}
    if proc.stdout.strip():
        payload = _extract_json_object(proc.stdout)

    return proc.returncode, proc.stdout, proc.stderr, payload


def _version_contains_v224(project_root: Path) -> bool:
    version_file = project_root / "VERSION.md"
    if not version_file.exists():
        return False
    return "V2.24.0 - snapshot live-runtime E2E" in version_file.read_text(
        encoding="utf-8",
        errors="replace",
    )


def build_report() -> dict[str, Any]:
    project_root = _project_root()
    snapshot_root = project_root / "external" / "PokerVisionFinalVersionNoSolver_snapshot" / "PokerVision V1_2"

    returncode, stdout, stderr, v220 = _run_v220_readiness(project_root)

    v220_checks = v220.get("checks", {}) if isinstance(v220, dict) else {}
    env = v220.get("env", {}) if isinstance(v220, dict) else {}
    stdout_tail = v220.get("stdout_tail", []) if isinstance(v220, dict) else []

    checks = {
        "v224_version_record_present": _version_contains_v224(project_root),
        "v220_tool_returncode_zero": returncode == 0,
        "v220_status_ok": v220.get("status") == "ok",
        "v220_real_click_ready_true": v220.get("real_click_ready") is True,
        "real_project_not_touched": v220.get("real_project_touched") is False,
        "live_ui_not_launched": v220.get("live_ui_launched") is False,
        "screen_capture_not_executed": v220.get("screen_capture_executed") is False,
        "yolo_detector_not_executed": v220.get("yolo_detector_executed") is False,
        "physical_click_not_executed": v220.get("physical_click_executed") is False,
        "no_click_mode_disabled": v220_checks.get("no_click_mode_disabled") is True,
        "master_armed": v220_checks.get("master_armed") is True,
        "action_real_click_enabled": v220_checks.get("action_real_click_enabled") is True,
        "service_real_click_enabled": v220_checks.get("service_real_click_enabled") is True,
        "readiness_ready": v220_checks.get("readiness_ready") is True,
        "startup_audit_only": v220_checks.get("startup_audit_only") is True,
        "max_clicks_zero": env.get("POKERVISION_CONTROLLED_LIVE_CLICK_MAX_CLICKS_PER_RUN") == "0",
        "startup_readiness_line_present": any(
            "[V10_REAL_CLICK_READINESS] status=ready_for_controlled_real_click ok=True real_click_ready=True" in str(line)
            for line in stdout_tail
        ),
        "startup_audit_skip_line_present": any(
            "[V83_STARTUP_AUDIT_ONLY] live UI launch skipped" in str(line)
            for line in stdout_tail
        ),
        "no_traceback": "Traceback" not in stdout and "Traceback" not in stderr,
    }

    report = {
        "schema": SCHEMA,
        "status": "ok" if all(checks.values()) else "failed",
        "project_root": str(project_root),
        "snapshot_root": str(snapshot_root),
        "real_project_touched": v220.get("real_project_touched"),
        "live_ui_launched": v220.get("live_ui_launched"),
        "screen_capture_executed": v220.get("screen_capture_executed"),
        "yolo_detector_executed": v220.get("yolo_detector_executed"),
        "physical_click_executed": v220.get("physical_click_executed"),
        "real_click_ready": v220.get("real_click_ready"),
        "checks": checks,
        "v220_schema": v220.get("schema"),
        "v220_returncode": returncode,
        "v220_stdout_tail": stdout_tail,
        "stderr": stderr.strip(),
    }
    return report


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
