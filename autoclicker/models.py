from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitorInfo:
    id: str
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool


@dataclass(frozen=True)
class ClickConfig:
    monitor_id: str
    rel_x: int
    rel_y: int
    interval_ms: int
