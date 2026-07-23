import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_parity_manifest.py"


def _module():
    specification = importlib.util.spec_from_file_location("parity_builder", MODULE_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_committed_parity_manifest_matches_managed_files() -> None:
    module = _module()
    manifest = json.loads(
        (ROOT / "evidence" / "managed-live" / "parity-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["baseline_commit"] == module.BASELINE_COMMIT
    assert len(manifest["entries"]) == len(module.SHARED_FILES)
    for entry in manifest["entries"]:
        relative = entry["managed_path"].removeprefix(
            "Agents/Meeting-Agent/managed-agent/"
        )
        assert module.sha256(ROOT / relative) == entry["sha256"]
