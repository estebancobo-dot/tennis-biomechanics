"""27-10, the user: «la aplicación tiene que ser genérica: añadir partidos, seleccionar jugadores, golpes…,
nada hardcodeado». No string of the code names a player: the player comes from config (`player`,
config/players/<id>.yaml). Only the transliteration tables that read broadcast file names list surnames."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("rybakin", "sabalenk", "sobolenko", "osaka", "gauff", "zheng")
TABLES = {"src/tennisbio/app/cards.py", "src/tennisbio/app/state.py"}       # file-name transliterations (data)


def _strings(tree):
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
            yield n


def test_no_player_name_in_the_code():
    bad = []
    for f in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in TABLES:
            continue
        for n in _strings(ast.parse(f.read_text(encoding="utf-8"))):
            low = n.value.lower()
            if any(k in low for k in NAMES) and "help=" not in low:
                bad.append(f"{rel}:{n.lineno}: {n.value[:60]!r}")
    assert not bad, "\n".join(bad)


def test_windows_scripts_do_not_name_a_player():
    bad = [f"{f.name}:{i}" for f in (ROOT / "scripts" / "windows").glob("*.ps1")
           for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
           if not line.lstrip().startswith("#") and any(k in line.lower() for k in NAMES)]
    assert not bad, bad
