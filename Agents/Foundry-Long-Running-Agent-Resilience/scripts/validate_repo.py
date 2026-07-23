#!/usr/bin/env python3
"""Run deterministic repository, public-boundary, and image checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageStat

from lra_resilience.evidence import validate_matrix
from lra_resilience.manifest import load_manifest, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    ".gitignore",
    "CONTRIBUTING.md",
    "README-CN.md",
    "README.md",
    "SECURITY.md",
    "data/evidence-contract.schema.json",
    "data/validation-matrix.json",
    "docs/evidence-contract-CN.md",
    "docs/evidence-contract.md",
    "docs/failure-modes-CN.md",
    "docs/failure-modes.md",
    "docs/methodology-CN.md",
    "docs/methodology.md",
    "evidence/manifest.json",
    "evidence/README-CN.md",
    "evidence/README.md",
    "images/evidence-pipeline.png",
    "images/scenario-coverage.png",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "scenario-manifest.json",
    "scripts/build_public_evidence.py",
    "scripts/runtime_differential.py",
    "scripts/validate_evidence.py",
    "scripts/validate_readmes.py",
    "scripts/validate_repo.py",
}
TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".txt", ".yml", ".yaml"}
FORBIDDEN_LITERALS = {
    "cloudapp.azure.com",
    "/mnt/c/",
    "/mnt/g/",
    "@microsoft.com",
    "thread.v2",
    "workspaceStorage",
}
SECRET_PATTERNS = {
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Azure GUID": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    "Foundry endpoint": re.compile(r"https://[A-Za-z0-9.-]+\.services\.ai\.azure\.com"),
    "Private/internal GitHub URL": re.compile(
        r"https://github\.com/[^/\s]+/[^)\s]*(?:private|internal)[^)\s]*",
        re.IGNORECASE,
    ),
    "Windows absolute path": re.compile(r"\b[A-Za-z]:\\"),
}
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in TEXT_SUFFIXES
        and not (set(path.relative_to(ROOT).parts) & IGNORED_PARTS)
        and not any(part.endswith(".egg-info") for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    errors: list[str] = []
    present = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    missing = sorted(REQUIRED - present)
    if missing:
        errors.append(f"missing required files: {', '.join(missing)}")

    matrix = json.loads((ROOT / "data" / "validation-matrix.json").read_text(encoding="utf-8"))
    errors.extend(validate_matrix(matrix))
    errors.extend(validate_manifest(ROOT, load_manifest(ROOT / "evidence" / "manifest.json")))

    for path in text_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        if relative == "scripts/validate_repo.py":
            continue
        for literal in FORBIDDEN_LITERALS:
            if literal in text:
                errors.append(f"{relative}: forbidden public literal: {literal}")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{relative}: matched {name}")

    manifest = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))
    scenario_types = {scenario.get("type") for scenario in manifest.get("scenarios", [])}
    if scenario_types != {"architecture-explainer", "dynamic-runtime", "test-fixture"}:
        errors.append("scenario-manifest.json must classify architecture, dynamic runtime, and test fixture")

    expected_dimensions = {
        "evidence-pipeline.png": (1600, 900),
        "scenario-coverage.png": (1600, 900),
    }
    for filename, dimensions in expected_dimensions.items():
        with Image.open(ROOT / "images" / filename) as image:
            rgb = image.convert("RGB")
            if rgb.size != dimensions:
                errors.append(f"{filename}: expected {dimensions}, got {rgb.size}")
            if any(value <= 100 for value in ImageStat.Stat(rgb).var):
                errors.append(f"{filename}: image variance is too low")

    ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required_ignore in (".env", ".venv/", "__pycache__/", "*.egg-info/", "build/", "dist/"):
        if required_ignore not in ignore_text:
            errors.append(f".gitignore missing generated/private pattern: {required_ignore}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: public boundary, 8 scenarios, 9 evidence artifacts, and 2 images verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
