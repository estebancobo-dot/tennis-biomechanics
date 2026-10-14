"""Cuts with TransNetV2: reference windowing, peaks, the grid of the cheap pass and the fallback to the
histograms. The model itself is only needed by the last test (skipped when models/transnetv2.onnx is
missing; scripts/setup_models.py makes it)."""
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tennisbio.scenes import (TN_WINDOW, CutStream, analyse_video, boundaries_from_probs, cut_probabilities,
                              grid_index, to_grid)

MODEL = Path(__file__).resolve().parents[1] / "models" / "transnetv2.onnx"


def marked(n):
    """48×27 frames whose first pixel carries a per-frame value (the fake model's 'probability')."""
    fr = np.zeros((n, 27, 48, 3), np.uint8)
    fr[:, 0, 0, 0] = np.arange(n) % 251
    return list(fr)


def echo(windows):
    """Fake model: each frame's probability is its own mark; checks the shape of every window."""
    assert windows.dtype == np.uint8 and windows.shape[1:] == (TN_WINDOW, 27, 48, 3)
    return windows[:, :, 0, 0, 0].astype(np.float32)


@pytest.mark.parametrize("n", [1, 24, 49, 50, 51, 100, 101, 237])
@pytest.mark.parametrize("batch", [1, 3])
def test_windowing_returns_one_aligned_value_per_frame(n, batch):
    p = cut_probabilities(marked(n), echo, batch=batch)
    assert np.array_equal(p, np.arange(n) % 251)


def test_reference_window_count():
    calls = []
    cut_probabilities(marked(120), lambda w: calls.append(len(w)) or np.zeros((len(w), TN_WINDOW)), batch=1)
    # reference: 25 + 120 + 30 padded frames → windows at 0, 50, 100 (each keeps its 50 central frames)
    assert len(calls) == 3


def test_failure_is_reported_not_raised_in_the_stream():
    st = CutStream(lambda w: (_ for _ in ()).throw(RuntimeError("driver")), batch=1)
    for f in marked(150):
        st.add(f)
    assert len(st.finish()) == 0 and isinstance(st.error, RuntimeError)


def test_peaks():
    p = np.zeros(40)
    p[9] = 0.9                                   # hard cut: last frame of the outgoing shot
    p[20:25] = [0.6, 0.7, 0.9, 0.8, 0.55]        # dissolve: one boundary, after its peak
    p[30] = 0.5                                  # not above the threshold
    p[39] = 0.99                                 # at the very end: no shot after it
    assert boundaries_from_probs(p) == [10, 23]
    assert boundaries_from_probs(np.zeros(10)) == []


def test_cuts_to_the_cheap_pass_grid():
    assert [grid_index(k, 25, 10) for k in range(5)] == [0, 3, 5, 8, 10]
    # cut at 25-fps frame 75 (3.0 s) → 10-fps frame 30; frame 76 → the next grid frame at or after it
    assert to_grid([75, 76, 0], 25, 10, 100) == [30, 31]
    assert to_grid([], 25, 10, 100) == []


def court(k=0):
    img = np.full((90, 160, 3), (40, 120, 40), np.uint8)
    img[25:85, 30 + k % 3:130 + k % 3] = (160, 90, 40)
    return img


def closeup():
    img = np.full((90, 160, 3), (30, 30, 30), np.uint8)
    img[10:90, 40:120] = (120, 150, 210)                         # skin tones fill the frame
    img[0:30, 50:110] = (40, 40, 160)                            # red cap
    return img


def jump_model(windows):
    """Fake TransNetV2: a transition on the last frame before a large change of the image."""
    w = windows.astype(np.int16)
    d = np.abs(np.diff(w, axis=1)).mean(axis=(2, 3, 4))
    return np.concatenate([(d > 20).astype(np.float32), np.zeros((len(w), 1), np.float32)], 1)


def test_analyse_video_with_model_cuts_on_the_grid_and_keeps_main_camera():
    frames = [court(k) for k in range(75)] + [closeup() for _ in range(50)] + [court(k) for k in range(75)]
    info = {}
    shots, mask = analyse_video(frames, cut_model=jump_model, fps=10, fast_fps=25, info=info)
    assert info["detector"] == "transnetv2" and info["cuts"] == 2
    assert [s.start for s in shots] == [0, 30, 50] and len(mask) == 80
    assert mask[:30].all() and not mask[30:50].any() and mask[50:].all()


def test_analyse_video_falls_back_to_histograms_when_the_model_fails():
    def broken(_):
        raise RuntimeError("DirectML")
    frames = [court(k) for k in range(75)] + [closeup() for _ in range(50)] + [court(k) for k in range(75)]
    info = {}
    shots, mask = analyse_video(frames, cut_model=broken, fps=10, fast_fps=25, info=info)
    assert info["detector"] == "histogram" and "DirectML" in info["error"]
    assert len(mask) == 80 and shots[0].start == 0 and shots[-1].end == 80


@pytest.mark.skipif(not MODEL.exists(), reason="sin models/transnetv2.onnx (scripts/setup_models.py)")
def test_transnetv2_finds_the_hard_cuts_of_a_video(tmp_path):
    from tennisbio.io.video import probe, read_frames
    from tennisbio.scenes import CutModel

    video = tmp_path / "cuts.mp4"
    srcs = ["testsrc", "smptebars", "rgbtestsrc", "testsrc2"]          # 2 s each, hard cuts at 2, 4 and 6 s
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for s in srcs:
        cmd += ["-f", "lavfi", "-i", f"{s}=duration=2:size=640x360:rate=50"]
    cmd += ["-filter_complex", "".join(f"[{i}:v]" for i in range(len(srcs))) + f"concat=n={len(srcs)}:v=1:a=0",
            "-c:v", "libx264", "-preset", "ultrafast", str(video)]
    subprocess.run(cmd, check=True)
    info = {}
    shots, _ = analyse_video(read_frames(probe(video), width=160, fps=25), cut_model=CutModel(MODEL, "cpu"),
                             fps=10, fast_fps=25, info=info)
    assert info["detector"] == "transnetv2"
    starts = [s.start for s in shots]
    assert len(shots) == 4 and all(any(abs(s - c) <= 1 for s in starts) for c in (20, 40, 60))
