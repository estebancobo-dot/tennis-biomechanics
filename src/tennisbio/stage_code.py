"""Guard for the stages without a code fingerprint (all but the fine passes): their results depend on
their version number, so a change to their code must come with a new version, or be declared as one
that does not change their results. Putting the code into their fingerprint instead would recompute
every analysed match (hours) the day it is adopted.

The code of a stage = its function in stages.py, every function, class or constant of stages.py it reaches by name
(transitively), and the project modules all of those import, compared as normalised syntax (comments, docstrings and
formatting do not count). 12-11: only the stage's own function and its own imports counted, so a change to a helper
it calls (candidates → add_serve_candidates → point_count.her_serve_points) left old results passing for new ones."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT.parents[1] / "config" / "stage_code.json"


def _norm(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            body.pop(0)                                    # docstrings
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def _module_code(mod: str) -> str:
    f = ROOT / (mod.replace(".", "/") + ".py")
    if not f.exists():
        f = ROOT / mod.replace(".", "/") / "__init__.py"
    return _norm(ast.parse(f.read_text(encoding="utf-8"))) if f.exists() else ""


def reachable(tree: ast.Module, entry: str) -> list[ast.AST]:
    """The top-level nodes of a module that its function `entry` reaches by name, transitively: functions, classes,
    constants, and the module-level «from .x import y» lines of the names it uses (entry first, then by name)."""
    defs: dict[str, list] = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(n.name, []).append(n)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        defs.setdefault(x.id, []).append(n)
        elif isinstance(n, ast.ImportFrom) and n.level == 1:
            for a in n.names:
                defs.setdefault(a.asname or a.name, []).append(n)
    seen, todo = set(), [entry]
    while todo:
        k = todo.pop()
        if k in seen or k not in defs:
            continue
        seen.add(k)
        for node in defs[k]:
            todo += [x.id for x in ast.walk(node) if isinstance(x, ast.Name) and x.id in defs]
    out = list(defs.get(entry, []))
    for k in sorted(seen - {entry}):
        out += [n for n in defs[k] if n not in out]
    return out


def stage_code(src: str | None = None) -> dict[str, dict]:
    """stage → {version, hash} for every stage without `code=` (src: another text of stages.py, for the tests)."""
    from .pipeline import STAGES
    from . import stages  # noqa: F401  (registers the stages)

    tree = ast.parse((ROOT / "stages.py").read_text(encoding="utf-8") if src is None else src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    out = {}
    for name, st in STAGES.items():
        if st.code:
            continue
        fn = funcs.get(st.run.__name__)
        if fn is None:
            continue
        nodes = reachable(tree, fn.name)
        mods = sorted({n.module for node in nodes for n in ast.walk(node)
                       if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module})
        h = hashlib.sha1("\n".join(_norm(ast.parse(ast.unparse(node))) for node in nodes).encode())
        for m in mods:
            h.update(m.encode())
            h.update(_module_code(m).encode())
        out[name] = {"version": st.version, "hash": h.hexdigest()[:16], "modules": mods}
    return out


def check() -> list[str]:
    """Stages whose code changed while their version stayed the same."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    bad = []
    for name, cur in stage_code().items():
        r = reg.get(name)
        if r and r["version"] == cur["version"] and r["hash"] != cur["hash"]:
            bad.append(f"{name} (v{cur['version']}): su código cambió; sube su versión en stages.py o, si el cambio no altera "
                       f"sus resultados, actualiza el registro con `uv run python -m tennisbio.stage_code --update`")
    return bad


def update():
    REGISTRY.write_text(json.dumps(stage_code(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys

    if "--update" in sys.argv:
        update()
        print(f"registro actualizado: {REGISTRY}")
    else:
        msgs = check()
        print("\n".join(msgs) or "ok")
        sys.exit(1 if msgs else 0)
