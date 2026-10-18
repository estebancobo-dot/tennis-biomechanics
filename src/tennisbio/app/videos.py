"""Adding a video (docs/aplicacion_local.md §5.1 «Añadir un partido» and the corner cases of §5.2-5.4).

`propose` reads the video and says what it is: its identity by content (size + sampled pieces, the same
identity the pipeline pins in video.json), duration, frame rate, interlacing, and a proposal of tournament,
year, surface and players taken from the file name. It never changes anything. `confirm` registers the
match and queues its work once the user has said yes (one click in the window, a flag on the command line).

The questions it can ask (each one an entry in `Proposal.flags`):
- duplicado: the same video is already there (moved, copied or renamed): nothing is added or recomputed;
- otra_cadena: the same match (tournament, year and both players) from another broadcaster: which one;
- corto: under 20 minutes: is it a summary? (it may not be the main camera);
- largo: over 4 hours: accepted, it only takes longer;
- danado / sin_audio: the video cannot be read or has no sound: registered «con aviso», nothing queued
  for a damaged one (no useless retries);
- sin_jugadora: no known player in the name: the user picks her (or adds her file).
"""
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..catalog import ascii_id, surface_of
from ..pipeline import video_sample
from .db import DB, now

SHORT_S = 20 * 60
LONG_S = 4 * 3600
NAME_MATCH = 0.75             # similarity of a word of the file name to a surname or alias

TOURNAMENT_NAMES = [
    (r"us ?open|yusi?p?open|flushing", "US Open"), (r"australian ?open|avstrali|melbourne", "Australian Open"),
    (r"wimbledon|uimbldon|vimbldon", "Wimbledon"), (r"roland|garros|french ?open|frantsi", "Roland Garros"),
    (r"indian ?wells", "Indian Wells"), (r"miami", "Miami"), (r"madrid", "Madrid"), (r"roma\b|rome|internazionali", "Roma"),
    (r"cincinnati", "Cincinnati"), (r"beijing|pekin", "Pekín"), (r"wuhan", "Wuhan"), (r"doha", "Doha"), (r"dubai", "Dubái"),
    (r"stuttgart|shtutgart", "Stuttgart"), (r"eastbourne", "Eastbourne"), (r"berlin", "Berlín"), (r"wta ?finals|itogovy", "WTA Finals"),
]


@dataclass
class Proposal:
    path: Path
    size: int
    sample: str
    duration: float = 0.0
    fps: float = 0.0
    interlaced: bool = False
    audio: bool = True
    tournament: str = ""
    year: str = ""
    surface: str = ""
    players: list = field(default_factory=list)       # ids of known players found in the name, in order
    match_id: str = ""
    duplicate_of: str = ""                             # match id of the same video, if already there
    same_match: list = field(default_factory=list)     # matches with the same tournament, year and players
    flags: dict = field(default_factory=dict)          # code → message for the user (Spanish)

    @property
    def readable(self) -> bool:
        return "danado" not in self.flags


def _probe(path: Path):
    from ..io.video import probe
    return probe(path)


def _words(name: str) -> list[str]:
    return [w for w in ascii_id(name, 200).split("-") if len(w) >= 4]


def find_players(db: DB, name: str) -> list[str]:
    """Known players whose surname (or an alias read by the OCR) is a word of the file name, in the order
    they appear. Spelling and transliteration differ («Rybakin», «Rybakina»): close words count too."""
    words = _words(name)
    found = []
    for p in db.q("SELECT id, name, aliases FROM players"):
        keys = {ascii_id(p["name"].split()[-1]) if p["name"] else p["id"], p["id"]}
        keys |= {ascii_id(a) for a in json.loads(p["aliases"] or "[]")}
        pos = [i for i, w in enumerate(words) for k in keys if k and difflib.SequenceMatcher(None, w, k).ratio() >= NAME_MATCH]
        if pos:
            found.append((min(pos), p["id"]))
    return [pid for _, pid in sorted(found)]


def tournament_of(name: str) -> str:
    t = ascii_id(name, 200).replace("-", " ")
    for rx, label in TOURNAMENT_NAMES:
        if re.search(rx, t) or re.search(rx, t.replace(" ", "")):
            return label
    return ""


