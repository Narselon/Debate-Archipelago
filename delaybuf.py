"""Thread-safe delay line for PiP frames (capture thread pushes, UI thread reads)."""
from __future__ import annotations

import threading
from collections import deque


class DelayBuffer:
    def __init__(self):
        self._items = deque()
        self._current = None
        self._lock = threading.Lock()

    def push(self, t: float, item) -> None:
        with self._lock:
            self._items.append((t, item))

    def get(self, now: float, delay: float):
        """Newest frame captured at or before now-delay (None until one exists)."""
        target = now - delay
        with self._lock:
            while self._items and self._items[0][0] <= target:
                self._current = self._items.popleft()[1]
            return self._current
