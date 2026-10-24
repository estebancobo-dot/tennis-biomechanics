"""The ball as an input of the learned stroke spotter (plan N2, 24-10): with the body alone the spotter stays at
~62 % of the near player's strokes (10 fps) and more frames of the body did not help (25 fps: 63 %). A stroke is
where the ball turns and goes away (docs/validacion.md: ball + pose gave precision 0.73, recall 0.84 on
RacketVision), so the ball track over the match play becomes a few numbers per spotter frame.

The ball model (TrackNetV3, tennisbio.ball) runs only on main-camera play (scenes + court), at ~25 fps (as it was
trained) and on frames shrunk to 1280 px (its input is 512x288; no deinterlacing at that size)."""
from pathlib import Path

import numpy as np

BALL_FPS = 25.0
BALL_DIM = 8
CHUNK_S = 30.0          # longest stretch tracked at once (one background per stretch, bounded memory)


def play_segments(sc: dict, court: dict | None, fps: float, min_s: float = 1.0) -> list[tuple[float, float]]:
    """(start, end) in seconds of each stretch of match play, cut into pieces of at most CHUNK_S."""
    from .stages import play_mask

    m = play_mask(sc, court)
    out, i = [], 0
    while i < len(m):
        if not m[i]:
            i += 1
            continue
        j = i
        while j < len(m) and m[j]:
            j += 1
        a, b = i / fps, j / fps
        while b - a >= min_s:
            out.append((a, min(b, a + CHUNK_S)))
            a += CHUNK_S
        i = j
    return out


def track_play(video: Path, sc: dict, court: dict | None, tracker, fps: float, log=None) -> np.ndarray:
    """(M, 4): time (s), x, y (fraction of the frame), confidence of the ball over the match play; x, y NaN
    where the ball was not seen."""
    from .io.video import probe, read_frames

    info = probe(video)
    rows = []
    segs = play_segments(sc, court, fps)
    total = sum(b - a for a, b in segs)
    done = 0.0
    for k, (a, b) in enumerate(segs):
        frames = read_frames(info, a, b - a, width=min(1280, info.width), fps=BALL_FPS)
        tr = tracker.track(frames)
        if len(tr):
            h, w = (min(1280, info.width) * info.height / info.width), min(1280, info.width)
            t = a + np.arange(len(tr)) / BALL_FPS
            rows.append(np.column_stack([t, tr[:, 0] / w, tr[:, 1] / h, tr[:, 2]]))
        done += b - a
        if log and (k % 20 == 0 or k == len(segs) - 1):
            log(f"  bola: {done / 60:.1f} de {total / 60:.1f} min de juego")
    return np.concatenate(rows) if rows else np.zeros((0, 4))


def features(track: np.ndarray, n: int, fps: float) -> np.ndarray:
    """(n, BALL_DIM) per spotter frame (bin [i/fps, (i+1)/fps)): fraction of ball samples seen, mean x, y,
    velocity x, y (frame fractions per second), speed, sharpest turn of the direction (0-1 = 0-180°) and whether
    the vertical direction flips (towards / away from the camera: a hit or a bounce). Zeros where nothing is
    known (no play or no track)."""
    out = np.zeros((n, BALL_DIM), np.float32)
    if not len(track):
        return out
    t, xy = track[:, 0], track[:, 1:3]
    seen = ~np.isnan(xy).any(axis=1)
    dt = 1.0 / BALL_FPS
    v = np.full_like(xy, np.nan)
    v[1:-1] = (xy[2:] - xy[:-2]) / (2 * dt)
    v[1:-1][(np.abs(t[2:] - t[:-2] - 2 * dt) > dt / 2)] = np.nan       # across two separate stretches
    ang = np.arctan2(v[:, 1], v[:, 0])
    turn = np.full(len(t), np.nan)
    d = np.abs(np.angle(np.exp(1j * (ang[2:] - ang[:-2]))))
    turn[1:-1] = d / np.pi
    flip = np.zeros(len(t))
    flip[1:-1] = (np.sign(v[2:, 1]) * np.sign(v[:-2, 1]) < 0).astype(float)
    b = np.floor(t * fps).astype(int)
    for i in np.unique(b[(b >= 0) & (b < n)]):
        s = b == i
        ok = s & seen
        out[i, 0] = ok.sum() / max(1, s.sum())
        if not ok.any():
            continue
        out[i, 1:3] = np.nanmean(xy[ok], axis=0)
        vv = v[ok]
        if np.isfinite(vv).any():
            m = np.nanmean(vv, axis=0)
            out[i, 3:5] = np.clip(np.nan_to_num(m), -5, 5)
            out[i, 5] = min(5.0, float(np.nanmean(np.linalg.norm(vv, axis=1))))
        tt = turn[ok]
        if np.isfinite(tt).any():
            out[i, 6] = float(np.nanmax(tt))
        out[i, 7] = float(flip[ok].max())
    return out


def cached_track(mdir: Path, video: Path, tracker_factory, log=None) -> np.ndarray:
    """track_play of an analysed video, kept in <mdir>/ball_track.npz (the ball model is the slow part)."""
    import json

    f = Path(mdir) / "ball_track.npz"
    if f.exists():
        with np.load(f) as z:
            return z["track"]
    rd = lambda n: json.loads((Path(mdir) / n).read_text(encoding="utf-8")) if (Path(mdir) / n).exists() else None
    sc, court = rd("scenes.json") or {"shots": []}, rd("court.json")
    with np.load(Path(mdir) / "players.npz", allow_pickle=True) as z:
        fps = float(z["fps"])
    tr = track_play(video, sc, court, tracker_factory(), fps, log) if sc.get("shots") else np.zeros((0, 4))
    np.savez_compressed(f, track=tr.astype(np.float32))
    return tr
