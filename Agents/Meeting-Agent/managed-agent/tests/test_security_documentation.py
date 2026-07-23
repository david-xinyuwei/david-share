from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_security_documentation_states_runtime_boundaries() -> None:
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "*.services.ai.azure.com" in text
    assert "127.0.0.1" in text
    assert "2 MiB" in text
    assert "%LOCALAPPDATA%" in text
