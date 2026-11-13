"""«¿Cuál es ella?»: the user's one click per match (19-10, the only manual step). The identity stage splits
the near player's runs into two people by their clothes; here each group gets one photo (the near player in
the run whose clothes are most typical of its group, checked on the photo itself) and the click on one of them
is saved as <match>/identidad_clic.json. The candidates stage reads it (tennisbio.identity.apply_pick) and, being
part of its fingerprint, re-runs with what follows: no other stage is repeated.

09-11 (request 167): in Rybakina–Pegula both photos were the same woman (both players in white: the clothes
groups were not the two people). The photos are now checked (photo_set): when the clothes cannot tell the two
apart the photos are of the two ends of the court by the scoreboard's end changes, and when neither works no
click is asked and the screen says so."""
import json
import time
from pathlib import Path

import numpy as np

from .. import match_files as _mf
from ..identity import PICK_FILE

PHOTOS = "identidad_fotos"
PHOTOS_VERSION = 2          # 09-11: the photo checked against its group, the cache tied to identity.json
PHOTO_MIN_DIST = 0.10       # the clothes of the two photos must differ at least this much (clothes_distances)
META = "fotos.json"
N_TRY = 3                   # candidate runs per group (each one frame read from the video)


def _groups(runs: list, by: str | None) -> dict[int, int]:
    """run index → group: the clothes cluster («clothes») or the parity of the end changes («ends»)."""
    if by == "clothes":
        return {i: int(r["cluster"]) for i, r in enumerate(runs) if r.get("cluster", -1) >= 0}
    if by == "ends":
        return {i: int(r["end_changes"]) % 2 for i, r in enumerate(runs) if r.get("end_changes") is not None}
    return {}


def state(match_dir: Path) -> dict:
    """{"possible", "done", "pick"}: the photos can be made once the identity stage has split the runs in two
    (by their clothes, or by the end changes when the clothes are alike: identity.json «click_by»)."""
    d = Path(match_dir)
    ident = _mf.at(d, "identity.json")
    # through match_files (09-11): in a library folder the click lives in etapas/, with the identity it decides; read
    # straight from the folder, the 4 clicked reference matches looked unclicked
    pf = _mf.at(d, PICK_FILE)
    pick = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else None
    groups = set()
    if ident.exists():
        idj = json.loads(ident.read_text(encoding="utf-8"))
        groups = set(_groups(idj.get("runs", []), idj.get("click_by", "clothes")).values())
    return {"possible": len(groups) == 2, "done": pick is not None and not pick.get("simulated"), "pick": pick}


def stage_check(match_dir: Path) -> dict | None:
    """The identity stage's check of its clothes groups (clothes.groups_check), or None before it (or v8 and older)."""
    ident = _mf.at(Path(match_dir), "identity.json")
    if not ident.exists():
        return None
    return (json.loads(ident.read_text(encoding="utf-8")).get("clothes") or {}).get("check")


def photos(match_dir: Path, video: Path, height: int = 360) -> list[dict]:
    """One photo per group: [{"cluster", "t", "path", "group_by"}] (cached in <match>/identidad_fotos/); see photo_set."""
    return photo_set(match_dir, video, height)["photos"]


def _identity_key(d: Path) -> str:
    import hashlib
    return f"v{PHOTOS_VERSION}-" + hashlib.sha1(_mf.at(d, "identity.json").read_bytes()).hexdigest()[:16]


def cached(match_dir: Path) -> dict | None:
    """The photo set made for the current identity.json, or None (none yet, or made for another one: until 09-11
    a photo once written was never redone, even after the identity changed)."""
    d = Path(match_dir)
    try:
        meta = json.loads((d / PHOTOS / META).read_text(encoding="utf-8"))
        if meta.get("key") == _identity_key(d) and all(Path(p["path"]).exists() for p in meta.get("photos", [])):
            return meta
    except (OSError, ValueError):  # esperado: a damaged or old photo set is made again
        pass
    return None


def _run_codes(runs: list) -> np.ndarray:
    from ..clothes import CLOTHES_DIM
    X = np.full((len(runs), CLOTHES_DIM), np.nan, np.float32)
    for i, r in enumerate(runs):
        c = r.get("clothes_code")
        if c is not None and len(c) == CLOTHES_DIM:
            X[i] = [np.nan if v is None else v for v in c]
    return X


