"""Checks which overlay windows Windows can hide from screen capture (needed by PiP and rotate).
Run:  python tools/capture_selftest.py        (takes ~15 s; opens magenta test windows; don't touch the mouse)"""
from __future__ import annotations

import sys
import time
from pathlib import Path

if sys.platform != "win32":
    print("Windows only.")
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mss  # noqa: E402
from PySide6.QtGui import QColor, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from overlay import exclude_from_capture, exclude_when_ready, prepare  # noqa: E402

MAGENTA = (255, 0, 255)
app = QApplication(sys.argv)


class Probe(QWidget):
    def __init__(self, click_through: bool, fullscreen: bool):
        super().__init__()
        prepare(self, translucent=False, click_through=click_through)
        self.setGeometry(app.primaryScreen().geometry() if fullscreen else self.geometry().adjusted(0, 0, 0, 0))
        if not fullscreen:
            self.setGeometry(200, 200, 300, 200)

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), QColor(*MAGENTA))


def pump(seconds: float = 0.0, until=None):
    end = time.time() + (seconds or 3.0)
    while time.time() < end and not (until and until()):
        app.processEvents()
        time.sleep(0.01)


def magenta_visible(w: QWidget) -> bool:
    g, dpr = w.geometry(), w.devicePixelRatio()
    cx, cy = int((g.x() + g.width() / 2) * dpr), int((g.y() + g.height() / 2) * dpr)
    maker = getattr(mss, "MSS", None) or mss.mss
    with maker() as sct:
        shot = sct.grab({"left": cx - 4, "top": cy - 4, "width": 8, "height": 8})
    return (shot.bgra[2], shot.bgra[1], shot.bgra[0]) == MAGENTA


def run_case(click_through: bool, fullscreen: bool, mode: str) -> tuple:
    w = Probe(click_through, fullscreen)
    w.show()
    if mode == "after 0.5s":
        pump(0.5)
    if mode == "retry helper":
        done = []
        exclude_when_ready(w, done.append)
        pump(until=lambda: done)
        accepted = bool(done and done[0])
    else:
        accepted = exclude_from_capture(w, log_failure=True)
    pump(0.6)
    hidden = not magenta_visible(w)
    w.close()
    pump(0.3)
    return accepted, hidden


print(f"{'window':<14}{'size':<12}{'when asked':<14}{'Windows said':<16}{'hidden in capture'}")
rows = []
for click_through in (False, True):
    for fullscreen in (False, True):
        for mode in ("immediate", "after 0.5s", "retry helper"):
            accepted, hidden = run_case(click_through, fullscreen, mode)
            rows.append((click_through, fullscreen, mode, accepted, hidden))
            print(f"{'click-through' if click_through else 'plain':<14}{'fullscreen' if fullscreen else 'small':<12}"
                  f"{mode:<14}{'accepted' if accepted else 'REFUSED':<16}{'yes' if hidden else 'NO'}")

ok_plain = all(r[4] for r in rows if not r[0] and r[2] == "retry helper")
ok_ct = all(r[4] for r in rows if r[0] and r[2] == "retry helper")
print("\nPiP/rotate (plain window + retry helper):", "PASS" if ok_plain else "FAIL")
print("Same with click-through windows:", "PASS (click-through can be turned back on)" if ok_ct else "FAIL")