"""Export: one MP4 per stroke with the analysis drawn on it, reels per conclusion and a PDF summary.

    tennisbio export [--stroke forehand] [--player rybakina] [--out <output>/exportar_derecha]

Everything is rendered offline from the window videos and the per-frame series of the fine
pass (the same data the HTML report draws in the browser), so the files play anywhere: a phone,
a TV, a messaging app. Output (re-running only renders what is missing or changed):

    golpes/<stroke id>.mp4     real speed → slow motion around the impact → freeze with its metrics
    montajes/NN_<title>.mp4    title card + the strokes that support each conclusion
    resumen.pdf                conclusions, findings, the typical stroke in 8 phases, metrics, court
"""
import json
import math
import os
import hashlib
import re
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import match_files as _mf
from . import findings as F

W, H = 1280, 720
OUT_FPS = 25
BONES = [(5, 6, "c"), (11, 12, "c"), (5, 11, "l"), (6, 12, "r"), (5, 7, "l"), (7, 9, "l"), (6, 8, "r"), (8, 10, "r"),
         (11, 13, "l"), (13, 15, "l"), (12, 14, "r"), (14, 16, "r")]
SKC = {"l": (230, 211, 95), "r": (67, 159, 255), "c": (236, 232, 227)}          # BGR
ACCENT = (212, 240, 58)      # RGB (text drawn with PIL)
PINK = (255, 95, 210)
STROKE_ES = {"forehand": "Derecha", "backhand": "Revés", "overhead": "Saque / remate"}
OUT_ES = {"out": "error (fuera)", "net": "error (red)", "winner": "no devuelta (ganador o error forzado)", "rally": "sigue el punto"}

# ---------------------------------------------------------------- fonts
_FONTS = {
    "regular": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "Arial.ttf"],
    "bold": ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"],
    "mono": ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "Courier New.ttf"],
}
_FONT_DIRS = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path("/usr/share/fonts/truetype/dejavu"),
              Path("/usr/share/fonts/TTF"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
_cache: dict = {}


def font(kind="regular", size=20) -> ImageFont.FreeTypeFont:
    key = (kind, size)
    if key not in _cache:
        f = None
        for name in _FONTS[kind]:
            for d in _FONT_DIRS:
                if (d / name).exists():
                    f = ImageFont.truetype(str(d / name), size)
                    break
            if f:
                break
        _cache[key] = f or ImageFont.load_default(size)
    return _cache[key]


class Texts:
    """Text items collected while drawing with OpenCV, rendered in one PIL pass (accents, nice fonts)."""

    def __init__(self):
        self.items = []

    def add(self, xy, text, kind="regular", size=20, color=(241, 244, 246), bg=(10, 13, 16, 205), pad=7, anchor="la"):
        self.items.append((xy, text, kind, size, color, bg, pad, anchor))

    def render(self, img_bgr: np.ndarray) -> np.ndarray:
        if not self.items:
            return img_bgr
        im = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
        over = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(over)
        for (x, y), text, kind, size, color, bg, pad, anchor in self.items:
            f = font(kind, size)
            x0, y0, x1, y1 = dr.textbbox((x, y), text, font=f, anchor=anchor)
            if bg:
                dr.rounded_rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), radius=4, fill=bg)
            dr.text((x, y), text, font=f, fill=color + (255,), anchor=anchor)
        im = Image.alpha_composite(im, over).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def wrap(text: str, f, width: float) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def fmt_t(t: float) -> str:
    """Time relative to the impact: +0,12 s / −0,40 s (no "−0,00")."""
    return f"{'−' if t < -0.005 else '+'}{F.fmt(abs(t), 2)} s"


# ---------------------------------------------------------------- one stroke
def _interp_nan(a: np.ndarray) -> np.ndarray:
    a = a.copy()
    ok = np.isfinite(a)
    if ok.sum() == 0:
        return a
    idx = np.arange(len(a))
    a[~ok] = np.interp(idx[~ok], idx[ok], a[ok])
    return a


