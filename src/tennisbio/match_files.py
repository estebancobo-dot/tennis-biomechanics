"""Where each file of a match lives (docs/almacenamiento.md, block 4 connection, 24-10).

A match folder is either the flat one of before (<output>/<id>/, every file side by side) or the library's
(biblioteca/partidos/<año>/<partido>/): there the cheap pass (one per video) is in etapas/ and the rest (fine
pass, windows, series, caches) in golpes/<jugadora>/. Every reader and writer asks `at(match_dir, name)`, so
the same code works on both and the old folders keep working until they are migrated."""
import json
from pathlib import Path

# the cheap pass and what decides who is who (one per video): etapas/. The migration (library.plan_migration)
# splits the old folders with this same list.
CHEAP_FILES = {"probe.json", "scenes.json", "audio_onsets.json", "audio_track.json", "players.npz", "court.json",
               "score.json", "identity.json", "candidates.json", "manifest.json", "video.json", "source.mkv",
               "source.json", "manifest.damaged.json", "identidad_clic.json", "identidad_fotos", "spotting.json",
               "ball_track.npz", "registro.log"}


def is_library(match_dir: Path) -> bool:
    """A library match folder has etapas/ (a partido.json alone is not enough: the application's test runs
    write one of their own in the flat folders, catalog.save_test_info)."""
    return (Path(match_dir) / "etapas").is_dir()


def player_dir(match_dir: Path) -> Path:
    """golpes/<jugadora>/ of the analysed player (partido.json «jugadora», else the only folder there)."""
    d = Path(match_dir)
    who = None
    try:
        who = json.loads((d / "partido.json").read_text(encoding="utf-8")).get("jugadora")
    except (OSError, ValueError):
        pass
    if not who:
        sub = sorted(p.name for p in (d / "golpes").glob("*") if p.is_dir()) if (d / "golpes").is_dir() else []
        who = sub[0] if len(sub) == 1 else "jugadora"
    return d / "golpes" / who


def at(match_dir: Path, name: str) -> Path:
    """The path of `name` (a file or a sub-folder such as windows/ or series/) in a match folder."""
    d = Path(match_dir)
    if not is_library(d):
        return d / name
    first = name.replace("\\", "/").split("/")[0]
    if first in CHEAP_FILES:
        return d / "etapas" / name
    return player_dir(d) / name


def test_info(match_dir: Path) -> Path:
    """What a run knew of its match (catalog.TEST_INFO): partido.json in a flat folder; in the library that
    name is the library's own record, so it is etapas/partido_origen.json (where the migration copies it)."""
    d = Path(match_dir)
    return d / "etapas" / "partido_origen.json" if is_library(d) else d / "partido.json"
