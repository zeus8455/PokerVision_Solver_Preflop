from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
EXAMPLE_CLEAR_JSON = PROJECT_ROOT / "examples" / "clear_json" / "table_02_hand_29_preflop_01_preclick.json"
OUT_DIR = PROJECT_ROOT / "tmp_preintegration_outputs"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    report: dict = {
        "schema": "pokervision_solver_preflop_preintegration_report_v1",
        "project_root": str(PROJECT_ROOT),
        "checks": {},
    }

    # Important:
    # Do not run the preintegration test from inside the preintegration tool.
    # Otherwise pytest -> test_preintegration -> tool -> pytest -> test_preintegration
    # becomes recursive and may hang.
    pytest_result = _run([PYTHON, "-m", "pytest", "-k", "not preintegration"])
    report["checks"]["pytest"] = {
        "ok": True,
        "command": f"{PYTHON} -m pytest -k \"not preintegration\"",
        "stdout_tail": pytest_result.stdout.splitlines()[-8:],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*"):
        if old.is_file():
            old.unlink()

    cli_result = _run([
        PYTHON,
        "tools/solve_clear_json.py",
        str(EXAMPLE_CLEAR_JSON),
        "--write-files",
        "--out-dir",
        str(OUT_DIR),
    ])
    cli_payload = json.loads(cli_result.stdout)
    files = cli_payload["manifest"]["files"]

    required_keys = {
        "solver_decision_json",
        "solver_action_decision_json",
        "solver_runtime_hint_json",
        "pokervision_bridge_json",
    }
    missing_keys = sorted(required_keys - set(files))
    if missing_keys:
        raise AssertionError(f"Missing manifest keys: {missing_keys}")

    missing_files = [path for path in files.values() if not Path(path).exists()]
    if missing_files:
        raise AssertionError(f"Manifest points to missing files: {missing_files}")

    bridge = _load_json(Path(files["pokervision_bridge_json"]))
    plan = bridge["runtime_plan_candidate"]
    safety = bridge["safety"]

    required_true_flags = [
        "real_click_must_be_guarded",
        "requires_active_guard",
        "requires_slot_roi_guard",
        "requires_no_repeat_guard",
        "requires_button_availability_guard",
    ]
    failed_flags = [flag for flag in required_true_flags if plan.get(flag) is not True]
    if failed_flags:
        raise AssertionError(f"Bridge plan is missing required guard flags: {failed_flags}")

    if safety.get("must_not_execute_directly") is not True:
        raise AssertionError("Bridge safety.must_not_execute_directly must be true")

    report["checks"]["cli_write_files"] = {
        "ok": True,
        "status": cli_payload["status"],
        "source_frame_id": cli_payload["source_frame_id"],
        "decision_id": cli_payload["decision_id"],
        "files": files,
    }
    report["checks"]["bridge_guard_contract"] = {
        "ok": True,
        "schema": bridge["schema"],
        "runtime_plan_schema": plan["schema"],
        "button_sequence": plan["button_sequence"],
        "safety": safety,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
