"""15-11 (#304): the proof of concept that tells whether a cloud session can download from YouTube."""
from tennisbio.infra import poc_youtube as P


def test_each_step_is_reported_with_its_error(monkeypatch, tmp_path):
    def blocked(args, timeout=300):
        if args == ["--version"]:
            return 0, "2026.08.19\n", ""
        return 1, "", "ERROR: [youtube] abcdefghijk: Sign in to confirm you’re not a bot.\n"
    monkeypatch.setattr(P, "_run", blocked)
    res = P.run(["https://youtu.be/abcdefghijk"])
    v = res["videos"][0]
    assert v["id"] == "abcdefghijk" and not v["metadata"] and not v["subtitles"] and not v["video"]
    assert "not a bot" in v["video_error"] and "hace falta el PC" in res["conclusion"]

    def works(args, timeout=300):
        if "-o" in args:
            out = args[args.index("-o") + 1].replace("%(id)s", "abcdefghijk").replace("%(ext)s", "mp4" if "video" in args[args.index("-o") + 1] else "en.vtt")
            open(out, "w").write("x")
        return 0, "Title\t42\n", ""
    monkeypatch.setattr(P, "_run", works)
    res = P.run(["https://www.youtube.com/shorts/abcdefghijk"])
    assert res["videos"][0]["video"] and res["videos"][0]["subtitles"] and "1 de 1" in res["conclusion"]


def test_the_kaggle_runner_knows_it(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("correr", Path(__file__).resolve().parents[1] / "cloud" / "kaggle" / "correr.py")
    src = (Path(__file__).resolve().parents[1] / "cloud" / "kaggle" / "correr.py").read_text(encoding="utf-8")
    assert '"youtube": "tennisbio.infra.poc_youtube"' in src and '["--urls", str(job.get("urls") or "")]' in src
