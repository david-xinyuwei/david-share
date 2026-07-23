from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_name_pattern_is_restricted() -> None:
    source = (ROOT / "scripts" / "build_customer_package.py").read_text(encoding="utf-8")
    assert r'[A-Za-z0-9._-]+' in source
