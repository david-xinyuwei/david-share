from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_managed_readme_links_to_parity_evidence() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "evidence/managed-live/parity-manifest.json" in text
    assert "FEATURE-PARITY.md" in text
