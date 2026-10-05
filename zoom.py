"""Zoomed-in screen via the Magnification API: eases in, holds, eases back out.
Magnifies the whole PRIMARY monitor; if the emulator is on another monitor, move it or use rotate instead."""
from __future__ import annotations

import logging
import time

import magnifier
from manager import Effect
from viewmath import envelope, zoom_view

log = logging.getLogger("overlay.zoom")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class ZoomEffect(Effect):
    """params: factor (1.2-6, default 2), ease (seconds, 0-5, default 1.5),
    focus_x / focus_y (0-1 within the game window, default 0.5 = centre)"""
    name = "zoom"

    def start(self, params):
        self._abort = True
        if not magnifier.available():
            log.warning("zoom needs Windows")
            return
        self.factor = _clamp(float(params.get("factor", 2.0)), 1.2, 6.0)
        self.ease = _clamp(float(params.get("ease", 1.5)), 0.0, 5.0)
        self.fx = _clamp(float(params.get("focus_x", 0.5)), 0.0, 1.0)
        self.fy = _clamp(float(params.get("focus_y", 0.5)), 0.0, 1.0)
        if not magnifier.begin("zoom"):
            return
        self._abort = False
        self.t0 = time.monotonic()
        self._focus, self._focus_at = None, 0.0
        self._apply(self.t0)

    def tick(self, now):
        if not self._abort:
            self._apply(now)

    def done(self):
        return self._abort

    def stop(self):
        if self._abort:
            return
        magnifier.set_transform(1.0, 0, 0)
        magnifier.end("zoom")

    def _focus_point(self, now):
        if self._focus is None or now - self._focus_at > 0.5:     # window lookup is slow; refresh twice a second
            l, t, r, b = self.ctx.target.physical()
            self._focus = (l + self.fx * (r - l), t + self.fy * (b - t))
            self._focus_at = now
        return self._focus

    def _apply(self, now):
        remaining = (self.ends_at - now) if self.ends_at else 1e9
        amount = envelope(now - self.t0, remaining, self.ease)
        factor = 1.0 + (self.factor - 1.0) * amount
        sw, sh = magnifier.screen_size()
        fx, fy = self._focus_point(now)
        x, y = zoom_view(sw, sh, factor, fx, fy)
        magnifier.set_transform(factor, x, y)
