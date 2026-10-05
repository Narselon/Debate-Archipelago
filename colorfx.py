"""Full-screen color effects (grayscale, invert) via the shared Magnification session.
Only one full-screen color matrix exists at a time, so active effects are composed into one."""
from __future__ import annotations

import logging
import sys

import magnifier
from colormath import GRAY, IDENTITY, INVERT, compose, lerp
from manager import Effect

log = logging.getLogger("overlay.colorfx")
_active: dict = {}


def _apply():
    if not magnifier.available():
        return
    if not _active:
        if magnifier.is_active("color"):
            magnifier.set_color(IDENTITY)      # reset the color matrix even if zoom keeps the session open
            magnifier.end("color")
        return
    if not magnifier.begin("color"):
        return
    if not magnifier.set_color(compose(list(_active.values()))):
        log.error("MagSetFullscreenColorEffect failed")


def acquire(name: str, matrix) -> None:
    _active[name] = matrix
    _apply()


def release(name: str) -> None:
    _active.pop(name, None)
    _apply()


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