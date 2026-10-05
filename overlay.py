"""Shared bits for click-through, always-on-top overlay windows."""
from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget

log = logging.getLogger("overlay.window")


def prepare(widget, translucent: bool = True, click_through: bool = True) -> None:
    """Call before show().
    On Windows both translucency and Qt's WindowTransparentForInput make the window 'layered', and Windows
    refuses to hide layered windows from screen capture (SetWindowDisplayAffinity error 8). So windows that
    must be capture-excluded (PiP, rotate) are created opaque with click_through=False: they never take
    keyboard focus, but mouse clicks on them don't fall through to the game."""
    W = Qt.WindowType
    flags = W.FramelessWindowHint | W.WindowStaysOnTopHint | W.Tool | W.WindowDoesNotAcceptFocus
    if click_through:
        flags |= W.WindowTransparentForInput
    widget.setWindowFlags(flags)
    widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    if translucent:
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def exclude_from_capture(widget, log_failure: bool = False) -> bool:
    """Ask Windows to hide this overlay from screen capture (WDA_EXCLUDEFROMCAPTURE, Windows 10 2004+).
    Without this, PiP/rotate would capture themselves and recurse. Call after show().
    Returns False if Windows refused. A freshly shown window is sometimes refused (error 8) and accepted a
    moment later, so effects should use exclude_when_ready() instead of calling this once."""
    if sys.platform != "win32":
        return True
    try:
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        hwnd = int(widget.winId())
        if user32.SetWindowDisplayAffinity(hwnd, 0x11):
            return True
        if log_failure:
            err = ctypes.get_last_error()
            ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
            log.warning("SetWindowDisplayAffinity failed: Windows error %s (5 = access denied, 8 = not enough "
                        "memory/window not ready, 87 = not supported on this Windows build); window "
                        "exstyle=0x%08X layered=%s, size=%dx%d. It will appear in screen captures.",
                        err, ex, bool(ex & 0x80000), widget.width(), widget.height())
    except Exception:
        log.exception("could not exclude window from capture")
    return False


def exclude_when_ready(widget, on_done, delays_ms=(0, 50, 100, 200, 400, 800)) -> None:
    """Retry exclude_from_capture a few times while the new window finishes appearing, then call
    on_done(True/False). Silent if the window is closed in the meantime. Needs the Qt event loop."""
    remaining = list(delays_ms)

    def attempt():
        if not widget.isVisible():
            return
        last = not remaining
        ok = exclude_from_capture(widget, log_failure=last)
        if ok or last:
            on_done(ok)
        else:
            QTimer.singleShot(remaining.pop(0), attempt)

    QTimer.singleShot(remaining.pop(0), attempt)


class OverlayWidget(QWidget):
    def __init__(self, translucent: bool = True, click_through: bool = True):
        super().__init__()
        prepare(self, translucent, click_through)