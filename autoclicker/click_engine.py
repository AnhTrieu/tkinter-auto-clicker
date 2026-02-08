from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Callable


_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010


def send_right_click(abs_x: int, abs_y: int) -> None:
    """Move the cursor and issue a right-click at absolute screen coordinates."""
    if sys.platform != "win32":
        raise OSError("Right-click injection is supported only on Windows.")

    user32 = ctypes.windll.user32
    if not user32.SetCursorPos(int(abs_x), int(abs_y)):
        raise ctypes.WinError()

    user32.mouse_event(_MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    user32.mouse_event(_MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


class ClickWorker(threading.Thread):
    def __init__(
        self,
        abs_x: int,
        abs_y: int,
        interval_ms: int,
        stop_event: threading.Event,
        on_error: Callable[[Exception], None] | None,
        click_fn: Callable[[int, int], None] = send_right_click,
    ) -> None:
        super().__init__(name="ClickWorker", daemon=True)
        if interval_ms < 1:
            raise ValueError("Interval must be at least 1 ms.")

        self._abs_x = int(abs_x)
        self._abs_y = int(abs_y)
        self._interval_ms = int(interval_ms)
        self._stop_event = stop_event
        self._on_error = on_error
        self._click_fn = click_fn

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._click_fn(self._abs_x, self._abs_y)
            except Exception as exc:  # noqa: BLE001
                if self._on_error is not None:
                    self._on_error(exc)
                break

            if self._stop_event.wait(self._interval_ms / 1000.0):
                break

