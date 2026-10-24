"""«¿Cuál es ella?»: the user's one click per match (19-10, the only manual step). The identity stage splits
the near player's runs into two people by their clothes; here each group gets one photo (the near player in
the middle of the run where her clothes are clearest) and the click on one of them is saved as
<match>/identidad_clic.json. The candidates stage reads it (tennisbio.identity.apply_pick) and, being part of
its fingerprint, re-runs with what follows: no other stage is repeated."""
import json
import time
from pathlib import Path

import numpy as np

from .. import match_files as _mf
from ..identity import PICK_FILE

PHOTOS = "identidad_fotos"


def state(match_dir: Path) -> dict:
    """{"needed", "done", "pick"}: the photos can be made once the identity stage has split the clothes."""
    d = Path(match_dir)
    ident = _mf.at(d, "identity.json")
    pick = json.loads((d / PICK_FILE).read_text(encoding="utf-8")) if (d / PICK_FILE).exists() else None
    groups = set()
    if ident.exists():
        groups = {r.get("cluster", -1) for r in json.loads(ident.read_text(encoding="utf-8")).get("runs", [])} - {-1}
    return {"possible": len(groups) == 2, "done": pick is not None and not pick.get("simulated"), "pick": pick}


def photos(match_dir: Path, video: Path, height: int = 360) -> list[dict]:
    """One photo per clothes group: [{"cluster", "t", "path"}] (cached in <match>/identidad_fotos/)."""
    import cv2

    from ..skeleton import Skeleton
    from ..stages import grab_frame, near_runs

    d = Path(match_dir)
    ident = json.loads((_mf.at(d, "identity.json")).read_text(encoding="utf-8"))
    fps = float(ident.get("fps") or 1.0)
    best: dict[int, dict] = {}
    for r in ident.get("runs", []):
        c = r.get("cluster", -1)
        if c >= 0 and (c not in best or (r.get("clothes_margin") or 0) > (best[c].get("clothes_margin") or 0)):
            best[c] = r
    out_dir = d / PHOTOS
    out_dir.mkdir(exist_ok=True)
    out = []
    want = {r["start"]: c for c, r in best.items()}
    with np.load(_mf.at(d, "players.npz"), allow_pickle=True) as z:
        pl = {k: z[k] for k in z.files}
    court = json.loads((_mf.at(d, "court.json")).read_text(encoding="utf-8")) if (_mf.at(d, "court.json")).exists() else None
    frames = pl["frames"]
    for run, img, cf, h, app, sel in near_runs(pl, Skeleton("coco17", "right"), court, with_sel=True):
        c = want.get(int(frames[run[0]]))
        if c is None:
            continue
        ok = np.flatnonzero(sel >= 0)
        k = int(ok[len(ok) // 2]) if len(ok) else len(run) // 2
        t = float(frames[run[k]]) / fps
        f = out_dir / f"{c}.jpg"
        if not f.exists():
            fr = grab_frame(video, t)
            if fr is None:
                continue
            j = int(sel[k]) if sel[k] >= 0 else 0
            x0, y0, x1, y1 = [float(v) for v in pl["boxes"][run[k]][j][:4]]
            bh = y1 - y0
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            y0, y1 = max(0, int(cy - 0.8 * bh)), min(fr.shape[0], int(cy + 0.8 * bh))
            x0, x1 = max(0, int(cx - 0.6 * bh)), min(fr.shape[1], int(cx + 0.6 * bh))
            crop = fr[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, (max(1, int(crop.shape[1] * height / crop.shape[0])), height))
            cv2.imwrite(str(f), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out.append({"cluster": c, "t": round(t, 3), "path": str(f)})
    return sorted(out, key=lambda p: p["cluster"])


def save_pick(match_dir: Path, t: float, near_is_her: bool = True) -> dict:
    """Saves the click (the user's own decision: written only when the user clicks)."""
    pick = {"t": round(float(t), 3), "near_is_her": bool(near_is_her), "when": time.strftime("%Y-%m-%d %H:%M")}
    (Path(match_dir) / PICK_FILE).write_text(json.dumps(pick, ensure_ascii=False), encoding="utf-8")
    return pick
