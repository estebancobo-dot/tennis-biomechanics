"""The report page of a cloud run (runs/<tag>/informe.html, brought by «recoger») rebuilt with the code of the repository
and checked in a browser, at no cost: the real data of the analysed matches with today's template and «Aprende» content.

14-11 (#278: the application goes on while the GPU waits): every change of the report is checked on the real matches
here, before a cloud run. The data of the page (strokes, measures, series links) stays as the cloud made it; only the
template and the static content of «Aprende» (learn.content) are today's.

    uv run python scripts/informe_real.py nube-out/informe2/informe.html [--out <carpeta temporal>/informe_real/index.html]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

MARK = "const DATA = "


def page_data(html: str) -> dict:
    """The DATA object written into a report page (report.build)."""
    i = html.index(MARK) + len(MARK)
    data, _ = json.JSONDecoder().raw_decode(html, i)
    return data


def rebuild(src: Path, out: Path) -> Path:
    """The page of `src` with today's template and «Aprende» content; written to `out`."""
    from tennisbio.learn import content
    from tennisbio.report import TEMPLATE

    data = page_data(src.read_text(encoding="utf-8"))
    data["learn"] = content()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)),
                   encoding="utf-8")
    return out


def check(page: Path, chromium: str | None = None) -> dict:
    """The audit's browser checks of the lesson and the first screen on the page (1280 × 900), and its page errors."""
    from playwright.sync_api import sync_playwright

    from tennisbio.learn_check import check_entry, check_lesson

    with sync_playwright() as p:
        b = p.chromium.launch(**({"executable_path": chromium} if chromium else {}), args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(page.resolve().as_uri())
        pg.wait_for_timeout(800)
        lesson = check_lesson(pg)
        entry = check_entry(pg)
        b.close()
    return {"lesson": lesson, "entry": entry, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("page", type=Path)
    ap.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "informe_real" / "index.html")
    ap.add_argument("--chromium", default=None, help="the browser to use (default: Playwright's)")
    a = ap.parse_args(argv)
    r = check(rebuild(a.page, a.out), a.chromium)
    for row in r["lesson"]["phases"]:
        print(f"{row['phase']:<13} claves {row['keys']} · {row['words']} palabras · {row['height']} px · "
              + ", ".join(f"{k} {n}" for k, n in row.get("key_words") or []))
    e = r["entry"]["entry"]
    print(f"primera pantalla: vídeo en y={e['vid_top']}-{e['vid_bottom']} de {e['height']}")
    bad = r["lesson"]["failures"] + r["entry"]["failures"] + r["errors"]
    for x in bad:
        print("FALLO:", x)
    print("bien" if not bad else f"{len(bad)} fallos")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
