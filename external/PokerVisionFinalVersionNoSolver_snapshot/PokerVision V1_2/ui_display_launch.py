r"""
ui_display_launch.py

PokerVision Core V1.2 — live desktop UI entry.

V1.2 no longer opens PNG files from the test dataset. The button starts/stops a
real desktop analysis loop: capture primary monitor -> crop configured table_01
... table_06 slots -> run detector/runtime chain -> save table JSON + solver
payload only for slots where Trigger_UI found at least one relevant class.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Dict, List, Optional, Set

from config import (
    UI_BOTTOM_BAR_HEIGHT,
    UI_DISPLAY_CYCLE_OUTPUT_DIR,
    UI_MONITOR_REFRESH_MS,
    UI_START_MAXIMIZED,
    UI_WINDOW_HEIGHT,
    UI_WINDOW_WIDTH,
    V12_CLEAR_OUTPUTS_ON_LIVE_START,
    V12_PROCESS_ALL_TABLE_SLOTS,
    V12_REAL_SCAN_INTERVAL_MS,
    V12_UI_BUTTON_TEXT_START,
    V12_UI_BUTTON_TEXT_STOP,
    ensure_dir,
)
from display_analysis_cycle import (
    ActionEventGate,
    HandIdentityTracker,
    make_cycle_id,
    run_ui_display_analysis_cycle,
)
from table_slots import list_table_slots

try:
    from runtime.table_overlay_status import clear_runtime_statuses, snapshot_runtime_statuses, update_table_runtime_status
except Exception:
    clear_runtime_statuses = None
    snapshot_runtime_statuses = None
    update_table_runtime_status = None

try:
    from PIL import ImageGrab, ImageTk
    PIL_AVAILABLE = True
except Exception:
    ImageGrab = None
    ImageTk = None
    PIL_AVAILABLE = False


class PokerVisionLiveApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.sequence_running = False
        self.active_cycle_id: Optional[str] = None
        self.hand_tracker: Optional[HandIdentityTracker] = None
        self.action_event_gate: Optional[ActionEventGate] = None
        self.monitor_photo_ref = None
        self.live_pass_index = 0
        self.saved_json_count = 0

        ensure_dir(UI_DISPLAY_CYCLE_OUTPUT_DIR)
        self._setup_root_window()
        self._build_layout()
        self._start_monitor_relay()

    def _setup_root_window(self) -> None:
        self.root.title("PokerVision Core V1.2 — Live Desktop Runtime")
        self.root.geometry(f"{UI_WINDOW_WIDTH}x{UI_WINDOW_HEIGHT}+0+0")
        self.root.minsize(1280, 720)
        self.root.configure(bg="#101318")
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0, minsize=UI_BOTTOM_BAR_HEIGHT)
        self.root.grid_columnconfigure(0, weight=1)

        if UI_START_MAXIMIZED:
            self.root.after(100, self._maximize_window)

    def _maximize_window(self) -> None:
        try:
            self.root.state("zoomed")
        except Exception:
            pass

    def _build_layout(self) -> None:
        self.preview_frame = tk.Frame(self.root, bg="#0b0f14")
        self.preview_frame.grid(row=0, column=0, sticky="nsew")

        self.preview_label = tk.Label(
            self.preview_frame,
            bg="#0b0f14",
            fg="#d7dde8",
            text="Live preview основного монитора запускается...",
            font=("Segoe UI", 16),
        )
        self.preview_label.pack(fill="both", expand=True)

        self.bottom_bar = tk.Frame(self.root, bg="#18202b", height=UI_BOTTOM_BAR_HEIGHT)
        self.bottom_bar.grid(row=1, column=0, sticky="ew")
        self.bottom_bar.grid_propagate(False)
        self.bottom_bar.grid_columnconfigure(0, weight=0)
        self.bottom_bar.grid_columnconfigure(1, weight=1)

        self.open_button = tk.Button(
            self.bottom_bar,
            text=V12_UI_BUTTON_TEXT_START,
            font=("Segoe UI", 13, "bold"),
            command=self.on_live_toggle_clicked,
            height=2,
            padx=24,
            bg="#2d7dff",
            fg="white",
            activebackground="#1f5fcc",
            activeforeground="white",
        )
        self.open_button.grid(row=0, column=0, padx=24, pady=16, sticky="w")

        self.status_label = tk.Label(
            self.bottom_bar,
            text="Статус: V1.2 live mode готов. Кнопка запускает анализ реального рабочего стола, без открытия PNG.",
            bg="#18202b",
            fg="#d7dde8",
            font=("Segoe UI", 11),
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, padx=16, pady=16, sticky="ew")

    def _start_monitor_relay(self) -> None:
        if not PIL_AVAILABLE:
            self.preview_label.configure(
                text=(
                    "Pillow не установлен. Live preview и screenshot-анализ отключены.\n"
                    "Установи Pillow: pip install pillow"
                )
            )
            return
        self._update_monitor_preview()

    @staticmethod
    def _resample_filter():
        try:
            from PIL import Image
            if hasattr(Image, "Resampling"):
                return Image.Resampling.LANCZOS
            return Image.LANCZOS
        except Exception:
            return 1

    def _update_monitor_preview(self) -> None:
        try:
            screenshot = ImageGrab.grab(all_screens=False)
            target_w = max(1, self.preview_frame.winfo_width())
            target_h = max(1, self.preview_frame.winfo_height())
            screenshot = screenshot.resize((target_w, target_h), self._resample_filter())
            self.monitor_photo_ref = ImageTk.PhotoImage(screenshot)
            self.preview_label.configure(image=self.monitor_photo_ref, text="")
        except Exception as exc:
            self.preview_label.configure(image="", text=f"Ошибка live preview монитора:\n{exc}")
        self.root.after(UI_MONITOR_REFRESH_MS, self._update_monitor_preview)

    def on_live_toggle_clicked(self) -> None:
        if self.sequence_running:
            self.stop_live_cycle()
        else:
            self.start_live_cycle()

    def start_live_cycle(self) -> None:
        if not PIL_AVAILABLE:
            messagebox.showerror("PokerVision V1.2", "Pillow is required for live desktop capture. Install: pip install pillow")
            return

        self.sequence_running = True
        self.live_pass_index = 0
        self.saved_json_count = 0
        self.active_cycle_id = make_cycle_id()
        self.hand_tracker = HandIdentityTracker()
        self.action_event_gate = ActionEventGate(inactive_reset_passes=2)
        self.open_button.configure(text=V12_UI_BUTTON_TEXT_STOP, bg="#b91c1c", activebackground="#7f1d1d")

        if clear_runtime_statuses is not None:
            clear_runtime_statuses()

        self.status_label.configure(
            text="Статус: V1.2 live-анализ запущен. Захват рабочего стола → 6 table ROI → detector chain → runtime action."
        )
        self.root.after(10, lambda: self._run_live_cycle(clear_outputs=bool(V12_CLEAR_OUTPUTS_ON_LIVE_START)))

    def stop_live_cycle(self) -> None:
        self.sequence_running = False
        self.open_button.configure(text=V12_UI_BUTTON_TEXT_START, bg="#2d7dff", activebackground="#1f5fcc")
        self.status_label.configure(
            text=f"Статус: V1.2 live-анализ остановлен. Циклов: {self.live_pass_index}. JSON сохранено: {self.saved_json_count}."
        )

    def _live_table_bindings(self) -> tuple[Dict[str, Path], Set[str]]:
        slots = list_table_slots()
        if not V12_PROCESS_ALL_TABLE_SLOTS:
            slots = slots[:1]
        # Paths are placeholders only. display_analysis_cycle uses them only to select table_ids.
        image_by_table_id = {slot.table_id: Path(f"live_desktop_{slot.table_id}.png") for slot in slots}
        opened_table_ids = {slot.table_id for slot in slots}
        return image_by_table_id, opened_table_ids

    def _run_live_cycle(self, *, clear_outputs: bool) -> None:
        if not self.sequence_running:
            return

        try:
            if self.hand_tracker is None or self.action_event_gate is None or self.active_cycle_id is None:
                raise RuntimeError("Live runtime was not initialized")

            self.live_pass_index += 1
            pass_id = f"live_{self.live_pass_index:06d}"
            image_by_table_id, opened_table_ids = self._live_table_bindings()

            if update_table_runtime_status is not None:
                for table_id in opened_table_ids:
                    update_table_runtime_status(
                        table_id,
                        json_status="process",
                        json_time_ms=None,
                        payload_status="skipped",
                        solver_status="skipped",
                        service_click_status="process",
                        click_status="skipped",
                        click_target=None,
                    )

            self.status_label.configure(
                text=(
                    f"Статус: live-cycle {pass_id}. Анализ областей table_01..table_06. "
                    f"Сохранено JSON: {self.saved_json_count}."
                )
            )
            self.root.update_idletasks()

            saved_paths = run_ui_display_analysis_cycle(
                image_by_table_id=image_by_table_id,
                opened_table_ids=opened_table_ids,
                hand_tracker=self.hand_tracker,
                action_event_gate=self.action_event_gate,
                display_pass_id=pass_id,
                clear_previous_outputs_on_start=clear_outputs,
                cycle_id=self.active_cycle_id,
            )
            self.saved_json_count += len(saved_paths)

            statuses = snapshot_runtime_statuses() if snapshot_runtime_statuses is not None else {}
            active_statuses = [f"{tid}:{(st or {}).get('click_status', '-')}/{(st or {}).get('service_click_status', '-')}" for tid, st in statuses.items()]
            status_tail = " | ".join(active_statuses[:6]) if active_statuses else "no runtime status"
            self.status_label.configure(
                text=f"Статус: {pass_id} завершён. Новых JSON: {len(saved_paths)}. Всего: {self.saved_json_count}. {status_tail}"
            )

        except Exception as exc:
            self.sequence_running = False
            self.open_button.configure(text=V12_UI_BUTTON_TEXT_START, bg="#2d7dff", activebackground="#1f5fcc")
            self.status_label.configure(text=f"Ошибка live-cycle: {exc}")
            messagebox.showerror("PokerVision V1.2 Live Cycle Error", str(exc))
            return

        self.root.after(int(V12_REAL_SCAN_INTERVAL_MS), lambda: self._run_live_cycle(clear_outputs=False))

    def close_app(self) -> None:
        self.sequence_running = False
        self.root.destroy()


def run_ui_display_launch() -> None:
    root = tk.Tk()
    PokerVisionLiveApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_ui_display_launch()
