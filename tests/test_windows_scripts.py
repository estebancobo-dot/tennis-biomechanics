"""Request #40: double-click scripts to install, for the quick test and for the full analysis, without reading
anything. Each button at the repository's root starts its PowerShell script, which exists, asks nothing to type and
(on the PC, Windows PowerShell 5.1) parses without a syntax error. Run on the PC with the other tests (pruebas.xml),
so the audit ties #40 to this module."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WIN = ROOT / "scripts" / "windows"
BATS = sorted(ROOT.glob("[0-9]*.bat"))
# the one script that asks something: GitHub's one-time code to connect the PC with Actions (4_conectar_github.bat,
# done once by the user; not part of installing, testing or analysing)
ASKS = {"instalar_runner.ps1"}


def _launched(bat: Path) -> list[Path]:
    return [WIN / m for m in re.findall(r"scripts\\windows\\([\w.]+\.ps1)", bat.read_text(encoding="ascii"))]


def test_the_three_buttons_the_user_asked_for_exist():
    names = {b.name for b in BATS}
    assert {"1_instalar.bat", "2_prueba_rapida.bat", "3_analisis_completo.bat"} <= names, names


def test_every_button_starts_a_script_that_exists_without_a_prompt_or_policy_question():
    bad = []
    for b in BATS:
        txt = b.read_text(encoding="ascii")
        if "powershell" not in txt.lower():
            bad.append(f"{b.name}: no lanza PowerShell")
        if "powershell" in txt.lower() and "-ExecutionPolicy Bypass" not in txt:
            bad.append(f"{b.name}: PowerShell preguntaría por la política de ejecución")
        for ps in _launched(b):
            if not ps.exists():
                bad.append(f"{b.name}: falta {ps.name}")
    assert len(BATS) >= 6 and not bad, bad


def _dot_sourced(ps: Path, seen: set) -> set:
    """A script and the ones it loads (". $PSScriptRoot\\comun.ps1") or starts (-File …\\x.ps1)."""
    if ps in seen or not ps.exists():
        return seen
    seen.add(ps)
    for m in re.findall(r"([\w]+\.ps1)", ps.read_text(encoding="ascii")):
        _dot_sourced(WIN / m, seen)
    return seen


def test_nothing_launched_by_a_button_asks_the_user_to_type_or_read():
    """«Sin leer nada»: no Read-Host or key press inside the scripts, no document opened for the user to read (the .bat
    keeps its window open at the end with `pause` only to show the result)."""
    bad = []
    for b in BATS:
        for ps in sorted(set().union(*(_dot_sourced(p, set()) for p in _launched(b))) if _launched(b) else []):
            if ps.name in ASKS:
                continue
            for i, line in enumerate(ps.read_text(encoding="ascii").splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(r"\bRead-Host\b|\bnotepad\b|Invoke-Item\s+.*\.(md|txt|pdf)\b|\$host\.UI\.RawUI\.ReadKey", code, re.I):
                    bad.append(f"{b.name} → {ps.name}:{i}: {line.strip()}")
    assert not bad, bad


def test_scripts_are_plain_ascii_for_windows_powershell():
    """Windows PowerShell 5.1 reads a file without BOM as ANSI: an accent would break a string or a comment."""
    bad = []
    for f in list(WIN.glob("*.ps1")) + BATS:
        try:
            f.read_bytes().decode("ascii")
        except UnicodeDecodeError as e:
            bad.append(f"{f.name}: byte {e.start}")
    assert not bad, bad


@pytest.mark.skipif(sys.platform != "win32", reason="solo en el PC: el analizador de Windows PowerShell")
def test_every_script_parses_in_windows_powershell(tmp_path):
    files = sorted(WIN.glob("*.ps1"))
    lst = ",".join("'" + str(f).replace("'", "''") + "'" for f in files)
    check = tmp_path / "analizar.ps1"                    # a file, not -Command: no quoting of the command line
    check.write_text("$fs = @(" + lst + ")\n$n = 0\nforeach ($f in $fs) {\n  $t = $null; $e = $null\n"
                     "  [void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$t, [ref]$e)\n"
                     "  foreach ($x in $e) { $n++; Write-Output ('{0}:{1}: {2}' -f (Split-Path $f -Leaf), "
                     "$x.Extent.StartLineNumber, $x.Message) }\n}\n"
                     "Write-Output ('analizados: ' + $fs.Count + ' errores: ' + $n)\n", encoding="ascii")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(check)],
                       capture_output=True, text=True, timeout=180)
    assert f"analizados: {len(files)} errores: 0" in r.stdout, r.stdout + r.stderr
