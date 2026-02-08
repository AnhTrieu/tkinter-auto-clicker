import pytest

from autoclicker.models import MonitorInfo
from autoclicker.monitors import absolute_to_relative, relative_to_absolute


def test_relative_to_absolute_primary_monitor() -> None:
    monitor = MonitorInfo(
        id="monitor-0",
        name="Primary",
        x=0,
        y=0,
        width=1920,
        height=1080,
        is_primary=True,
    )

    assert relative_to_absolute(monitor, 100, 250) == (100, 250)


def test_relative_to_absolute_secondary_monitor() -> None:
    monitor = MonitorInfo(
        id="monitor-1",
        name="Secondary",
        x=-1920,
        y=0,
        width=1920,
        height=1080,
        is_primary=False,
    )

    assert relative_to_absolute(monitor, 300, 200) == (-1620, 200)


@pytest.mark.parametrize(
    ("rel_x", "rel_y"),
    [(-1, 0), (0, -1), (1920, 10), (10, 1080)],
)
def test_relative_to_absolute_rejects_out_of_bounds(rel_x: int, rel_y: int) -> None:
    monitor = MonitorInfo(
        id="monitor-0",
        name="Primary",
        x=0,
        y=0,
        width=1920,
        height=1080,
        is_primary=True,
    )

    with pytest.raises(ValueError):
        relative_to_absolute(monitor, rel_x, rel_y)


def test_absolute_to_relative_maps_correct_monitor() -> None:
    monitors = [
        MonitorInfo(
            id="monitor-0",
            name="Primary",
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True,
        ),
        MonitorInfo(
            id="monitor-1",
            name="Secondary",
            x=-1920,
            y=0,
            width=1920,
            height=1080,
            is_primary=False,
        ),
    ]

    match = absolute_to_relative(monitors, -50, 500)
    assert match is not None

    monitor, rel_x, rel_y = match
    assert monitor.id == "monitor-1"
    assert (rel_x, rel_y) == (1870, 500)

