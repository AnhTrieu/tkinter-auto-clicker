from __future__ import annotations

import hashlib
from collections.abc import Iterable

from .models import MonitorInfo


def _stable_monitor_id(name: str, x: int, y: int, width: int, height: int) -> str:
    identity = f"{name}|{x}|{y}|{width}|{height}".encode("utf-8")
    digest = hashlib.blake2s(identity, digest_size=6).hexdigest()
    return f"monitor-{digest}"


def list_monitors() -> list[MonitorInfo]:
    try:
        from screeninfo import get_monitors
    except ImportError as exc:
        raise RuntimeError("The 'screeninfo' package is required to enumerate monitors.") from exc

    monitors: list[MonitorInfo] = []
    for index, monitor in enumerate(get_monitors()):
        name = str(getattr(monitor, "name", None) or f"Monitor {index + 1}")
        x = int(monitor.x)
        y = int(monitor.y)
        width = int(monitor.width)
        height = int(monitor.height)
        monitors.append(
            MonitorInfo(
                id=_stable_monitor_id(name=name, x=x, y=y, width=width, height=height),
                name=name,
                x=x,
                y=y,
                width=width,
                height=height,
                is_primary=bool(getattr(monitor, "is_primary", False)),
            )
        )
    return monitors


def relative_to_absolute(monitor: MonitorInfo, rel_x: int, rel_y: int) -> tuple[int, int]:
    if not 0 <= rel_x < monitor.width:
        raise ValueError(f"X coordinate must be between 0 and {monitor.width - 1}.")
    if not 0 <= rel_y < monitor.height:
        raise ValueError(f"Y coordinate must be between 0 and {monitor.height - 1}.")
    return monitor.x + rel_x, monitor.y + rel_y


def absolute_to_relative(
    monitors: Iterable[MonitorInfo], abs_x: int, abs_y: int
) -> tuple[MonitorInfo, int, int] | None:
    for monitor in monitors:
        x_end = monitor.x + monitor.width
        y_end = monitor.y + monitor.height
        if monitor.x <= abs_x < x_end and monitor.y <= abs_y < y_end:
            return monitor, abs_x - monitor.x, abs_y - monitor.y
    return None
