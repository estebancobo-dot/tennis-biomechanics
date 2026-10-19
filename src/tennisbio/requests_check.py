"""Checks of the register of user requests (docs/peticiones_usuario.md).

The register lists every request and requirement the user made (chat, pasted lists, CLAUDE.md, the
technical matrix, coach videos, the Ivanovic guide, the audits), with its real status. This module makes
sure the register cannot hide anything:

- every row has a known status (HECHO, PARCIAL, FALTA/NO, NO MEDIBLE, NO APLICA);
- a HECHO row names its evidence (where it is in the code) and that evidence exists: each `file` it
  names is in the repository and each `module.name` is written in that module;
- a row that is not HECHO says what is missing;
- numbers are unique.

`pending()` gives the rows that are not done, so the audit and the automatic review can list them first,
never folded among the passing checks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "peticiones_usuario.md"
SRC = ROOT / "src" / "tennisbio"
# canonical statuses; "NO" (older rows) means FALTA
STATUSES = ("HECHO", "PARCIAL", "FALTA", "NO MEDIBLE", "NO APLICA")
FILE_DIRS = (ROOT, SRC, ROOT / "scripts", ROOT / "scripts" / "windows", ROOT / "docs", ROOT / "config", SRC / "app", SRC / "pose", SRC / "io", SRC / "validation")
EMPTY = {"", "—", "-", "–"}


@dataclass
class Row:
    n: int
    text: str
    state: str          # as written in the register
    code: str           # «Dónde está (código)»
    web: str            # «Dónde se ve en la web»
    check: str          # «Cómo se valida solo»
    missing: str        # «Qué falta»

    @property
    def status(self) -> str | None:
        return canonical(self.state)


def canonical(state: str) -> str | None:
    """The canonical status of a register cell, or None if it has none."""
    s = re.sub(r"\*", "", state).strip().upper()
    if "NO MEDIBLE" in s:                 # also «HECHO (como «no medible»)»: said so, not measured
        return "NO MEDIBLE"
    for st in ("NO APLICA", "PARCIAL", "FALTA", "HECHO"):
        if s.startswith(st):
            return st
    if re.match(r"^NO\b", s):
        return "FALTA"
    return None


def parse(path: Path = REGISTER) -> list[Row]:
    """Rows of the register's table (first column a number)."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 3 and c[0].isdigit():
            c += [""] * (7 - len(c))
            rows.append(Row(int(c[0]), c[1], c[2], c[3], c[4], c[5], c[6]))
    return rows


def _file_ok(name: str) -> bool:
    name = name.strip().rstrip("/")
    return any((d / name).exists() for d in FILE_DIRS) or any((d / Path(name).name).exists() for d in FILE_DIRS)


def broken_refs(text: str) -> list[str]:
    """`file.ext` that do not exist and `module.name` not written in src/tennisbio/<module>.py."""
    bad = []
    for tok in re.findall(r"`([^`]+)`", text):
        tok = re.sub(r":[0-9-]+$", "", tok.strip())       # file.py:52-71 → file.py
        if " " in tok or "*" in tok or "<" in tok:
            continue
        if re.search(r"\.(py|html|md|bat|ps1|vbs|yaml|json)$", tok) and ("/" in tok or tok.count(".") == 1):
            if not tok.endswith((".json", "local.yaml")) and not _file_ok(tok):   # run outputs and the PC-only config
                bad.append(tok)
            continue
        m = re.match(r"^([a-z_0-9]+)\.([A-Za-z_][A-Za-z_0-9]*)", tok)
        if m:
            mod = SRC / f"{m.group(1)}.py"
            if not mod.exists():
                mod = SRC / m.group(1) / "__init__.py"
            if mod.exists() and not re.search(rf"\b{re.escape(m.group(2))}\b", mod.read_text(encoding="utf-8")):
                bad.append(tok)
    return bad


def problems(rows: list[Row]) -> list[str]:
    """What makes the register untrustworthy: each one is an error."""
    out, seen = [], set()
    for r in rows:
        if r.n in seen:
            out.append(f"#{r.n}: número repetido")
        seen.add(r.n)
        st = r.status
        if st is None:
            out.append(f"#{r.n}: sin estado válido («{r.state}»); usa uno de {', '.join(STATUSES)}")
            continue
        if st == "HECHO":
            if r.code in EMPTY and r.web in EMPTY:
                out.append(f"#{r.n}: HECHO sin prueba (ni código ni dónde se ve)")
            bad = broken_refs(r.code + " " + r.web)
            if bad:
                out.append(f"#{r.n}: HECHO con referencias que no existen en el código: {', '.join(bad)}")
        elif st in ("PARCIAL", "FALTA") and r.missing in EMPTY:
            out.append(f"#{r.n}: {st} sin decir qué falta")
    return out


def pending(rows: list[Row]) -> list[Row]:
    """Rows that are not done (PARCIAL or FALTA), the ones that must be listed first."""
    return [r for r in rows if r.status in ("PARCIAL", "FALTA")]


def counts(rows: list[Row]) -> dict[str, int]:
    c = {st: 0 for st in STATUSES}
    for r in rows:
        if r.status:
            c[r.status] += 1
    return c


def _short(s: str, n: int = 160) -> str:
    s = re.sub(r"\s+", " ", s)
    return s if len(s) <= n else s[: n - 1] + "…"


def pending_markdown(rows: list[Row] | None = None) -> str:
    """The block the audit and the automatic review put at the top: what is still not done."""
    rows = parse() if rows is None else rows
    p = pending(rows)
    c = counts(rows)
    head = (f"## Peticiones del usuario SIN TERMINAR: {len(p)} de {len(rows)}\n\n"
            f"Registro `docs/peticiones_usuario.md`: {c['HECHO']} hechas · {c['PARCIAL']} a medias · {c['FALTA']} sin hacer · "
            f"{c['NO MEDIBLE']} no medibles desde la tele · {c['NO APLICA']} no aplican. "
            "Que las comprobaciones de abajo pasen **no** significa que estas estén hechas.\n")
    if not p:
        return head
    lines = [f"- **#{r.n} [{r.status}]** {_short(r.text, 140)} — falta: {_short(r.missing)}" for r in
             sorted(p, key=lambda r: (r.status != "FALTA", r.n))]
    return head + "\n" + "\n".join(lines) + "\n"


def header_problems(path: Path = REGISTER, rows: list[Row] | None = None) -> list[str]:
    """The counts table at the top of the register must match its rows (it went stale before)."""
    rows = parse(path) if rows is None else rows
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    out = []
    for st, n in counts(rows).items():
        m = re.search(rf"^\| {re.escape(st)} \| (\d+) \|", text, re.M)
        if m is None or int(m.group(1)) != n:
            out.append(f"cabecera: «{st}» dice {m.group(1) if m else 'nada'} y hay {n} filas")
    m = re.search(r"^\| \*\*Total\*\* \| \*\*(\d+)\*\* \|", text, re.M)
    if m is None or int(m.group(1)) != len(rows):
        out.append(f"cabecera: el total dice {m.group(1) if m else 'nada'} y hay {len(rows)} filas")
    return out
