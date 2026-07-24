from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bff_checks_backend_health_and_unknown_api_routes() -> None:
    source = (ROOT / "ui" / "server" / "index.mjs").read_text(encoding="utf-8")

    assert "/readiness" in source
    assert "backend_unavailable" in source
    assert 'app.all("/api/{*splat}"' in source
    assert "new AbortController()" in source


def test_e2e_runner_clears_stale_report_and_live_test_uses_deployed_version() -> None:
    runner = (ROOT / "scripts" / "run_ui_e2e.py").read_text(encoding="utf-8")
    live = (ROOT / "ui" / "e2e" / "live-managed.spec.ts").read_text(
        encoding="utf-8"
    )

    assert '(RUNTIME_DIR / "playwright.json").unlink(missing_ok=True)' in runner
    assert "process.env.MANAGED_AGENT_VERSION" in live
    assert 'toContainText(`v${expectedVersion}`)' in live
    assert 'toContainText("v1")' not in live
