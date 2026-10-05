"""Rotated screen: a capture of the game window, redrawn rotated on top of it (the real window stays upright
underneath, so inputs are unchanged). Needs capture-exclusion to work, otherwise it would capture itself."""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter

from capture import CaptureLoop
from delaybuf import DelayBuffer
from manager import Effect
from overlay import OverlayWidget, exclude_from_capture
from viewmath import envelope, rotated_fit_scale

log = logging.getLogger("overlay.rotate")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class _RotateWidget(OverlayWidget):
    def __init__(self):
        super().__init__(translucent=False)
        self.frame = None
        self.theta = 0.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))     # hides the real window underneath
        if self.frame is None:
            return
        w, h = self.width(), self.height()
        s = rotated_fit_scale(w, h, self.theta, w, h)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.translate(w / 2, h / 2)
        p.rotate(self.theta)
        p.scale(s, s)
        p.drawImage(QRectF(-w / 2, -h / 2, w, h), self.frame)


class RotateEffect(Effect):
    """params: angle (degrees, default 180), spin (degrees/second added over time, +-45 max, default 0),
    ease (seconds, 0-5, default 1.5), mirror (true/false), fps (10-60, default 30), quality (0.4-1.0, default 1.0).
    Shows a copy of the game that lags a frame or two behind; lower fps/quality if your PC struggles."""
    name = "rotate"

    def start(self, params):
        self._abort, self._loop = True, None
        try:
            import mss  # noqa: F401
        except ImportError:
            log.warning("rotate needs `pip install mss`")
            return
        self.angle = float(params.get("angle", 180))
        self.spin = _clamp(float(params.get("spin", 0)), -45.0, 45.0)    # slow on purpose (photosensitivity)
        self.ease = _clamp(float(params.get("ease", 1.5)), 0.0, 5.0)
        self.quality = _clamp(float(params.get("quality", 1.0)), 0.4, 1.0)
        fps = _clamp(int(params.get("fps", 30)), 10, 60)
        mode = "mirror" if params.get("mirror") else "normal"

        self.buf = DelayBuffer()
        self.w = _RotateWidget()
        self._sync()
        self.w.show()
        if not exclude_from_capture(self.w):
            log.error("rotate cancelled: Windows would not hide the overlay from capture, so it would "
                      "capture itself. See the SetWindowDisplayAffinity warning above.")
            self.w.close()
            return
        self._abort = False
        self.t0 = self._last_sync = time.monotonic()
        self._loop = CaptureLoop(lambda: self._shared["region"], lambda: self._shared["size"],
                                 self.buf, fps, mode)
        self._loop.start()

    def tick(self, now):
        if self._abort:
            return
        if now - self._last_sync > 1.0:
            self._sync()
            self._last_sync = now
        elapsed = now - self.t0
        remaining = (self.ends_at - now) if self.ends_at else 1e9
        amount = envelope(elapsed, remaining, self.ease)
        self.w.theta = amount * (self.angle + self.spin * elapsed)
        self.w.frame = self.buf.get(now, 0)
        self.w.update()

    def done(self):
        return self._abort

    def stop(self):
        if self._loop is not None:
            self._loop.stop()
            self.w.close()

    def _sync(self):
        self.w.setGeometry(self.ctx.target.rect())
        l, t, r, b = self.ctx.target.physical()
        q = self.quality
        self._shared = {"region": (l, t, r - l, b - t),
                        "size": (max(1, int((r - l) * q)), max(1, int((b - t) * q)))}
