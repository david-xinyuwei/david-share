from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_local_files_are_not_present() -> None:
    forbidden = (
        ".env",
        ".msal_token_cache.json",
        "password",
        "password.txt",
        "session-logs",
        "logs",
        "dist",
        "build",
    )
    assert not [name for name in forbidden if (ROOT / name).exists()]


def test_runtime_dependencies_are_exactly_pinned() -> None:
    requirements = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert requirements
    assert all("==" in requirement for requirement in requirements)


def test_public_version_fields_are_aligned() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert version == "1.0.1"
    assert f'version = "{version}"' in pyproject
    assert f"## {version} - 2026-08-26" in changelog


def test_public_json_is_stored_as_regular_git_text() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.json !filter !diff !merge text eol=lf" in attributes
    for path in ROOT.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not text.startswith("version https://git-lfs.github.com/spec/v1")
        json.loads(text)


def test_environment_template_keeps_image_generation_opt_in() -> None:
    values = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            values[key] = value

    assert values["AZURE_OPENAI_IMAGE_DEPLOYMENT"] == ""


def test_explicit_image_deployment_registers_twenty_five_tools() -> None:
    environment = os.environ.copy()
    environment["AZURE_OPENAI_IMAGE_DEPLOYMENT"] = "caller-owned-image-deployment"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src import tools; print(len(tools.registered_names()))",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "25"


def test_scenario_manifest_has_no_unclassified_scenario() -> None:
    manifest = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))
    allowed = {"dynamic-runtime", "architecture-explainer", "test-fixture"}
    assert manifest["scenarios"]
    assert {item["classification"] for item in manifest["scenarios"]} <= allowed
    assert all(item.get("entrypoint") and item.get("boundary") for item in manifest["scenarios"])


def test_public_entrypoints_exist() -> None:
    for relative in (
        "app.py",
        "run.cmd",
        "VoiceLiveAgent-dir.spec",
        "scripts/preflight.py",
        "scripts/smoke_tools.py",
        "src/backends/voicelive.py",
        "src/tools/power.py",
    ):
        assert (ROOT / relative).is_file(), relative
