from colormath import GRAY, IDENTITY, INVERT, apply_rgb, compose, lerp


def close(a, b):
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def test_invert():
    assert close(apply_rgb((1, 1, 1), INVERT), (0, 0, 0))
    assert close(apply_rgb((0.2, 0.5, 1.0), INVERT), (0.8, 0.5, 0.0))


def test_gray_of_red():
    assert close(apply_rgb((1, 0, 0), GRAY), (0.3, 0.3, 0.3))


def test_invert_twice_is_identity():
    assert close(compose([INVERT, INVERT]), IDENTITY)


def test_gray_and_invert_commute():
    c = (0.9, 0.1, 0.4)
    assert close(apply_rgb(c, compose([GRAY, INVERT])), apply_rgb(c, compose([INVERT, GRAY])))


def test_lerp_endpoints():
    assert close(lerp(IDENTITY, GRAY, 0), IDENTITY)
    assert close(lerp(IDENTITY, GRAY, 1), GRAY)
