import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication  # noqa: E402

import manager  # noqa: E402
from manager import Effect, EffectManager  # noqa: E402


class Log:
    events = []


def make(name):
    class Fx(Effect):
        def start(self, params): Log.events.append(("start", name))
        def stop(self): Log.events.append(("stop", name))
    return Fx


@pytest.fixture
def env(monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    Log.events = []
    clock = {"t": 1000.0}
    monkeypatch.setattr(manager.time, "monotonic", lambda: clock["t"])
    def make_mgr(**limits):
        m = EffectManager({"a": make("a"), "b": make("b")}, None, limits)
        m._timer.stop()   # drive ticks by hand
        return m
    yield make_mgr, clock, app


def test_expiry(env):
    mk, clock, _ = env
    m = mk()
    m._on_request("a", {"duration": 5})
    assert "a" in m.active
    clock["t"] += 6; m._tick()
    assert "a" not in m.active and ("stop", "a") in Log.events


def test_stack_extends_but_is_capped(env):
    mk, clock, _ = env
    m = mk(max_duration=10)
    m._on_request("a", {"duration": 8}); m._on_request("a", {"duration": 8})
    assert m.active["a"].ends_at <= clock["t"] + 10
    assert Log.events.count(("start", "a")) == 1


def test_concurrency_queue(env):
    mk, clock, _ = env
    m = mk(max_concurrent=1)
    m._on_request("a", {"duration": 5}); m._on_request("b", {"duration": 5})
    assert list(m.active) == ["a"] and len(m.queue) == 1
    clock["t"] += 6; m._tick()
    assert list(m.active) == ["b"]


def test_cooldown_delays_retrigger(env):
    mk, clock, _ = env
    m = mk()
    m._on_request("a", {"duration": 5, "cooldown": 30})
    clock["t"] += 6; m._tick()
    m._on_request("a", {"duration": 5})
    assert "a" not in m.active and len(m.queue) == 1
    clock["t"] += 31; m._tick()
    assert "a" in m.active


def test_cleanse_clears_active_and_queue(env):
    mk, clock, _ = env
    m = mk(max_concurrent=1)
    m._on_request("a", {"duration": 50}); m._on_request("b", {"duration": 50})
    m._on_request("cleanse", {})
    assert not m.active and not m.queue


def test_targeted_cleanse(env):
    mk, clock, _ = env
    m = mk()
    m._on_request("a", {"duration": 50}); m._on_request("b", {"duration": 50})
    m._on_request("cleanse", {"only": ["a"]})
    assert list(m.active) == ["b"]


def test_unknown_effect_ignored(env):
    mk, *_ = env
    m = mk()
    m._on_request("nope", {})
    assert not m.active