def _smooth(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1 or len(a) < 3:
        return a
    pad = np.pad(a, (k // 2, k - 1 - k // 2), mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")


CLIP_FROM_S, CLIP_TO_S = -1.0, 0.8      # real-speed part of a stroke video, s from contact


class StrokeClip:
    """A stroke ready to draw: its frames cropped around the player (16:9) and its series."""

    def __init__(self, rec: dict, ctx: dict, size=(W, H)):
        self.rec, self.ctx, self.size = rec, ctx, size
        d = Path(rec["_dir"])
        self.ser = json.loads((d / rec["_series"]).read_text(encoding="utf-8"))
        self.video = _mf.at(d, "windows") / rec["_window"]
        s = self.ser
        self.fps, self.first, self.n, self.impact = float(s["fps"]), s["first"], s["n"], s["impact"]
        self.T0 = (self.first - self.impact) / self.fps
        self.T1 = self.T0 + (self.n - 1) / self.fps
        self.dom_wrist = 9 if ctx.get("hand") == "left" else 10
        self.kp = [None if k is None else np.array([np.nan if v is None else v for v in k], float).reshape(-1, 2) for k in s["kp"]]
        self._crops()
        self.frames = self._read()
        self.Hi = np.linalg.inv(np.array(s["H"], float)) if s.get("H") else None

    def _crops(self):
        """Per-frame crop: centred on her box, constant zoom (median height), smoothed over ~0.3 s."""
        from .io.video import probe
        self.info = probe(self.video)          # ffmpeg, not OpenCV: paths with accents work on Windows
        self.vw, self.vh = self.info.width, self.info.height
        bx = np.array([[np.nan] * 4 if b is None else b for b in self.ser["box"]], float)
        if not np.isfinite(bx).any():
            cx, cy, h = np.full(self.n, self.vw / 2), np.full(self.n, self.vh / 2), np.full(self.n, self.vh / 2.1)
        else:
            cx = _interp_nan((bx[:, 0] + bx[:, 2]) / 2)
            cy = _interp_nan((bx[:, 1] + bx[:, 3]) / 2)
            h = np.full(self.n, np.nanmedian(bx[:, 3] - bx[:, 1]))
        k = max(1, int(round(0.3 * self.fps)))
        cx, cy = _smooth(cx, k), _smooth(cy, k)
        ch = np.minimum(h * 2.1, self.vh)
        cw = ch * self.size[0] / self.size[1]
        self.scale = self.size[0] / cw
        self.sx = np.clip(cx - cw / 2, 0, np.maximum(0, self.vw - cw))
        self.sy = np.clip(cy - ch / 2, 0, np.maximum(0, self.vh - ch))

    def _read(self) -> list:
        from .io.video import read_frames
        # frame-exact seek to the first frame of the series (the windows are constant-rate, so frame
        # k starts at k/fps; half a frame earlier lands on it): same frames as decoding from the start
        out = []
        start = self.info.start_time + (self.first - 0.5) / self.info.fps if self.first > 0 else 0.0
        for f, fr in enumerate(read_frames(self.info, start=start)):
            if f >= self.n:
                break
            out.append(self._crop(fr, f))
        while len(out) < self.n:               # short video: hold the last frame
            out.append(out[-1] if out else np.zeros((self.size[1], self.size[0], 3), np.uint8))
        return out

    def _crop(self, fr: np.ndarray, f: int) -> np.ndarray:
        """Her crop of frame f at the output size: a slice and a resize (fast) when it fits inside
        the frame, an affine warp with black borders otherwise."""
        sc, x0, y0 = float(self.scale[f]), float(self.sx[f]), float(self.sy[f])
        w, h = self.size[0] / sc, self.size[1] / sc
        xi, yi = int(round(x0)), int(round(y0))
        wi, hi = int(round(w)), int(round(h))
        if xi >= 0 and yi >= 0 and xi + wi <= fr.shape[1] and yi + hi <= fr.shape[0] and wi > 1 and hi > 1:
            return cv2.resize(fr[yi:yi + hi, xi:xi + wi], self.size, interpolation=cv2.INTER_LINEAR)
        M = np.float32([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]])
        return cv2.warpAffine(fr, M, self.size, flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))

    def P(self, f, p):
        return (float((p[0] - self.sx[f]) * self.scale[f]), float((p[1] - self.sy[f]) * self.scale[f]))

    def f_at(self, t: float) -> int:
        return int(np.clip(round(t * self.fps + self.impact - self.first), 0, self.n - 1))

    def t_of(self, f: int) -> float:
        return (f + self.first - self.impact) / self.fps

    def phase_near(self, t: float):
        best = None
        for k, short, long in F.phases_for(self.ctx.get("stroke", "forehand")):
            pt = self.rec["phases"].get(k)
            if pt is not None and abs(pt - t) <= 1.5 / self.fps and (best is None or abs(pt - t) < abs(best[0] - t)):
                best = (pt, long)
        return best and best[1]

    # ---- drawing
    def draw(self, f: int, texts: Texts, layers=("skel", "ang", "trail", "ball", "racket", "court"), mono=None,
             ghost=None, base: np.ndarray | None = None) -> np.ndarray:
        img = (self.frames[f] if base is None else base).copy()
        lw = max(2, int(self.size[0] / 420))
        q = self.kp[f]
        pt = lambda p: tuple(int(round(v)) for v in self.P(f, p))
        ok = lambda j: q is not None and j < len(q) and np.isfinite(q[j]).all()
        if "trail" in layers:
            pts = [pt(self.kp[g][self.dom_wrist]) for g in range(f + 1)
                   if self.kp[g] is not None and np.isfinite(self.kp[g][self.dom_wrist]).all()]
            if len(pts) > 1:
                cv2.polylines(img, [np.array(pts, np.int32)], False, (58, 240, 212), lw, cv2.LINE_AA)
        if ghost is not None:
            gq, col = ghost
            for a, b, _ in BONES:
                if np.isfinite(gq[[a, b]]).all():
                    cv2.line(img, pt(gq[a]), pt(gq[b]), col, lw + 1, cv2.LINE_AA)
        if "skel" in layers and q is not None:
            for a, b, c in BONES:
                if ok(a) and ok(b):
                    cv2.line(img, pt(q[a]), pt(q[b]), mono or SKC[c], lw + 1, cv2.LINE_AA)
            for j in range(5, 17):
                if ok(j):
                    cv2.circle(img, pt(q[j]), lw + 2, (19, 15, 12), -1, cv2.LINE_AA)
                    cv2.circle(img, pt(q[j]), lw + 2, mono or SKC["l" if j % 2 else "r"], max(1, lw - 1), cv2.LINE_AA)
        if "racket" in layers:
            fk = ((self.ser.get("face") or {}).get("keypoints") or {}).get(str(f + self.first))
            if fk:
                R = [pt(p) for p in fk]
                for u, v in ((0, 3), (3, 1), (1, 4), (4, 0), (1, 2)):
                    cv2.line(img, R[u], R[v], (210, 95, 255), lw, cv2.LINE_AA)
        if "ball" in layers and self.ser.get("ball"):
            nt = max(3, int(round(.25 * self.fps)))
            for g in range(max(0, f - nt), f + 1):
                b = self.ser["ball"][g]
                if b and b[0] is not None:
                    if g == f:
                        cv2.circle(img, pt(b), lw * 4, (210, 95, 255), lw, cv2.LINE_AA)
                    else:
                        cv2.circle(img, pt(b), lw + 1, (210, 95, 255), -1, cv2.LINE_AA)
        if "ang" in layers and q is not None:
            dw = self.dom_wrist
            for a, b, c, name in ((dw - 4, dw - 2, dw, "Codo"), (11, 13, 15, "Rod."), (12, 14, 16, "Rod.")):
                if ok(a) and ok(b) and ok(c):
                    u, v = q[a] - q[b], q[c] - q[b]
                    ang = math.degrees(math.acos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9), -1, 1)))
                    x, y = pt(q[b])
                    right = (b % 2) == (dw % 2)
                    texts.add((x + 14 if right else x - 14, y), f"{name} {ang:.0f}°", "mono", 17,
                              (255, 209, 102) if name == "Codo" else (227, 232, 236), anchor="lm" if right else "rm", pad=4)
        if "court" in layers and self.Hi is not None:
            self._minimap(img, f, texts)
        return img

    def _minimap(self, img, f, texts):
        mh = int(self.size[1] * .42)
        mw = int(mh * 15 / 31)
        x0, y0 = self.size[0] - mw - 18, 92
        k = mh / 31
        X = lambda x: int(x0 + mw / 2 + x * k)
        Y = lambda y: int(y0 + mh - (y + 3.5) * k)
        sub = img[y0:y0 + mh, x0:x0 + mw]
        img[y0:y0 + mh, x0:x0 + mw] = (sub * .25 + np.array([30, 40, 16]) * .75).astype(np.uint8)
        for a, b, c, d in ((-5.485, 0, 5.485, 0), (-5.485, 23.77, 5.485, 23.77), (-5.485, 0, -5.485, 23.77), (5.485, 0, 5.485, 23.77),
                           (-4.115, 0, -4.115, 23.77), (4.115, 0, 4.115, 23.77), (-4.115, 5.485, 4.115, 5.485),
                           (-4.115, 18.285, 4.115, 18.285), (0, 5.485, 0, 18.285)):
            cv2.line(img, (X(a), Y(b)), (X(c), Y(d)), (230, 235, 238), 1, cv2.LINE_AA)
        cv2.line(img, (X(-6.4), Y(11.885)), (X(6.4), Y(11.885)), (236, 232, 227), 3, cv2.LINE_AA)

        def feet(g):
            q = self.kp[g]
            if q is None or not np.isfinite(q[[15, 16]]).all():
                return None
            m = (q[15] + q[16]) / 2
            p = self.Hi @ np.array([m[0], m[1], 1.0])
            c = p[:2] / p[2]
            return c if abs(c[0]) < 9 and -4 < c[1] < 14 else None
        pts = [feet(g) for g in range(f + 1)]
        tr = [(X(c[0]), Y(c[1])) for c in pts if c is not None]
        if len(tr) > 1:
            cv2.polylines(img, [np.array(tr, np.int32)], False, (58, 240, 212), 2, cv2.LINE_AA)
        if pts and pts[-1] is not None:
            cv2.circle(img, (X(pts[-1][0]), Y(pts[-1][1])), 5, (58, 240, 212), -1, cv2.LINE_AA)
        for c, col, show in ((self.ser.get("bounce_court_m"), (210, 95, 255), True),
                             (self.ser.get("shot_bounce_m"), (230, 211, 95), f >= self.impact - self.first)):
            if c and show:
                cv2.circle(img, (X(c[0]), Y(c[1])), 5, col, 2, cv2.LINE_AA)
        texts.add((x0 + 5, y0 + 5), "PISTA", "mono", 13, (170, 180, 190), bg=None)

    def hud(self, texts: Texts, f: int, t: float, speed: str):
        r, c = self.rec, self.ctx
        score = f" · {r['set']}º set {r['score']}" if r.get("score") else ""
        texts.add((22, 22), f"{c['player']} · {STROKE_ES.get(c['stroke'], c['stroke'])} · vs {c['rival'][r['match']]}{score}", "bold", 22)
        sub = [F.fmt(r.get("tAvail"), 2) + " s disponibles" if r.get("tAvail") is not None else None,
               r.get("stance"), OUT_ES.get(r.get("outcomeDetail") or "", None), "PRESIÓN" if r.get("pressure") else None]
        texts.add((22, 62), " · ".join(x for x in sub if x) or r["id"], "regular", 18, (200, 208, 214))
        texts.add((self.size[0] - 22, 22), f"{fmt_t(t)} · {speed}", "mono", 22, anchor="ra")
        ph = self.phase_near(t)
        if ph:
            texts.add((22, self.size[1] - 26), ph.upper(), "bold", 28, ACCENT, anchor="ls")
        fc = self.ser.get("face")
        if fc:
            fi = f + self.first - fc["first"]
            if 0 <= fi < len(fc["label"]) and fc["label"][fi]:
                tl = fc["tilt"][fi] or 0
                txt = f"CUERDAS → {fc['label'][fi].upper()} · {'CERRADA' if tl >= 0 else 'ABIERTA'} {abs(tl):.0f}°{'' if fc['observed'][fi] else ' (estimada)'}"
                texts.add((self.size[0] - 22, self.size[1] - 26), txt, "mono", 19, PINK, anchor="rs")

    def metrics_panel(self, texts: Texts, img: np.ndarray, metrics: list, dist: dict, top=6):
        rows = [m for m in metrics if self.rec["m"].get(m["k"]) is not None and dist.get(m["k"])][:top]
        if not rows:
            return img
        x0, y0, w = self.size[0] - 470, 110, 448
        h = 64 + 58 * len(rows)
        over = img.copy()
        cv2.rectangle(over, (x0, y0), (x0 + w, y0 + h), (16, 13, 10), -1)
        img = cv2.addWeighted(over, .82, img, .18, 0)
        texts.add((x0 + 18, y0 + 16), "ESTE GOLPE · respecto a su mediana", "bold", 18, ACCENT, bg=None)
        for i, m in enumerate(rows):
            v, d = self.rec["m"][m["k"]], dist[m["k"]]
            y = y0 + 58 + 58 * i
            z = (v - d["p50"]) / (m["noise"] or 1)
            txt = "en su rango" if abs(z) <= 1 else ("por encima" if z > 0 else "por debajo")
            texts.add((x0 + 18, y), m["name"], "regular", 18, (231, 235, 238), bg=None)
            texts.add((x0 + w - 18, y), F.fmt_metric(m, v), "mono", 20, (241, 244, 246), bg=None, anchor="ra")
            texts.add((x0 + 18, y + 24), f"mediana {F.fmt_metric(m, d['p50'])} · {txt}", "regular", 15,
                      (170, 180, 190) if abs(z) <= 1 else ACCENT, bg=None)
        return img

    def strokes_frames(self, metrics, dist):
        """Real speed → 0,25× around the impact → freeze on the impact with her metrics."""
        # the clip at real speed keeps its former reach (the series now start at the opponent's hit, 2.5 s
        # before contact, 27-10): a stroke video stays as long, and the export as fast, as before
        for t in np.arange(max(self.T0, CLIP_FROM_S), min(self.T1, CLIP_TO_S) + 1e-9, 1 / OUT_FPS):
            yield self._frame(self.f_at(t), t, "1×")
        lo, hi = max(self.T0, -0.6), min(self.T1, 0.5)
        for t in np.arange(lo, hi + 1e-9, 0.25 / OUT_FPS):
            yield self._frame(self.f_at(t), t, "0,25×")
        f0 = self.f_at(0.0)
        tx = Texts()
        img = self.draw(f0, tx)
        self.hud(tx, f0, 0.0, "pausa")
        img = self.metrics_panel(tx, img, metrics, dist)
        img = tx.render(img)
        for _ in range(int(2.2 * OUT_FPS)):
            yield img

    def _frame(self, f, t, speed):
        tx = Texts()
        img = self.draw(f, tx)
        self.hud(tx, f, t, speed)
        return tx.render(img)


