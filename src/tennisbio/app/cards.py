"""What the match list shows about each match, like a sports app (25-10, the user: «nombres, logos, fechas,
fotos… es muy cutre»): the players' full names with their own photo taken from the match itself (the clothes
groups of the identity stage; hers once the user has clicked), the tournament as a coloured badge (no logos of
others), the round in words, the date, the surface and a real frame of the main camera.

Everything comes from the match's own folder and video, nothing from outside. Made once per match and kept in
<data>/tarjetas/ (re-made when the click or the identity change), so the list stays fast."""
import json
import re
from pathlib import Path

from .. import match_files as mf

MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# the four majors (badge colours of the app's own, not their logos)
TOURNAMENTS = {
    "us open": ("US Open", "#1f5fbf"), "yusipopen": ("US Open", "#1f5fbf"), "yusopen": ("US Open", "#1f5fbf"),
    "usopen": ("US Open", "#1f5fbf"), "australian open": ("Australian Open", "#1c9ad6"), "avstral": ("Australian Open", "#1c9ad6"),
    "wimbledon": ("Wimbledon", "#3b7a3b"), "uimbldon": ("Wimbledon", "#3b7a3b"), "roland": ("Roland Garros", "#c4612a"),
}
ROUNDS = [(r"\b(final)\b", "Final"), (r"polufinal|\bsf\b|semifinal", "Semifinal"), (r"chetvertfinal|\bqf\b|cuartos", "Cuartos de final"),
          (r"\br4\b|octavos", "Octavos de final"), (r"\br3\b", "Tercera ronda"), (r"\br2\b", "Segunda ronda"), (r"\br1\b", "Primera ronda")]
# full names of the players met so far (the file names carry surnames, often transliterated)
PLAYERS = {"rybakin": "Elena Rybakina", "sobolenko": "Aryna Sabalenka", "sabalenka": "Aryna Sabalenka", "gauff": "Coco Gauff",
           "osaka": "Naomi Osaka", "zheng": "Zheng Qinwen", "swiatek": "Iga Świątek", "svyontek": "Iga Świątek",
           "pegula": "Jessica Pegula", "kenin": "Sofia Kenin", "azarenka": "Victoria Azarenka", "ostapenko": "Jelena Ostapenko",
           "keys": "Madison Keys", "jabeur": "Ons Jabeur", "rybakina": "Elena Rybakina"}
ROUND_CODES = {"f": "Final", "sf": "Semifinal", "qf": "Cuartos de final", "r16": "Octavos de final", "r4": "Octavos de final",
               "r32": "Tercera ronda", "r3": "Tercera ronda", "r64": "Segunda ronda", "r2": "Segunda ronda",
               "r128": "Primera ronda", "r1": "Primera ronda"}
SURFACES = {"dura": "Pista dura", "hierba": "Hierba", "tierra batida": "Tierra batida"}


def parse_name(name: str) -> dict:
    """Tournament, round, date and players read from a broadcast's file or folder name."""
    low = re.sub(r"^(smoke|poc\w*):", "", name).lower().replace("_", "-")
    tour, color = "", ""
    for k, (t, c) in TOURNAMENTS.items():
        if k.replace(" ", "-") in low or k in low.replace("-", " "):
            tour, color = t, c
            break
    rnd = next((r for rx, r in ROUNDS if re.search(rx, low.replace("-", " "))), "")
    date, iso = "", ""
    m = re.search(r"(\d{1,2})-(\d{1,2})-(20\d\d)", low)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            date, iso = f"{d} {MONTHS[mo - 1]} {y}", f"{y}-{mo:02d}-{d:02d}"
    year = re.search(r"(20\d\d)", low)
    people = []
    for w in re.split(r"[-\s.]+", low):
        for k, full in PLAYERS.items():
            if w.startswith(k) and full not in people:
                people.append(full)
    return {"tournament": tour, "color": color, "round": rnd, "date": date, "iso": iso,
            "year": (year.group(1) if year else ""), "players": people}


def _photos(d: Path) -> list[dict]:
    """The clothes-group photos made for the click ([{cluster, t, path}]), from identidad_fotos/ (no video read)."""
    fdir = mf.at(d, "identidad_fotos")
    ident = mf.at(d, "identity.json")
    if not fdir.is_dir() or not ident.exists():
        return []
    try:
        runs = json.loads(ident.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError):
        return []
    out = []
    for f in sorted(fdir.glob("*.jpg")):
        try:
            c = int(f.stem)
        except ValueError:
            continue
        out.append({"cluster": c, "path": str(f), "starts": [r.get("start", 0) for r in runs if r.get("cluster") == c]})
    return out


