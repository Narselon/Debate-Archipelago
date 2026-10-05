from viewmath import envelope, rotated_fit_scale, smoothstep, zoom_view


def test_smoothstep_bounds():
    assert smoothstep(-1) == 0 and smoothstep(2) == 1 and smoothstep(0.5) == 0.5


def test_envelope_eases_in_and_out():
    assert envelope(0, 20, 2) == 0
    assert 0 < envelope(1, 19, 2) < 1
    assert envelope(10, 10, 2) == 1
    assert envelope(19, 1, 2) < 1 and envelope(20, 0, 2) == 0
    assert envelope(0, 0, 0) == 1                        # ease 0 = instant on/off


def test_zoom_view_centres_on_focus():
    # 2x zoom of a 1920x1080 screen shows a 960x540 area; centred on (960, 540) it starts at (480, 270)
    assert zoom_view(1920, 1080, 2.0, 960, 540) == (480, 270)


def test_zoom_view_never_leaves_screen():
    assert zoom_view(1920, 1080, 2.0, 0, 0) == (0, 0)
    assert zoom_view(1920, 1080, 2.0, 1920, 1080) == (960, 540)
    assert zoom_view(1920, 1080, 1.0, 500, 500) == (0, 0)


def test_rotated_fit_scale():
    assert abs(rotated_fit_scale(960, 720, 0, 960, 720) - 1) < 1e-9
    assert abs(rotated_fit_scale(960, 720, 180, 960, 720) - 1) < 1e-9
    assert abs(rotated_fit_scale(960, 720, 90, 960, 720) - 0.75) < 1e-9     # 4:3 on its side letterboxes
    assert rotated_fit_scale(500, 500, 45, 500, 500) < 0.75                 # diagonal needs ~0.707
