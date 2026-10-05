"""Effect manager: stacking, queueing, caps, cooldowns, cleanse, kill switch.
Everything here runs on the Qt main thread. Other threads only emit signals."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("overlay.manager")

DEFAULT_LIMITS = {"max_concurrent": 2, "max_duration": 60.0}


class Effect:
    """Base class for effect plugins."""
    name = "base"
    ends_at: float | None = None   # set by the manager; lets effects ease out before they end

    def __init__(self, ctx):
        self.ctx = ctx

    def start(self, params: dict) -> None: ...
    def stop(self) -> None: ...
    def tick(self, now: float) -> None: ...
    def done(self) -> bool:
        """Return True to end early (e.g. a video clip finished)."""
        return False


@dataclass
class _Active:
    effect: Effect
    ends_at: float
    cooldown: float


class EffectManager(QObject):
    request = Signal(str, object)  # (effect name, params) - safe to emit from any thread
    kill = Signal()                # panic button - safe to emit from any thread

    def __init__(self, registry: dict, ctx, limits: dict | None = None):
        super().__init__()
        self.registry = registry
        self.ctx = ctx
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.active: dict[str, _Active] = {}
        self.queue: deque[tuple[str, dict]] = deque()
        self.cooldown_until: dict[str, float] = {}

        self.request.connect(self._on_request)
        self.kill.connect(lambda: self.clear_all())
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ---- incoming ----
    def _on_request(self, name: str, params: dict) -> None:
        params = params or {}
        if name == "cleanse":
            # optional `only: [effect, ...]`; no `only` clears everything
            self.clear_all(only=params.get("only"))
            return
        if name not in self.registry:
            log.warning("unknown effect %r", name)
            return
        self.queue.append((name, params))
        self._drain()

    def clear_all(self, only: list[str] | None = None) -> None:
        names = list(self.active) if only is None else [n for n in only if n in self.active]
        for n in names:
            self._stop(n, apply_cooldown=False)
        # cleanse also drops anything still waiting in the queue
        self.queue = deque(q for q in self.queue if only is not None and q[0] not in only)
        log.info("cleansed %s", "all" if only is None else only)

    # ---- internals ----
    def _drain(self) -> None:
        now = time.monotonic()
        waiting: deque[tuple[str, dict]] = deque()
        while self.queue:
            name, params = self.queue.popleft()
            dur = min(float(params.get("duration", 20)), self.limits["max_duration"])
            if name in self.active:  # stacking rule: extend, but never past max_duration from now
                a = self.active[name]
                a.ends_at = min(a.ends_at + dur, now + self.limits["max_duration"])
                continue
            if len(self.active) >= self.limits["max_concurrent"] or now < self.cooldown_until.get(name, 0):
                waiting.append((name, params))
                continue
            eff = self.registry[name](self.ctx)
            eff.ends_at = now + dur
            try:
                eff.start(params)
            except Exception:
                log.exception("effect %s failed to start", name)
                continue
            self.active[name] = _Active(eff, now + dur, float(params.get("cooldown", 0)))
            if eff.done():
                log.warning("%s could not run (see the messages above); it will be cleaned up now", name)
            else:
                log.info("started %s for %.0fs", name, dur)
        self.queue = waiting

    def _stop(self, name: str, apply_cooldown: bool = True) -> None:
        a = self.active.pop(name, None)
        if not a:
            return
        try:
            a.effect.stop()
        except Exception:
            log.exception("effect %s failed to stop", name)
        if apply_cooldown and a.cooldown:
            self.cooldown_until[name] = time.monotonic() + a.cooldown

    def _tick(self) -> None:
        now = time.monotonic()
        for name, a in list(self.active.items()):
            a.effect.ends_at = a.ends_at
            if now >= a.ends_at or a.effect.done():
                self._stop(name)
            else:
                try:
                    a.effect.tick(now)
                except Exception:
                    log.exception("effect %s tick failed; stopping it", name)
                    self._stop(name)
        if self.queue:
            self._drain()