import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_public_tree.py"


def test_public_tree_validator_runs_all_gates() -> None:
    specification = importlib.util.spec_from_file_location("public_validator", VALIDATOR)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.GATES == (
        "audit_no_send.py",
        "audit_public_package.py",
        "validate_evidence.py",
        "validate_readmes.py",
        "pre_delivery_check.py",
    )