def rank_runs(runs: list, by: str, n_try: int = N_TRY) -> tuple[dict[int, list[int]], list]:
    """The best runs of each group for its photo, best first, and the groups' typical clothing codes.

    «clothes»: the runs whose clothes are most typical of their group and least of the other one (distance to
    the other group's typical code − to its own; without codes, the clothes margin). Until 09-11 the photo was
    the run with the largest margin, unchecked. «ends»: runs whose neighbours in time have the same parity (a
    misread game on the scoreboard flips the parity of a lone run), longer first."""
    from ..clothes import clothes_distances, group_centroids

    groups = _groups(runs, by)
    X = _run_codes(runs)
    cents: list = [None, None]
    score = {}
    if by == "clothes":
        idx = sorted(groups)
        lab = np.full(len(runs), -1)
        lab[idx] = [groups[i] for i in idx]
        mar = np.array([r.get("clothes_margin") or 0.0 for r in runs], float)
        if np.isfinite(X).any():
            cents = group_centroids(X, lab, mar)
        for i in idx:
            g = groups[i]
            score[i] = float(mar[i]) - 1.0                       # below any checked run
            if cents[0] is not None and cents[1] is not None and np.isfinite(X[i]).any():
                dd = clothes_distances(X[i:i + 1], np.array([cents[g], cents[1 - g]]))[0]
                if np.isfinite(dd).all():
                    score[i] = float(dd[1] - dd[0])
    else:
        order = sorted(groups, key=lambda i: runs[i]["start"])
        for k, i in enumerate(order):
            nb = [order[k - 1]] if k else []
            nb += [order[k + 1]] if k + 1 < len(order) else []
            score[i] = sum(groups[j] == groups[i] for j in nb) + min(runs[i]["end"] - runs[i]["start"], 10_000) / 10_000
    out: dict[int, list[int]] = {0: [], 1: []}
    for i in sorted(score, key=lambda i: -score[i]):
        if len(out[groups[i]]) < n_try:
            out[groups[i]].append(i)
    return out, cents


