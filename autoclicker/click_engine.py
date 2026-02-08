from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Callable


_INPUT_MOUSE = 0
_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_VIRTUALDESK = 0x4000
_MOUSEEVENTF_ABSOLUTE = 0x8000

_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

_ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]


def _configure_user32(user32: ctypes.LibraryLoader[ctypes.CDLL]) -> None:
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]
    user32.SendInput.restype = ctypes.c_uint


def _to_normalized_coordinate(value: int, start: int, size: int) -> int:
    if size <= 1:
        return 0
    return int(round((value - start) * 65535 / (size - 1)))


def _normalized_virtual_desktop_coordinates(
    user32: ctypes.LibraryLoader[ctypes.CDLL], abs_x: int, abs_y: int
) -> tuple[int, int]:
    virtual_x = int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
    virtual_y = int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
    virtual_width = int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    virtual_height = int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))

    if virtual_width <= 0 or virtual_height <= 0:
        raise OSError("Unable to determine virtual desktop dimensions.")

    return (
        _to_normalized_coordinate(abs_x, virtual_x, virtual_width),
        _to_normalized_coordinate(abs_y, virtual_y, virtual_height),
    )


def _send_mouse_input(
    user32: ctypes.LibraryLoader[ctypes.CDLL], flags: int, dx: int = 0, dy: int = 0
) -> None:
    event = _INPUT(
        type=_INPUT_MOUSE,
        union=_INPUT_UNION(
            mi=_MOUSEINPUT(
                dx=int(dx),
                dy=int(dy),
                mouseData=0,
                dwFlags=int(flags),
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    sent = int(user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_INPUT)))
    if sent != 1:
        raise ctypes.WinError()


def send_right_click(abs_x: int, abs_y: int) -> None:
    """Move and right-click at absolute screen coordinates using SendInput."""
    if sys.platform != "win32":
        raise OSError("Right-click injection is supported only on Windows.")

    user32 = ctypes.windll.user32
    _configure_user32(user32)
    normalized_x, normalized_y = _normalized_virtual_desktop_coordinates(
        user32, int(abs_x), int(abs_y)
    )

    # Keep move + button-down in the same injected event so the down occurs at the target.
    _send_mouse_input(
        user32,
        flags=_MOUSEEVENTF_MOVE
        | _MOUSEEVENTF_ABSOLUTE
        | _MOUSEEVENTF_VIRTUALDESK
        | _MOUSEEVENTF_RIGHTDOWN,
        dx=normalized_x,
        dy=normalized_y,
    )
    _send_mouse_input(
        user32,
        flags=_MOUSEEVENTF_MOVE
        | _MOUSEEVENTF_ABSOLUTE
        | _MOUSEEVENTF_VIRTUALDESK
        | _MOUSEEVENTF_RIGHTUP,
        dx=normalized_x,
        dy=normalized_y,
    )


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
