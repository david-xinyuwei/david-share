"""Deterministic, dependency-free quality gate for this repository."""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path
from urllib.parse import unquote

from job_contract import REQUIRED_SAMPLE_FILES, SKU_TO_GPUS_PER_NODE, SKU_TO_INSTANCE_TYPE

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
    "tests/test_preflight.py",
    "tests/test_submit_job.py",
    "evidence/training-metrics.jsonl",
    "evidence/validation-baseline.json",
    "evidence/run-manifest.json",
    "evidence/image-build.json",
    "evidence/sdk-demo-runs.jsonl",
    "evidence/input-manifest.jsonl",
    "evidence/compute-quota.jsonl",
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


def markdown_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for line in prose_without_fences(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not match:
            continue
        heading = match.group(1).replace("`", "").lower()
        slug = "".join(character for character in heading if character.isalnum() or character in " -_")
        slug = re.sub(r"\s+", "-", slug).strip("-")
        duplicate = seen.get(slug, 0)
        seen[slug] = duplicate + 1
        anchors.add(slug if duplicate == 0 else f"{slug}-{duplicate}")
    return anchors


def check_links(path: Path, text: str) -> int:
    checked = 0
    for target in LOCAL_LINK_RE.findall(text):
        parts = target.split("#", 1)
        relative = unquote(parts[0])
        fragment = unquote(parts[1]).lower() if len(parts) == 2 else ""
        target_path = path if not relative else path.parent / relative
        require(target_path.exists(), f"broken link in {path.name}: {target}")
        if fragment and target_path.suffix.lower() == ".md":
            anchors = markdown_anchors(target_path.read_text(encoding="utf-8"))
            require(fragment in anchors, f"broken anchor in {path.name}: {target}")
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
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        require(re.search(r"actions/checkout@[0-9a-f]{40}", workflow), "checkout action is not SHA-pinned")
        require(re.search(r"actions/setup-python@[0-9a-f]{40}", workflow), "setup-python action is not SHA-pinned")
        require("python -m pip check" in workflow, "CI does not validate the dependency graph")

        english = README_FILES[0].read_text(encoding="utf-8")
        chinese = README_FILES[1].read_text(encoding="utf-8")
        require(english.startswith("# Microsoft Foundry Custom Code Training"), "English H1 is not product-first")
        require(chinese.startswith("# Microsoft Foundry Custom Code Training"), "Chinese H1 is not product-first")
        require(markdown_shape(english) == markdown_shape(chinese), "README bilingual structure differs")
        links = sum(check_links(path, text) for path, text in zip(README_FILES, (english, chinese)))

        for text, name in ((english, "README.md"), (chinese, "README-CN.md")):
            for demo in ("hello-world", "quickstart-sft", "rft-with-verl"):
                require(f"`{demo}`" in text, f"{name} does not name completed demo {demo}")
            require("GPU" in text and "quota" in text, f"{name} lacks GPU/quota planning")
            require("Microsoft.MachineLearningServices/locations/" in text, f"{name} lacks quota scope")
            require("TotalDedicatedCores" in text, f"{name} lacks regional quota gate")
            require("compute-quota.jsonl" in text, f"{name} lacks quota evidence link")
            require("018d095f508280efce9e79c4b19fc941d7361b30" in text, f"{name} lacks measured lineage")
            overview_position = text.find("portal-code-workbench-overview.png")
            templates_position = text.find("portal-code-workbench-templates.png")
            entry_position = text.find("portal-start-training-entry-points.png")
            require(
                0 <= overview_position < templates_position < entry_position,
                f"{name} does not place the Code workbench overview before existing screenshots",
            )

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

        demo_runs = [
            json.loads(line)
            for line in (ROOT / "evidence/sdk-demo-runs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        require(
            [row["sample"] for row in demo_runs] == ["hello-world", "quickstart-sft", "rft-with-verl"],
            "SDK demo evidence set changed",
        )
        require(all(row["status"] == "Completed" for row in demo_runs), "an SDK demo is not completed")
        require(demo_runs[2]["optimizerStepsCompleted"] == 14, "VERL demo step count changed")
        require(demo_runs[2]["validationPasses"] == [0, 5, 10, 14], "VERL demo validation set changed")

        quota_path = ROOT / "evidence/compute-quota.jsonl"
        quota_text = quota_path.read_text(encoding="utf-8")
        quota = read_json(quota_path)
        tested = quota["testedCompute"]
        family = quota["quotaObservations"]["targetVmFamily"]
        regional = quota["quotaObservations"]["regionalDedicated"]
        capacity = quota["nodeCapacityAtObservation"]
        require(tested["nodeCount"] * tested["vcpusPerNode"] == family["usageVcpus"], "quota usage does not match tested topology")
        require(family["remainingVcpus"] == family["limitVcpus"] - family["usageVcpus"], "family quota arithmetic differs")
        require(regional["remainingVcpus"] == regional["limitVcpus"] - regional["usageVcpus"], "regional quota arithmetic differs")
        require(capacity["effectiveAdditionalNodes"] == 0, "tested quota boundary changed")
        require("<subscription-id>" in quota_text, "quota evidence lacks a subscription placeholder")
        require(
            not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", quota_text, re.IGNORECASE),
            "quota evidence contains a GUID",
        )

        validation = read_json(ROOT / "evidence/validation-baseline.json")
        passes = [row["afterStep"] for row in validation]
        require(passes == [0, 5, 10, 14], f"validation pass set changed: {passes}")
        require(
            passes[-1] == max(steps),
            "final validation pass is not aligned with the last optimizer step",
        )
        read_json(ROOT / "evidence/image-build.json")
        schema = read_json(ROOT / "configs/foundry-job.schema.json")
        schema_skus = set(schema["properties"]["computeClusterSku"]["enum"])
        require(schema_skus == set(SKU_TO_INSTANCE_TYPE), "schema and Python SKU mappings differ")
        require(set(SKU_TO_GPUS_PER_NODE) == set(SKU_TO_INSTANCE_TYPE), "GPU-count and instance mappings differ")
        read_json(ROOT / "configs/foundry-job.example.json")
        read_json(ROOT / "configs/verified-overrides.json")

        lineage = (ROOT / "docs/method-and-lineage.md").read_text(encoding="utf-8")
        require("14 STEPS CAPTURED" in lineage, "method lineage does not reflect the completed run")
        require("steps 0, 5, 10 and 14" in lineage, "method lineage lacks all validation passes")

        input_manifest = [
            json.loads(line)
            for line in (ROOT / "evidence/input-manifest.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        input_paths = [row["path"] for row in input_manifest]
        require(input_paths == list(REQUIRED_SAMPLE_FILES), "input manifest and runtime file contract differ")
        require(len(input_paths) == len(set(input_paths)), "input manifest contains duplicate paths")
        for row in input_manifest:
            require(isinstance(row["bytes"], int) and row["bytes"] > 0, f"invalid byte count for {row['path']}")
            require(re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), f"invalid SHA-256 for {row['path']}")
            require(f"`{row['path']}`" in lineage, f"method lineage lacks {row['path']}")
            require(row["sha256"] in lineage, f"method lineage hash differs for {row['path']}")
        require(next(row for row in input_manifest if row["path"] == "data/train.jsonl")["records"] == 270, "train record count changed")
        require(next(row for row in input_manifest if row["path"] == "data/validation.jsonl")["records"] == 62, "validation record count changed")

        require("14 steps" in english, "English README lacks 14-step evidence claim")
        require("14 步" in chinese, "Chinese README lacks 14-step evidence claim")
        require("8 steps" not in english, "English README retains stale 8-step claim")
        require("8 步" not in chinese, "Chinese README retains stale 8-step claim")
        require("isolated run snapshot" in english, "English README lacks upload snapshot contract")
        require("隔离运行快照" in chinese, "Chinese README lacks upload snapshot contract")

        preflight_source = (ROOT / "scripts/preflight.py").read_text(encoding="utf-8")
        submit_source = (ROOT / "scripts/submit_job.py").read_text(encoding="utf-8")
        status_source = (ROOT / "scripts/job_status.py").read_text(encoding="utf-8")
        submit_tests = (ROOT / "tests/test_submit_job.py").read_text(encoding="utf-8")
        require("create_upload_snapshot" in preflight_source, "preflight lacks upload snapshot support")
        require('"uploadInventory"' in preflight_source, "preflight lacks full upload inventory")
        require("potentiallyCreatedDatasetVersions" in submit_source, "submit evidence lacks partial upload recovery")
        require("potentiallyCreatedJobs" in submit_source, "submit evidence lacks uncertain job recovery")
        require('"automaticDeletion": False' in submit_source, "submit may silently auto-delete datasets")
        require("--tenant-id requires --credential azure-cli" in submit_source, "submit tenant constraint is not fail-closed")
        require("--tenant-id requires --credential azure-cli" in status_source, "status tenant constraint is not fail-closed")
        require("test_records_code_asset_when_data_upload_fails" in submit_tests, "partial upload failure is untested")
        require("test_validate_uses_snapshot_and_never_submits" in submit_tests, "snapshot isolation is untested")
        require("test_submit_timeout_records_potential_job_before_retry" in submit_tests, "submit timeout recovery is untested")

        for text, name in ((english, "README.md"), (chinese, "README-CN.md")):
            rows = {int(step): float(seconds) for step, seconds in STEP_ROW_RE.findall(text)}
            for metric in metrics:
                require(
                    rows.get(metric["step"]) == round(metric["perf/time_per_step"], 2),
                    f"{name} step {metric['step']} does not match evidence",
                )

        images = sorted((ROOT / "images").glob("*.png"))
        require(len(images) >= 13, "expected at least 13 product screenshots")
        for image in images:
            width, height = png_size(image)
            require(width >= 400 and height >= 280, f"image too small: {image.name} {width}x{height}")

        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for line in requirements.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "--")):
                continue
            require("==" in stripped, f"unpinned direct dependency: {stripped}")
        dockerfile = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
        require(":latest" not in dockerfile, "Dockerfile uses :latest")
        image_build = read_json(ROOT / "evidence/image-build.json")
        require(image_build["base"]["digest"] in dockerfile, "Dockerfile base digest differs from image evidence")

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
