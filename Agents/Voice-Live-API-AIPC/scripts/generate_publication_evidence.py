"""Generate sanitized source/package provenance after a successful local build."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .evidence_provenance import canonical_sha256_file, sha256_file, source_snapshot
else:
    from evidence_provenance import canonical_sha256_file, sha256_file, source_snapshot

ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = ROOT.parents[1]
DEFAULT_OUTPUT = ROOT / "evidence" / "publication-validation.json"
WORKFLOW = MONOREPO_ROOT / ".github" / "workflows" / "voice-live-aipc-ci.yml"
EXE = ROOT / "dist" / "VoiceLiveAgent" / "VoiceLiveAgent.exe"
SELF_CHECK = ROOT / "dist" / "VoiceLiveAgent" / "self_check.txt"


def _package_version(distribution: str) -> str:
    return importlib.metadata.version(distribution)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    for required in (WORKFLOW, EXE, SELF_CHECK):
        if not required.is_file():
            raise SystemExit(f"Required validation artifact is missing: {required}")

    report = SELF_CHECK.read_text(encoding="utf-8")
    match = re.search(r"SELF_CHECK=(PASS|FAIL) failed=(\d+)", report)
    if match is None or match.group(1) != "PASS" or match.group(2) != "0":
        raise SystemExit("Packaged self-check report did not pass")
    passed = len(re.findall(r"^\[PASS]", report, flags=re.MULTILINE))

    payload = {
        "schema_version": "1.0",
        "evidence_type": "publication-package-validation",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_tree": source_snapshot(ROOT),
        "workflow": {
            "path": ".github/workflows/voice-live-aipc-ci.yml",
            "sha256": canonical_sha256_file(WORKFLOW),
        },
        "package": {
            "format": "PyInstaller onedir",
            "artifact_published": False,
            "path": "dist/VoiceLiveAgent/VoiceLiveAgent.exe",
            "bytes": EXE.stat().st_size,
            "sha256": sha256_file(EXE),
        },
        "packaged_self_check": {
            "path": "dist/VoiceLiveAgent/self_check.txt",
            "result": "PASS",
            "passed": passed,
            "failed": 0,
            "sha256": sha256_file(SELF_CHECK),
            "side_effects": [],
        },
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "azure_ai_voicelive": _package_version("azure-ai-voicelive"),
            "pyinstaller": _package_version("pyinstaller"),
            "pip": _package_version("pip"),
            "pip_audit": _package_version("pip-audit"),
            "pytest": _package_version("pytest"),
            "setuptools": _package_version("setuptools"),
        },
        "boundaries": [
            "The package was built and self-checked locally but is not committed or published.",
            "The package hash is evidence for this single build, not a reproducible-build guarantee.",
            "No endpoint, account, tenant, subscription, resource, token, key, or request ID is recorded.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"PUBLICATION_EVIDENCE=PASS files={payload['source_tree']['file_count']} "
        f"package_bytes={payload['package']['bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
