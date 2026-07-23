import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_customer_package.py"


def test_public_evidence_contains_only_sanitized_managed_summaries() -> None:
    specification = importlib.util.spec_from_file_location("builder", BUILDER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    paths = {path.relative_to(ROOT).as_posix() for path in module.package_files()}
    managed = {path for path in paths if path.startswith("evidence/managed-live/")}

    assert managed == {
        "evidence/managed-live/README-CN.md",
        "evidence/managed-live/README.md",
        "evidence/managed-live/artifact-validation.json",
        "evidence/managed-live/parity-manifest.json",
        "evidence/managed-live/toolbox-skill-validation.json",
        "evidence/managed-live/ui-live-validation.json",
    }
