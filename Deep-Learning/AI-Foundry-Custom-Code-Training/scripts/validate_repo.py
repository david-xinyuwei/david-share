"""Deterministic, dependency-free quality gate for this repository."""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT.parents[1] / ".github/workflows/ai-foundry-custom-code-training-ci.yml"
README_FILES = (ROOT / "README.md", ROOT / "README-CN.md")
REQUIRED = (
    "README.md",
    "README-CN.md",
    "requirements.txt",
    "requirements-dev.txt",
    "configs/foundry-job.schema.json",
    "configs/foundry-job.example.json",
    "configs/verified-overrides.json",
    "docker/Dockerfile",
    "scripts/job_contract.py",
    "scripts/preflight.py",
    "scripts/submit_job.py",
    "scripts/job_status.py",
    "evidence/training-metrics.jsonl",
    "evidence/validation-baseline.json",
    "evidence/run-manifest.json",
    "evidence/image-build.json",
    "docs/method-and-lineage.md",
    "docs/reproduction.md",
)
LOCAL_LINK_RE = re.compile(r"\[[^]]*\]\((?!https?://|mailto:|#)([^)]+)\)")
HTML_IMAGE_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+", re.MULTILINE)
FENCE_RE = re.compile(r"^```([^\s`]*)", re.MULTILINE)
STEP_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|", re.MULTILINE)


class GateError(RuntimeError):
    """One or more deterministic repository invariants failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateError(f"invalid JSON {path.relative_to(ROOT)}: {error}") from error


def prose_without_fences(text: str) -> str:
    """Remove fenced code so shell comments are not mistaken for Markdown headings."""
    prose: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            prose.append(line)
    require(not in_fence, "unclosed Markdown code fence")
    return "\n".join(prose)


def markdown_shape(text: str) -> dict:
    prose = prose_without_fences(text)
    table_separators = [
        line for line in prose.splitlines() if re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line)
    ]
    return {
        "headings": [len(match.group(1)) for match in HEADING_RE.finditer(prose)],
        "tables": [line.count("|") - 1 for line in table_separators],
        "fences": [match.group(1) for match in FENCE_RE.finditer(text)],
        "images": [Path(path).name for path in HTML_IMAGE_RE.findall(text)],
    }


def check_links(path: Path, text: str) -> int:
    checked = 0
    for target in LOCAL_LINK_RE.findall(text):
        relative = unquote(target.split("#", 1)[0])
        if not relative:
            continue
        require((path.parent / relative).exists(), f"broken link in {path.name}: {target}")
        checked += 1
    for target in HTML_IMAGE_RE.findall(text):
        require((path.parent / target).is_file(), f"missing image in {path.name}: {target}")
        checked += 1
    return checked


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {path.name}")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    try:
        for relative in REQUIRED:
            require((ROOT / relative).is_file(), f"required file missing: {relative}")
        require(CI_WORKFLOW.is_file(), "monorepo-root CI workflow is missing")

        english = README_FILES[0].read_text(encoding="utf-8")
        chinese = README_FILES[1].read_text(encoding="utf-8")
        require(english.startswith("# Custom Code Training on Microsoft Foundry"), "English H1 is not product-first")
        require(chinese.startswith("# Microsoft Foundry Custom Code Training"), "Chinese H1 is not product-first")
        require(markdown_shape(english) == markdown_shape(chinese), "README bilingual structure differs")
        links = sum(check_links(path, text) for path, text in zip(README_FILES, (english, chinese)))

        metrics = [
            json.loads(line)
            for line in (ROOT / "evidence/training-metrics.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        require(metrics, "training metrics are empty")
        steps = [row["step"] for row in metrics]
        require(steps == sorted(set(steps)), "training steps are duplicated or unordered")
        required_metrics = {
            "perf/time_per_step",
            "global_seqlen/mean",
            "global_seqlen/minmax_diff",
            "actor/entropy",
            "critic/score/mean",
            "actor/kl_loss",
            "actor/grad_norm",
        }
        for row in metrics:
            require(required_metrics <= row.keys(), f"step {row['step']} is missing metrics")

        manifest = read_json(ROOT / "evidence/run-manifest.json")
        require(manifest["run"]["stepsCaptured"] == steps, "manifest and metrics step sets differ")
        require(manifest["sourceLog"]["sha256"], "source log hash is empty")

        validation = read_json(ROOT / "evidence/validation-baseline.json")
        passes = [row["afterStep"] for row in validation]
        require(passes == [0, 5, 10, 14], f"validation pass set changed: {passes}")
        require(
            passes[-1] == max(steps),
            "final validation pass is not aligned with the last optimizer step",
        )
        read_json(ROOT / "evidence/image-build.json")
        read_json(ROOT / "configs/foundry-job.schema.json")
        read_json(ROOT / "configs/foundry-job.example.json")
        read_json(ROOT / "configs/verified-overrides.json")

        for text, name in ((english, "README.md"), (chinese, "README-CN.md")):
            rows = {int(step): float(seconds) for step, seconds in STEP_ROW_RE.findall(text)}
            for metric in metrics:
                require(
                    rows.get(metric["step"]) == round(metric["perf/time_per_step"], 2),
                    f"{name} step {metric['step']} does not match evidence",
                )

        images = sorted((ROOT / "images").glob("*.png"))
        require(len(images) >= 12, "expected at least 12 product screenshots")
        for image in images:
            width, height = png_size(image)
            require(width >= 400 and height >= 280, f"image too small: {image.name} {width}x{height}")

        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for line in requirements.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "--")):
                continue
            require("==" in stripped, f"unpinned direct dependency: {stripped}")
        require(":latest" not in (ROOT / "docker/Dockerfile").read_text(encoding="utf-8"), "Dockerfile uses :latest")

        print(f"REQUIRED_FILES={len(REQUIRED)}")
        print(f"CI_WORKFLOW={CI_WORKFLOW.relative_to(ROOT.parents[1])}")
        print(f"LOCAL_LINKS_AND_IMAGES={links}")
        print(f"BILINGUAL_SHAPE={markdown_shape(english)}")
        print(f"METRIC_STEPS={steps}")
        print(f"PRODUCT_SCREENSHOTS={len(images)}")
        print("REPO_GATE=PASS")
        return 0
    except (GateError, KeyError, TypeError, ValueError) as error:
        print(f"REPO_GATE=FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
