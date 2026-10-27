"""27-10 (the user: «sin fallos, cuelgues ni bloqueos»; the backhand export hung twice): every external program
run to completion has a time limit. Long-lived processes (Popen: video streams, encoders, the app's job) are
watched by their callers instead (read loops, `en_curso.txt`, the app's Watch) and are listed here."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "tennisbio"


def _calls(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess":
            yield n


def test_every_module_compiles():
    """27-10: a timeout added twice to one call (ast.parse accepts it, the interpreter does not) broke 3
    modules of the application; every source file must compile."""
    bad = []
    for f in list(SRC.rglob("*.py")) + list((SRC.parents[1] / "scripts").glob("*.py")):
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as e:
            bad.append(f"{f.name}:{e.lineno}: {e.msg}")
    assert not bad, bad


def test_every_subprocess_run_has_a_timeout():
    bad = []
    for f in SRC.rglob("*.py"):
        for n in _calls(ast.parse(f.read_text(encoding="utf-8")), "run"):
            if not any(k.arg == "timeout" for k in n.keywords):
                bad.append(f"{f.relative_to(SRC)}:{n.lineno}")
    assert not bad, bad


def test_long_lived_processes_are_the_known_watched_ones():
    found = sorted(f"{f.relative_to(SRC).as_posix()}" for f in SRC.rglob("*.py")
                   for _ in _calls(ast.parse(f.read_text(encoding="utf-8")), "Popen"))
    assert found == sorted(["app/window.py", "export.py", "io/video.py", "io/video.py", "pose/yolo.py", "spotting.py"]), found
