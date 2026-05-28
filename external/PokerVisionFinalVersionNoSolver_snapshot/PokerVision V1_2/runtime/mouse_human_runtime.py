r"""
runtime/mouse_human_runtime.py

PokerVision Core V1.2 — human-like mouse execution helpers.

Current V1.2.1 behavior:
- no mouse "static for 3 sec" takeover wait;
- no pre-click twitching/wiggle after idle wait;
- movement follows a curved cubic Bezier path with light low-frequency drift;
- caller-side slot guard still decides whether a click is allowed.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, Iterable, List, Tuple

from config import (
    V12_MOUSE_BETWEEN_CLICKS_MAX_SEC,
    V12_MOUSE_BETWEEN_CLICKS_MIN_SEC,
    V12_MOUSE_CLICK_SETTLE_MAX_SEC,
    V12_MOUSE_CLICK_SETTLE_MIN_SEC,
    V12_MOUSE_JITTER_PX,
    V12_MOUSE_MOVE_MAX_DURATION_SEC,
    V12_MOUSE_MOVE_MIN_DURATION_SEC,
    V12_MOUSE_STATIC_REQUIRED_SEC,
    V12_MOUSE_STEPS_MAX,
    V12_MOUSE_STEPS_MIN,
)


def _load_pyautogui():
    try:
        import pyautogui  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("pyautogui is required for real mouse clicks. Install: pip install pyautogui") from exc
    pyautogui.PAUSE = 0
    return pyautogui


def _point_from_report(point: Dict[str, Any]) -> Tuple[int, int]:
    global_point = point.get("global_click_point") if isinstance(point.get("global_click_point"), dict) else {}
    return int(global_point.get("x")), int(global_point.get("y"))


def wait_until_mouse_static(pyautogui: Any) -> Dict[str, Any]:
    """
    V1.2.1: static-wait takeover is intentionally disabled.

    Earlier V1.2 waited until the cursor was static for several seconds before
    moving. In live play this felt like a visible twitch/takeover delay, so the
    click runtime now starts the planned curved movement immediately.
    """
    return {
        "status": "disabled",
        "waited_sec": 0.0,
        "required_static_sec": float(V12_MOUSE_STATIC_REQUIRED_SEC),
        "reason": "static mouse wait disabled in V1.2.1",
    }


def _ease_in_out_sine(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _cubic_bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    u = 1.0 - t
    return (u ** 3) * p0 + 3.0 * (u ** 2) * t * p1 + 3.0 * u * (t ** 2) * p2 + (t ** 3) * p3


def _control_points(start_x: int, start_y: int, end_x: int, end_y: int) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    dx = end_x - start_x
    dy = end_y - start_y
    distance = max(1.0, math.hypot(dx, dy))

    # Perpendicular vector gives a visible non-linear arc. Larger movements get a
    # larger curve, but it is capped so the cursor does not leave the general path.
    nx = -dy / distance
    ny = dx / distance
    direction = random.choice([-1.0, 1.0])
    bend = min(120.0, max(18.0, distance * random.uniform(0.10, 0.24))) * direction

    c1_t = random.uniform(0.22, 0.38)
    c2_t = random.uniform(0.62, 0.82)
    c1 = (
        start_x + dx * c1_t + nx * bend * random.uniform(0.70, 1.10),
        start_y + dy * c1_t + ny * bend * random.uniform(0.70, 1.10),
    )
    c2 = (
        start_x + dx * c2_t - nx * bend * random.uniform(0.35, 0.85),
        start_y + dy * c2_t - ny * bend * random.uniform(0.35, 0.85),
    )
    return c1, c2


def human_move_to(pyautogui: Any, x: int, y: int) -> Dict[str, Any]:
    start_x, start_y = pyautogui.position()
    steps = random.randint(int(V12_MOUSE_STEPS_MIN), int(V12_MOUSE_STEPS_MAX))
    duration = random.uniform(float(V12_MOUSE_MOVE_MIN_DURATION_SEC), float(V12_MOUSE_MOVE_MAX_DURATION_SEC))
    jitter = max(0, int(V12_MOUSE_JITTER_PX))
    sleep_per_step = duration / max(1, steps)
    c1, c2 = _control_points(int(start_x), int(start_y), int(x), int(y))

    # Low-frequency drift changes slowly along the path. This looks less robotic
    # than independent random jitter on every point.
    drift_phase_x = random.uniform(0, math.tau)
    drift_phase_y = random.uniform(0, math.tau)
    drift_amp = random.uniform(0.35, 1.0) * jitter

    last_sent: Tuple[int, int] | None = None
    for index in range(1, steps + 1):
        raw_t = index / steps
        t = _ease_in_out_sine(raw_t)
        nx = _cubic_bezier(float(start_x), c1[0], c2[0], float(x), t)
        ny = _cubic_bezier(float(start_y), c1[1], c2[1], float(y), t)

        # Do not jitter the final target. The click must land exactly on the safe point.
        if index != steps and jitter > 0:
            envelope = math.sin(math.pi * raw_t)
            nx += math.sin(raw_t * math.tau * 1.7 + drift_phase_x) * drift_amp * envelope
            ny += math.cos(raw_t * math.tau * 1.3 + drift_phase_y) * drift_amp * envelope
            if random.random() < 0.18:
                nx += random.uniform(-jitter, jitter) * 0.45
                ny += random.uniform(-jitter, jitter) * 0.45

        point = (int(round(nx)), int(round(ny)))
        if point != last_sent:
            pyautogui.moveTo(point[0], point[1], duration=0)
            last_sent = point
        time.sleep(sleep_per_step * random.uniform(0.72, 1.28))

    pyautogui.moveTo(int(x), int(y), duration=0)
    settle = random.uniform(float(V12_MOUSE_CLICK_SETTLE_MIN_SEC), float(V12_MOUSE_CLICK_SETTLE_MAX_SEC))
    time.sleep(settle)
    return {
        "steps": steps,
        "duration_sec": round(duration, 3),
        "settle_sec": round(settle, 3),
        "curve": "cubic_bezier",
        "static_wait": "disabled",
    }


def execute_click_points_human_like(click_points: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    pyautogui = _load_pyautogui()
    wait_report = wait_until_mouse_static(pyautogui)
    movement_reports: List[Dict[str, Any]] = []

    for index, point in enumerate(click_points):
        x, y = _point_from_report(point)
        move_report = human_move_to(pyautogui, x, y)
        pyautogui.click()
        move_report.update({"index": index, "x": x, "y": y, "clicked": True})
        movement_reports.append(move_report)
        time.sleep(random.uniform(float(V12_MOUSE_BETWEEN_CLICKS_MIN_SEC), float(V12_MOUSE_BETWEEN_CLICKS_MAX_SEC)))

    return {
        "mouse_static": wait_report,
        "movements": movement_reports,
        "click_count": len(movement_reports),
    }
