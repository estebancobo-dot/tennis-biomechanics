"""Data contracts of the stages (#265, R25): checked as soon as a stage ends (pipeline.run_stage), not days later in
the audit. Professional ML pipelines validate every stage's data on the spot (TFX Data Validation, Great Expectations;
Google's ML Test Score asks that an input of a model never arrives empty or at zero unnoticed): R17 was exactly that,
a model trained with the ball and used without it.

Each contract reads the stage's summary (what it returns, kept in the manifest) and its outputs and raises a fault of
the catalogue (config/fallos.yaml): an empty or broken output is C0 (the match stops), an input under its minimum is
C1 (marked; a full analysis is not accepted with it). Every stage has at least the general contract: the outputs it
declares exist when it ends.
"""
from __future__ import annotations

from typing import Callable

from .faults import fault

CONTRACTS: dict[str, Callable] = {}


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
    if fn is not None:
        fn(ctx, summary or {})
