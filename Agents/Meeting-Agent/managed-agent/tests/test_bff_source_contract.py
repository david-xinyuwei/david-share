from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bff_checks_backend_health_and_unknown_api_routes() -> None:
    source = (ROOT / "ui" / "server" / "index.mjs").read_text(encoding="utf-8")

    assert "/readiness" in source
    assert "backend_unavailable" in source
    assert 'app.all("/api/{*splat}"' in source
    assert "new AbortController()" in source
