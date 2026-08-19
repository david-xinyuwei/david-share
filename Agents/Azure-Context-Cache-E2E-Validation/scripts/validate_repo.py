"""Deterministic, dependency-free quality gate for this public subtree."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from audit_public_content import findings
from parse_demo_output import parse_rows, summarize


ROOT = Path(__file__).resolve().parents[1]
MONOREPO = ROOT.parents[1]
CI = MONOREPO / ".github" / "workflows" / "azure-context-cache-e2e-validation-ci.yml"
AGENTS_INDEX = ROOT.parent / "README.md"
ROOT_ATTRIBUTES = MONOREPO / ".gitattributes"
READMES = (ROOT / "README.md", ROOT / "README-CN.md")
METHODS = (ROOT / "docs" / "METHOD.md", ROOT / "docs" / "METHOD-CN.md")
REQUIRED = (
    ".agentignore",
    ".gitattributes",
    ".gitignore",
    "ATTRIBUTION.md",
    "README.md",
    "README-CN.md",
    "SECURITY.md",
    "UPSTREAM_LOCK.json",
    "VALIDATION_CHECKLIST.md",
    "docs/METHOD.md",
    "docs/METHOD-CN.md",
    "evidence/README.md",
    "evidence/manifest.json",
    "evidence/validation-history.json",
    "evidence/verified-run-summary.json",
    "images/architecture.svg",
    "images/verified-observation.svg",
    "requirements.txt",
    "requirements-live-win-py311.lock",
    "scenario-manifest.json",
    "scripts/audit_public_content.py",
    "scripts/demo_code_validator.py",
    "scripts/parse_demo_output.py",
    "scripts/run_official_e2e.ps1",
    "scripts/validate_arm_summary.py",
    "scripts/validate_repo.py",
    "scripts/verify_upstream.py",
)
LOCAL_LINK = re.compile(r"\[[^]]*\]\((?!https?://|mailto:|#)([^)]+)\)")
IMAGE_LINK = re.compile(r"!\[[^]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
FENCE = re.compile(r"^```([^\s`]*)", re.MULTILINE)


class GateError(RuntimeError):
    """A deterministic repository invariant failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def load_json(relative: str):
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"invalid JSON: {relative}: {error}") from error


def markdown_shape(text: str) -> dict[str, object]:
    return {
        "headings": [len(match.group(1)) for match in HEADING.finditer(text)],
        "fences": [match.group(1) for match in FENCE.finditer(text)],
        "tableSeparators": [
            line.count("|") - 1
            for line in text.splitlines()
            if re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line)
        ],
        "images": [Path(value).name for value in IMAGE_LINK.findall(text)],
    }


def validate_links(path: Path, text: str) -> int:
    count = 0
    for raw in LOCAL_LINK.findall(text):
        target = unquote(raw.split("#", 1)[0])
        if target:
            require((path.parent / target).exists(), f"broken link in {path.name}: {raw}")
            count += 1
    return count


