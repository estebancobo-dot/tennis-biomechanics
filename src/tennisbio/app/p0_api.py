"""P0.5d (15-11, docs/p0_plan.md §3 ter): what the new application's management screens do, for its window (pywebview's
js_api, P0.5e) and for the tests: each action of the user is a request on the volume, the one queue turns it into jobs
(tennisbio.infra.peticiones, cloud/cola.py), and the answer comes back on the volume (/cola/app.json, /cola/estado.json).

The application never analyses and never touches the repository: it uploads the video and its record, writes the click
the user made and her approval, and reads the state. Storage by its port (tennisbio.infra.storage): on the PC the Modal
volume's adapter with the key of 5_conectar_nube.bat, in the tests a local folder.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path

from ..infra import peticiones as pt
from ..infra.storage import Storage

LIBRARY = "/biblioteca/partidos"
CLICK = "etapas/identidad_clic.json"


def match_id(ficha: dict) -> str:
    """A match's id from its record (players, tournament, round, date): lower-case ASCII with «-», as the catalogue's."""
    parts = [ficha.get(k) for k in ("jugadora", "rival", "torneo", "ronda", "fecha")]
    text = unicodedata.normalize("NFKD", " ".join(str(p) for p in parts if p)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:100].strip("-")
    if not pt.MATCH_ID.match(slug or ""):
        raise ValueError("la ficha no da un nombre para el partido (faltan la jugadora y la rival)")
    return slug


def player_record(name: str, players_dir: Path | None = None) -> str:
    """The id of her record in config/players (by its name), else the id it will have (her surname): the queue refuses a
    match whose player has no record, with its reason, rather than an analysis that cannot load her height and hand."""
    import yaml

    from ..config import CONFIG_DIR
    d = Path(players_dir) if players_dir else CONFIG_DIR / "players"
    for f in sorted(d.glob("*.yaml")):
        try:
            if str((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("name", "")).strip().lower() == name.strip().lower():
                return f.stem
        except (OSError, yaml.YAMLError):  # esperado: a damaged record is not hers
            continue
    return pt.player_id(name)


def video_minutes(video: Path) -> float | None:
    """The video's length (ffprobe), for the queue's forecast; None without ffprobe or when it cannot be read."""
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True, timeout=120)
        return round(float(r.stdout.strip()) / 60, 1)
    except (ValueError, subprocess.SubprocessError, OSError):  # esperado: unreadable: the queue uses its default
        return None


class Gestion:
    """The management actions. `work`: a folder of this machine for the small files on their way to the storage."""

    def __init__(self, store: Storage, work: Path, now=time.time):
        self.store, self.work, self.now = store, Path(work), now

    # -- requests ---------------------------------------------------------------------------------------------------
    def _ask(self, kind: str, match: str | None = None, **data) -> dict:
        t = self.now()
        r = pt.request(kind, t, match, **data)
        why = pt.problem(r)
        if why:
            return {"ok": False, "motivo": why}
        out = self.work / "peticiones"
        out.mkdir(parents=True, exist_ok=True)
        f = out / pt.file_name(kind, match, t)
        f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        self.store.put_files([f], out, pt.FOLDER)
        return {"ok": True, "peticion": f.name, "cuando": r["cuando"]}

    def _put_json(self, remote: str, obj) -> None:
        rel = remote.strip("/")
        f = self.work / "subida" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        self.store.put_files([f], self.work / "subida", "/")

    # -- the actions --------------------------------------------------------------------------------------------------
    def alta(self, video: str | Path, ficha: dict, preparar: bool) -> dict:
        """Adds a match: checks everything first (a 5 GB upload is never wasted on a record that would be refused),
        then uploads the video as /videos/<match><ext>, its record, and the request (with her yes to the preparation)."""
        video = Path(video)
        if not video.is_file():
            return {"ok": False, "motivo": f"no está el vídeo {video}"}
        try:
            m = match_id(ficha)
        except ValueError as e:  # esperado: the record names no players: said on the screen, nothing uploaded
            return {"ok": False, "motivo": str(e)}
        data = {"video": video.name, "jugadora": str(ficha.get("jugadora") or ""), "rival": str(ficha.get("rival") or ""),
                "jugadora_id": player_record(str(ficha.get("jugadora") or "")),
                "preparar": preparar is True, "minutos_video": video_minutes(video)}
        why = pt.problem(pt.request("alta", self.now(), m, **data))
        if why:
            return {"ok": False, "motivo": why}
        if self.store.read_json(f"{LIBRARY}/{m}/partido.json") is not None:
            return {"ok": False, "motivo": f"ya hay un partido «{m}»"}
        self.store.put_file(video, f"/videos/{m}{video.suffix.lower()}")
        self._put_json(f"{LIBRARY}/{m}/partido.json",
                       {"jugadora": data["jugadora"], "opponent": data["rival"],
                        **{k: str(ficha[a]) for a, k in (("torneo", "tournament"), ("fecha", "date"),
                                                         ("superficie", "surface"), ("ronda", "round")) if ficha.get(a)}})
        return {**self._ask("alta", m, **data), "partido": m}

    def clic(self, match: str, t: float, near_is_her: bool = True, by: str | None = None) -> dict:
        """Her click on «¿Cuál es ella?»: the same file the PC's screen writes (tennisbio.app.identity_click.save_pick)."""
        pick = {"t": round(float(t), 3), "near_is_her": bool(near_is_her),
                "when": time.strftime("%Y-%m-%d %H:%M", time.gmtime(self.now()))}
        if by:
            pick["by"] = by
        self._put_json(f"{LIBRARY}/{match}/{CLICK}", pick)
        return self._ask("clic", match, t=pick["t"], near_is_her=pick["near_is_her"])

    def aprobar(self, match: str, previsto: dict | None = None) -> dict:
        """#262: her approval of the whole analysis, with what the screen showed her (hours, cost)."""
        return self._ask("aprobar", match, previsto=previsto or {})

    def pausar(self) -> dict:
        return self._ask("pausar")

    def reanudar(self) -> dict:
        return self._ask("reanudar")

    def cancelar(self, trabajo: str) -> dict:
        return self._ask("cancelar", trabajo=trabajo)

    def descargado(self, match: str) -> dict:
        return self._ask("descargado", match)

    def borrar_video(self, match: str) -> dict:
        return self._ask("borrar_video", match)

    def persona(self, ficha: dict) -> dict:
        return self._ask("persona", **{k: ficha[k] for k in ("name", "hand", "backhand", "height_m") if k in ficha})

    # -- what comes back ----------------------------------------------------------------------------------------------
    def estado(self) -> dict:
        """The queue's answer: {"app": waits, refused requests, pause, deleted videos; "trabajos": each job's state}."""
        app = self.store.read_json("/cola/app.json") or {}
        jobs = self.store.read_json("/cola/estado.json") or {}
        return {"app": app, "trabajos": {k: {"estado": v.get("estado"), "donde": v.get("donde", ""),
                                             "nota": (v.get("resultado") or {}).get("nota") or v.get("progreso") or ""}
                                         for k, v in jobs.items() if isinstance(v, dict)}}

    def fotos(self, match: str, dest: Path) -> list[Path]:
        """The two photos of the click, made in the cloud after `identity` ([] while they are not there)."""
        try:
            self.store.get(f"/output/{match}/identidad_fotos", Path(dest))
        except (FileNotFoundError, subprocess.CalledProcessError):  # esperado: not made yet (local / Modal's CLI)
            return []
        return sorted((Path(dest) / "identidad_fotos").glob("*.jpg"))


