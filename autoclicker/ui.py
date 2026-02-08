from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .click_engine import ClickWorker
from .hotkey import GlobalHotkeyController
from .models import ClickConfig, MonitorInfo
from .monitors import absolute_to_relative, list_monitors, relative_to_absolute


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_cursor_position() -> tuple[int, int]:
    if sys.platform != "win32":
        raise OSError("Cursor capture is only supported on Windows.")

    point = _POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError()
    return int(point.x), int(point.y)


class AutoClickerApp(tk.Tk):
    def __init__(self, dpi_mode: str) -> None:
        super().__init__()
        self.title("Windows 11 Auto Clicker")
        self.resizable(False, False)

        self._dpi_mode = dpi_mode
        self._worker: ClickWorker | None = None
        self._stop_event = threading.Event()
        self._shutting_down = False
        self._hotkey: GlobalHotkeyController | None = None

        self._monitors_by_id: dict[str, MonitorInfo] = {}
        self._monitor_label_to_id: dict[str, str] = {}
        self._monitor_id_to_label: dict[str, str] = {}

        self.monitor_var = tk.StringVar()
        self.rel_x_var = tk.StringVar(value="0")
        self.rel_y_var = tk.StringVar(value="0")
        self.interval_var = tk.StringVar(value="1000")
        self.status_var = tk.StringVar(value="Initializing...")

        self._build_widgets()
        self._refresh_monitors()
        self._set_running_controls(False)
        self._set_status(f"Ready. DPI mode: {self._dpi_mode}")

        self._hotkey = GlobalHotkeyController(on_toggle=self._on_hotkey_toggle)
        try:
            self._hotkey.start()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Hotkey unavailable: {exc}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")

        ttk.Label(root, text="Monitor").grid(row=0, column=0, sticky="w")
        self.monitor_combo = ttk.Combobox(
            root, textvariable=self.monitor_var, state="readonly", width=56
        )
        self.monitor_combo.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0))

        ttk.Button(root, text="Refresh", command=self._on_refresh_monitors).grid(
            row=0, column=3, sticky="ew", padx=(8, 0)
        )

        ttk.Label(root, text="Relative X").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.rel_x_entry = ttk.Entry(root, textvariable=self.rel_x_var, width=12)
        self.rel_x_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(root, text="Relative Y").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(8, 0))
        self.rel_y_entry = ttk.Entry(root, textvariable=self.rel_y_var, width=12)
        self.rel_y_entry.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(8, 0))

        ttk.Label(root, text="Interval (ms)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.interval_entry = ttk.Entry(root, textvariable=self.interval_var, width=12)
        self.interval_entry.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        self.capture_button = ttk.Button(
            root, text="Capture Cursor", command=self.capture_cursor_position
        )
        self.capture_button.grid(row=2, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0))

        self.start_button = ttk.Button(root, text="Start", command=self.start_clicking)
        self.start_button.grid(row=3, column=1, sticky="ew", pady=(12, 0))

        self.stop_button = ttk.Button(root, text="Stop", command=self.stop_clicking)
        self.stop_button.grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=(12, 0))

        ttk.Label(root, textvariable=self.status_var, wraplength=560).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(12, 0)
        )

        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=1)
        root.columnconfigure(3, weight=1)

    def _on_refresh_monitors(self) -> None:
        selected_id = self._selected_monitor_id()
        try:
            self._refresh_monitors(preferred_monitor_id=selected_id)
        except RuntimeError as exc:
            self._set_status(str(exc))
            messagebox.showerror("Monitor refresh failed", str(exc), parent=self)
            return
        self._set_status("Monitor list refreshed.")

    def _refresh_monitors(self, preferred_monitor_id: str | None = None) -> None:
        if preferred_monitor_id is None:
            preferred_monitor_id = self._selected_monitor_id()

        monitors = list_monitors()
        if not monitors:
            raise RuntimeError("No monitors were detected by screeninfo.")

        self._monitors_by_id = {monitor.id: monitor for monitor in monitors}
        self._monitor_label_to_id.clear()
        self._monitor_id_to_label.clear()

        labels: list[str] = []
        for monitor in monitors:
            label = self._format_monitor_label(monitor)
            labels.append(label)
            self._monitor_label_to_id[label] = monitor.id
            self._monitor_id_to_label[monitor.id] = label

        self.monitor_combo["values"] = labels

        selected_id = preferred_monitor_id
        if selected_id not in self._monitors_by_id:
            primary = next((m for m in monitors if m.is_primary), monitors[0])
            selected_id = primary.id

        self.monitor_var.set(self._monitor_id_to_label[selected_id])

    @staticmethod
    def _format_monitor_label(monitor: MonitorInfo) -> str:
        primary_suffix = " [Primary]" if monitor.is_primary else ""
        return (
            f"{monitor.name} [{monitor.id}] "
            f"({monitor.width}x{monitor.height} at {monitor.x},{monitor.y})"
            f"{primary_suffix}"
        )

    def _selected_monitor_id(self) -> str | None:
        label = self.monitor_var.get()
        return self._monitor_label_to_id.get(label)

    def _selected_monitor(self) -> MonitorInfo | None:
        monitor_id = self._selected_monitor_id()
        if monitor_id is None:
            return None
        return self._monitors_by_id.get(monitor_id)

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)

    def _set_running_controls(self, running: bool) -> None:
        self.start_button.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL if running else tk.DISABLED)

    def _is_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _build_click_config(self) -> tuple[ClickConfig, MonitorInfo, tuple[int, int]]:
        self._refresh_monitors(preferred_monitor_id=self._selected_monitor_id())

        monitor = self._selected_monitor()
        if monitor is None:
            raise ValueError("Select a valid monitor.")

        try:
            rel_x = int(self.rel_x_var.get().strip())
            rel_y = int(self.rel_y_var.get().strip())
            interval_ms = int(self.interval_var.get().strip())
        except ValueError as exc:
            raise ValueError("Relative X, Relative Y, and Interval must be integers.") from exc

        if interval_ms < 1:
            raise ValueError("Interval must be at least 1 ms.")

        config = ClickConfig(
            monitor_id=monitor.id,
            rel_x=rel_x,
            rel_y=rel_y,
            interval_ms=interval_ms,
        )
        abs_x, abs_y = relative_to_absolute(monitor, config.rel_x, config.rel_y)
        return config, monitor, (abs_x, abs_y)

    def start_clicking(self) -> None:
        if self._is_running():
            return

        try:
            config, monitor, (abs_x, abs_y) = self._build_click_config()
        except (RuntimeError, ValueError) as exc:
            self._set_status(f"Cannot start: {exc}")
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        self._stop_event.clear()
        self._worker = ClickWorker(
            abs_x=abs_x,
            abs_y=abs_y,
            interval_ms=config.interval_ms,
            stop_event=self._stop_event,
            on_error=self._on_worker_error,
        )
        self._worker.start()
        self._set_running_controls(True)
        self._set_status(
            "Running right-click loop on "
            f"{monitor.name} at ({config.rel_x}, {config.rel_y}) every {config.interval_ms} ms."
        )
        self.after(100, self._poll_worker_state)

    def stop_clicking(self) -> None:
        if self._worker is None:
            self._set_running_controls(False)
            self._set_status("Stopped.")
            return

        self._stop_event.set()
        self._set_status("Stopping...")
        self.after(50, self._poll_worker_state)

    def _poll_worker_state(self) -> None:
        worker = self._worker
        if worker is None:
            self._set_running_controls(False)
            return

        if worker.is_alive():
            self.after(100, self._poll_worker_state)
            return

        self._worker = None
        self._set_running_controls(False)
        if not self._shutting_down:
            if self._stop_event.is_set():
                self._set_status("Stopped.")
            else:
                self._set_status("Idle.")

    def _on_worker_error(self, exc: Exception) -> None:
        try:
            self.after(0, self._handle_worker_error, str(exc))
        except tk.TclError:
            return

    def _handle_worker_error(self, message: str) -> None:
        self._stop_event.set()
        self._worker = None
        self._set_running_controls(False)
        self._set_status(f"Worker error: {message}")
        if not self._shutting_down:
            messagebox.showerror("Click loop failed", message, parent=self)

    def capture_cursor_position(self) -> None:
        try:
            self._refresh_monitors(preferred_monitor_id=self._selected_monitor_id())
            abs_x, abs_y = _get_cursor_position()
            result = absolute_to_relative(self._monitors_by_id.values(), abs_x, abs_y)
            if result is None:
                raise ValueError("Cursor position is outside the detected monitor bounds.")
            monitor, rel_x, rel_y = result
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Capture failed: {exc}")
            messagebox.showerror("Capture failed", str(exc), parent=self)
            return

        self.monitor_var.set(self._monitor_id_to_label[monitor.id])
        self.rel_x_var.set(str(rel_x))
        self.rel_y_var.set(str(rel_y))
        self._set_status(f"Captured cursor on {monitor.name}: ({rel_x}, {rel_y}).")

    def _on_hotkey_toggle(self) -> None:
        try:
            self.after(0, self._toggle_start_stop)
        except tk.TclError:
            return

    def _toggle_start_stop(self) -> None:
        if self._is_running():
            self.stop_clicking()
        else:
            self.start_clicking()

    def _on_close(self) -> None:
        self._shutting_down = True
        self._stop_event.set()

        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._worker = None

        if self._hotkey is not None:
            self._hotkey.stop()
            self._hotkey = None

        self.destroy()