def _her_cluster(d: Path, photos: list[dict]) -> int | None:
    """The clothes group the user clicked (identidad_clic.json: the time of the photo chosen)."""
    pick = mf.at(d, "identidad_clic.json")
    if not pick.exists() or not photos:
        return None
    try:
        p = json.loads(pick.read_text(encoding="utf-8"))
        if p.get("simulated"):
            return None
        ident = json.loads(mf.at(d, "identity.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fps = float(ident.get("fps") or 1.0)
    t = float(p.get("t", -1)) * fps + 1e-6                 # the photo is in the middle of its run: the run started before
    runs = [r for r in ident.get("runs", []) if r.get("cluster", -1) >= 0 and r.get("start", 0) <= t]
    if not runs:
        return None
    return int(max(runs, key=lambda r: r.get("start", 0))["cluster"])


def _thumb(d: Path, video: str, dest: Path) -> str:
    """A frame of the main camera in the middle of the match (once), as a small JPEG."""
    if dest.exists():
        return str(dest)
    try:
        sc = json.loads(mf.at(d, "scenes.json").read_text(encoding="utf-8"))
        fps = float(sc.get("fps") or 1.0)
        main = [s for s in sc.get("shots", []) if s.get("main_camera") and s["end"] - s["start"] > 5 * fps]
        if not main or not video or not Path(video).exists():
            return ""
        s = main[len(main) // 2]
        from ..stages import grab_frame
        import cv2
        fr = grab_frame(Path(video), (s["start"] + s["end"]) / 2 / fps)
        if fr is None:
            return ""
        dest.parent.mkdir(parents=True, exist_ok=True)
        h = 180
        cv2.imwrite(str(dest), cv2.resize(fr, (int(fr.shape[1] * h / fr.shape[0]), h)), [cv2.IMWRITE_JPEG_QUALITY, 80])
        return str(dest)
    except Exception:  # noqa: BLE001 — no frame: the card shows the drawn court
        return ""


def card(m: dict, d: Path, data_dir: Path, her_name: str) -> dict:
    """The card of one match row (m: the index row with vpath)."""
    cache = data_dir / "tarjetas" / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', m['id'])}.json"
    stamp = [str(p.stat().st_mtime) if p.exists() else "" for p in (mf.at(d, "identidad_clic.json"), mf.at(d, "identity.json"))]
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("stamp") == stamp and (not c.get("thumb") or Path(c["thumb"]).exists()):
            return c
    except (OSError, ValueError):
        pass
    info = parse_name(m["id"] + " " + Path(m.get("vpath") or "").stem)
    tour = m.get("tournament") or info["tournament"]
    color = info["color"] or next((c for k, (t, c) in TOURNAMENTS.items() if t.lower() == (tour or "").lower()), "#555")
    people = info["players"]
    her = her_name or "Elena Rybakina"
    rival = next((p for p in people if p != her), "") or (m.get("opponent") or "")
    photos = _photos(d)
    hc = _her_cluster(d, photos)
    ph_her = next((p["path"] for p in photos if p["cluster"] == hc), "") if hc is not None else ""
    ph_rival = next((p["path"] for p in photos if p["cluster"] != hc), "") if hc is not None else ""
    rnd = m.get("round") or ""
    rnd = ROUND_CODES.get(rnd.lower(), rnd) or info["round"]
    c = {"stamp": stamp, "tournament": tour, "color": color, "round": rnd,
         "date": info["date"] or (m.get("date") or "")[:10], "iso": info["iso"] or (m.get("date") or ""),
         "year": info["year"] or (m.get("date") or "")[:4], "her": her, "rival": rival,
         "her_photo": ph_her, "rival_photo": ph_rival, "photos": [p["path"] for p in photos],
         "click_done": hc is not None, "click_possible": len(photos) == 2,
         "surface": SURFACES.get(m.get("surface") or "", m.get("surface") or ""),
         "thumb": _thumb(d, m.get("vpath") or "", data_dir / "tarjetas" / f"{cache.stem}.jpg")}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return c
