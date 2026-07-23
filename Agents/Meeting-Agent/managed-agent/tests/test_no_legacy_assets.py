import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_customer_package.py"


def test_public_tree_excludes_classic_media_owned_by_repo_root() -> None:
    specification = importlib.util.spec_from_file_location("builder", BUILDER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    paths = {path.relative_to(ROOT).as_posix() for path in module.package_files()}

    assert not any(path.startswith("media/") for path in paths)
    assert not any("demo-preview" in path or "demo-poster" in path for path in paths)
    assert not any(path.startswith("evidence/aoai-") for path in paths)