def _shoot(d: Path, video: Path, ident: dict, want: dict[int, int], height: int) -> dict[int, dict]:
    """For each wanted run (index → group): one frame of the near player read from the video (the middle one of
    the frames where her torso is seen), its crop and the clothing code measured on it."""
    import cv2

    from ..clothes import clothing_feature
    from ..skeleton import Skeleton
    from ..stages import grab_frame, near_runs

    runs = ident["runs"]
    fps = float(ident.get("fps") or 1.0)
    by_start = {int(runs[i]["start"]): i for i in want}
    with np.load(_mf.at(d, "players.npz"), allow_pickle=True) as z:
        pl = {k: z[k] for k in z.files}
    court = json.loads((_mf.at(d, "court.json")).read_text(encoding="utf-8")) if (_mf.at(d, "court.json")).exists() else None
    frames = pl["frames"]
    out = {}
    for run, img, cf, h, app, sel in near_runs(pl, Skeleton("coco17", "right"), court, with_sel=True):
        i = by_start.get(int(frames[run[0]]))
        if i is None:
            continue
        ok = np.flatnonzero(sel >= 0)
        torso = [k for k in ok if np.all(np.asarray(pl["confs"][run[k]][int(sel[k])])[[5, 6, 11, 12]] > 0.3)]
        pool = torso or list(ok)
        k = int(pool[len(pool) // 2]) if len(pool) else len(run) // 2
        t = float(frames[run[k]]) / fps
        fr = grab_frame(video, t)
        if fr is None:
            continue
        j = int(sel[k]) if sel[k] >= 0 else 0
        box = np.asarray(pl["boxes"][run[k]][j][:4], np.float32)
        x0, y0, x1, y1 = [float(v) for v in box]
        bh = y1 - y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        y0, y1 = max(0, int(cy - 0.8 * bh)), min(fr.shape[0], int(cy + 0.8 * bh))
        x0, x1 = max(0, int(cx - 0.6 * bh)), min(fr.shape[1], int(cx + 0.6 * bh))
        crop = fr[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        crop = cv2.resize(crop, (max(1, int(crop.shape[1] * height / crop.shape[0])), height))
        code = None
        if sel[k] >= 0:
            code = clothing_feature(fr, np.asarray(pl["kps"][run[k]][j], np.float32),
                                    np.asarray(pl["confs"][run[k]][j], np.float32), box)
        out[i] = {"t": round(t, 3), "crop": crop, "code": code}
    return out


def _pick_photos(runs: list, mode: str, shots: dict, ranked: dict, cents: list) -> tuple[dict, dict]:
    """Each group's photo among its shots: in «clothes» the one closest to its own group's typical clothes and
    farthest from the other's (verified: closer to its own); in «ends» the best ranked one."""
    from ..clothes import clothes_distances

    chosen, verified = {}, {}
    for g in (0, 1):
        cand = [(i, shots[i]) for i in ranked[g] if i in shots]
        if not cand:
            continue
        best, best_s, ok = cand[0], -np.inf, False
        if mode == "clothes" and cents[0] is not None and cents[1] is not None:
            for i, s in cand:
                if s["code"] is None or not np.isfinite(s["code"]).any():
                    continue
                dd = clothes_distances(np.asarray(s["code"])[None], np.array([cents[g], cents[1 - g]]))[0]
                if np.isfinite(dd).all() and dd[1] - dd[0] > best_s:
                    best, best_s, ok = (i, s), float(dd[1] - dd[0]), bool(dd[0] < dd[1])
        chosen[g], verified[g] = {"run": best[0], **best[1]}, ok
    return chosen, verified


def photos_check(stage_check: dict, chosen: dict, verified: dict, cents: list) -> dict:
    """Are the two photos two different groups? Not when the identity stage found the clothes groups not to be
    two people, when the clothes measured on the two photos are closer than PHOTO_MIN_DIST, or when a photo
    looks more like the other group than its own. {"distinguishable", "why", "photo_dist", "verified"}."""
    from ..clothes import clothes_distances

    c0, c1 = (chosen.get(g, {}).get("code") for g in (0, 1))
    pd = np.nan
    if c0 is not None and c1 is not None:
        pd = clothes_distances(np.asarray(c0)[None], np.asarray(c1)[None])[0, 0]
    out = {"distinguishable": stage_check.get("distinguishable"), "why": stage_check.get("why"),
           "photo_dist": None if not np.isfinite(pd) else round(float(pd), 3),
           "verified": bool(verified.get(0) and verified.get(1))}
    bad = []
    if out["distinguishable"] is False:
        bad.append(out["why"] or "los grupos de ropa no son dos personas")
    if out["photo_dist"] is not None and out["photo_dist"] < PHOTO_MIN_DIST:
        bad.append(f"la ropa de las dos fotos es casi igual (distancia {out['photo_dist']})")
    if cents[0] is not None and cents[1] is not None and not out["verified"]:
        bad.append("una foto se parece más al otro grupo que al suyo")
    if bad:
        out["distinguishable"], out["why"] = False, "; ".join(bad)
    else:
        out["distinguishable"] = True
        out["why"] = out["why"] or "dos personas"
    return out


def photo_set(match_dir: Path, video: Path, height: int = 360, n_try: int = N_TRY) -> dict:
    """The click's photos, one per group, checked (09-11, request 167: in Rybakina–Pegula both photos were the
    same woman). {"photos": [{"cluster", "t", "path", "group_by"}], "by": «clothes» / «ends» / None,
    "check": {"distinguishable", "why", "photo_dist", "verified"}}.

    Groups: the clothes clusters when the identity stage found them to be two people (identity.json
    «click_by»), else the two ends of the court by the end changes read on the scoreboard. The clothes photos
    must pass photos_check; when they do not, the photos are taken by the end changes instead (when the
    scoreboard gives them) and the check keeps «distinguishable» False: the screen says the clothes cannot tell
    them apart. With neither there are no photos: no click is asked that cannot work."""
    import cv2

    d = Path(match_dir)
    hit = cached(d)
    if hit is not None:
        return hit
    ident = json.loads((_mf.at(d, "identity.json")).read_text(encoding="utf-8"))
    runs = ident.get("runs", [])
    stage_check = (ident.get("clothes") or {}).get("check") or {}
    by0 = ident.get("click_by", "clothes")
    check = {"distinguishable": stage_check.get("distinguishable"), "why": stage_check.get("why"),
             "photo_dist": None, "verified": None}
    modes = ["clothes", "ends"] if by0 == "clothes" else ["ends"] if by0 == "ends" else []
    chosen, by = {}, None
    for mode in modes:
        if len(set(_groups(runs, mode).values())) < 2:
            continue
        ranked, cents = rank_runs(runs, mode, n_try)
        shots = _shoot(d, Path(video), ident, {i: g for g, ii in ranked.items() for i in ii}, height)
        got, verified = _pick_photos(runs, mode, shots, ranked, cents)
        if len(got) < 2:
            continue
        if mode == "clothes":
            check = photos_check(stage_check, got, verified, cents)
            if not check["distinguishable"]:
                continue                                    # the end changes instead, if the scoreboard gives them
        chosen, by = got, mode
        break
    if by0 is None and check["distinguishable"] is None:
        check["distinguishable"] = False
    out_dir = d / PHOTOS
    out_dir.mkdir(exist_ok=True)
    photos_out = []
    for g, c in sorted(chosen.items()):
        f = out_dir / (f"{g}.jpg" if by == "clothes" else f"lado{g}.jpg")
        cv2.imwrite(str(f), c["crop"], [cv2.IMWRITE_JPEG_QUALITY, 85])
        photos_out.append({"cluster": g, "t": c["t"], "path": str(f), "group_by": by})
    res = {"key": _identity_key(d), "photos": photos_out, "by": by, "check": check}
    (out_dir / META).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def save_pick(match_dir: Path, t: float, near_is_her: bool = True) -> dict:
    """Saves the click (the user's own decision: written only when the user clicks), with how its photos were
    grouped («by»: the clothes or the end changes), so the candidates stage applies it the same way."""
    pick = {"t": round(float(t), 3), "near_is_her": bool(near_is_her), "when": time.strftime("%Y-%m-%d %H:%M")}
    meta = cached(match_dir) if _mf.at(Path(match_dir), "identity.json").exists() else None
    if meta and meta.get("by"):
        pick["by"] = meta["by"]
    pf = _mf.at(Path(match_dir), PICK_FILE)
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(json.dumps(pick, ensure_ascii=False), encoding="utf-8")
    return pick