# ---------------------------------------------------------------- encoding
class Encoder:
    """Raw BGR frames → H.264 MP4 (yuv420p, constant 25 fps): the same parameters for every file, so
    reels are joined without re-encoding."""

    def __init__(self, path: Path, size=(W, H)):
        self.path = Path(path)
        self.tmp = self.path.with_name(self.path.stem + ".part.mp4")
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{size[0]}x{size[1]}",
                                   "-r", str(OUT_FPS), "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                                   "-pix_fmt", "yuv420p", "-g", str(OUT_FPS), "-movflags", "+faststart", str(self.tmp)],
                                  stdin=subprocess.PIPE)

    def write(self, img: np.ndarray):
        self.p.stdin.write(np.ascontiguousarray(img).tobytes())

    def abort(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.kill()
        self.p.wait()
        self.tmp.unlink(missing_ok=True)

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError(f"ffmpeg falló al escribir {self.path}")
        self.tmp.replace(self.path)


def title_card(lines: list[tuple[str, str, int, tuple]], size=(W, H)) -> np.ndarray:
    """lines: (text, font kind, size, RGB colour); centred, wrapped."""
    im = Image.new("RGB", size, (12, 15, 19))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 10, size[1]), fill=ACCENT)
    blocks = []
    for text, kind, sz, col in lines:
        f = font(kind, sz)
        for ln in wrap(text, f, size[0] - 220):
            blocks.append((ln, f, col, sz))
    total = sum(int(b[3] * 1.35) for b in blocks)
    y = (size[1] - total) / 2
    for ln, f, col, sz in blocks:
        dr.text((110, y), ln, font=f, fill=col)
        y += int(sz * 1.35)
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def write_still(path: Path, img: np.ndarray, seconds: float):
    enc = Encoder(path)
    for _ in range(int(seconds * OUT_FPS)):
        enc.write(img)
    enc.close()


