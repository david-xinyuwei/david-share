import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_public_package.py"


def test_public_audit_scans_private_identifiers_and_secrets() -> None:
    specification = importlib.util.spec_from_file_location("audit", AUDIT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert {
        "private project term",
        "Azure resource ID",
        "OpenAI-style secret",
        "private key",
    } <= set(module.PATTERNS)
