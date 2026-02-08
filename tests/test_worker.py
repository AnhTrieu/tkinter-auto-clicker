import threading
import time

from autoclicker.click_engine import ClickWorker


def test_click_worker_stops_quickly_after_stop_event() -> None:
    stop_event = threading.Event()
    click_times: list[float] = []

    def click_fn(_x: int, _y: int) -> None:
        click_times.append(time.perf_counter())

    worker = ClickWorker(
        abs_x=100,
        abs_y=200,
        interval_ms=1000,
        stop_event=stop_event,
        on_error=None,
        click_fn=click_fn,
    )
    worker.start()

    time.sleep(0.05)
    stop_event.set()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert len(click_times) >= 1


def test_click_worker_waits_between_clicks() -> None:
    stop_event = threading.Event()
    click_times: list[float] = []

    def click_fn(_x: int, _y: int) -> None:
        click_times.append(time.perf_counter())
        if len(click_times) >= 2:
            stop_event.set()

    worker = ClickWorker(
        abs_x=50,
        abs_y=80,
        interval_ms=140,
        stop_event=stop_event,
        on_error=None,
        click_fn=click_fn,
    )
    worker.start()
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert len(click_times) == 2
    assert click_times[1] - click_times[0] >= 0.11


def test_click_worker_reports_click_errors() -> None:
    stop_event = threading.Event()
    captured_errors: list[Exception] = []

    def click_fn(_x: int, _y: int) -> None:
        raise RuntimeError("click failed")

    worker = ClickWorker(
        abs_x=1,
        abs_y=1,
        interval_ms=10,
        stop_event=stop_event,
        on_error=captured_errors.append,
        click_fn=click_fn,
    )
    worker.start()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert len(captured_errors) == 1
    assert str(captured_errors[0]) == "click failed"

