"""The copy for the phone (docs/aplicacion_local.md §5.1 «Copia al móvil», part 4): the web of one analysis in a
folder that works without connection, <root>/movil/<jugadora>_<golpe>/, plus the same folder as one .zip to
send to the phone (cable, USB stick or memory card; nothing leaves the PC by itself).

- The web is the analysis in use (`actual`), the same page, with every path relative to the folder.
- Each stroke's window video is re-encoded at 720p at most (broadcast windows are 1080), H.264 + AAC with
  the index at the start (it plays while it loads). The page draws the skeleton in the coordinates of the
  original video: each stroke carries `vk` (pixels of the copy per pixel of the original) and the page scales
  only the picture it draws (report_template.html, cropRect / drawFrame), never the measures.
- Frame series, thumbnails, the side view from practice and the PDF summary are copied as they are.
- Again later: only what changed is encoded (a clip newer than its copy), and what no longer belongs to the
  analysis is removed from the copy (it is a copy, its source stays).
- It never starts if the copy does not fit on the disk, and says so."""
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from . import storage
from .quality import analysis_id

HEIGHT = 720
MARK = "const DATA = "


def root(paths) -> Path:
    return paths.data.parent / "movil"


def read_data(html: str) -> tuple[dict, int, int]:
    """The analysis' data in its web (report.build writes it on one line after `const DATA = `)."""
    i = html.index(MARK) + len(MARK)
    data, end = json.JSONDecoder().raw_decode(html, i)
    return data, i, end


def _size(path: Path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
        return w, h
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def encode(src: Path, dst: Path, height: int = HEIGHT) -> bool:
    """src at `height` lines at most (never enlarged), playable on any phone."""
    tmp = dst.with_name(dst.stem + ".tmp.mp4")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?",
                        "-vf", f"scale=-2:'min({height},ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)],
                       capture_output=True, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, dst)
    return True


def _fresh(src: Path, dst: Path) -> bool:
    return dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime


def _copy(src: Path, dst: Path) -> bool:
    if _fresh(src, dst) and dst.stat().st_size == src.stat().st_size:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def plan(paths, player: str, stroke: str, web: Path | None = None, dest: Path | None = None) -> dict:
    """What the copy needs: the web in use, its clips and an estimate of the space (a 720p clip is about half
    of a 1080 one; the rest is copied as it is). `web`/`dest` in place of the analysis' (the PC's check uses
    the automatic cycle's reports while the application has published none)."""
    aid = analysis_id(player, stroke)
    web = Path(web) if web else paths.analyses / aid / "actual"
    page = web / "index.html"
    if not page.exists():
        raise FileNotFoundError(f"Todavía no hay análisis publicado de {aid}: se copia cuando termine el primero.")
    data, _, _ = read_data(page.read_text(encoding="utf-8"))
    clips = [(r["id"], (web / r["video"]).resolve()) for r in data.get("strokes", []) if r.get("video")]
    have = [(i, p) for i, p in clips if p.exists()]
    pr = data.get("practice") or {}
    prc = [(web / pr["base"] / s["clip"]).resolve() for s in pr.get("strokes", []) if pr.get("base") and s.get("clip")]
    need = sum(p.stat().st_size for _, p in have) * 0.55 + sum(p.stat().st_size for p in prc if p.exists()) * 0.55
    need += sum(f.stat().st_size for d in ("series", "thumbs") for f in (web / d).glob("*") if (web / d).exists())
    return {"id": aid, "web": web, "data": data, "clips": have, "missing": len(clips) - len(have),
            "practice": prc, "bytes": int(need), "dest": Path(dest) if dest else root(paths) / aid}


