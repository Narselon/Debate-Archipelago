"""Shared bits for click-through, always-on-top overlay windows."""
from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

log = logging.getLogger("overlay.window")


def prepare(widget, translucent: bool = True) -> None:
    """Call before show()."""
    W = Qt.WindowType
    widget.setWindowFlags(W.FramelessWindowHint | W.WindowStaysOnTopHint | W.Tool
                          | W.WindowTransparentForInput | W.WindowDoesNotAcceptFocus)
    widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    if translucent:
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def exclude_from_capture(widget) -> None:
    """Hide our overlays from screen capture (WDA_EXCLUDEFROMCAPTURE, Windows 10 2004+).
    Without this the PiP window would capture itself and recurse. Call after show()."""
    if sys.platform != "win32":
        return
    try:
        ok = ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), 0x11)
        if not ok:
            log.warning("SetWindowDisplayAffinity failed; PiP may show overlays/feedback")
    except Exception:
        log.exception("could not exclude window from capture")


class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        prepare(self)
