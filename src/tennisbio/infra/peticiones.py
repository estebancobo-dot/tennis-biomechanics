"""P0.5d (15-11, docs/p0_plan.md §3 ter): what the user does in the application, as jobs of the one queue. In the core:
the application writes the requests (tennisbio.app.p0_api) and the queue reads them (cloud/cola.py) with the same contract.

The application never touches the repository: each action of the user is a file of its own on the volume,
/app/peticiones/<UTC time>_<type>_<match>.json, written through the storage port and never overwritten or deleted (the
record of what was asked and when). Each pass of the queue (cloud/cola.py) reads them all and turns them, here, into
the same jobs, cancellations and pause the queue already knows. Pure functions: the queue gives the requests and the
state, this gives back what to do.

    alta          its video in /videos/ and its record in /biblioteca/partidos/<match>/partido.json, with her yes to its
                  preparation (#262: the screen showed what it spends) → the 10-minute test, then the cheap pass on a
                  CPU session and the stages up to `identity` (the click's photos)
    clic          /biblioteca/partidos/<match>/etapas/identidad_clic.json (the same file the PC writes)
    aprobar       the user's approval (#262) with what the screen showed (hours, cost) → the whole match
    pausar        nothing new is launched (what is running finishes); `reanudar` lifts it
    cancelar      a job, the same way as Claude's cancellations (the reason says «desde la aplicación»)
    descargado    the application has the match's results on the PC
    borrar_video  the match's video off the volume, only when it is analysed and its results downloaded (requirement 10)
    persona       a player's record (name, hand, backhand, height) for the cloud's catalogue
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import PurePosixPath

FOLDER = "/app/peticiones"
PREFIX = "app_"
TYPES = ("alta", "clic", "aprobar", "pausar", "reanudar", "cancelar", "descargado", "borrar_video", "persona")
MATCH_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,100}$")
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".ts", ".m2ts", ".mts", ".trp", ".avi", ".webm")
HANDS, BACKHANDS = ("right", "left"), ("one_handed", "two_handed")
# the stages of each part (as the split test T24 measures them): the start on a CPU session, the rest up to the click
# on a GPU one; after the approval the whole match, which keeps what these did
CPU_STAGES = ["probe", "scenes", "court", "audio"]
CLICK_STAGES = ["players", "score", "identity"]
# after her approval (T24, adopted 15-11): the fine pass on a GPU, then the end (views, clips) on a CPU session
FINE_STAGES = ["spotting", "candidates", "fine", "fine_opponent", "fine_doubtful"]
END_STAGES = ["views", "views_link", "view_clips", "slowmo_fine"]


APP_PLAYERS = "app/personas.json"          # the queue writes the people added in the application (the cloud reads it)


def player_id(name: str) -> str:
    """A player record's id from her name, as config/players names them (the surname, lower-case ASCII)."""
    t = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]+", t)
    return words[-1] if words else ""


def file_name(kind: str, match: str | None, now: float) -> str:
    """Sorted by time: the order the user did things in (the last pause or resume wins)."""
    return f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime(now))}_{kind}_{match or 'cola'}.json"


def request(kind: str, now: float, match: str | None = None, **data) -> dict:
    if kind not in TYPES:
        raise ValueError(f"petición desconocida: {kind}")
    return {"tipo": kind, "partido": match, "cuando": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now)),
            "ts": round(now, 3), "desde": "aplicacion", **data}


def problem(r: dict) -> str | None:
    """Why a request cannot be used (None when it can): it stays in the state with its reason; the queue goes on."""
    if not isinstance(r, dict) or r.get("tipo") not in TYPES:
        return "tipo de petición desconocido"
    kind, m = r["tipo"], r.get("partido")
    if kind in ("alta", "clic", "aprobar", "descargado", "borrar_video") and not (isinstance(m, str) and MATCH_ID.match(m)):
        return "sin un partido válido (minúsculas, números, . _ -)"
    if kind == "alta":
        if PurePosixPath(str(r.get("video") or "")).suffix.lower() not in VIDEO_EXT:
            return f"el vídeo no es de un tipo conocido ({', '.join(VIDEO_EXT)})"
        if not str(r.get("jugadora") or "").strip() or not str(r.get("rival") or "").strip():
            return "faltan la jugadora o la rival"
        if r.get("preparar") is not True:        # #262: the screen showed what the preparation spends and she said yes
            return "el alta no lleva la aprobación de su preparación (prueba de 10 min y pasada hasta el clic)"
    if kind == "clic" and not isinstance(r.get("t"), (int, float)):
        return "el clic no dice en qué momento"
    if kind == "cancelar" and not str(r.get("trabajo") or "").strip():
        return "no dice qué trabajo cancelar"
    if kind == "persona":
        if not str(r.get("name") or "").strip():
            return "la persona no tiene nombre"
        if r.get("hand") not in HANDS or r.get("backhand") not in BACKHANDS:
            return "faltan la mano o el revés"
    return None


