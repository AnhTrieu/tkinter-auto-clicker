# Tkinter Auto Clicker

A Windows-based GUI application for automated mouse clicking with precise monitor-relative coordinate targeting. Built with Python and Tkinter, this tool enables users to specify click locations relative to individual monitors in multi-monitor setups, converting them automatically to absolute desktop coordinates. Background threading ensures the GUI remains responsive during operation, while a global F8 hotkey provides convenient start/stop control.

---

## Features

### Reasoning

The main features center on easy coordinate entry, threaded clicking logic for responsiveness, and global hotkey safety. We should emphasize user-friendly GUI, precise monitor-relative target selection, reliable hotkey/stop system, and cross-platform compatibility within Windows environments. The unique selling point is the monitor-relative coordinate system, which simplifies multi-monitor setups.

### Content

- **Intuitive Tkinter GUI** for entering monitor-relative coordinates with visual monitor selection
- **Automatic coordinate conversion** from monitor-relative to absolute desktop positions
- **Responsive interface** - clicking operates in a background thread; GUI stays responsive
- **Global F8 hotkey** for seamless start/stop toggle and emergency halt
- **Reliable thread signaling** using `threading.Event` for graceful shutdown
- **Multi-monitor support** with DPI awareness for accurate clicking across different display configurations
- **Cursor capture** feature to easily grab current mouse coordinates

---

## Installation

### Reasoning

Users need to know the minimum Python version (3.8+ for frozen dataclasses), platform requirement (Windows-only due to ctypes Windows API usage), and how to install dependencies. We should provide clear installation steps and note that tkinter comes with standard Python installations.

### Content

**Requirements:**
- Python 3.8 or higher
- Windows operating system (uses Windows API via ctypes)
- Tkinter (included with standard Python installations)

**Installation Steps:**

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd PROJ_TkinterWindowsAutoClicker
   ```

2. Install dependencies:
   ```bash
   pip install -r windows_auto_clicker/requirements.txt
   ```

   Or install manually:
   ```bash
   pip install screeninfo pynput
   ```

3. Verify tkinter is available (usually pre-installed):
   ```python
   python -c "import tkinter"
   ```

---

## Usage

### Reasoning

Users need a clear step-by-step workflow from launch through coordinate entry to starting/stopping clicks. The coordinate capture feature is a key convenience feature that should be highlighted. We must clarify that coordinates are monitor-relative (0,0 = top-left of selected monitor) and explain the F8 hotkey behavior. Concrete examples with realistic coordinates help users understand the system, especially in multi-monitor scenarios.

### Content

### Launching the Application

```bash
cd windows_auto_clicker
python -m autoclicker
```

### Step-by-Step Workflow

1. **Select Monitor**
   - Use the "Monitor" dropdown to select which display to target
   - Monitor format: `Name [id] (WIDTHxHEIGHT at X,Y) [Primary]`
   - Click "Refresh" if monitors aren't detected correctly

2. **Enter Coordinates**
   - Enter X and Y coordinates **relative to the selected monitor**
   - Coordinates are 0-based: `(0, 0)` is the top-left corner of the selected monitor
   - **OR** click "Capture Cursor" to automatically fill in your current mouse position

3. **Set Click Interval**
   - Enter interval in milliseconds (e.g., `1000` for one click per second)
   - Minimum recommended: 100ms to avoid system overload

4. **Start Clicking**
   - Click "Start" button **OR** press `F8` key
   - Status display shows clicking status and target coordinates

5. **Stop Clicking**
   - Click "Stop" button **OR** press `F8` key again
   - F8 acts as both a toggle and emergency stop

### Global Hotkey

- **F8 Key**: Toggle start/stop from anywhere (application doesn't need focus)
- Works as an emergency stop if you need to halt clicking immediately

### Example Scenarios

**Example 1: Single Monitor (1920x1080)**
- To click the center of your screen:
  - Relative X: `960`
  - Relative Y: `540`
  - Interval: `1000` (clicks once per second)

**Example 2: Dual Monitor Setup**
- Setup: Primary monitor (1920x1080) at (0, 0), Secondary monitor (1920x1080) at (1920, 0)
- To click the center of the secondary monitor:
  - Select "Monitor 1" (the secondary)
  - Relative X: `960`
  - Relative Y: `540`
  - Behind the scenes: Converts to absolute position (2880, 540)

**Example 3: Triple Monitor with Left-Side Secondary**
- Setup: Left monitor at (-1920, 0), Primary at (0, 0), Right monitor at (1920, 0)
- To click top-left of left monitor:
  - Select the left monitor
  - Relative X: `0`
  - Relative Y: `0`
  - Absolute position: (-1920, 0)

---

## How It Works

### Reasoning

Users curious about the technical implementation will benefit from understanding the coordinate conversion formula, the threading architecture, and how global hotkeys work. We should explain at a high level without overwhelming detail. A diagram illustrating the three-thread architecture (GUI, worker, hotkey) and their communication via Events and callbacks would be valuable. Mention the Windows API usage for clicking and DPI awareness for multi-monitor accuracy.

### Content

### Coordinate Conversion

The application maintains a list of connected monitors with their absolute positions. When you enter coordinates:

1. **Monitor Detection**: Uses `screeninfo` to enumerate monitors and their positions
   - Each monitor has: `(x, y, width, height, is_primary)`
   - Example: Monitor 0 at (0, 0), Monitor 1 at (1920, 0)

2. **Relative to Absolute Conversion**:
   ```
   absolute_x = monitor.x + relative_x
   absolute_y = monitor.y + relative_y
   ```

   Example: Secondary monitor at (1920, 0) with relative coords (500, 300)
   - Absolute: (1920 + 500, 0 + 300) = (2420, 300)

3. **Validation**: Ensures coordinates are within monitor bounds before clicking

### Threading Architecture

![Architecture Diagram](docs/architecture-diagram.png)

The application uses three concurrent threads for responsive operation:

```
┌─────────────────────┐
│   Main GUI Thread   │  ← Tkinter event loop, user interaction
│    (Tkinter)        │
└──────────┬──────────┘
           │
           │ Creates & controls
           ├──────────────────────────────┐
           │                              │
           ▼                              ▼
