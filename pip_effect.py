"""Picture-in-picture: captures the game window and shows a small (optionally mirrored/flipped/delayed) copy."""
from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from delaybuf import DelayBuffer
from manager import Effect
from overlay import OverlayWidget, exclude_from_capture

log = logging.getLogger("overlay.pip")


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class _PipWidget(OverlayWidget):
    def __init__(self):
        super().__init__()
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
        self._thread = None
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
        self._stop = threading.Event()
        self.w = _PipWidget()
        self._sync()
        self.w.show()
        exclude_from_capture(self.w)
        self._last_sync = time.monotonic()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def tick(self, now):
        if self._thread is None:
            return
        if now - self._last_sync > 1.0:       # follow the emulator window
            self._sync()
            self._last_sync = now
        self.w.frame = self.buf.get(now, self.delay)
        self.w.update()

    def stop(self):
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.w.close()

    # ---- main thread ----
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

    # ---- capture thread ----
    def _capture_loop(self):
        import mss
        period, warned = 1.0 / self.fps, False
        try:
            sct = mss.mss()
        except Exception as e:
            log.warning("screen capture unavailable: %s", e)
            return
        with sct:
            while not self._stop.is_set():
                t0 = time.monotonic()
                try:
                    l, t, w, h = self._shared["region"]
                    pw, ph = self._shared["size"]
                    shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
                    img = QImage(shot.bgra, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32)
                    img = img.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.FastTransformation)   # also detaches from shot.bgra
                    if self.mode == "mirror":
                        img = img.mirrored(True, False)
                    elif self.mode == "flip":
                        img = img.mirrored(False, True)
                    self.buf.push(t0, img)
                except Exception as e:
                    if not warned:
                        log.warning("capture failed: %s", e)
                        warned = True
                    time.sleep(0.5)
                self._stop.wait(max(0.0, period - (time.monotonic() - t0)))
