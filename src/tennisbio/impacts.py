"""Ball-contact candidates: audio transients fused with wrist-speed peaks.

Audio alone is not enough (other courts, crowd, mic handling), and the wrist peak alone is
a few frames off contact. A contact confirmed by both is trusted; one seen only in the swing
is kept with lower confidence and goes to manual review.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks


def audio_onsets(y: np.ndarray, sr: int, band=(1000, 6000), delta=0.35, hop=128):
    """Times (s) and strengths of sharp broadband transients in the racket-impact band."""
    import librosa

    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    flux = np.maximum(0, np.diff(np.log1p(S[(f > band[0]) & (f < band[1])] * 50), axis=1)).sum(0)
    flux = (flux - np.median(flux)) / (np.percentile(flux, 99) - np.median(flux) + 1e-9)
    w = int(0.15 * sr / hop)
    pk = librosa.util.peak_pick(flux, pre_max=w, post_max=w, pre_avg=3 * w, post_avg=3 * w, delta=delta, wait=3 * w)
    return librosa.frames_to_time(pk + 1, sr=sr, hop_length=hop), flux[pk]


def swing_peaks(wrist_speed: np.ndarray, fps: float, min_gap=0.6, height=2.0, prominence=1.2) -> np.ndarray:
    """Frames where the dominant wrist (body-relative, body heights/s) peaks as in a swing."""
    v = np.nan_to_num(wrist_speed)
    pk, _ = find_peaks(v, distance=max(1, int(min_gap * fps)), height=height, prominence=prominence)
    return pk


@dataclass
class Impact:
    frame: int
    t: float
    source: str            # "audio+swing" or "swing"
    audio_offset_ms: int | None
    confidence: float


def fuse(swing_frames: np.ndarray, fps: float, onset_times: np.ndarray, tol=0.12) -> list[Impact]:
    """Snap each swing to the nearest audio transient within `tol` seconds when there is one."""
    out = []
    for f in swing_frames:
        t = f / fps
        if len(onset_times):
            j = int(np.argmin(np.abs(onset_times - t)))
            dt = float(onset_times[j] - t)
            if abs(dt) <= tol:
                ta = float(onset_times[j])
                out.append(Impact(int(round(ta * fps)), ta, "audio+swing", int(dt * 1000), 0.9))
                continue
            out.append(Impact(int(f), t, "swing", int(dt * 1000), 0.5))
        else:
            out.append(Impact(int(f), t, "swing", None, 0.5))
    return out
