"""Finds the emulator/game window so overlays can line up with it."""
from __future__ import annotations

import fnmatch
import logging

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication

log = logging.getLogger("overlay.target")


class Target:
    def __init__(self, process_pattern: str):
        self.pattern = (process_pattern or "").lower()
        self._noted = set()

    def _note(self, key: str, level: int, msg: str, *args) -> None:
        """Log each distinct message once, so a missing window doesn't spam the console."""
        if key not in self._noted:
            self._noted.add(key)
            log.log(level, msg, *args)

    def physical(self) -> tuple:
        """(left, top, right, bottom) in physical pixels - what screen capture wants."""
        found = self._find() if self.pattern else None
        if found is not None:
            return found
        screen = QGuiApplication.primaryScreen()
        g, dpr = screen.geometry(), screen.devicePixelRatio()
        return (int(g.x() * dpr), int(g.y() * dpr), int((g.x() + g.width()) * dpr), int((g.y() + g.height()) * dpr))

    def rect(self) -> QRect:
        """Same window in device-independent pixels - what Qt widgets want.
        Good enough for single-DPI setups; mixed-DPI multi-monitor needs per-screen handling."""
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        l, t, r, b = self.physical()
        return QRect(int(l / dpr), int(t / dpr), int((r - l) / dpr), int((b - t) / dpr))

    def _find(self):
        try:
            import psutil
            import win32gui
            import win32process
        except ImportError as e:
            self._note("deps", logging.WARNING,
                       "window tracking disabled (%s). Run: py -m pip install pywin32 psutil. "
                       "Overlays will cover the whole primary screen.", e)
            return None
        best = None

        def cb(hwnd, _):
            nonlocal best
            if not win32gui.IsWindowVisible(hwnd):
                return
            l, t, r, b = win32gui.GetClientRect(hwnd)
            w, h = r - l, b - t
            if w < 200 or h < 150:
                return
            try:
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                name = psutil.Process(pid).name().lower()
            except Exception:
                return
            if not fnmatch.fnmatch(name, self.pattern):
                return
            if best is None or w * h > best[0]:  # largest matching window wins
                x, y = win32gui.ClientToScreen(hwnd, (0, 0))
                best = (w * h, (x, y, x + w, y + h))

        win32gui.EnumWindows(cb, None)
        if best is None:
            self._note("nowin", logging.WARNING,
                       "no visible window found for process %r; using the whole primary screen. "
                       "Is the emulator running, and does window_match.process match its .exe name?", self.pattern)
            return None
        self._note("found", logging.INFO, "tracking the %r window (%dx%d)", self.pattern,
                   best[1][2] - best[1][0], best[1][3] - best[1][1])
        return best[1]