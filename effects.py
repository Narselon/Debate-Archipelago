"""Effect plugins."""
from __future__ import annotations

import logging
import math
import time

from PySide6.QtGui import QColor, QPainter

from colorfx import GrayscaleEffect, InvertEffect
from manager import Effect
from overlay import OverlayWidget, exclude_from_capture
from pip_effect import PipEffect
from pip_video import PipVideoEffect
from video import VideoEffect
from rotate import RotateEffect
from zoom import ZoomEffect

log = logging.getLogger("overlay.effects")


class _BlindsWidget(OverlayWidget):
    def __init__(self, slats: int):
        super().__init__()
        self.slats = slats
        self.cover = 0.0

    def paintEvent(self, _):
        p = QPainter(self)
        band = self.height() / self.slats
        h = max(1, int(band * self.cover)) if self.cover > 0 else 0
        for i in range(self.slats):
            p.fillRect(0, int(i * band), self.width(), h, QColor(0, 0, 0, 255))


class BlindsEffect(Effect):
    name = "blinds"

    def start(self, params):
        self.period = max(3.0, float(params.get("period", 6.0)))      # floor keeps it slow (photosensitivity)
        self.max_cover = min(0.75, float(params.get("max_cover", 0.65)))
        self.w = _BlindsWidget(int(params.get("slats", 8)))
        self.t0 = self._last_sync = time.monotonic()
        self._sync()
        self.w.show()
        exclude_from_capture(self.w)

    def tick(self, now):
        phase = (now - self.t0) / self.period
        self.w.cover = self.max_cover * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
        if now - self._last_sync > 1.0:
            self._sync()
            self._last_sync = now
        self.w.update()

    def stop(self):
        self.w.close()

    def _sync(self):
        self.w.setGeometry(self.ctx.target.rect())


class ReverseControlsEffect(Effect):
    name = "reverse_controls"

    def start(self, params):
        prof = self.ctx.profile
        self._pad = self._kb = None
        if prof.input in ("gamepad", "both"):
            if self.ctx.pad is None:
                log.warning("gamepad proxy not running (ViGEmBus / vgamepad missing?)")
            elif prof.reverse_pad is None:
                log.warning("profile has no reverse_controls buttons/axes")
            else:
                self._pad = self.ctx.pad
                self._pad.set_remap(prof.reverse_pad)
        if prof.input in ("keyboard", "both") and prof.reverse_keys:
            from inputs import KeyboardRemap
            self._kb = KeyboardRemap(prof.reverse_keys)
            self._kb.start()

    def stop(self):
        if self._pad:
            self._pad.set_remap(None)
        if self._kb:
            self._kb.stop()


def _stub(effect_name: str):
    class Stub(Effect):
        name = effect_name

        def start(self, params):
            log.warning("effect %r is not implemented yet", effect_name)
    return Stub


REGISTRY = {
    "blinds": BlindsEffect,
    "grayscale": GrayscaleEffect,
    "reverse_controls": ReverseControlsEffect,
    "invert": InvertEffect,
    "pip": PipEffect,
    "video": VideoEffect,
    "pip_video": PipVideoEffect,
    "rotate": RotateEffect,
    "zoom": ZoomEffect,
}