from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hosted_main_binds_loopback() -> None:
    source = (ROOT / "src" / "meeting_agent" / "hosted.py").read_text(encoding="utf-8")

    assert 'app.run(host="127.0.0.1", port=port)' in source
