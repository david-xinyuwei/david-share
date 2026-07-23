from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_tree_validator_includes_value_aware_audit() -> None:
    source = (ROOT / "scripts" / "validate_public_tree.py").read_text(encoding="utf-8")
    assert '"audit_public_package.py"' in source
