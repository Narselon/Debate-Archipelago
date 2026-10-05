"""Grayscale via the Windows Magnification API (affects the whole desktop)."""
from __future__ import annotations

import atexit
import ctypes
import logging
import sys
from ctypes import wintypes

from manager import Effect

log = logging.getLogger("overlay.grayscale")

IDENTITY = [1, 0, 0, 0, 0,  0, 1, 0, 0, 0,  0, 0, 1, 0, 0,  0, 0, 0, 1, 0,  0, 0, 0, 0, 1]
GRAY = [0.3, 0.3, 0.3, 0, 0,  0.6, 0.6, 0.6, 0, 0,  0.1, 0.1, 0.1, 0, 0,  0, 0, 0, 1, 0,  0, 0, 0, 0, 1]
_initialized = False


class _Effect(ctypes.Structure):
    _fields_ = [("transform", ctypes.c_float * 25)]


def _mag():
    mag = ctypes.WinDLL("Magnification.dll")
    mag.MagInitialize.restype = wintypes.BOOL
    mag.MagUninitialize.restype = wintypes.BOOL
    mag.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(_Effect)]
    mag.MagSetFullscreenColorEffect.restype = wintypes.BOOL
    return mag


def _set(matrix):
    mag = _mag()
    return mag.MagSetFullscreenColorEffect(ctypes.byref(_Effect((ctypes.c_float * 25)(*matrix))))


def _shutdown():
    global _initialized
    if _initialized:
        _set(IDENTITY)
        _mag().MagUninitialize()
        _initialized = False


atexit.register(lambda: sys.platform == "win32" and _shutdown())


class GrayscaleEffect(Effect):
    name = "grayscale"

    def start(self, params):
        global _initialized
        if sys.platform != "win32":
            log.warning("grayscale needs Windows")
            return
        k = max(0.0, min(1.0, float(params.get("intensity", 1.0))))  # 1.0 = fully gray
        matrix = [(1 - k) * i + k * g for i, g in zip(IDENTITY, GRAY)]
        # Must be called from the thread that initialises it: the Qt main thread (manager guarantees this)
        if not _initialized:
            if not _mag().MagInitialize():
                log.error("MagInitialize failed")
                return
            _initialized = True
        if not _set(matrix):
            log.error("MagSetFullscreenColorEffect failed")

    def stop(self):
        if sys.platform == "win32":
            _shutdown()
