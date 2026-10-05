"""Pure-python remap logic (no Windows deps) so it can be unit-tested anywhere."""
from __future__ import annotations

from dataclasses import dataclass

# XInput button bits (vgamepad uses the same values)
BUTTON_MASKS = {
    "up": 0x0001, "down": 0x0002, "left": 0x0004, "right": 0x0008,
    "start": 0x0010, "back": 0x0020, "ls": 0x0040, "rs": 0x0080,
    "lb": 0x0100, "rb": 0x0200, "a": 0x1000, "b": 0x2000, "x": 0x4000, "y": 0x8000,
}
AXES = ("lx", "ly", "rx", "ry")


@dataclass(frozen=True)
class PadState:
    buttons: int = 0
    lt: int = 0
    rt: int = 0
    lx: int = 0
    ly: int = 0
    rx: int = 0
    ry: int = 0


def _invert(v: int) -> int:
    return max(-32768, min(32767, -v))


class PadRemap:
    """buttons: {physical: output}. List both directions for a swap.
    axes: {lx|ly|rx|ry: "invert"}."""

    def __init__(self, buttons: dict | None = None, axes: dict | None = None):
        self.pairs = []
        for src, dst in (buttons or {}).items():
            if src not in BUTTON_MASKS or dst not in BUTTON_MASKS:
                raise ValueError(f"unknown button in remap: {src!r} -> {dst!r}")
            self.pairs.append((BUTTON_MASKS[src], BUTTON_MASKS[dst]))
        self.invert = set()
        for axis, mode in (axes or {}).items():
            if axis not in AXES or mode != "invert":
                raise ValueError(f"unsupported axis remap: {axis!r}: {mode!r}")
            self.invert.add(axis)
        self.touched = 0
        for src, _ in self.pairs:
            self.touched |= src

    def apply(self, s: PadState) -> PadState:
        out = s.buttons & ~self.touched
        for src, dst in self.pairs:
            if s.buttons & src:
                out |= dst
        axes = {a: (_invert(getattr(s, a)) if a in self.invert else getattr(s, a)) for a in AXES}
        return PadState(out, s.lt, s.rt, **axes)