def proponer(ruta: str, jugadora: str = "") -> dict:
    """A match's record proposed from its file's name (tennisbio.app.cards.parse_name, the report's own reading):
    tournament, round, date and the players it names; she corrects only what is wrong."""
    from .cards import parse_name

    p = parse_name(Path(ruta).stem)
    people = [x for x in p.get("players") or [] if x != jugadora]
    return {k: v for k, v in (("jugadora", jugadora or (p.get("players") or [""])[0]),
                              ("rival", people[0] if people else ""), ("torneo", p.get("tournament")),
                              ("ronda", p.get("round")), ("fecha", p.get("iso") or p.get("year"))) if v}


SELF_CHECK = "/app/autocomprobacion.json"        # cloud/cola.py SELF_CHECK copies it to nube-logs (cola/app.json)


class ApiVentana:
    """What the interface calls (ui/src/api.ts, by the same names), in the PC's window: pywebview's js_api object
    (P0.5e). `choose`: the window's file dialog (returns a path or None). Its own state is private (pywebview exposes an
    object's public attributes to the page too); each call is written to the window's log."""

    def __init__(self, gestion: Gestion, jugadora: str, choose=lambda: None, traer=None, abrir=None):
        self._g, self._jugadora, self._choose, self._traer, self._abrir = gestion, jugadora, choose, traer, abrir

    def abrir(self, ruta: str) -> dict:
        """21-11 (P0.5e): a result brought from the cloud (the export's PDF, a montage, its folder) opened with the PC's
        own program (tennisbio.app.p0_nube.open_result, only inside the results' folder)."""
        if self._abrir is None:
            return {"ok": False, "motivo": "esta ventana no sabe abrir ficheros"}
        return self._abrir(ruta)

    def autocomprobacion(self, r: dict) -> dict:
        """21-11 (#310): the window's own check of its videos and series on this PC (ui/src/autocomprobacion.ts), said in
        its log and kept on the cloud's volume (/app/autocomprobacion.json), where Claude reads it."""
        r = {**(r or {}), "cuando": time.strftime("%Y-%m-%d %H:%M:%S")}
        print(f"{time.strftime('%H:%M:%S')} autocomprobación: {r.get('videos_ok')} de {r.get('probados')} vídeos se abren, "
              f"{r.get('series_ok')} series ({r.get('origen')})", flush=True)
        try:
            self._g._put_json(SELF_CHECK, r)
        except Exception as e:  # esperado: no connection: the log keeps it
            print(f"autocomprobación: no se pudo dejar en la nube ({type(e).__name__}: {e})", flush=True)
        return {"ok": True}

    def traer_resultados(self) -> dict:
        """21-11 (P0.5e): the cloud's latest results to the PC (tennisbio.app.p0_nube.pull) and the page made again with
        them; {"recargar": True} tells the page to load itself again."""
        if self._traer is None:
            return {"ok": False, "motivo": "esta ventana no sabe traer resultados"}
        return self._traer()

    def elegir_video(self) -> str | None:
        return self._choose()

    def proponer(self, ruta: str) -> dict:
        return proponer(ruta, self._jugadora)

    def alta(self, ruta: str, ficha: dict, preparar: bool) -> dict:
        return self._g.alta(ruta, ficha, preparar)

    def fotos(self, partido: str) -> list[dict]:
        """The click's photos as images the page shows (data URLs), each with its moment and how it was grouped."""
        import base64

        dest = self._g.work / "fotos" / partido
        files = self._g.fotos(partido, dest)
        meta_f = dest / "identidad_fotos" / "fotos.json"
        try:
            meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {}
        except (OSError, ValueError):  # esperado: the photos without their moments cannot be clicked: none shown
            meta = {}
        by_name = {Path(str(ph.get("path", ""))).name: ph for ph in meta.get("photos") or []}
        out = []
        for f in files:
            ph = by_name.get(f.name)
            if ph is None or ph.get("t") is None:
                continue
            out.append({"src": "data:image/jpeg;base64," + base64.b64encode(f.read_bytes()).decode(), "t": ph["t"],
                        "by": ph.get("group_by") or meta.get("by")})
        return out

    def clic(self, partido: str, t: float, near_is_her: bool = True, by: str | None = None) -> dict:
        return self._g.clic(partido, t, near_is_her, by)

    def aprobar(self, partido: str, previsto: dict) -> dict:
        return self._g.aprobar(partido, previsto)

    def pausar(self) -> dict:
        return self._g.pausar()

    def reanudar(self) -> dict:
        return self._g.reanudar()

    def cancelar(self, trabajo: str) -> dict:
        return self._g.cancelar(trabajo)

    def borrar_video(self, partido: str) -> dict:
        return self._g.borrar_video(partido)


class SinNube:
    """The window's API without the cloud (no Modal key or client): every action says why instead of failing."""

    def __init__(self, why: str):
        self._why = why

    def _no(self, *_a, **_k) -> dict:
        return {"ok": False, "motivo": self._why}

    elegir_video = staticmethod(lambda: None)
    proponer = staticmethod(lambda ruta: {})
    fotos = staticmethod(lambda partido: [])
    alta = clic = aprobar = pausar = reanudar = cancelar = borrar_video = traer_resultados = autocomprobacion = abrir = _no