def concat(parts: list[Path], out: Path):
    lst = out.with_suffix(".txt")
    q = lambda p: p.resolve().as_posix().replace("'", "'\\''")          # quoting of the concat list
    lst.write_text("".join(f"file '{q(p)}'\n" for p in parts), encoding="utf-8")
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    "-movflags", "+faststart", str(tmp)], check=True, timeout=1800)
    tmp.replace(out)
    lst.unlink()


def pair_clip(a: StrokeClip, b: StrokeClip, labels: tuple[str, str], path: Path):
    """Two strokes side by side, synced on the impact, at 0,25× (and real speed first)."""
    tw, th = W // 2 - 12, H - 120          # tall tiles: each crop is centred on the player
    lo, hi = max(a.T0, b.T0, -0.8), min(a.T1, b.T1, 0.5)
    enc = Encoder(path)
    real = list(np.arange(lo, hi + 1e-9, 1 / OUT_FPS))
    ts = real + list(np.arange(max(lo, -0.6), hi + 1e-9, 0.25 / OUT_FPS))
    for i, t in enumerate(ts):
        canvas = np.full((H, W, 3), (19, 15, 12), np.uint8)
        tx = Texts()
        for j, (c, col) in enumerate(((a, (229, 135, 57)), (b, (38, 89, 217)))):
            f = c.f_at(t)
            ty = Texts()
            img = c.draw(f, ty, layers=("skel", "trail", "ball", "racket"))
            img = ty.render(img)
            x0, y0 = 8 + j * (W // 2), 104
            cw = int(img.shape[0] * tw / th)
            img = img[:, (img.shape[1] - cw) // 2:(img.shape[1] + cw) // 2]
            canvas[y0:y0 + th, x0:x0 + tw] = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)
            cv2.rectangle(canvas, (x0, y0 - 6), (x0 + tw, y0 - 2), col, -1)
            tx.add((x0, y0 - 36), labels[j], "bold", 20, (241, 244, 246), bg=None)
            ph = c.phase_near(t)
            if ph:
                tx.add((x0 + 10, y0 + th - 14), ph.upper(), "bold", 20, ACCENT, anchor="ls")
        tx.add((W // 2, 18), f"{fmt_t(t)} respecto al impacto · {'1×' if i < len(real) else '0,25×'}",
               "mono", 20, anchor="ma")
        enc.write(tx.render(canvas))
    enc.close()


# ---------------------------------------------------------------- PDF summary
PAGE = (1754, 1240)     # A4 landscape at 150 dpi
INK, INK2, INK3, LINE = (25, 30, 36), (80, 90, 100), (130, 138, 146), (220, 224, 228)
LEVEL_COL = {"good": (34, 150, 70), "warn": (200, 140, 10), "crit": (200, 70, 66)}


class Pdf:
    def __init__(self, title: str):
        self.pages, self.title = [], title

    def page(self, heading: str):
        im = Image.new("RGB", PAGE, "white")
        dr = ImageDraw.Draw(im)
        dr.rectangle((0, 0, PAGE[0], 12), fill=(150, 170, 30))
        dr.text((90, 60), heading, font=font("bold", 44), fill=INK)
        self.pages.append(im)
        return im, dr

    def save(self, path: Path):
        n = len(self.pages)
        for i, im in enumerate(self.pages):
            dr = ImageDraw.Draw(im)
            dr.text((90, PAGE[1] - 60), f"{self.title} · página {i + 1} de {n}", font=font("regular", 20), fill=INK3)
        self.pages[0].save(path, save_all=True, append_images=self.pages[1:], resolution=150)


def _chip(dr, x, y, text, level):
    f = font("bold", 20)
    w = f.getlength(text)
    col = LEVEL_COL.get(level, INK2)
    dr.rounded_rectangle((x - w - 24, y - 4, x, y + 30), radius=6, outline=col, width=2)
    dr.text((x - w - 12, y), text, font=f, fill=col)


def pdf_summary(path: Path, data: dict, dist: dict, finds: list, concl: list, typical: StrokeClip | None, ctx: dict,
                reel_names: dict):
    title = f"{ctx['player']} · {STROKE_ES.get(ctx['stroke'], ctx['stroke'])}"
    pdf = Pdf(f"TennisBio · {title} · {time.strftime('%Y-%m-%d')}")
    st = data["strokes"]
    MK = {m["k"]: m for m in data["metrics"]}

    # 1. cover + conclusions
    im, dr = pdf.page(title)
    sub = (f"{len(data['matches'])} partidos · {len(st)} golpes ({sum(1 for s in st if s['side'] == 'far')} desde el fondo) · "
           f"{data['review']} con dudas · ruido de medida {'medido en golpes equivalentes' if data['noise_validated'] else 'provisional'}")
    dr.text((90, 122), sub, font=font("regular", 24), fill=INK2)
    dr.text((90, 160), "Partidos: " + " · ".join(f"{m['id']} vs {m['rival']}" for m in data["matches"]), font=font("regular", 20), fill=INK3)
    # the same model the report shows: «En pocas palabras» and the 8 phases in sentences
    from .explain import model_view
    from .model import build_model
    mv = model_view(build_model(data.get("_raw", [])), ctx["stroke"]) if data.get("_raw") else {}
    y = 220
    fr = font("regular", 23)
    if mv.get("summary"):
        dr.text((90, y), "En pocas palabras", font=font("bold", 32), fill=INK)
        y += 56
        for t in mv["summary"]:
            for k, ln in enumerate(wrap(t, fr, 1350)):
                dr.text((90 if k == 0 else 112, y), ("• " if k == 0 else "") + ln, font=fr, fill=INK)
                y += 34
            y += 6
        y += 24
    dr.text((90, y), "Conclusiones", font=font("bold", 32), fill=INK)
    y += 56
    for c in concl:
        lines = wrap(c.text, fr, 1250)
        need = 34 * len(lines) + (28 if c.strokes and c.text in reel_names else 0) + 18
        if y + need > PAGE[1] - 110:
            im, dr = pdf.page("Conclusiones (continuación)")
            y = 150
        for i, ln in enumerate(lines):
            dr.text((90, y + 34 * i), ln, font=fr, fill=INK)
        _chip(dr, PAGE[0] - 90, y, c.confidence, c.level)
        y += 34 * len(lines)
        if c.text in reel_names:
            dr.text((90, y + 2), f"Vídeo: montajes/{reel_names[c.text]}", font=font("regular", 19), fill=(60, 110, 200))
            y += 28
        dr.line((90, y + 8, PAGE[0] - 90, y + 8), fill=LINE, width=1)
        y += 18

    # 2. findings (forest plot)
    if finds:
        im, dr = pdf.page("Hallazgos")
        dr.text((90, 122), "Diferencia entre situaciones en múltiplos del ruido de medida (franja gris: ±1 ruido; línea: IC 95 %).",
                font=font("regular", 22), fill=INK2)
        y, X0, X1 = 190, 1020, 1420
        Xv = lambda v, nz: (X0 + X1) / 2 + max(-3.2, min(3.2, v / nz)) * (X1 - X0) / 2 / 3.2
        for f in finds:
            m, e = MK[f.k], f.effect
            dr.text((90, y), f"{f.title}: {F.sign(e.d)}{F.fmt(abs(e.d), m['dec'])}{F.unit_str(m)}", font=font("bold", 23), fill=INK)
            dr.text((90, y + 32), f"{f.context} · n={e.na}/{e.nb} · {F.fmt(e.ma, m['dec'])} → {F.fmt(e.mb, m['dec'])}", font=font("regular", 18), fill=INK2)
            if f.verdict[0] != "crit":
                dr.text((90, y + 56), "→ " + F.meaning(f.k, e.d), font=font("regular", 18), fill=INK2)
            cy = y + 30
            dr.rectangle((Xv(-m["noise"], m["noise"]), cy - 14, Xv(m["noise"], m["noise"]), cy + 14), fill=(236, 238, 240))
            dr.line((Xv(0, 1), cy - 20, Xv(0, 1), cy + 20), fill=INK3, width=2)
            dr.line((Xv(e.lo, m["noise"]), cy, Xv(e.hi, m["noise"]), cy), fill=INK, width=3)
            px = Xv(e.d, m["noise"])
            dr.ellipse((px - 9, cy - 9, px + 9, cy + 9), fill=(150, 170, 30), outline=INK)
            _chip(dr, PAGE[0] - 90, cy - 14, f.verdict[1], f.verdict[0])
            y += 96
            if y > PAGE[1] - 160:
                break

    # 3. the typical stroke in 8 phases, with what she does at each one (key points of «Su derecha»
    # and «Para copiarla»), 4 phases per page
    cards = {c["phase"]: c for c in (mv.get("cards") or [])}
    if typical is not None:
        r = typical.rec
        tw, th, fs = 370, 380, font("regular", 18)
        for i, (k, short, long) in enumerate(F.phases_for(ctx["stroke"])):
            if i % 4 == 0:
                im, dr = pdf.page("Su golpe, fase a fase" + (" (continuación)" if i else ""))
                dr.text((90, 122), f"Golpe típico: {r['id']} · {r.get('stance') or '—'} · las frases salen de todos sus golpes "
                                   f"(solo con golpes suficientes)", font=font("regular", 20), fill=INK2)
            x, y = 90 + (i % 4) * (tw + 22), 170
            t = r["phases"].get(k)
            if t is None:
                dr.rectangle((x, y, x + tw, y + th), outline=LINE, width=2)
                dr.text((x + 12, y + th / 2 - 12), "no detectado", font=font("regular", 20), fill=INK3)
            else:
                f = typical.f_at(t)
                tx = Texts()
                img = tx.render(typical.draw(f, tx, layers=("skel", "trail", "racket")))
                cw = int(img.shape[0] * tw / th)              # the player is centred in the crop
                img = img[:, max(0, (img.shape[1] - cw) // 2):(img.shape[1] + cw) // 2]
                im.paste(Image.fromarray(cv2.cvtColor(cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (int(x), int(y)))
            yy = y + th + 10
            dr.text((x, yy), f"{i + 1} · {long}", font=font("bold", 22), fill=INK)
            yy += 34
            c = cards.get(k) or {}
            texts = [ln["text"] for ln in c.get("lines", []) if ln.get("main")][:4]
            if not texts:
                texts = ["Sin datos suficientes en esta fase."]
            for t_ in texts + ([f"Para copiarla: {c['copy']}"] if c.get("copy") else []):
                for ln in wrap(t_, fs, tw):
                    if yy > PAGE[1] - 90:
                        break
                    dr.text((x, yy), ln, font=fs, fill=(120, 140, 20) if t_.startswith("Para copiarla") else INK)
                    yy += 24
                yy += 8

    # 5. court
    pos = [s for s in st if s.get("x") is not None and s.get("y") is not None]
    dest = [s for s in st if s.get("shotY") is not None]
    if pos or dest:
        im, dr = pdf.page("Pista")
        for j, (name, pts) in enumerate((("Posición en el impacto (su campo; la red arriba)", [(s["x"], s["y"], (57, 135, 229)) for s in pos]),
                                         ("Dónde bota su golpe (campo rival; la red arriba)",
                                          [(s["shotX"], s["shotY"] - 11.885, (200, 70, 66) if s.get("shotIn") is False else (25, 158, 112)) for s in dest]))):
            S, ox, oy = 44, 140 + j * 800 + 7 * 44, 230
            Xc, Yc = lambda x: ox + x * S, lambda d: oy + d * S
            dr.text((140 + j * 800, 160), name, font=font("bold", 24), fill=INK)
            dr.rectangle((Xc(-6.9), Yc(0), Xc(6.9), Yc(16)), fill=(220, 236, 226))
            dr.rectangle((Xc(-5.485), Yc(0), Xc(5.485), Yc(11.885)), fill=(196, 216, 238))
            for a, b, c, d in ((-6.4, 0, 6.4, 0), (-5.485, 0, -5.485, 11.885), (5.485, 0, 5.485, 11.885), (-4.115, 0, -4.115, 11.885),
                               (4.115, 0, 4.115, 11.885), (-5.485, 11.885, 5.485, 11.885), (-4.115, 6.4, 4.115, 6.4), (0, 0, 0, 6.4)):
                dr.line((Xc(a), Yc(b), Xc(c), Yc(d)), fill="white", width=4 if b == d == 0 else 3)
            for x, yv, col in pts:
                dr.ellipse((Xc(x) - 8, Yc(yv) - 8, Xc(x) + 8, Yc(yv) + 8), fill=col, outline="white")
        dr.text((140, PAGE[1] - 120), "Zurdos reflejados: +x es siempre el lado de su derecha. Destino: verde dentro, rojo fuera.",
                font=font("regular", 19), fill=INK2)
    pdf.save(path)


# ---------------------------------------------------------------- driver
def slug(text: str, n=48) -> str:
    t = text.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:n] or "montaje"


def _fresh(out: Path, *inputs: Path) -> bool:
    return out.exists() and all(out.stat().st_mtime >= p.stat().st_mtime for p in inputs if p.exists())


def export(matches, out_root: Path, dest: Path, stroke="forehand", player_id: str | None = None,
           reel_max=10, strokes_all=True, log=print) -> Path:
    from .report import player_dict, prepare

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg no está en el PATH")
    data = prepare(matches, out_root, stroke, player_id)
    player = player_dict(matches, player_id)
    dist = F.distributions(data)
    F.representativeness(data, dist)
    finds = F.discover(data)
    concl = F.conclusions(data, dist, finds)
    ctx = {"player": player.get("name", "Jugador"), "hand": player.get("hand"), "stroke": stroke,
           "rival": [m["rival"] for m in data["matches"]]}
    ok = [s for s in data["strokes"] if s.get("_window") and s.get("_series")
          and (_mf.at(Path(s["_dir"]), "windows") / s["_window"]).exists() and (Path(s["_dir"]) / s["_series"]).exists()]
    dest = Path(dest)
    (dest / "golpes").mkdir(parents=True, exist_ok=True)
    (dest / "montajes").mkdir(parents=True, exist_ok=True)
    key_metrics = data["metrics"]
    ranked = sorted(ok, key=lambda s: -F.show_score(s))

    # which strokes are needed: every one (default) or only those in the reels
    reels = [("Su golpe típico", "Los golpes más cercanos a su mediana en todas las métricas y mejor capturados", None, "good", ranked[:reel_max], None)]
    for c in concl:
        sel = [s for s in c.strokes if s in ok][:reel_max]
        if sel:
            reels.append((c.text, None, c.confidence, c.level, sel, c.finding))
    errors = [s for s in ranked if s.get("outcome") == "error"][:reel_max]
    if errors:
        reels.append(("Errores", "Golpes que acabaron fuera o en la red", None, "warn", errors, None))
    need = ok if strokes_all else list({s["id"]: s for r in reels for s in r[4]}.values())

    t0, done = time.time(), 0
    paths = {}
    # each clip shows this stroke against her median and the noise: it is redone when they change
    sig_path = dest / "golpes" / "firmas.json"
    try:
        sigs = json.loads(sig_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sigs = {}
    base = json.dumps([[m.get("k"), m.get("noise")] for m in key_metrics] + [dist.get(m.get("k")) for m in key_metrics],
                      sort_keys=True, default=str)
    for i, s in enumerate(need):
        out = dest / "golpes" / f"{s['id']}.mp4"
        paths[s["id"]] = out
        src = [_mf.at(Path(s["_dir"]), "windows") / s["_window"], Path(s["_dir"]) / s["_series"]]
        sig = hashlib.sha1((base + json.dumps({k: v for k, v in s.items() if not k.startswith("_")},
                                              sort_keys=True, default=str)).encode()).hexdigest()[:12]
        if _fresh(out, *src) and sigs.get(s["id"]) == sig:
            continue
        sigs[s["id"]] = sig
        # the stroke being encoded, with the time: the Windows script cuts an export that stays on one stroke
        # too long and says which one (27-10: the backhand export hung twice with no trace of where)
        try:
            (dest / "en_curso.txt").write_text(f"{s['id']} {time.strftime('%Y-%m-%d %H:%M:%S')} {i + 1}/{len(need)}", encoding="utf-8")
        except OSError:
            pass
        enc = None
        try:
            clip = StrokeClip(s, ctx)
            enc = Encoder(out)
            for img in clip.strokes_frames(key_metrics, dist):
                enc.write(img)
            enc.close()
            done += 1
        except Exception as e:           # one broken window must not stop the export
            if enc is not None:
                enc.abort()
            log(f"  {s['id']}: no se pudo exportar ({e})")
            paths.pop(s["id"], None)
        if (i + 1) % 10 == 0:
            log(f"  golpes {i + 1}/{len(need)} ({time.time() - t0:.0f} s)")
    if strokes_all:                      # clips of strokes that no longer exist
        for f in (dest / "golpes").glob("*.mp4"):
            if f.stem not in paths:
                f.unlink(missing_ok=True)
                sigs.pop(f.stem, None)
    sig_path.write_text(json.dumps(sigs), encoding="utf-8")
    log(f"Golpes: {done} nuevos, {len(paths)} en {dest / 'golpes'}")

    # reels: title card + (for a finding) its typical strokes side by side + its strokes
    reel_names = {}
    for f in (dest / "montajes").glob("*.mp4"):
        f.unlink()
    tmp = dest / "montajes" / "_tmp"
    tmp.mkdir(exist_ok=True)
    MK = {m["k"]: m for m in data["metrics"]}
    for i, (text, subtitle, conf, level, sel, fnd) in enumerate(reels):
        sel = [s for s in sel if s["id"] in paths]
        if not sel:
            continue
        name = f"{i:02d}_{slug(text if fnd is None else fnd.title)}.mp4"
        card = tmp / f"card_{i:02d}.mp4"
        lines = [(text, "bold", 40, (241, 244, 246))]
        if subtitle:
            lines.append((subtitle, "regular", 26, (200, 208, 214)))
        if conf:
            lines.append((f"Confianza: {conf}", "regular", 26, ACCENT))
        lines.append((f"{len(sel)} golpes · {ctx['player']} · {STROKE_ES.get(stroke, stroke)}", "regular", 24, (170, 180, 190)))
        write_still(card, title_card(lines), 4.0)
        parts = [card]
        if fnd is not None:
            ta, tb = F.typical(fnd.A, fnd.k, MK[fnd.k]["noise"]), F.typical(fnd.B, fnd.k, MK[fnd.k]["noise"])
            if ta in ok and tb in ok and ta is not tb:
                pc = tmp / f"pair_{i:02d}.mp4"
                try:
                    m = MK[fnd.k]
                    pair_clip(StrokeClip(ta, ctx), StrokeClip(tb, ctx),
                              (f"Típico del resto · {m['name']} {F.fmt_metric(m, ta['m'][fnd.k])}",
                               f"Típico de este grupo · {m['name']} {F.fmt_metric(m, tb['m'][fnd.k])}"), pc)
                    parts.append(pc)
                except Exception as e:
                    log(f"  comparación de {name}: {e}")
        parts += [paths[s["id"]] for s in sel]
        concat(parts, dest / "montajes" / name)
        reel_names[text] = name
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"Montajes: {len(reel_names)} en {dest / 'montajes'}")

    typ = None
    for s in ranked[:5]:
        try:
            typ = StrokeClip(s, ctx)
            break
        except Exception:
            continue
    pdf = dest / "resumen.pdf"
    pdf_summary(pdf, data, dist, finds, concl, typ, ctx, reel_names)
    log(f"Resumen: {pdf}")
    return dest
