"""Requests #43 «el PC no es servidor» and #145 «nada en la nube ni de pago»: the code never opens a server on the PC,
the window and the reports are files opened from the disk, nothing is uploaded anywhere and every address in the
code is a free public download (models, datasets, fonts, videos to learn from). Run on the PC with the other tests
(pruebas.xml), so the audit ties both requests to this module.

13-11 (#271-#273): the user decided that the whole application moves to the cloud after the 6 matches (package N, 0 € a
month). Until then the one exception is N0, the proof of concept: scripts/subir_nube.py uploads, once and by the single
queue, the PC's models and the F3Set compilations to the user's own Modal volume (cloud/, which never runs on the PC).
Nothing else on the PC sends anything out; the match videos are not uploaded."""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = [p for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py"))
        + list((ROOT / "scripts" / "windows").glob("*.ps1")) + list(ROOT.glob("*.bat"))
        + list((ROOT / "src").rglob("*.html")) + list((ROOT / "src").rglob("*.js")) if "__pycache__" not in p.parts]

# a server listening on the PC (Python or PowerShell), or a tunnel that would publish it
SERVER = re.compile(r"\bhttp\.server\b|\bHTTPServer\b|\bsocketserver\b|serve_forever|\bflask\b|\bfastapi\b|\buvicorn\b|"
                    r"aiohttp\.web|websockets\.serve|\.listen\(\s*\d|\bHttpListener\b|New-NetFirewallRule|\bngrok\b|"
                    r"cloudflared|http_server\s*=\s*True", re.I)
# sending anything out (the PC only downloads public files; its logs go to the user's own repository with git)
UPLOAD = re.compile(r"[\"']POST[\"']|requests\.(post|put)\(|\.upload_file\(|put_object\(|(?i:Invoke-(RestMethod|WebRequest)\s+.*-Method\s+(Post|Put))")
# free public downloads: models and datasets (Hugging Face, GitHub, ModelScope, OpenMMLab, Google Drive/Storage
# public files, PyPI), the window's fonts, uv's installer, YouTube (videos to learn from, request 6)
FREE_HOSTS = {"huggingface.co", "github.com", "raw.githubusercontent.com", "codeload.github.com", "api.github.com",
              "www.modelscope.cn", "download.openmmlab.com", "drive.google.com", "drive.usercontent.google.com",
              "storage.googleapis.com", "files.pythonhosted.org", "fonts.googleapis.com", "fonts.gstatic.com",
              "astral.sh", "www.youtube.com", "youtube.com", "youtu.be"}
# software development kits of paid or cloud services
CLOUD_SDKS = re.compile(r"^(boto3|botocore|google-cloud|azure|firebase|openai|anthropic|stripe|twilio|sentry|dropbox|"
                        r"supabase|pusher|ngrok|cloudflare)", re.I)


def _lines(rx):
    out = []
    for f in CODE:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if rx.search(line) and "test_local_only" not in f.name:
                out.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
    return out


def test_no_code_opens_a_server_on_the_pc():
    assert len(CODE) > 50
    assert not _lines(SERVER), _lines(SERVER)


def test_the_window_and_the_reports_are_files_opened_from_the_disk():
    win = (ROOT / "src" / "tennisbio" / "app" / "window.py").read_text(encoding="utf-8")
    # pywebview loads an absolute path as a file (no server: http_server is never switched on, checked above)
    assert re.search(r"create_window\(\"Tennisbio\", url=str\(page\)", win)
    assert "as_uri()" in win                              # without the window engine: the same file in the browser
    assert "localhost" not in win and "127.0.0.1" not in win
    rep = (ROOT / "src" / "tennisbio" / "report.py").read_text(encoding="utf-8")
    assert "index.html" in rep and "localhost" not in rep


def test_nothing_is_uploaded_anywhere():
    assert not _lines(UPLOAD), _lines(UPLOAD)


# 13-11 (#273): the only upload on the PC, to the user's own Modal volume (see the module docstring)
CLOUD_UPLOAD = re.compile(r"[\"']volume[\"'],\s*[\"']put[\"']|modal\s+volume\s+put")
CLOUD_UPLOADERS = {"scripts/subir_nube.py"}


def test_the_only_upload_is_the_proof_of_concept_to_the_users_own_volume():
    where = {ln.split(":", 1)[0].replace("\\", "/") for ln in _lines(CLOUD_UPLOAD)}
    assert where == CLOUD_UPLOADERS, where
    src = (ROOT / "scripts" / "subir_nube.py").read_text(encoding="utf-8")
    assert 'VOLUME = "tennisbio-datos"' in src                     # one volume, the user's
    # what it uploads (never a match video) is checked on a tree in tests/test_nube.py


def test_every_address_in_the_code_is_a_free_public_download():
    hosts = {}
    for f in CODE:
        for h in re.findall(r"https?://([a-zA-Z0-9.-]+)", f.read_text(encoding="utf-8", errors="replace")):
            hosts.setdefault(h, f.relative_to(ROOT).as_posix())
    other = {h: f for h, f in hosts.items() if h not in FREE_HOSTS}
    assert hosts and not other, other


def test_no_paid_or_cloud_service_among_the_dependencies():
    pp = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    deps = list(pp["dependencies"]) + [d for ds in pp.get("optional-dependencies", {}).values() for d in ds]
    bad = [d for d in deps if CLOUD_SDKS.match(d.strip())]
    assert deps and not bad, bad


def test_the_users_decision_is_written_where_the_architecture_is():
    doc = (ROOT / "docs" / "arquitectura_producto.md").read_text(encoding="utf-8")
    assert "## Decisión del usuario (17-10): todo en el PC, nada en la nube y nada de pago" in doc
