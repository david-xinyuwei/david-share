from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_manifest_readme_exists() -> None:
    assert (ROOT / "PUBLIC-MANIFEST.md").is_file()
