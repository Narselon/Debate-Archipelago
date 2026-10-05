import time

import pytest

pytest.importorskip("PySide6")

from capture import CaptureLoop  # noqa: E402
from delaybuf import DelayBuffer  # noqa: E402


class Shot:
    def __init__(self, w, h, px):
        self.width, self.height, self.bgra = w, h, px


class FakeSct:
    """4x2 screen whose first (top-left) pixel is pure red."""
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def grab(self, region):
        w, h = region["width"], region["height"]
        px = bytearray(w * h * 4)
        px[0:4] = bytes([0, 0, 255, 255])          # B, G, R, A
        return Shot(w, h, bytes(px))


def grab_one(mode, size=(4, 2)):
    buf = DelayBuffer()
    loop = CaptureLoop(lambda: (0, 0, 4, 2), lambda: size, buf, fps=30, mode=mode, sct_factory=FakeSct)
    loop.start(); time.sleep(0.3); loop.stop()
    return buf.get(time.monotonic() + 1, 0)


def red(img, x, y):
    return img.pixelColor(x, y).red() == 255


def test_normal_mirror_flip():
    n = grab_one("normal")
    assert (n.width(), n.height()) == (4, 2) and red(n, 0, 0) and not red(n, 3, 0)
    m = grab_one("mirror")
    assert red(m, 3, 0) and not red(m, 0, 0)
    f = grab_one("flip")
    assert red(f, 0, 1) and not red(f, 0, 0)


def test_scaled_output_size():
    img = grab_one("normal", size=(8, 4))
    assert (img.width(), img.height()) == (8, 4)


def test_missing_capture_backend_does_not_crash():
    def boom():
        raise RuntimeError("no display")
    buf = DelayBuffer()
    loop = CaptureLoop(lambda: (0, 0, 4, 2), lambda: (4, 2), buf, sct_factory=boom)
    loop.start(); time.sleep(0.2); loop.stop()
    assert buf.get(time.monotonic() + 1, 0) is None
