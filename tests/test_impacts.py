

def test_the_peak_picker_gives_librosas_picks_without_numba(monkeypatch):
    """22-11: Sinner's fine pass died of a segmentation fault in librosa's numba-compiled peak picker, in the processes
    that had loaded TensorFlow (MeTRAbs). impacts.peak_pick gives the same picks bit for bit (float32 and float64,
    spikes and ties; 6.000 cases checked when it was written) and the analysis no longer calls librosa's."""
    import librosa
    import numpy as _np

    from tennisbio import impacts
    rng = _np.random.default_rng(7)
    for dt in (_np.float32, _np.float64):
        for i in range(150):
            n = int(rng.integers(1, 900))
            x = [rng.standard_normal(n), _np.abs(rng.standard_normal(n)) ** 3, _np.round(rng.standard_normal(n), 1)][i % 3]
            x = x.astype(dt)
            w = int(rng.integers(1, 60))
            kw = dict(pre_max=w, post_max=w, pre_avg=3 * w, post_avg=3 * w, delta=float(rng.choice([0.0, 0.35, 1.0])), wait=3 * w)
            assert _np.array_equal(librosa.util.peak_pick(x, **kw), impacts.peak_pick(x, **kw)), (dt, n, kw)
    assert impacts.peak_pick(_np.zeros(0, _np.float32), pre_max=1, post_max=1, pre_avg=1, post_avg=1, delta=0, wait=1).size == 0

    def boom(*a, **k):
        raise AssertionError("librosa.util.peak_pick (numba) called")
    monkeypatch.setattr(librosa.util, "peak_pick", boom)
    sr = 22050
    y = (_np.random.default_rng(1).standard_normal(sr * 2) * 0.01).astype(_np.float32)
    y[sr // 2:sr // 2 + 200] += _np.random.default_rng(2).standard_normal(200).astype(_np.float32)   # a sharp hit
    t, s = impacts.audio_onsets(y, sr)
    assert len(t) >= 1 and abs(float(t[0]) - 0.5) < 0.05
