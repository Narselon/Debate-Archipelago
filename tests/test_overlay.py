import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from overlay import prepare  # noqa: E402


_app = QApplication.instance() or QApplication([])   # module-level so it isn't garbage-collected mid-test


def flags(**kw):
    w = QWidget()
    prepare(w, **kw)
    return w


def test_click_through_flag_is_optional():
    T = Qt.WindowType.WindowTransparentForInput
    assert flags(click_through=True).windowFlags() & T
    assert not (flags(click_through=False).windowFlags() & T)


def test_overlays_never_take_focus():
    F = Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags(click_through=False).windowFlags() & F
    assert flags(click_through=True).windowFlags() & F


import time  # noqa: E402

import overlay  # noqa: E402

FAST = (0, 1, 1, 1, 1, 1)


def pump(cond, timeout=3.0):
    end = time.time() + timeout
    while not cond() and time.time() < end:
        _app.processEvents()
        time.sleep(0.005)


def test_exclusion_is_retried_until_accepted(monkeypatch):
    calls, results = [], iter([False, False, True])
    monkeypatch.setattr(overlay, "exclude_from_capture", lambda w, log_failure=False: calls.append(log_failure) or next(results))
    w = QWidget(); w.show()
    done = []
    overlay.exclude_when_ready(w, done.append, FAST)
    pump(lambda: done)
    assert done == [True] and calls == [False, False, False]


def test_exclusion_gives_up_and_only_logs_the_last_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(overlay, "exclude_from_capture", lambda w, log_failure=False: calls.append(log_failure) or False)
    w = QWidget(); w.show()
    done = []
    overlay.exclude_when_ready(w, done.append, FAST)
    pump(lambda: done)
    assert done == [False] and len(calls) == 6 and calls[-1] is True and not any(calls[:-1])


def test_closed_window_stops_retrying_quietly(monkeypatch):
    calls = []
    monkeypatch.setattr(overlay, "exclude_from_capture", lambda w, log_failure=False: calls.append(1) or False)
    w = QWidget(); w.show(); w.close()
    done = []
    overlay.exclude_when_ready(w, done.append, FAST)
    pump(lambda: done, timeout=0.3)
    assert done == [] and calls == []