def make(paths, player: str, stroke: str, zip_it: bool = True, progress=None, enc=None,
         web: Path | None = None, dest: Path | None = None) -> dict:
    """Writes (or brings up to date) the phone copy; returns where it is and what it did."""
    enc = enc or encode
    p = plan(paths, player, stroke, web, dest)
    dest, web, data = p["dest"], p["web"], p["data"]
    need = p["bytes"] * (2 if zip_it else 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if storage.free_bytes(dest.parent) < need + 2e9:
        raise RuntimeError(f"No cabe la copia para el móvil: hacen falta unos {storage._gb(need)} GB "
                           f"y quedan {storage._gb(storage.free_bytes(dest.parent))} GB libres.")
    (dest / "v").mkdir(parents=True, exist_ok=True)
    res = {"dest": str(dest), "encoded": 0, "kept": 0, "failed": [], "missing": p["missing"], "removed": 0}
    by_id = {r["id"]: r for r in data["strokes"]}
    for r in data["strokes"]:
        if r.get("video") and (web / r["video"]).resolve() not in {c for _, c in p["clips"]}:
            r.pop("video")                        # its window no longer exists: «sin vídeo», never a broken link
    total = len(p["clips"])
    for k, (sid, src) in enumerate(p["clips"]):
        out = dest / "v" / f"{sid}.mp4"
        if _fresh(src, out):
            res["kept"] += 1
        elif enc(src, out):
            res["encoded"] += 1
        else:
            res["failed"].append(sid)
        r = by_id[sid]
        if out.exists():
            r["video"] = f"v/{sid}.mp4"
            a, b = _size(src), _size(out)
            if a and b and a[0] and b[0] != a[0]:
                r["vk"] = round(b[0] / a[0], 5)
            else:
                r.pop("vk", None)
        else:
            r.pop("video", None)
        if progress:
            progress(k + 1, total)
    for sub in ("series", "thumbs"):
        for f in (web / sub).glob("*") if (web / sub).exists() else []:
            _copy(f, dest / sub / f.name)
    pr = data.get("practice")
    if pr and pr.get("base"):
        src_base = (web / pr["base"]).resolve()
        for s in pr.get("strokes", []):
            for key in ("clip", "thumb"):
                if not s.get(key):
                    continue
                src, out = src_base / s[key], dest / "entrenamiento" / s[key]
                if not src.exists():
                    s.pop(key)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                if key == "thumb":
                    _copy(src, out)
                elif not _fresh(src, out) and not enc(src, out):
                    s.pop(key)
        pr["base"] = "entrenamiento"
    exports = []
    for e in data.get("exports", []):
        src = (web / e).resolve()
        if src.suffix.lower() == ".pdf" and src.exists():
            _copy(src, dest / "exportar" / src.name)
            exports.append(f"exportar/{src.name}")
    data["exports"] = exports                     # the montages stay on the PC: the clips are already here
    data["mobile"] = {"from_version": json.loads((web.parent / "analisis.json").read_text(encoding="utf-8")).get("version")
                      if (web.parent / "analisis.json").exists() else None, "height": HEIGHT}
    keep = {f"{i}.mp4" for i, _ in p["clips"]}
    for f in (dest / "v").glob("*.mp4"):          # strokes no longer in the analysis
        if f.name not in keep:
            f.unlink(missing_ok=True)
            res["removed"] += 1
    for sub in ("series", "thumbs"):
        names = {f.name for f in (web / sub).glob("*")} if (web / sub).exists() else set()
        for f in (dest / sub).glob("*") if (dest / sub).exists() else []:
            if f.name not in names:
                f.unlink(missing_ok=True)
    html = page_html(web / "index.html", data)
    (dest / "index.html").write_text(html, encoding="utf-8")
    (dest / "LEEME.txt").write_text(README, encoding="utf-8")
    if zip_it:
        z = dest.parent / f"{dest.name}.zip"
        tmp = z.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:      # the videos are already compressed
            for f in sorted(dest.rglob("*")):
                if f.is_file() and not f.name.endswith(".tmp.mp4"):
                    zf.write(f, Path(dest.name) / f.relative_to(dest))
        os.replace(tmp, z)
        res["zip"] = str(z)
    res["bytes"] = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    res["strokes"] = len(data["strokes"])
    res["with_video"] = sum(1 for r in data["strokes"] if r.get("video"))
    return res


def page_html(page: Path, data: dict) -> str:
    html = page.read_text(encoding="utf-8")
    _, i, end = read_data(html)
    return html[:i] + json.dumps(data, ensure_ascii=False) + html[end:]


README = """Tennisbio: copia para el móvil, sin conexión.

En un Android (p. ej. Google Pixel 8):
1. Conecta el teléfono al PC con el cable USB-C y, en el aviso del teléfono, elige «Transferencia de archivos».
2. En el Explorador de Windows aparece «Pixel 8»: arrastra el .zip a su carpeta Download.
3. En el teléfono, abre la app Archivos, toca el .zip y «Extraer».
4. Abre Chrome y escribe en la barra: file:///sdcard/Download/<nombre de esta carpeta>/index.html
   (guárdala en marcadores o «Añadir a pantalla de inicio» para la próxima vez).
Todo está dentro: la página, los vídeos de cada golpe (720p), las series del esqueleto y las fotos.
Es una copia: los análisis nuevos llegan cuando vuelvas a pulsar «Copiar al móvil» en el PC.
"""
