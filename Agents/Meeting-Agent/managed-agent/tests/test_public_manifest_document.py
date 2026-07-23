from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_manifest_documents_excluded_private_material() -> None:
    text = (ROOT / "PUBLIC-MANIFEST.md").read_text(encoding="utf-8")

    assert "password.txt" in text
    assert "Raw Toolbox responses" in text
    assert "Legacy AOAI screenshots" in text
