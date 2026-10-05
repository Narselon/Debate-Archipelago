from delaybuf import DelayBuffer


def test_no_delay_returns_latest():
    b = DelayBuffer()
    b.push(1.0, "a"); b.push(1.1, "b")
    assert b.get(1.2, 0) == "b"


def test_delay_returns_old_frame_then_catches_up():
    b = DelayBuffer()
    for i in range(10):
        b.push(i * 0.1, i)
    assert b.get(0.5, 2.0) is None          # nothing old enough yet
    assert b.get(2.35, 2.0) == 3            # newest frame captured at or before t=0.35
    assert b.get(2.35, 2.0) == 3            # stable on repeat calls
    assert b.get(3.0, 2.0) == 9


def test_holds_last_frame_when_capture_stalls():
    b = DelayBuffer()
    b.push(0.0, "x")
    assert b.get(5.0, 1.0) == "x"
    assert b.get(9.0, 1.0) == "x"
