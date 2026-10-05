"""Background screen-capture loop shared by PiP and rotate. Frames are pushed into a DelayBuffer."""
from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage

log = logging.getLogger("overlay.capture")


def _default_factory():
    import mss
    return mss.mss()


class CaptureLoop:
    """region_fn() -> (left, top, width, height) in physical pixels; size_fn() -> (w, h) of output frames.
    Both are called from the capture thread, so they must just read values the main thread keeps updated.
    mode: normal | mirror | flip"""

    def __init__(self, region_fn, size_fn, buf, fps=20, mode="normal", sct_factory=None):
        self.region_fn, self.size_fn, self.buf = region_fn, size_fn, buf
        self.fps, self.mode = fps, mode
        self._factory = sct_factory or _default_factory
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)

    def _run(self):
        period, warned = 1.0 / self.fps, False
        try:
            sct = self._factory()
        except Exception as e:
            log.warning("screen capture unavailable: %s", e)
            return
        with sct:
            while not self._stop.is_set():
                t0 = time.monotonic()
                try:
                    l, t, w, h = self.region_fn()
                    pw, ph = self.size_fn()
                    shot = sct.grab({"left": l, "top": t, "width": w, "height": h})
                    # .copy() detaches from the capture buffer (QImage doesn't own it)
                    img = QImage(shot.bgra, shot.width, shot.height, shot.width * 4,
                                 QImage.Format.Format_RGB32).copy()
                    if img.size() != QSize(pw, ph):
                        img = img.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.FastTransformation)
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