def propose(db: DB, path: Path, probe=_probe) -> Proposal:
    path = Path(path)
    size = path.stat().st_size
    prop = Proposal(path, size, video_sample(path))
    dup = db.one("SELECT m.id, v.path FROM videos v LEFT JOIN matches m ON m.video = v.sample WHERE v.sample=? AND v.size=?",
                 prop.sample, size)
    if dup:
        prop.duplicate_of = dup["id"] or ""
        moved = Path(dup["path"]) != path
        prop.flags["duplicado"] = ("Este vídeo ya está" + (f" (partido {dup['id']})" if dup["id"] else "")
                                   + (", movido o copiado a otra carpeta: lo reconozco por su contenido" if moved else "")
                                   + ". No se añade ni se recalcula nada.")
        if moved:                                   # the same video at a new place: remember where it is now
            db.x("UPDATE videos SET path=? WHERE sample=?", str(path), prop.sample)
        return prop
    try:
        info = probe(path)
        prop.duration, prop.fps, prop.interlaced = float(info.duration), float(info.fps), bool(info.interlaced)
        prop.audio = bool(getattr(info, "audio_tracks", 0) or getattr(info, "audio_rate", None))
    except Exception as e:                          # unreadable: say so in Spanish, never retry blindly
        prop.flags["danado"] = f"El vídeo no se puede leer ({str(e)[:160]}). Prueba a descargarlo otra vez."
        return prop
    if not prop.audio:
        prop.flags["sin_audio"] = ("El vídeo no tiene sonido: los golpes se detectarán solo con la bola y la pose, "
                                   "con algo menos de precisión.")
    if prop.duration < SHORT_S:
        prop.flags["corto"] = (f"Dura {prop.duration / 60:.0f} min. ¿Es un resumen? Puede no ser la cámara principal "
                               "(repeticiones, otros planos). Se acepta igual.")
    elif prop.duration > LONG_S:
        prop.flags["largo"] = f"Dura {prop.duration / 3600:.1f} h: se acepta; solo tardará más."
    stem = path.stem
    prop.tournament = tournament_of(stem)
    prop.surface = surface_of(stem)
    m = re.search(r"(19|20)\d\d", stem)
    prop.year = m.group(0) if m else ""
    prop.players = find_players(db, stem)
    if not prop.players:
        prop.flags["sin_jugadora"] = "No reconozco a ninguna jugadora en el nombre: elige quién es (o añade su ficha)."
    prop.match_id = unique_id(db, "-".join(x for x in (prop.year, ascii_id(prop.tournament, 20, ""), *prop.players[:2]) if x)
                              or ascii_id(stem, 40))
    if prop.tournament and prop.year and len(prop.players) >= 2:
        same = [r["id"] for r in db.q("SELECT id, player, opponent_id FROM matches WHERE tournament=? AND date LIKE ?",
                                      prop.tournament, f"{prop.year}%")
                if {r["player"], r["opponent_id"]} == set(prop.players[:2])]
        if same:
            prop.same_match = same
            prop.flags["otra_cadena"] = (f"Parece el mismo partido que {', '.join(same)} (mismo torneo, año y jugadoras), "
                                         "quizá de otra cadena o en otro idioma. ¿Cuál uso?")
    return prop


def unique_id(db: DB, base: str) -> str:
    base, i = base or "partido", 2
    mid = base
    while db.one("SELECT id FROM matches WHERE id=?", mid):
        mid, i = f"{base}-{i}", i + 1
    return mid


def confirm(db: DB, prop: Proposal, player: str | None = None, opponent_id: str | None = None, *, choose: str = "nuevo",
            **fields) -> str | None:
    """Registers the proposal (the user said yes). Returns the match id, or None when nothing is added
    (a duplicate, or «keep the one I had» for the same match from another broadcaster).
    choose: for «otra_cadena», 'nuevo' (this one; the other is archived, never deleted) or 'existente'."""
    if prop.duplicate_of or "duplicado" in prop.flags:
        return None
    if prop.same_match and choose == "existente":
        return None
    player = player or (prop.players[0] if prop.players else None)
    if not player:
        raise ValueError("Falta la jugadora: elígela o añade su ficha.")
    if opponent_id is None and len(prop.players) > 1:
        opponent_id = next((p for p in prop.players if p != player), None)
    opp = db.one("SELECT name FROM players WHERE id=?", opponent_id) if opponent_id else None
    db.upsert("videos", {"sample": prop.sample, "size": prop.size, "path": str(prop.path), "duration": prop.duration,
                         "fps": prop.fps, "interlaced": int(prop.interlaced), "added": now()}, "sample")
    state, note = "nuevo", ""
    if not prop.readable:
        state, note = "con aviso", prop.flags["danado"]
    elif "sin_audio" in prop.flags:
        note = prop.flags["sin_audio"]
    db.upsert("matches", {"id": prop.match_id, "video": prop.sample,
                          "tournament": fields.get("tournament", prop.tournament),
                          "date": fields.get("date", prop.year), "round": fields.get("round", ""),
                          "surface": fields.get("surface", prop.surface), "player": player,
                          "opponent": fields.get("opponent", opp["name"] if opp else ""), "opponent_id": opponent_id or "",
                          "state": state, "note": note, "created": now()})
    for other in prop.same_match if choose == "nuevo" else []:
        db.x("UPDATE matches SET state='archivado', note=? WHERE id=?", f"sustituido por {prop.match_id} (otra cadena)", other)
    if prop.readable:
        from .jobs import enqueue
        enqueue(db, "partido", match=prop.match_id, player=player, reason="partido nuevo")
    return prop.match_id
