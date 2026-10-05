"""Pure geometry/timing helpers for zoom and rotate (no Qt, no Windows) so they can be unit-tested."""
from __future__ import annotations

import math


def smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def envelope(elapsed: float, remaining: float, ease: float) -> float:
    """0 -> 1 over `ease` seconds after the start, and 1 -> 0 over the last `ease` seconds."""
    if ease <= 0:
        return 1.0
    return smoothstep(min(elapsed, remaining) / ease)


def zoom_view(screen_w: int, screen_h: int, factor: float, focus_x: float, focus_y: float) -> tuple:
    """Top-left corner of the visible area when magnifying by `factor` around a focus point,
    clamped so the view never leaves the screen."""
    vw, vh = screen_w / factor, screen_h / factor
    x = min(max(focus_x - vw / 2, 0), screen_w - vw)
    y = min(max(focus_y - vh / 2, 0), screen_h - vh)
    return int(round(x)), int(round(y))


def rotated_fit_scale(w: float, h: float, angle_deg: float, W: float, H: float) -> float:
    """Scale at which a w x h picture rotated by angle fits entirely inside a W x H window."""
    t = math.radians(angle_deg)
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return min(W / (w * c + h * s), H / (w * s + h * c))
