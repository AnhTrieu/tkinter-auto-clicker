from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

from autoclicker import click_engine


class _FakeApiCall:
    def __init__(self, fn):
        self._fn = fn
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self._fn(*args)


class _FakeUser32:
    def __init__(self) -> None:
        self._metrics = {
            click_engine._SM_XVIRTUALSCREEN: -1920,
            click_engine._SM_YVIRTUALSCREEN: 0,
            click_engine._SM_CXVIRTUALSCREEN: 3840,
            click_engine._SM_CYVIRTUALSCREEN: 1080,
        }
        self.events: list[tuple[int, int, int]] = []
        self.GetSystemMetrics = _FakeApiCall(self._get_system_metrics)
        self.SendInput = _FakeApiCall(self._send_input)

    def _get_system_metrics(self, metric: int) -> int:
        return self._metrics[metric]

    def _send_input(self, count: int, event_ptr, _size: int) -> int:
        assert count == 1
        event = ctypes.cast(event_ptr, ctypes.POINTER(click_engine._INPUT)).contents
        self.events.append((int(event.mi.dwFlags), int(event.mi.dx), int(event.mi.dy)))
        return 1


def test_send_right_click_requires_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(click_engine.sys, "platform", "darwin")

    with pytest.raises(OSError):
        click_engine.send_right_click(100, 200)


def test_send_right_click_uses_send_input_events(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_user32 = _FakeUser32()
    monkeypatch.setattr(click_engine.sys, "platform", "win32")
    monkeypatch.setattr(
        click_engine.ctypes,
        "windll",
        SimpleNamespace(user32=fake_user32),
        raising=False,
    )

    click_engine.send_right_click(100, 200)

    expected_x = click_engine._to_normalized_coordinate(100, -1920, 3840)
    expected_y = click_engine._to_normalized_coordinate(200, 0, 1080)

    assert fake_user32.events == [
        (
            click_engine._MOUSEEVENTF_MOVE
            | click_engine._MOUSEEVENTF_ABSOLUTE
            | click_engine._MOUSEEVENTF_VIRTUALDESK
            | click_engine._MOUSEEVENTF_RIGHTDOWN,
            expected_x,
            expected_y,
        ),
        (
            click_engine._MOUSEEVENTF_MOVE
            | click_engine._MOUSEEVENTF_ABSOLUTE
            | click_engine._MOUSEEVENTF_VIRTUALDESK
            | click_engine._MOUSEEVENTF_RIGHTUP,
            expected_x,
            expected_y,
        ),
    ]
