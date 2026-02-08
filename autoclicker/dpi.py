import ctypes
import sys


_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
_PER_MONITOR_AWARE = 2
_S_OK = 0
_E_ACCESSDENIED = -2147024891


def set_dpi_awareness() -> str:
    """Set the best DPI awareness mode available for the current process."""
    if sys.platform != "win32":
        return "unsupported-platform"

    user32 = ctypes.windll.user32

    try:
        if user32.SetProcessDpiAwarenessContext(_PER_MONITOR_AWARE_V2):
            return "per-monitor-v2"
    except AttributeError:
        pass

    shcore = getattr(ctypes.windll, "shcore", None)
    if shcore is not None:
        try:
            result = shcore.SetProcessDpiAwareness(_PER_MONITOR_AWARE)
            if result in (_S_OK, _E_ACCESSDENIED):
                return "per-monitor-v1"
        except AttributeError:
            pass

    try:
        if user32.SetProcessDPIAware():
            return "system-dpi-aware"
    except AttributeError:
        pass

    return "dpi-awareness-unavailable"

