from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard


class GlobalHotkeyController:
    def __init__(self, on_toggle: Callable[[], None]) -> None:
        self._on_toggle = on_toggle
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._listener is not None:
                return
            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.daemon = True
            self._listener.start()

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None

        if listener is not None:
            listener.stop()
            listener.join(timeout=1.0)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key == keyboard.Key.f8:
            self._on_toggle()