def validate_svg(path: Path) -> None:
    root = ElementTree.parse(path).getroot()
    require(root.attrib.get("viewBox") == "0 0 1600 900", f"unexpected viewBox: {path.name}")
    require(root.find("{http://www.w3.org/2000/svg}title") is not None, f"missing title: {path.name}")
    require(root.find("{http://www.w3.org/2000/svg}desc") is not None, f"missing desc: {path.name}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        for relative in REQUIRED:
            require((ROOT / relative).is_file(), f"required file missing: {relative}")
        require(CI.is_file(), "monorepo CI workflow is missing")

        english = READMES[0].read_text(encoding="utf-8")
        chinese = READMES[1].read_text(encoding="utf-8")
        require(english.startswith("# Azure Context Cache E2E Validation"), "English H1 changed")
        require(chinese.startswith("# Azure Context Cache 端到端验证"), "Chinese H1 changed")
        require(markdown_shape(english) == markdown_shape(chinese), "bilingual README shape differs")
        links = sum(validate_links(path, text) for path, text in zip(READMES, (english, chinese)))

        method_en = METHODS[0].read_text(encoding="utf-8")
        method_cn = METHODS[1].read_text(encoding="utf-8")
        require(markdown_shape(method_en) == markdown_shape(method_cn), "bilingual method shape differs")
        links += sum(validate_links(path, text) for path, text in zip(METHODS, (method_en, method_cn)))

        for image in (ROOT / "images").glob("*.svg"):
            validate_svg(image)
        require(len(list((ROOT / "images").glob("*.svg"))) == 2, "expected exactly two SVGs")

        lock = load_json("UPSTREAM_LOCK.json")
        require(
            lock["hashMode"] == "git-blob-content-sha256",
            "upstream hash mode changed",
        )
        require(re.fullmatch(r"[0-9a-f]{40}", lock["commit"]) is not None, "invalid commit")
        require(len(lock["files"]) == 25, "upstream file set changed")
        require(
            len([path for path in lock["files"] if path.startswith("demo/diffs/")]) == 20,
            "all demo diff inputs must be pinned",
        )
        require(
            all(re.fullmatch(r"[0-9a-f]{64}", value) for value in lock["files"].values()),
            "invalid upstream SHA-256",
        )
        python_lock = (ROOT / "requirements-live-win-py311.lock").read_text(encoding="utf-8")
        locked_packages = re.findall(
            r"^([A-Za-z0-9_-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})$",
            python_lock,
            re.MULTILINE,
        )
        require(len(locked_packages) == 18, "Python artifact lock must contain 18 hashes")
        require(
            {name.casefold() for name, _, _ in locked_packages}
            >= {"httpx", "azure-identity"},
            "Python artifact lock is missing upstream direct dependencies",
        )

        scenario = load_json("scenario-manifest.json")
        require(len(scenario["scenarios"]) == 5, "scenario count changed")
        evidence = load_json("evidence/verified-run-summary.json")
        evidence_manifest = load_json("evidence/manifest.json")
        history = load_json("evidence/validation-history.json")
        calls = evidence["calls"]
        require(len(calls) == 6, "evidence run count changed")
        warm = calls[1:]
        warm_mean = round(sum(row["latencyMs"] for row in warm) / len(warm), 3)
        speedup = round(calls[0]["latencyMs"] / warm_mean, 6)
        require(warm_mean == evidence["recomputed"]["warmMeanLatencyMs"], "warm mean mismatch")
        require(speedup == evidence["recomputed"]["firstToWarmSpeedup"], "speedup mismatch")
        require(sum(row["cachedTokens"] > 0 for row in warm) == 5, "warm hit count mismatch")
        require({row["cachedTokens"] for row in warm} == {2304}, "cached tokens changed")

        evidence_paths = (
            ROOT / "evidence" / "validation-history.json",
            ROOT / "evidence" / "verified-run-summary.json",
        )
        manifest_entries = {row["path"]: row for row in evidence_manifest["files"]}
        require(set(manifest_entries) == {path.name for path in evidence_paths}, "evidence manifest set changed")
        for evidence_path in evidence_paths:
            manifest_entry = manifest_entries[evidence_path.name]
            require(manifest_entry["bytes"] == evidence_path.stat().st_size, "evidence byte count mismatch")
            require(manifest_entry["sha256"] == sha256(evidence_path), "evidence hash mismatch")
        require([row["verdict"] for row in history["runs"]] == [
            "pass", "pass", "rejected-incomplete", "rejected-incomplete"
        ], "validation history verdicts changed")
        require([row["transportErrors"] for row in history["runs"]] == [0, 0, 3, 4], "validation history transport counts changed")

        fixture_summary = summarize(
            parse_rows((ROOT / "tests/fixtures/demo-success.txt").read_text(encoding="utf-8"))
        )
        require(fixture_summary["warm"]["hits"] == 5, "fixture differential changed")
        for text, name in ((english, "README.md"), (chinese, "README-CN.md")):
            for marker in ("6", "5", "2304", "3642.4", "5820", "1.597848"):
                require(marker in text, f"{name} missing evidence marker: {marker}")

        require(
            not findings(ROOT, (AGENTS_INDEX, ROOT_ATTRIBUTES)),
            "public boundary scan failed",
        )
        require(
            "[Azure-Context-Cache-E2E-Validation](Azure-Context-Cache-E2E-Validation/)"
            in AGENTS_INDEX.read_text(encoding="utf-8"),
            "Agents index is missing this project",
        )
        workflow = CI.read_text(encoding="utf-8")
        require(re.search(r"actions/checkout@[0-9a-f]{40}", workflow) is not None, "checkout not pinned")
        require(re.search(r"actions/setup-python@[0-9a-f]{40}", workflow) is not None, "setup-python not pinned")
        require("permissions:\n  contents: read" in workflow, "workflow permissions are not read-only")
        for path_filter in ('"Agents/README.md"', '".gitattributes"'):
            require(path_filter in workflow, f"workflow path filter missing: {path_filter}")

        evidence_hash = sha256(ROOT / "evidence" / "verified-run-summary.json")
        print(f"REQUIRED_FILES={len(REQUIRED)}")
        print(f"LOCAL_LINKS={links}")
        print(f"BILINGUAL_SHAPE={markdown_shape(english)}")
        print(f"EVIDENCE_SHA256={evidence_hash}")
        print("REPO_GATE=PASS")
        return 0
    except (GateError, KeyError, TypeError, ValueError, OSError, ElementTree.ParseError) as error:
        print(f"REPO_GATE=FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())