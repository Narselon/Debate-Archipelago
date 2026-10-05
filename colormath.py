"""5x5 color-matrix helpers for the Magnification API (row-vector convention: [r g b a 1] x M).
Pure python so it's testable anywhere."""
from __future__ import annotations

IDENTITY = [1, 0, 0, 0, 0,  0, 1, 0, 0, 0,  0, 0, 1, 0, 0,  0, 0, 0, 1, 0,  0, 0, 0, 0, 1]
GRAY = [0.3, 0.3, 0.3, 0, 0,  0.6, 0.6, 0.6, 0, 0,  0.1, 0.1, 0.1, 0, 0,  0, 0, 0, 1, 0,  0, 0, 0, 0, 1]
INVERT = [-1, 0, 0, 0, 0,  0, -1, 0, 0, 0,  0, 0, -1, 0, 0,  0, 0, 0, 1, 0,  1, 1, 1, 0, 1]


def lerp(a, b, k):
    return [(1 - k) * x + k * y for x, y in zip(a, b)]


def matmul(a, b):
    return [sum(a[i * 5 + k] * b[k * 5 + j] for k in range(5)) for i in range(5) for j in range(5)]


def compose(mats):
    out = IDENTITY
    for m in mats:
        out = matmul(out, m)
    return out


def apply_rgb(rgb, m):
    v = [rgb[0], rgb[1], rgb[2], 1.0, 1.0]
    return tuple(sum(v[i] * m[i * 5 + j] for i in range(5)) for j in range(3))