def interpret(requests: list[tuple[str, dict]], analysed: set[str] | None = None,
              players: set[str] | None = None) -> dict:
    """{"trabajos", "cancelar", "pausa", "borrar", "partidos", "personas", "errores", "esperas"} from the requests
    (name, content), in the order of their names. `analysed`: the matches whose whole analysis finished (the only ones
    whose video may go). `players`: the ids of the player records there are (config/players); with it, a match whose
    player has no record (there nor added in the application) is refused with its reason. Jobs carry the `app_` prefix:
    they never clash with Claude's."""
    analysed = analysed or set()
    out: dict = {"trabajos": [], "cancelar": {}, "pausa": None, "borrar": [], "partidos": [], "personas": [],
                 "errores": [], "esperas": {}}
    alta, clicks, approved, downloaded, delete = {}, set(), {}, set(), []
    for name, r in sorted(requests, key=lambda x: x[0]):
        why = problem(r)
        if why:
            out["errores"].append((name, why))
            continue
        kind, m = r["tipo"], r.get("partido")
        if kind == "alta":
            alta.setdefault(m, r)                    # the first one counts: the same match is never added twice
        elif kind == "clic":
            clicks.add(m)
        elif kind == "aprobar":
            approved[m] = r
        elif kind == "descargado":
            downloaded.add(m)
        elif kind == "borrar_video":
            delete.append((name, m))
        elif kind in ("pausar", "reanudar"):
            out["pausa"] = {"en_pausa": kind == "pausar", "cuando": r.get("cuando", "")}
        elif kind == "cancelar":
            out["cancelar"][str(r["trabajo"])] = f"cancelado desde la aplicación ({r.get('cuando', '')})"
        elif kind == "persona":
            out["personas"].append({"id": player_id(r["name"]),
                                    **{k: r[k] for k in ("name", "hand", "backhand", "height_m") if k in r}})
    known = None if players is None else set(players) | {p["id"] for p in out["personas"]}
    for m, r in alta.items():
        ext = PurePosixPath(str(r["video"])).suffix.lower()
        pid = str(r.get("jugadora_id") or player_id(r["jugadora"]))
        if known is not None and pid not in known:     # the analysis loads config/players/<id>.yaml: never without it
            out["errores"].append((f"alta {m}", f"no hay ficha de «{r['jugadora']}» ({pid}): añádela en Personas"))
            continue
        out["partidos"].append({"id": m, "video": f"{m}{ext}", "jugador": pid, "jugadora": r["jugadora"].strip(),
                                "rival": r["rival"].strip(), "desde": "aplicacion"})
        prep = f"la preparación, aprobada al añadirlo ({r.get('cuando', '')})"     # #262: her yes on the alta screen
        out["trabajos"] += [
            {"id": f"{PREFIX}prueba_{m}", "accion": "prueba", "partido": m},
            {"id": f"{PREFIX}cortes_{m}", "accion": "partido", "partido": m, "cpu": True, "etapas": CPU_STAGES,
             "tras": f"{PREFIX}prueba_{m}", "minutos_video": r.get("minutos_video"), "aprobado": True,
             "aprobado_en": prep},
            {"id": f"{PREFIX}clic_{m}", "accion": "partido", "partido": m, "etapas": CLICK_STAGES,
             "tras": f"{PREFIX}cortes_{m}", "minutos_video": r.get("minutos_video"), "aprobado": True,
             "aprobado_en": prep}]
        if m not in clicks:
            out["esperas"][m] = "falta el clic «¿Cuál es ella?» (cuando estén sus fotos)"
        elif m not in approved:
            out["esperas"][m] = "falta tu aprobación del análisis completo"
        else:                                            # #262: only with the user's own approval, and after the click
            ok = {"accion": "partido", "partido": m, "aprobado": True, "minutos_video": r.get("minutos_video"),
                  "aprobado_en": approved[m].get("cuando", "")}
            out["trabajos"] += [{"id": f"{PREFIX}fina_{m}", **ok, "etapas": FINE_STAGES, "tras": f"{PREFIX}clic_{m}"},
                                {"id": f"{PREFIX}{m}", **ok, "cpu": True, "etapas": END_STAGES, "tras": f"{PREFIX}fina_{m}"}]
    for t in out["trabajos"]:
        if t.get("minutos_video") is None:
            t.pop("minutos_video", None)
    for name, m in delete:
        if m not in analysed:
            out["errores"].append((name, "el partido no está analizado entero: su vídeo se queda"))
        elif m not in downloaded:
            out["errores"].append((name, "la aplicación aún no tiene sus resultados en el PC: su vídeo se queda"))
        else:
            out["borrar"].append(m)
    return out


def paused_decisions(decisions: list, pause: dict | None) -> list:
    """While paused nothing new starts (the queue's decisions turned into waits, with the time it was paused)."""
    if not pause or not pause.get("en_pausa"):
        return decisions
    why = f"en pausa desde la aplicación ({pause.get('cuando', '')})"
    return [(jid, None, why if src else w) for jid, src, w in decisions]
