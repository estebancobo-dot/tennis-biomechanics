import numpy as np

from tennisbio.scenes import analyse_video


def court_frame(shift=0):
    img = np.full((90, 160, 3), (40, 120, 40), np.uint8)          # green surround (BGR)
    img[25:85, 30 + shift:130 + shift] = (160, 90, 40)            # blue court, large
    img[25:27, 30:130] = 255                                       # a line
    return img


def closeup_frame():
    img = np.full((90, 160, 3), (30, 30, 30), np.uint8)
    img[10:90, 40:120] = (120, 150, 210)                           # skin tones fill the frame
    img[0:30, 50:110] = (40, 40, 160)                              # red cap
    return img


def test_cut_dissolve_and_main_camera():
    frames = [court_frame(k % 3) for k in range(30)]               # main camera
    frames += [closeup_frame() for _ in range(20)]                 # hard cut to a close-up
    a, b = closeup_frame().astype(float), court_frame().astype(float)
    frames += [((1 - w) * a + w * b).astype(np.uint8) for w in np.linspace(0, 1, 16)]   # dissolve back
    frames += [court_frame(k % 3) for k in range(30)]
    shots, mask = analyse_video(frames)
    starts = [s.start for s in shots]
    assert any(abs(s - 30) <= 1 for s in starts)                   # the hard cut
    assert any(55 <= s <= 62 for s in starts)                      # the dissolve, around its middle
    assert mask[:30].all() and not mask[32:48].any() and mask[-25:].all()