┌──────────────────────┐      ┌─────────────────────┐
│   Worker Thread      │      │  Hotkey Thread      │
│   (Click Loop)       │      │  (pynput listener)  │
└──────────────────────┘      └─────────────────────┘
           │                              │
           │ threading.Event              │ Callback
           │ (stop signal)                │ (toggle start/stop)
           │                              │
           └──────────┬───────────────────┘
                      │
                      ▼
              Synchronized via
           threading primitives
```

**Thread Communication:**
- **Main → Worker**: `threading.Event` signals worker to stop
- **Worker → Main**: Error callback (thread-safe via `tk.after()`)
- **Hotkey → Main**: Toggle callback (thread-safe via `tk.after()`)

**Click Worker Loop:**
```python
while not stop_event.is_set():
    perform_click(abs_x, abs_y)  # Windows API call
    if stop_event.wait(interval_seconds):
        break  # Stop signal received
```

### Global Hotkey Mechanism

Uses `pynput.keyboard.Listener` to monitor F8 key presses globally:
- Listener runs as daemon thread in background
- Intercepts F8 key press even when application doesn't have focus
- Calls GUI toggle method in thread-safe manner

### Windows API Integration

- **Mouse clicks**: Injected via `ctypes.windll.user32.mouse_event()`
- **Cursor capture**: Retrieved via `ctypes.windll.user32.GetCursorPos()`
- **DPI awareness**: Configured via `SetProcessDpiAwarenessContext()` for accurate multi-monitor coordinate mapping

---

## Troubleshooting & FAQ

### Reasoning

Users will likely encounter issues related to multi-monitor coordinate confusion, hotkey conflicts, permission problems, and thread behavior. We should anticipate the most common problems based on the design: monitor selection errors, coordinate validation failures, DPI scaling issues, hotkey conflicts with other software, and Windows UAC permission requirements. Provide clear solutions for each.

### Content

### Common Issues

**Q: Clicks are appearing on the wrong monitor**
- **Solution**: Ensure you've selected the correct monitor from the dropdown. Click "Refresh" to reload the monitor list if you've recently connected/disconnected displays.

**Q: "Coordinates out of range" error**
- **Solution**: Verify that your relative X is less than monitor width and relative Y is less than monitor height. For a 1920x1080 monitor, valid ranges are X: 0-1919, Y: 0-1079.

**Q: F8 hotkey doesn't work**
- **Solution**:
  - Check if another application is using F8 as a hotkey
  - On some systems, F8 may be reserved for boot menus - try running the application after system startup
  - Ensure the application is running (check system tray)

**Q: Application requires administrator privileges**
- **Solution**: Some Windows configurations restrict click injection for security. Right-click the Python executable and select "Run as administrator" if you encounter permission errors.

**Q: Coordinates are confusing in multi-monitor setup**
- **Solution**: Remember that coordinates are **relative to the selected monitor**, not absolute screen coordinates. The top-left corner of the selected monitor is always (0, 0). Use the "Capture Cursor" button to grab coordinates easily.

**Q: Worker thread won't stop / application hangs**
- **Solution**: Press F8 or click Stop. If the application remains unresponsive (rare), close via Task Manager and restart. This can occur if the interval is set extremely low (<10ms) or if Windows API calls are blocked.

### Multi-Monitor Setup Tips

- **DPI Scaling**: The application automatically handles DPI awareness, but ensure your Windows display scaling settings are configured correctly
- **Monitor Arrangement**: Check Windows Display Settings to understand your monitor positions (negative coordinates for monitors positioned to the left of primary)
- **Refresh Monitors**: If you connect/disconnect monitors while the app is running, click "Refresh" to update the monitor list

---

## Acknowledgments

This project uses the following open-source libraries:

- **[screeninfo](https://github.com/rr-/screeninfo)** - Multi-monitor detection and enumeration
- **[pynput](https://github.com/moses-palmer/pynput)** - Global keyboard listener and mouse control

---

## License

MIT License

Copyright (c) 2026 [Author Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
