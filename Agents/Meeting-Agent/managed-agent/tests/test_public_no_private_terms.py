import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_public_package.py"


def test_public_term_scanner_blocks_private_aliases() -> None:
    specification = importlib.util.spec_from_file_location("audit", AUDIT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    pattern = module.PATTERNS["private project term"]
    assert pattern.search("Yun" + "shang")
    assert pattern.search("Len" + "ovo")
