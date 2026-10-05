"""Full-screen color effects (grayscale, invert) via the Windows Magnification API.
Only one full-screen matrix can be active at a time, so active effects are composed into one."""
from __future__ import annotations

import atexit
import ctypes
import logging
import sys
from ctypes import wintypes

from colormath import GRAY, IDENTITY, INVERT, compose, lerp
from manager import Effect

log = logging.getLogger("overlay.colorfx")

_active: dict[str, list] = {}
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


def _set(matrix) -> bool:
    return bool(_mag().MagSetFullscreenColorEffect(
        ctypes.byref(_Effect((ctypes.c_float * 25)(*matrix)))))


def _apply():
    """Called on the Qt main thread only (Magnification must be used from the initialising thread)."""
    global _initialized
    if sys.platform != "win32":
        return
    if not _active:
        if _initialized:
            _set(IDENTITY)
            _mag().MagUninitialize()
            _initialized = False
        return
    if not _initialized:
        if not _mag().MagInitialize():
            log.error("MagInitialize failed")
            return
        _initialized = True
    if not _set(compose(list(_active.values()))):
        log.error("MagSetFullscreenColorEffect failed")


def acquire(name: str, matrix) -> None:
    _active[name] = matrix
    _apply()


def release(name: str) -> None:
    _active.pop(name, None)
    _apply()


atexit.register(lambda: (_active.clear(), _apply()))


class _ColorEffect(Effect):
    def matrix(self, params):
        raise NotImplementedError

    def start(self, params):
        if sys.platform != "win32":
            log.warning("%s needs Windows", self.name)
            return
        acquire(self.name, self.matrix(params))

    def stop(self):
        release(self.name)


class GrayscaleEffect(_ColorEffect):
    name = "grayscale"

    def matrix(self, params):
        k = max(0.0, min(1.0, float(params.get("intensity", 1.0))))   # 1.0 = fully gray
        return lerp(IDENTITY, GRAY, k)


class InvertEffect(_ColorEffect):
    name = "invert"

    def matrix(self, params):
        return INVERT
