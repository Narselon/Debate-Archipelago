import pytest
from remap import PadRemap, PadState, BUTTON_MASKS as M


def test_dpad_and_ab_swap():
    r = PadRemap({"up": "down", "down": "up", "left": "right", "right": "left", "a": "b", "b": "a"})
    s = PadState(buttons=M["up"] | M["a"] | M["start"])
    assert r.apply(s).buttons == M["down"] | M["b"] | M["start"]   # untouched buttons pass through


def test_swap_is_involution():
    r = PadRemap({"a": "b", "b": "a"})
    s = PadState(buttons=M["a"] | M["x"])
    assert r.apply(r.apply(s)) == s


def test_axis_invert_and_clamp():
    r = PadRemap(axes={"lx": "invert", "ly": "invert"})
    out = r.apply(PadState(lx=-32768, ly=1000, rx=500))
    assert (out.lx, out.ly, out.rx) == (32767, -1000, 500)


def test_empty_remap_is_identity():
    s = PadState(buttons=M["a"], lt=10, lx=5)
    assert PadRemap().apply(s) == s


def test_bad_names_fail_early():
    with pytest.raises(ValueError):
        PadRemap({"jump": "a"})
    with pytest.raises(ValueError):
        PadRemap(axes={"lx": "flip"})
