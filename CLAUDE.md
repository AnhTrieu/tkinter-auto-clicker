# CLAUDE.md

## Project Overview

Windows Tkinter Auto Clicker — GUI tool for automating mouse clicks with multi-monitor support using monitor-relative coordinates. Windows-only (uses ctypes for Win32 API).

## Commands

- **Run:** `python -m autoclicker`
- **Test:** `pytest tests/`
- **Install deps:** `pip install -r requirements.txt`

## Architecture

- `autoclicker/__main__.py` — Entry point (DPI setup → create app → mainloop)
- `autoclicker/models.py` — Frozen dataclasses (`MonitorInfo`, `ClickConfig`)
- `autoclicker/monitors.py` — Monitor enumeration, coordinate conversion (relative ↔ absolute)
- `autoclicker/ui.py` — Tkinter GUI (extends `tk.Tk`), main application class
- `autoclicker/click_engine.py` — Click worker thread, Win32 API left-click injection
- `autoclicker/hotkey.py` — Global F8 hotkey via pynput listener
- `autoclicker/dpi.py` — Windows DPI awareness setup with fallback chain
- `tests/` — pytest tests for coordinate conversion and worker threading

## Threading Model

- **Main thread:** Tkinter event loop (GUI)
- **Worker thread:** `ClickWorker` daemon for click execution
- **Hotkey thread:** pynput listener daemon for F8 toggle
- **Communication:** `threading.Event` for stop signals, `tk.after()` for thread-safe GUI callbacks

## Code Conventions

- Type hints throughout (PEP 484), `from __future__ import annotations`
- Frozen dataclasses for immutable models
- PascalCase classes, snake_case functions, UPPER_CASE constants
- Single underscore prefix for private attributes (`_worker`, `_stop_event`)
- Relative imports within package (`from .module import Class`)

## Dependencies

- Python 3.8+
- `screeninfo` — monitor detection
- `pynput` — global hotkey, mouse control
- `tkinter` (stdlib) — GUI
- `ctypes` (stdlib) — Windows API
