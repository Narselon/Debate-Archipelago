"""One shared Windows Magnification API session for color filters AND zoom.
Everything here must be called from the Qt main thread (the thread that initialises it)."""
from __future__ import annotations

import atexit
import ctypes
import logging
import sys
from ctypes import wintypes

from colormath import IDENTITY

log = logging.getLogger("overlay.magnifier")
_users: set = set()
_initialized = False
_dll_cache = None


class _ColorEffect(ctypes.Structure):
    _fields_ = [("transform", ctypes.c_float * 25)]


def available() -> bool:
    return sys.platform == "win32"


def _dll():
    global _dll_cache
    if _dll_cache is None:
        d = ctypes.WinDLL("Magnification.dll")
        d.MagInitialize.restype = wintypes.BOOL
        d.MagUninitialize.restype = wintypes.BOOL
        d.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(_ColorEffect)]
        d.MagSetFullscreenColorEffect.restype = wintypes.BOOL
        d.MagSetFullscreenTransform.argtypes = [ctypes.c_float, ctypes.c_int, ctypes.c_int]
        d.MagSetFullscreenTransform.restype = wintypes.BOOL
        _dll_cache = d
    return _dll_cache


def is_active(user: str) -> bool:
    return user in _users


def begin(user: str) -> bool:
    global _initialized
    if not available():
        return False
    if not _initialized:
        if not _dll().MagInitialize():
            log.error("MagInitialize failed")
            return False
        _initialized = True
    _users.add(user)
    return True


def end(user: str) -> None:
    """Release this user's hold. When the last user leaves, everything is reset and the session closed."""
    global _initialized
    _users.discard(user)
    if _initialized and not _users:
        set_color(IDENTITY)
        set_transform(1.0, 0, 0)
        _dll().MagUninitialize()
        _initialized = False


def set_color(matrix) -> bool:
    if not _initialized:
        return False
    return bool(_dll().MagSetFullscreenColorEffect(ctypes.byref(_ColorEffect((ctypes.c_float * 25)(*matrix)))))


def set_transform(factor: float, x: int, y: int) -> bool:
    if not _initialized:
        return False
    return bool(_dll().MagSetFullscreenTransform(float(factor), int(x), int(y)))


def screen_size() -> tuple:
    """Primary monitor size in physical pixels."""
    u = ctypes.windll.user32
    return u.GetSystemMetrics(0), u.GetSystemMetrics(1)


def _shutdown():
    for user in list(_users):
        end(user)


atexit.register(lambda: available() and _shutdown())
