"""Picture-in-picture: captures the game window and shows a small (optionally mirrored/flipped/delayed) copy."""
from __future__ import annotations

import logging
import time

from PySide6.QtGui import QColor, QPainter, QPen

from capture import CaptureLoop
from delaybuf import DelayBuffer
from manager import Effect
from overlay import OverlayWidget, exclude_when_ready

log = logging.getLogger("overlay.pip")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class _PipWidget(OverlayWidget):
    def __init__(self):
        super().__init__(translucent=False, click_through=False)   # non-layered, so Windows can exclude it from capture
        self.frame = None

    def paintEvent(self, _):
        p = QPainter(self)
        if self.frame is not None:
            p.drawImage(self.rect(), self.frame)
        else:
            p.fillRect(self.rect(), QColor(0, 0, 0))
        p.setPen(QPen(QColor(255, 255, 255), 3))
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))


class PipEffect(Effect):
    """params: scale (0.1-0.6, default 0.3), corner (tl|tr|bl|br), mode (normal|mirror|flip),
    delay (seconds, 0-5), fps (5-30)"""
    name = "pip"

    def start(self, params):
        self._loop, self.w, self._stopped = None, None, False
        try:
            import mss  # noqa: F401
        except ImportError:
            log.warning("pip needs `pip install mss`")
            return
        self.scale = _clamp(float(params.get("scale", 0.3)), 0.1, 0.6)
        self.corner = params.get("corner", "br")
        self.mode = params.get("mode", "mirror")
        self.delay = _clamp(float(params.get("delay", 0)), 0, 5)
        self.fps = _clamp(int(params.get("fps", 20)), 5, 30)
        self.buf = DelayBuffer()
        self.w = _PipWidget()
        self._sync()
        self.w.show()
        exclude_when_ready(self.w, self._begin_capture)   # capture only starts once we're hidden from it

    def _begin_capture(self, ok):
        if self._stopped:
            return
        if not ok:
            log.warning("PiP could not be hidden from screen capture; it may show itself where it overlaps the game")
        self._last_sync = time.monotonic()
        self._loop = CaptureLoop(lambda: self._shared["region"], lambda: self._shared["size"],
                                 self.buf, self.fps, self.mode)
        self._loop.start()

    def tick(self, now):
        if self._loop is None:
            return
        if now - self._last_sync > 1.0:       # follow the emulator window
            self._sync()
            self._last_sync = now
        self.w.frame = self.buf.get(now, self.delay)
        self.w.update()

    def stop(self):
        self._stopped = True
        if self._loop is not None:
            self._loop.stop()
        if self.w is not None:
            self.w.close()

    def _sync(self):
        r = self.ctx.target.rect()                       # DIPs, for placing the widget
        pw, ph = max(1, int(r.width() * self.scale)), max(1, int(r.height() * self.scale))
        m = 16
        x = r.left() + m if "l" in self.corner else r.right() - pw - m
        y = r.top() + m if "t" in self.corner else r.bottom() - ph - m
        self.w.setGeometry(x, y, pw, ph)
        l, t, rr, b = self.ctx.target.physical()         # physical pixels, for capturing
        self._shared = {"region": (l, t, rr - l, b - t),
                        "size": (max(1, int((rr - l) * self.scale)), max(1, int((b - t) * self.scale)))}