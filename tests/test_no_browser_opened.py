"""04-11: nothing automatic opens the user's browser (a report opened from the PC's cycle left Brave as a process of the
job, killed with it: the user lost their session). Reports are seen in the application."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_windows_script_opens_a_report_in_the_browser():
    bad = []
    for f in list((ROOT / "scripts" / "windows").glob("*.ps1")) + list(ROOT.glob("*.bat")):
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"Start-Process\s+[\"']?\$?[^\s]*(\.html|informe)", code, re.I) or re.search(r"\bstart\s+\"\"\s+.*\.html", code, re.I):
                bad.append(f"{f.name}:{i}: {line.strip()}")
    assert not bad, bad


def test_screenshots_never_use_the_users_brave():
    src = (ROOT / "src" / "tennisbio" / "screens.py").read_text(encoding="utf-8")
    assert "brave.exe" not in src and '"headless": True' in src and "p.chromium.launch(**kw)" in src
