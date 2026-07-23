from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_root_name_is_managed_meeting_agent() -> None:
    source = (ROOT / "scripts" / "build_customer_package.py").read_text(encoding="utf-8")
    assert 'PACKAGE_ROOT = "Managed-Meeting-Agent"' in source
