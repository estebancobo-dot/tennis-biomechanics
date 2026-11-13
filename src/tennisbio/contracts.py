"""Data contracts of the stages (#265, R25): checked as soon as a stage ends (pipeline.run_stage), not days later in
the audit. Professional ML pipelines validate every stage's data on the spot (TFX Data Validation, Great Expectations;
Google's ML Test Score asks that an input of a model never arrives empty or at zero unnoticed): R17 was exactly that,
a model trained with the ball and used without it.

Each contract reads the stage's summary (what it returns, kept in the manifest) and raises a fault of the catalogue
(config/fallos.yaml): an input that is empty is C0 (entrada.vacia: the match stops), one under its floor is C1
(entrada.cobertura_baja: marked; a full analysis is not accepted with it). The floors are the audit's «Entradas de los
modelos» (audit.INPUT_FLOORS), now checked when the stage ends. Every stage also has the general contract: the outputs
it declares exist when it ends.
"""
from __future__ import annotations

import json
from typing import Callable

from .faults import fault

CONTRACTS: dict[str, Callable] = {}
FLOORS = {"main_camera": 0.10, "court": 0.50, "onsets_per_min": 5.0, "server_read": 0.50, "near_seen": 0.25}
# no floor for the far player (R27, 13-11): the cheap pass sees her in ~0.1 % of the play in the matches and in F3Set,
# where the detector was trained; it never had her
MIN_PLAY_MIN = 1.0           # below a minute of play (a test clip) the shares say nothing
MIN_CANDIDATES = 20          # candidates of the fine pass from which none confirmed is no result


def contract(stage: str):
    def deco(fn):
        CONTRACTS[stage] = fn
        return fn
    return deco


def check(stage: str, ctx, summary: dict) -> None:
    """The general contract and the stage's own one (if any)."""
    from .pipeline import STAGES
    st = STAGES.get(stage)
    if st is not None:
        missing = [o for o in st.outputs if not ctx.path(o).exists()]
        if missing:
            fault("etapa.sin_salida", f"{stage}: no dejó {', '.join(missing)}")
    fn = CONTRACTS.get(stage)
    # the contract is of the package's own stage (a test's stand-in with the same name has its own summary)
    if fn is not None and st is not None and str(getattr(st.run, "__module__", "")).startswith("tennisbio."):
        fn(ctx, summary or {})


def _duration_min(ctx) -> float | None:
    f = ctx.path("probe.json")
    if not f.exists():
        return None
    try:
        return float(json.loads(f.read_text(encoding="utf-8")).get("duration") or 0) / 60 or None
    except (OSError, ValueError) as e:
        fault("entrada.ilegible", str(f), exc=e)


@contract("probe")
def _probe(ctx, s: dict):
    if not float(s.get("duration_min") or 0) > 0:
        fault("entrada.vacia", "probe: el vídeo no tiene duración")


@contract("scenes")
def _scenes(ctx, s: dict):
    if not int(s.get("main_camera_shots") or 0):
        fault("entrada.vacia", "escenas: ninguna toma de la cámara principal")
    dur = _duration_min(ctx)
    main = float(s.get("main_camera_min") or 0)
    if dur and dur >= MIN_PLAY_MIN and main < FLOORS["main_camera"] * dur:
        fault("entrada.cobertura_baja", f"escenas: cámara principal {main:.1f} de {dur:.0f} min "
                                        f"(mínimo {FLOORS['main_camera']:.0%})")


@contract("court")
def _court(ctx, s: dict):
    if float(s.get("main_camera_min") or 0) > 0 and not int(s.get("with_court") or 0):
        fault("entrada.vacia", "pista: no se encontró en ningún tramo de la cámara principal")
    share = s.get("court_share")
    if share is not None and float(s.get("main_camera_min") or 0) >= MIN_PLAY_MIN and float(share) < FLOORS["court"]:
        fault("entrada.cobertura_baja", f"pista en el {float(share):.0%} de la cámara principal "
                                        f"(mínimo {FLOORS['court']:.0%})")


@contract("audio")
def _audio(ctx, s: dict):
    if not int(s.get("tracks") or 0):
        fault("entrada.cobertura_baja", "sonido: el vídeo no tiene pista de sonido (golpes solo con la imagen)")
        return
    n = int(s.get("onsets") or 0)
    dur = _duration_min(ctx)
    if not n and dur and dur >= MIN_PLAY_MIN:
        fault("entrada.vacia", "sonido: ningún golpe en la pista de sonido")
    if dur and dur >= MIN_PLAY_MIN and n / dur < FLOORS["onsets_per_min"]:
        fault("entrada.cobertura_baja", f"sonido: {n / dur:.1f} golpes por minuto (mínimo {FLOORS['onsets_per_min']:g})")


@contract("score")
def _score(ctx, s: dict):
    n = int(s.get("readings") or 0)
    if not n:
        fault("entrada.cobertura_baja", "marcador: ninguna lectura (" + str(s.get("note") or "sin OCR o sin marcador") + ")")
        return
    if "server_read" in s and int(s.get("server_read") or 0) / n < FLOORS["server_read"]:
        fault("entrada.cobertura_baja", f"marcador: quién saca leído en el {int(s['server_read']) / n:.0%} de "
                                        f"{n} lecturas (mínimo {FLOORS['server_read']:.0%})")


@contract("spotting")
def _spotting(ctx, s: dict):
    inp = s.get("inputs") or {}
    if not s.get("enabled", True) or not inp or float(inp.get("play_min") or 0) < MIN_PLAY_MIN:
        return
    v = float(inp.get("near_seen") or 0)
    if v <= 0:
        fault("entrada.vacia", "detector: la jugadora cercana no se ve en ningún momento del juego")
    elif v < FLOORS["near_seen"]:
        fault("entrada.cobertura_baja", f"detector: la jugadora cercana vista en el {v:.0%} del juego "
                                        f"(mínimo {FLOORS['near_seen']:.0%})")


@contract("fine")
def _fine(ctx, s: dict):
    if int(s.get("candidates") or 0) >= MIN_CANDIDATES and not int(s.get("confirmed") or 0):
        fault("golpes.ninguno", f"{s.get('candidates')} candidatos y ningún golpe confirmado")
