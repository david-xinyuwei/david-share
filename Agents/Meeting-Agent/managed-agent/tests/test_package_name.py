from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_root_is_public_neutral_name() -> None:
    source = (ROOT / "scripts" / "build_customer_package.py").read_text(encoding="utf-8")

    assert 'PACKAGE_ROOT = "Managed-Meeting-Agent"' in source
    private_name = "Yun" + "shang"
    assert f'PACKAGE_ROOT = "{private_name}' not in source
