"""Build and verify a sanitized customer source package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "Managed-Meeting-Agent"
PUBLIC_ROOT_FILES = {
    ".agentignore",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CUSTOMER-START-HERE-CN.md",
    "CUSTOMER-START-HERE.md",
    "FEATURE-PARITY-CN.md",
    "FEATURE-PARITY.md",
    "LICENSE",
    "PUBLIC-MANIFEST.md",
    "README-PUBLIC-NOTE.md",
    "docs/MANAGED-IMPLEMENTATION-CN.md",
    "docs/MANAGED-IMPLEMENTATION.md",
    "SECURITY.md",
    "agent.yaml",
    "azure.yaml",
    "evidence-managed-agent.json",
    "evidence/managed-live/README-CN.md",
    "evidence/managed-live/README.md",
    "evidence/managed-live/artifact-validation.json",
    "evidence/managed-live/meeting-package-v2-SKILL.md",
    "evidence/managed-live/parity-manifest.json",
    "evidence/managed-live/public-v2-agent-reference-validation.json",
    "evidence/managed-live/public-v2-deployment-validation.json",
    "evidence/managed-live/public-v2-source-manifest.json",
    "evidence/managed-live/toolbox-skill-validation.json",
    "evidence/managed-live/ui-live-validation.json",
    "evidence/managed-live-gpt54/README-CN.md",
    "evidence/managed-live-gpt54/README.md",
    "evidence/managed-live-gpt54/dual-input-validation.json",
    "evidence/managed-live-gpt54/large-input-recovery-validation.json",
    "evidence/managed-live-gpt54/runtime-validation.json",
    "evidence/managed-live-gpt54/ui-validation.json",
    "evidence/sample-runs/operations-review/meeting-analysis.json",
    "evidence/sample-runs/product-planning/meeting-analysis.json",
    "instructions.md",
    "images/meeting-agent-architecture.svg",
    "main.py",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "scenario-manifest.json",
}
PUBLIC_DIRS = {
    "examples",
    "scripts",
    "skills",
    "src",
    "tests",
    "ui",
}
EXCLUDED_DIRS = {
    "__pycache__",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store", ".env", ".meeting-agent.lock"}
EXCLUDED_RELATIVE_PATHS = {
    "scripts/audit_public_content.py",
    "scripts/build_ppt_template.py",
    "scripts/validate_sample_runs.py",
    "src/meeting_agent/templates/meeting-agent-template.pptx",
}
SENSITIVE_SUFFIXES = {".key", ".pem", ".pfx", ".secret", ".token"}
REQUIRED_FILES = {
    ".agentignore",
    "CUSTOMER-START-HERE-CN.md",
    "CUSTOMER-START-HERE.md",
    "FEATURE-PARITY-CN.md",
    "FEATURE-PARITY.md",
    "LICENSE",
    "docs/MANAGED-IMPLEMENTATION-CN.md",
    "docs/MANAGED-IMPLEMENTATION.md",
    "examples/meeting-record-stargate.json",
    "agent.yaml",
    "azure.yaml",
    "evidence-managed-agent.json",
    "evidence/managed-live/artifact-validation.json",
    "evidence/managed-live/meeting-package-v2-SKILL.md",
    "evidence/managed-live/parity-manifest.json",
    "evidence/managed-live/public-v2-agent-reference-validation.json",
    "evidence/managed-live/public-v2-deployment-validation.json",
    "evidence/managed-live/public-v2-source-manifest.json",
    "evidence/managed-live/toolbox-skill-validation.json",
    "evidence/managed-live/ui-live-validation.json",
    "evidence/managed-live-gpt54/dual-input-validation.json",
    "evidence/managed-live-gpt54/large-input-recovery-validation.json",
    "evidence/managed-live-gpt54/runtime-validation.json",
    "evidence/managed-live-gpt54/ui-validation.json",
    "instructions.md",
    "scripts/reconcile_managed_runtime.py",
    "scripts/start-ui.ps1",
    "skills/meeting-package/SKILL.md",
    "skills/presentation-story/SKILL.md",
    "skills/presentation-story/deck-contract.yaml",
    "skills/presentation-story/presentation-style.yaml",
    "src/meeting_agent/templates/meeting-agent-template.zip",
    "ui/package-lock.json",
    "ui/package.json",
    "tests/test_managed_analyzer.py",
    "tests/test_hosted_api.py",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "delivery",
        help="Directory for the ZIP and SHA-256 file.",
    )
    parser.add_argument(
        "--name",
        default=f"Meeting-Agent-Customer-Package-{datetime.now(UTC):%Y%m%d}",
        help="Package filename without .zip.",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.name):
        raise ValueError(
            "Package name may contain only letters, numbers, dot, underscore, "
            "and hyphen."
        )

    files = package_files()
    relative_paths = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED_FILES - relative_paths)
    if missing:
        raise RuntimeError(f"Required package files are missing: {missing}")

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{args.name}.zip"
    checksum_path = output_dir / f"{args.name}.zip.sha256"
    if zip_path.parent != output_dir or checksum_path.parent != output_dir:
        raise ValueError("Package output must remain inside the output directory.")

    with TemporaryDirectory(prefix="meeting-agent-package-") as temporary:
        staging_root = Path(temporary) / PACKAGE_ROOT
        entries: list[dict[str, object]] = []
        for source in files:
            relative = source.relative_to(ROOT)
            destination = staging_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            entries.append(
                {
                    "path": relative.as_posix(),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                }
            )

        manifest = {
            "schema_version": 1,
            "package": args.name,
            "generated_at": datetime.now(UTC).isoformat(),
            "root_directory": PACKAGE_ROOT,
            "file_count": len(entries),
            "total_bytes": sum(int(entry["bytes"]) for entry in entries),
            "files": entries,
            "excluded_runtime_and_secrets": True,
        }
        manifest_path = staging_root / "PACKAGE-MANIFEST.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        zip_path.unlink(missing_ok=True)
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(staging_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging_root.parent).as_posix())

    verify_package(zip_path, manifest)
    package_hash = sha256(zip_path)
    checksum_path.write_text(
        f"{package_hash}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "zip": str(zip_path),
                "sha256": package_hash,
                "bytes": zip_path.stat().st_size,
                "files": len(entries),
                "checksum": str(checksum_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


def package_files() -> list[Path]:
    files = [ROOT / name for name in sorted(PUBLIC_ROOT_FILES)]
    for relative_root in sorted(PUBLIC_DIRS):
        public_root = ROOT / relative_root
        for current_root, directories, names in os.walk(public_root, followlinks=False):
            current = Path(current_root)
            directories[:] = sorted(
                directory
                for directory in directories
                if directory not in EXCLUDED_DIRS
                and not directory.endswith(".egg-info")
                and not (current / directory).is_symlink()
            )
            for name in sorted(names):
                path = current / name
                if path.is_symlink():
                    raise RuntimeError(
                        f"Symbolic links are not allowed in the customer package: {path}"
                    )
                if name in EXCLUDED_NAMES:
                    continue
                if name.startswith(".env") and name != ".env.example":
                    continue
                if path.suffix.casefold() in SENSITIVE_SUFFIXES:
                    continue
                if path.relative_to(ROOT).as_posix() in EXCLUDED_RELATIVE_PATHS:
                    continue
                files.append(path)
    missing_sources = [path for path in files if not path.is_file()]
    if missing_sources:
        raise RuntimeError(f"Public allowlist files are missing: {missing_sources}")
    return sorted(set(files), key=lambda value: value.relative_to(ROOT).as_posix())


def verify_package(zip_path: Path, manifest: dict[str, object]) -> None:
    expected = {
        f"{PACKAGE_ROOT}/{entry['path']}": (entry["bytes"], entry["sha256"])
        for entry in manifest["files"]
    }
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        expected_names = {*expected, f"{PACKAGE_ROOT}/PACKAGE-MANIFEST.json"}
        if names != expected_names:
            raise RuntimeError(
                f"Package file list mismatch: missing={sorted(expected_names - names)}, "
                f"unexpected={sorted(names - expected_names)}"
            )
        for name, (expected_bytes, expected_hash) in expected.items():
            content = archive.read(name)
            if len(content) != expected_bytes:
                raise RuntimeError(f"Package byte count mismatch: {name}")
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise RuntimeError(f"Package SHA-256 mismatch: {name}")
        forbidden = [
            name
            for name in names
            if any(part in EXCLUDED_DIRS for part in Path(name).parts)
            or Path(name).name in EXCLUDED_NAMES
            or Path(name).suffix.casefold() in SENSITIVE_SUFFIXES
        ]
        if forbidden:
            raise RuntimeError(f"Forbidden files entered the package: {forbidden}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())