#!/usr/bin/env python3
"""Fail-closed gate for the bilingual report, run contract, evidence, and code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

try:
    from generate_rule_results import (
        evaluate_rules,
        validate_document as validate_computed_rule_document,
    )
except ModuleNotFoundError:
    from scripts.generate_rule_results import (
        evaluate_rules,
        validate_document as validate_computed_rule_document,
    )


def parse_root() -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args().root.resolve()


ROOT = parse_root()
EN = ROOT / "README.md"
CN = ROOT / "README-CN.md"

ALLOWED_FILES = {
    ".gitattributes",
    ".gitignore",
    "LICENSE",
    "README-CN.md",
    "README.md",
    "THIRD-PARTY-NOTICES.md",
    "dotnet-agent/LraEvidenceAgent.csproj",
    "dotnet-agent/Program.cs",
    "evidence/README.md",
    "evidence/manifest.json",
    "evidence/observation-validation.json",
    "evidence/owned-approval-live-events.jsonl",
    "evidence/owned-approval-live-trace.txt",
    "evidence/owned-approval-live.json",
    "evidence/owned-approval-local-events.jsonl",
    "evidence/owned-approval-local-trace.txt",
    "evidence/owned-approval-local.json",
    "evidence/owned-hosted-agent-dotnet-events.jsonl",
    "evidence/owned-hosted-agent-dotnet.json",
    "evidence/owned-hosted-agent-graceful-attempt.json",
    "evidence/owned-hosted-agent-live.json",
    "evidence/owned-hosted-agent-live-recovery-events.jsonl",
    "evidence/owned-hosted-agent-live-recovery.json",
    "evidence/owned-hosted-agent-live-translation-events.jsonl",
    "evidence/owned-hosted-agent-live-translation-output.md",
    "evidence/owned-hosted-agent-live-translation-trace.txt",
    "evidence/owned-hosted-agent-live-translation.json",
    "evidence/owned-hosted-agent-local-events.jsonl",
    "evidence/owned-hosted-agent-local-trace.txt",
    "evidence/owned-hosted-agent-local.json",
    "evidence/owned-hosted-agent-observer-events.jsonl",
    "evidence/owned-hosted-agent-observer.json",
    "evidence/owned-hosted-agent-status.json",
    "evidence/owned-hosted-agent-translation-local-events.jsonl",
    "evidence/owned-hosted-agent-translation-local-trace.txt",
    "evidence/owned-hosted-agent-translation-local.json",
    "evidence/owned-steering-live-events.jsonl",
    "evidence/owned-steering-live-trace.txt",
    "evidence/owned-steering-live.json",
    "evidence/public-sdk-contract.json",
    "evidence/recovery-contract-demo.json",
    "evidence/recovery-contract-events.jsonl",
    "evidence/resilience-sdk-usage.json",
    "evidence/run-contract.json",
    "evidence/rule-results.json",
    "evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json",
    "evidence/scenario-manifest.json",
    "evidence/scenario-matrix.json",
    "evidence/steering-order-boundary.json",
    "evidence/ui-evidence.json",
    "examples/resilience_handler.py",
    "examples/resilience_sdk_usage.py",
    "examples/resilient_responses_agent.py",
    "hosted-agent/.env.example",
    "hosted-agent/azure.yaml",
    "hosted-agent/client.py",
    "hosted-agent/run_local_recovery.py",
    "hosted-agent/run_observer_restart.py",
    "hosted-agent/sanitize_agent_log.py",
    "hosted-agent/src/lra-evidence-agent/.azdignore",
    "hosted-agent/src/lra-evidence-agent/contract.py",
    "hosted-agent/src/lra-evidence-agent/main.py",
    "hosted-agent/src/lra-evidence-agent/requirements.txt",
    "hosted-agent/src/lra-evidence-agent/translation_workload.py",
    "hosted-agent-approval/.env.example",
    "hosted-agent-approval/azure.yaml",
    "hosted-agent-approval/run_approval_recovery.py",
    "hosted-agent-approval/scripts/deploy.sh",
    "hosted-agent-approval/src/resilient-approval-gate/.azdignore",
    "hosted-agent-approval/src/resilient-approval-gate/.dockerignore",
    "hosted-agent-approval/src/resilient-approval-gate/Dockerfile",
    "hosted-agent-approval/src/resilient-approval-gate/main.py",
    "hosted-agent-approval/src/resilient-approval-gate/requirements.txt",
    "hosted-agent-approval/src/resilient-approval-gate/translation_workload.py",
    "hosted-agent-steering/.env.example",
    "hosted-agent-steering/azure.yaml",
    "hosted-agent-steering/run_steering_recovery.py",
    "hosted-agent-steering/scripts/deploy.sh",
    "hosted-agent-steering/src/resilient-steering/.azdignore",
    "hosted-agent-steering/src/resilient-steering/.dockerignore",
    "hosted-agent-steering/src/resilient-steering/Dockerfile",
    "hosted-agent-steering/src/resilient-steering/main.py",
    "hosted-agent-steering/src/resilient-steering/requirements.txt",
    "hosted-agent-steering/src/resilient-steering/translation_workload.py",
    "images/official-lease-recovery-model.png",
    "images/lra-recovery-timeline.excalidraw",
    "images/lra-recovery-timeline.png",
    "images/lra-recovery-timeline.svg",
    "images/product-ui/portal-owned-agent-details.png",
    "images/product-ui/portal-owned-agent-list.png",
    "requirements-validation.txt",
    "scripts/generate_evidence_manifest.py",
    "scripts/generate_rule_results.py",
    "scripts/recovery_contract_demo.py",
    "scripts/render_approval_trace.py",
    "scripts/render_recovery_trace.py",
    "scripts/render_steering_trace.py",
    "scripts/render_translation_result.py",
    "scripts/validate_observations.py",
    "scripts/validate_repo.py",
    "scripts/verify_public_resilience_api.py",
    "tests/test_owned_hosted_agent.py",
    "tests/test_recovery_contract_demo.py",
    "tests/test_rule_results.py",
    "tests/test_steering_approval_evidence.py",
    "tests/test_validate_observations.py",
}

# The Invocations protocol names its session query parameter; the server reads
# it and the client sends it, so these two source files may spell it out.
# Evidence, documentation, and configuration still may not contain it.
PROTOCOL_PARAMETER_FILES = {
    "hosted-agent-approval/run_approval_recovery.py",
    "hosted-agent-approval/src/resilient-approval-gate/main.py",
}
PROTOCOL_PARAMETER_LITERAL = "agent_session_id"

LOCAL_ARTEFACT_DIRS = {
    ".azure",
    ".demo-state",
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".repo-evidence",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "bin",
    "node_modules",
    "obj",
    "venv",
}

REQUIRED_EN_SECTIONS = [
    "## Read this first",
    "## One complete recovery run",
    "### Where the Agent actually uses LRA",
    "### Exactly when it went down, recovered, and completed",
    "### Hosted run: delay, recovery, and completion log",
    "### Why the task did not stop and the data did not disappear",
    "## Fault matrix",
    "## Reproduce it",
    "### Prerequisites",
    "## Put the same hooks in your Agent",
    "## Acceptance contract",
    "## Evidence and boundaries",
    "## Related work and license",
]

REQUIRED_CN_SECTIONS = [
    "## 先看这里",
    "## 一次完整的恢复运行",
    "### Agent 到底在哪里接入 LRA",
    "### 什么时候 down、什么时候恢复、什么时候完成",
    "### 线上运行：延迟、接管和完成日志",
    "### 为什么任务没停、数据没丢",
    "## 故障矩阵",
    "## 自己复现",
    "### 前置条件",
    "## 把同样的接线放进你的 Agent",
    "## 验收合同",
    "## 证据与边界",
    "## 相关工作与许可证",
]

CRITICAL_NUMBERS = [
    "86",
    "1.415",
    "25.936",
    "49.555",
    "16.511",
    "4.322",
    "89.199",
    "0.606",
    "3.917",
    "73.868",
    "75.249",
    "52.411",
]

FORBIDDEN_LITERALS = [
    "services.ai.azure.com",
    "cloudapp.azure.com",
    "/mnt/c/",
    "/mnt/g/",
    "@microsoft.com",
    "agent_session_id",
    "api-version=",
]

SECRET_PATTERNS = {
    "GUID": re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    ),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Bearer-like key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Windows path": re.compile(r"\b[A-Za-z]:\\"),
}

RETIRED_STAGE_PATTERNS = (
    re.compile(r"\b1[8][ -](?:stage|phase)s?\b", re.IGNORECASE),
    re.compile(r"1[8]\s*个阶段"),
    re.compile(r"\b0-1[7]\b"),
    re.compile(r"\b1-1[8]\b"),
    re.compile(r"resilient" + r"-research", re.IGNORECASE),
    re.compile(r"historical" + r"-observations", re.IGNORECASE),
)


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def is_delivery_file(path: Path) -> bool:
    return not LOCAL_ARTEFACT_DIRS.intersection(path.parts)


def without_fences(text: str) -> str:
    return re.sub(
        r"^```[^\n]*\n.*?^```\s*$",
        "",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )


def heading_levels(text: str) -> list[int]:
    return [
        len(value)
        for value in re.findall(
            r"^(#{1,6})\s+",
            without_fences(text),
            flags=re.MULTILINE,
        )
    ]


def heading_titles(text: str) -> list[str]:
    return re.findall(
        r"^#{1,6}\s+(.+?)\s*$",
        without_fences(text),
        flags=re.MULTILINE,
    )


def github_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    counts: Counter[str] = Counter()
    for title in heading_titles(text):
        title = re.sub(r"<[^>]+>", "", title).replace("`", "").lower()
        slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
        slug = re.sub(r"[\s-]+", "-", slug).strip("-")
        index = counts[slug]
        counts[slug] += 1
        anchors.add(slug if index == 0 else f"{slug}-{index}")
    return anchors


def table_shapes(text: str) -> list[int]:
    shapes: list[int] = []
    for line in text.splitlines():
        if re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line):
            shapes.append(line.count("|") - 1)
    return shapes


def fenced_languages(text: str) -> list[str]:
    return re.findall(r"^```([A-Za-z0-9_-]*)\s*$", text, flags=re.MULTILINE)[::2]


def fenced_blocks(text: str, language: str) -> list[str]:
    return re.findall(
        rf"^```{re.escape(language)}\s*\n(.*?)^```$",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )


def html_images(text: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for tag in re.findall(r"<img\s+[^>]+>", text):
        attributes = dict(re.findall(r'(\w+)="([^"]*)"', tag))
        result.append(attributes)
    return result


def markdown_targets(text: str) -> list[str]:
    return re.findall(r"\]\(([^)\s]+)\)", text)


def sha256_file(path: Path) -> str:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt"}:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def normalized_size(path: Path) -> int:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt"}:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return len(content)


def read_json(gate: Gate, relative: str) -> dict:
    path = ROOT / relative
    gate.require(path.is_file(), f"missing JSON evidence: {relative}")
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        gate.require(False, f"{relative}: invalid JSON: {error}")
        return {}
    gate.require(isinstance(value, dict), f"{relative}: root must be an object")
    return value if isinstance(value, dict) else {}


def resolve_dotted_path(value: object, dotted_path: str) -> object:
    current = value
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(dotted_path)
        current = current[segment]
    return current


def event_matches(event: object, expected: object) -> bool:
    return (
        isinstance(event, dict)
        and isinstance(expected, dict)
        and all(event.get(key) == value for key, value in expected.items())
    )


def validate_readmes(gate: Gate) -> tuple[str, str]:
    gate.require(EN.is_file() and CN.is_file(), "both main READMEs are required")
    if not EN.is_file() or not CN.is_file():
        return "", ""
    en = EN.read_text(encoding="utf-8")
    cn = CN.read_text(encoding="utf-8")

    gate.require(
        heading_levels(en) == heading_levels(cn),
        "bilingual heading-level sequence differs",
    )
    gate.require(
        table_shapes(en) == table_shapes(cn),
        "bilingual table shapes differ",
    )
    gate.require(
        fenced_languages(en) == fenced_languages(cn),
        "bilingual code-block language sequence differs",
    )
    gate.require(
        abs(len(en.splitlines()) - len(cn.splitlines())) <= 10,
        "bilingual line-count drift exceeds 10",
    )
    gate.require(
        len(heading_titles(en)) <= 20 and len(heading_titles(cn)) <= 20,
        "main README re-fragmented beyond 20 headings",
    )

    for section in REQUIRED_EN_SECTIONS:
        gate.require(section in en, f"English README missing section: {section}")
    for section in REQUIRED_CN_SECTIONS:
        gate.require(section in cn, f"Chinese README missing section: {section}")
    en_positions = [en.index(value) for value in REQUIRED_EN_SECTIONS if value in en]
    cn_positions = [cn.index(value) for value in REQUIRED_CN_SECTIONS if value in cn]
    gate.require(en_positions == sorted(en_positions), "English reader flow is wrong")
    gate.require(cn_positions == sorted(cn_positions), "Chinese reader flow is wrong")

    en_images = html_images(en)
    cn_images = html_images(cn)
    gate.require(
        [item.get("src") for item in en_images]
        == [item.get("src") for item in cn_images],
        "bilingual image paths differ",
    )
    gate.require(
        len(en_images) == len(cn_images) == 1,
        "each README must embed only the explanatory official diagram",
    )
    for readme, images in ((EN, en_images), (CN, cn_images)):
        for image in images:
            gate.require(bool(image.get("alt")), f"{readme.name}: image alt missing")
            width = image.get("width", "")
            gate.require(
                width.isdigit() and int(width) <= 820,
                f"{readme.name}: image width missing or too large",
            )
            source = image.get("src", "")
            gate.require(
                bool(source) and (ROOT / source).is_file(),
                f"{readme.name}: image target missing: {source}",
            )

    contract = read_json(gate, "evidence/run-contract.json")
    trace_relatives = contract.get("readme_traces", [])
    gate.require(
        isinstance(trace_relatives, list)
        and bool(trace_relatives)
        and len(trace_relatives) == len(set(trace_relatives))
        and all(isinstance(value, str) and value for value in trace_relatives),
        "declared README traces are missing or duplicated",
    )
    traces: list[str] = []
    for relative in trace_relatives if isinstance(trace_relatives, list) else []:
        trace_path = ROOT / relative if isinstance(relative, str) else ROOT
        gate.require(trace_path.is_file(), f"declared README trace is missing: {relative}")
        if trace_path.is_file():
            traces.append(trace_path.read_text(encoding="utf-8"))
    for readme, text in ((EN, en), (CN, cn)):
        blocks = fenced_blocks(text, "text")
        gate.require(
            len(blocks) == len(traces)
            and all(
                block.strip() + "\n" == trace
                for block, trace in zip(blocks, traces, strict=True)
            ),
            f"{readme.name}: completion traces drifted from evidence",
        )

    for readme, text in ((EN, en), (CN, cn)):
        readme_anchors = github_anchors(text)
        for target in markdown_targets(text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            decoded = unquote(target)
            if decoded.startswith("#"):
                gate.require(
                    decoded[1:].lower() in readme_anchors,
                    f"{readme.name}: missing local anchor {target}",
                )
                continue
            path_text, _, fragment = decoded.partition("#")
            if path_text.startswith("../"):
                continue
            target_path = ROOT / path_text
            gate.require(
                target_path.exists(),
                f"{readme.name}: missing link target {path_text}",
            )
            if (
                fragment
                and target_path.suffix.lower() == ".md"
                and target_path.is_file()
            ):
                gate.require(
                    fragment.lower()
                    in github_anchors(target_path.read_text(encoding="utf-8")),
                    f"{readme.name}: missing Markdown anchor {target}",
                )

    for number in CRITICAL_NUMBERS:
        gate.require(number in en and number in cn, f"measured value drift: {number}")

    badges_en = re.findall(
        r"!\[[^\]]*\]\((https://img\.shields\.io/[^)]+)\)",
        en,
    )
    badges_cn = re.findall(
        r"!\[[^\]]*\]\((https://img\.shields\.io/[^)]+)\)",
        cn,
    )
    gate.require(badges_en == badges_cn, "bilingual badges differ")
    gate.require(
        4 <= len(badges_en) <= 5 and "public_preview" in badges_en[0],
        "badge row must state public preview and contain 4-5 facts",
    )

    boundaries = [
        "not an SLA",
        "not live process-loss recovery",
        "NOT VERIFIED",
        "do not prove process recovery",
    ]
    for boundary in boundaries:
        gate.require(boundary.lower() in en.lower(), f"English boundary missing: {boundary}")
    cn_boundaries = [
        "不是 SLA",
        "不证明线上进程恢复",
        "NOT VERIFIED",
        "不能证明恢复",
    ]
    for boundary in cn_boundaries:
        gate.require(boundary in cn, f"Chinese boundary missing: {boundary}")

    gate.require(
        "CC BY 4.0" in en
        and "CC BY 4.0" in cn
        and "THIRD-PARTY-NOTICES.md" in en
        and "THIRD-PARTY-NOTICES.md" in cn,
        "official diagram attribution is incomplete",
    )
    gate.require(
        not re.search(r"^####\s+", en, flags=re.MULTILINE)
        and not re.search(r"^####\s+", cn, flags=re.MULTILINE),
        "one-paragraph H4 fragments must not return",
    )
    return en, cn


def validate_run_contract(gate: Gate, en: str, cn: str) -> None:
    contract = read_json(gate, "evidence/run-contract.json")
    gate.require(
        contract.get("schema_version") == 1
        and isinstance(contract.get("scenario_id"), str)
        and isinstance(contract.get("subject"), str),
        "run contract identity is incomplete",
    )
    evidence_path = contract.get("evidence")
    gate.require(isinstance(evidence_path, str), "run contract evidence path missing")
    evidence = read_json(gate, evidence_path) if isinstance(evidence_path, str) else {}
    timeline_path = contract.get("timeline_path")
    try:
        timeline = resolve_dotted_path(evidence, timeline_path)
    except (KeyError, AttributeError):
        timeline = []
        gate.require(False, "run contract timeline path does not resolve")
    gate.require(
        isinstance(timeline, list) and bool(timeline),
        "run timeline must be non-empty",
    )
    if isinstance(timeline, list):
        timestamps = [
            datetime.fromisoformat(item["at_utc"])
            for item in timeline
            if isinstance(item, dict) and isinstance(item.get("at_utc"), str)
        ]
        gate.require(
            len(timestamps) == len(timeline) and timestamps == sorted(timestamps),
            "run timeline timestamps are missing or out of order",
        )

    milestones = contract.get("milestones", [])
    ids = [item.get("id") for item in milestones if isinstance(item, dict)]
    gate.require(
        isinstance(milestones, list)
        and len(ids) == len(milestones)
        and len(ids) == len(set(ids))
        and bool(ids),
        "run milestones need unique IDs",
    )
    previous_index = -1
    for milestone in milestones:
        expected = milestone.get("match") if isinstance(milestone, dict) else None
        indexes = [
            index
            for index, event in enumerate(timeline)
            if index > previous_index and event_matches(event, expected)
        ]
        gate.require(
            bool(indexes),
            f"run milestone missing or out of order: "
            f"{milestone.get('id') if isinstance(milestone, dict) else None}",
        )
        if indexes:
            previous_index = indexes[0]

    for assertion in contract.get("state_assertions", []):
        path = assertion.get("path") if isinstance(assertion, dict) else None
        gate.require(isinstance(path, str), "state assertion path missing")
        if not isinstance(path, str):
            continue
        try:
            actual = resolve_dotted_path(evidence, path)
        except KeyError:
            gate.require(False, f"state assertion path missing: {path}")
            continue
        gate.require(
            actual == assertion.get("equals"),
            f"state assertion failed: {path}",
        )

    evidence_types = contract.get("required_evidence_types", [])
    gate.require(
        isinstance(evidence_types, list)
        and bool(evidence_types)
        and len(evidence_types) == len(set(evidence_types))
        and all(isinstance(value, str) and value for value in evidence_types),
        "run contract evidence types are missing or duplicated",
    )

    code_requirements = contract.get("code_requirements", [])
    gate.require(
        isinstance(code_requirements, list) and bool(code_requirements),
        "run contract code requirements are missing",
    )
    for requirement in code_requirements:
        relative = requirement.get("path") if isinstance(requirement, dict) else None
        snippets = requirement.get("contains", []) if isinstance(requirement, dict) else []
        path = ROOT / relative if isinstance(relative, str) else ROOT
        gate.require(path.is_file(), f"run contract code file missing: {relative}")
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        for snippet in snippets:
            gate.require(
                isinstance(snippet, str) and snippet in source,
                f"{relative}: required code hook missing: {snippet}",
            )

    readme_tokens = contract.get("readme_required_tokens", [])
    for token in readme_tokens:
        gate.require(
            isinstance(token, str) and token in en and token in cn,
            f"declared README token missing: {token}",
        )

    generated_artifacts = contract.get("generated_artifacts", [])
    gate.require(
        isinstance(generated_artifacts, list) and bool(generated_artifacts),
        "generated-artifact declarations are missing",
    )
    with tempfile.TemporaryDirectory(prefix="lra-repo-gate-") as temporary:
        for index, artifact in enumerate(generated_artifacts):
            generator = artifact.get("generator") if isinstance(artifact, dict) else None
            source = artifact.get("input") if isinstance(artifact, dict) else None
            expected = artifact.get("output") if isinstance(artifact, dict) else None
            arguments = artifact.get("arguments", []) if isinstance(artifact, dict) else []
            arguments_valid = isinstance(arguments, list) and all(
                isinstance(value, str) and value for value in arguments
            )
            gate.require(
                all(isinstance(value, str) and value for value in (generator, source, expected)),
                f"generated artifact {index}: declaration is incomplete",
            )
            gate.require(
                arguments_valid,
                f"generated artifact {index}: arguments are invalid",
            )
            if not all(
                isinstance(value, str) and value
                for value in (generator, source, expected)
            ) or not arguments_valid:
                continue
            generator_path = ROOT / generator
            source_path = ROOT / source
            expected_path = ROOT / expected
            gate.require(
                generator_path.is_file()
                and source_path.is_file()
                and expected_path.is_file(),
                f"generated artifact {index}: source, generator, or output is missing",
            )
            if not (
                generator_path.is_file()
                and source_path.is_file()
                and expected_path.is_file()
            ):
                continue
            actual_path = Path(temporary) / f"artifact-{index}{expected_path.suffix}"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(generator_path),
                    "--input",
                    str(source_path),
                    "--output",
                    str(actual_path),
                    *arguments,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            gate.require(
                completed.returncode == 0,
                f"generated artifact {index}: generator failed",
            )
            gate.require(
                actual_path.is_file()
                and actual_path.read_bytes() == expected_path.read_bytes(),
                f"generated artifact {index}: committed output drifted",
            )

    matrix_path = contract.get("matrix")
    matrix = read_json(gate, matrix_path) if isinstance(matrix_path, str) else {}
    scenarios = matrix.get("scenarios", [])
    ids = [item.get("id") for item in scenarios if isinstance(item, dict)]
    gate.require(
        isinstance(scenarios, list)
        and bool(scenarios)
        and len(ids) == len(scenarios)
        and len(ids) == len(set(ids)),
        "scenario matrix IDs are missing or duplicated",
    )
    for scenario in scenarios:
        gate.require(isinstance(scenario, dict), "scenario entry must be an object")
        if not isinstance(scenario, dict):
            continue
        status = scenario.get("status")
        paths = scenario.get("evidence", [])
        gate.require(
            status in {"PASS", "NOT_VERIFIED"}
            and all(
                isinstance(scenario.get(field), str)
                for field in ("trigger", "expected", "actual", "runtime_protocol")
            )
            and isinstance(paths, list)
            and bool(paths),
            f"{scenario.get('id')}: scenario result is incomplete",
        )
        for relative in paths:
            path = ROOT / relative if isinstance(relative, str) else ROOT
            gate.require(path.is_file(), f"{scenario.get('id')}: evidence missing: {relative}")
            if path.is_file() and path.suffix.lower() == ".json":
                payload = read_json(gate, relative)
                if status == "PASS":
                    if "passed" in payload:
                        gate.require(
                            payload.get("passed") is True,
                            f"{scenario.get('id')}: PASS evidence is not passing",
                        )
                else:
                    if "status" in payload:
                        gate.require(
                            payload.get("status") == "NOT_VERIFIED",
                            f"{scenario.get('id')}: boundary evidence is missing",
                        )
        for correlation in scenario.get("correlations", []):
            gate.require(
                isinstance(correlation, dict),
                f"{scenario.get('id')}: correlation must be an object",
            )
            if not isinstance(correlation, dict):
                continue
            json_path = correlation.get("json_evidence")
            jsonl_path = correlation.get("jsonl_evidence")
            left_path = correlation.get("json_path")
            event_field = correlation.get("event_field")
            operator = correlation.get("operator")
            gate.require(
                all(
                    isinstance(value, str)
                    for value in (
                        json_path,
                        jsonl_path,
                        left_path,
                        event_field,
                        operator,
                    )
                ),
                f"{scenario.get('id')}: correlation fields are incomplete",
            )
            if not all(
                isinstance(value, str)
                for value in (
                    json_path,
                    jsonl_path,
                    left_path,
                    event_field,
                    operator,
                )
            ):
                continue
            left_document = read_json(gate, json_path)
            try:
                left_value = resolve_dotted_path(left_document, left_path)
            except KeyError:
                gate.require(
                    False,
                    f"{scenario.get('id')}: correlation JSON path is missing",
                )
                continue
            event_path = ROOT / jsonl_path
            events = [
                json.loads(line)
                for line in event_path.read_text(encoding="utf-8").splitlines()
            ]
            matching_event = next(
                (
                    event
                    for event in events
                    if event_matches(event, correlation.get("event_match"))
                ),
                None,
            )
            gate.require(
                isinstance(matching_event, dict)
                and event_field in matching_event,
                f"{scenario.get('id')}: correlation event is missing",
            )
            if not isinstance(matching_event, dict) or event_field not in matching_event:
                continue
            right_value = matching_event[event_field]
            if operator == "contains":
                gate.require(
                    isinstance(left_value, list) and right_value in left_value,
                    f"{scenario.get('id')}: correlated value is not contained",
                )
            elif operator == "equals":
                gate.require(
                    left_value == right_value,
                    f"{scenario.get('id')}: correlated values differ",
                )
            else:
                gate.require(
                    False,
                    f"{scenario.get('id')}: unsupported correlation operator",
                )


def validate_rule_results(gate: Gate) -> list[str]:
    contract = read_json(gate, "evidence/run-contract.json")
    relative = contract.get("rule_results")
    gate.require(isinstance(relative, str), "run contract rule-results path is missing")
    results = read_json(gate, relative) if isinstance(relative, str) else {}
    computed = evaluate_rules(ROOT)
    gate.require(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n"
        == json.dumps(computed, indent=2, ensure_ascii=False) + "\n",
        "committed rule results drifted from unconditional evaluator output",
    )
    rules = results.get("rules", [])
    for error in validate_computed_rule_document(ROOT, results):
        gate.require(False, error)
    summaries: list[str] = []
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id")
        status = rule.get("status")
        checks = rule.get("checks", [])
        evidence = rule.get("evidence", [])
        failed_checks = [
            item.get("id")
            for item in checks
            if isinstance(item, dict) and item.get("passed") is False
        ]
        gate.require(
            status == "PASS" and not failed_checks,
            f"{rule_id}: computed rule did not pass: {failed_checks}",
        )
        summaries.append(
            f"RULE {rule_id} {status} {len(evidence) if isinstance(evidence, list) else 0}"
        )
    return summaries


def validate_scenario_manifest(gate: Gate) -> None:
    manifest = read_json(gate, "evidence/scenario-manifest.json")
    scenarios = manifest.get("scenarios", [])
    ids = [item.get("id") for item in scenarios if isinstance(item, dict)]
    gate.require(
        isinstance(scenarios, list)
        and len(ids) == len(scenarios)
        and len(ids) == len(set(ids)),
        "scenario manifest IDs are missing or duplicated",
    )
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        gate.require(
            scenario.get("type")
            in {"dynamic-runtime", "test-fixture", "architecture-explainer"}
            and bool(scenario.get("real"))
            and bool(scenario.get("not_claimed")),
            f"{scenario.get('id')}: scenario truth boundary is incomplete",
        )
        evidence = scenario.get("evidence")
        gate.require(
            isinstance(evidence, str) and (ROOT / evidence).is_file(),
            f"{scenario.get('id')}: scenario evidence is missing",
        )


def validate_ui_and_run_bundles(gate: Gate) -> None:
    ui = read_json(gate, "evidence/ui-evidence.json")
    status_evidence = read_json(gate, "evidence/owned-hosted-agent-status.json")
    deployed_version = str(status_evidence.get("version", ""))
    gate.require(
        ui.get("capture_method")
        in {"user-manual-download", "agent-visible-window-capture"}
        and ui.get("raw_intake_directory") == ".repo-evidence/inbox/ui/"
        and ui.get("published_directory") == "images/product-ui/"
        and ui.get("raw_sources_committed") is False,
        "UI raw/public boundary is wrong",
    )
    assets = ui.get("assets", [])
    gate.require(isinstance(assets, list) and bool(assets), "UI assets are missing")
    for asset in assets:
        if not isinstance(asset, dict):
            gate.require(False, "UI asset must be an object")
            continue
        published = asset.get("published_path")
        path = ROOT / published if isinstance(published, str) else ROOT
        gate.require(
            path.is_file()
            and asset.get("published_sha256") == sha256_file(path)
            and re.fullmatch(r"[0-9a-f]{64}", str(asset.get("source_sha256", "")))
            is not None
            and bool(asset.get("redactions"))
            and bool(asset.get("proves"))
            and bool(asset.get("does_not_prove")),
            f"UI lineage is incomplete: {published}",
        )
        gate.require(
            any(
                f"version {deployed_version}" in str(claim).lower()
                for claim in asset.get("proves", [])
            ),
            f"UI evidence does not show current Version {deployed_version}",
        )

    run_manifests = sorted((ROOT / "evidence" / "runs").glob("*/run-manifest.json"))
    gate.require(bool(run_manifests), "at least one public run manifest is required")
    for path in run_manifests:
        relative = path.relative_to(ROOT).as_posix()
        bundle = read_json(gate, relative)
        commands = bundle.get("commands", [])
        gate.require(
            isinstance(commands, list)
            and bool(commands)
            and all(
                isinstance(item, dict)
                and item.get("exit_code") == 0
                and isinstance(item.get("command"), str)
                and isinstance(item.get("command_redacted"), bool)
                and isinstance(item.get("evidence"), str)
                and (ROOT / item["evidence"]).is_file()
                for item in commands
            ),
            f"{relative}: command evidence is incomplete",
        )
        for item in commands:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command", ""))
            if item.get("command_redacted") is True:
                gate.require(
                    bool(item.get("redactions")),
                    f"{relative}: redacted command lacks a redaction list",
                )
            if "<" in command and ">" in command:
                gate.require(
                    item.get("command_redacted") is True,
                    f"{relative}: placeholder command is not marked redacted",
                )
        for evidence in bundle.get("logs", []):
            gate.require(
                isinstance(evidence, str) and (ROOT / evidence).is_file(),
                f"{relative}: log evidence missing: {evidence}",
            )
        for field in ("status_evidence", "ui_evidence"):
            evidence = bundle.get(field)
            gate.require(
                isinstance(evidence, str) and (ROOT / evidence).is_file(),
                f"{relative}: {field} is missing",
            )
        key_code = bundle.get("key_code", [])
        gate.require(
            isinstance(key_code, list) and bool(key_code),
            f"{relative}: key-code manifest is missing",
        )
        for item in key_code:
            code_path = (
                ROOT / item.get("path", "") if isinstance(item, dict) else ROOT
            )
            gate.require(
                code_path.is_file()
                and item.get("sha256") == sha256_file(code_path),
                f"{relative}: key-code hash drifted: "
                f"{item.get('path') if isinstance(item, dict) else None}",
            )


def validate_evidence_manifest(gate: Gate) -> int:
    manifest = read_json(gate, "evidence/manifest.json")
    gate.require(
        manifest.get("algorithm") == "sha256"
        and manifest.get("normalization") == "utf-8-lf",
        "evidence manifest normalization is wrong",
    )
    entries = {
        item.get("path"): item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    expected = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "evidence").rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    gate.require(set(entries) == expected, "evidence manifest path set is incomplete")
    for relative in expected:
        path = ROOT / relative
        entry = entries.get(relative, {})
        gate.require(
            entry.get("sha256") == sha256_file(path)
            and entry.get("bytes") == normalized_size(path)
            and bool(entry.get("provenance")),
            f"evidence manifest drift: {relative}",
        )
    return len(entries)


def validate_jsonl(gate: Gate) -> int:
    count = 0
    for path in sorted((ROOT / "evidence").rglob("*.jsonl")):
        lines = path.read_text(encoding="utf-8").splitlines()
        gate.require(bool(lines), f"{path.name}: JSONL must not be empty")
        for line_number, line in enumerate(lines, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                gate.require(False, f"{path.name}:{line_number}: {error}")
                continue
            gate.require(
                isinstance(value, dict),
                f"{path.name}:{line_number}: JSON object required",
            )
            if isinstance(value, dict) and "at_utc" in value:
                try:
                    datetime.fromisoformat(str(value["at_utc"]))
                except ValueError:
                    gate.require(
                        False,
                        f"{path.name}:{line_number}: at_utc is not ISO-8601",
                    )
            if isinstance(value, dict):
                for field in (
                    "process_instance_sha256",
                    "response_id_sha256",
                ):
                    if field in value:
                        gate.require(
                            re.fullmatch(r"[0-9a-f]{64}", str(value[field]))
                            is not None,
                            f"{path.name}:{line_number}: invalid {field}",
                        )
            count += 1
    return count


def validate_code_and_tests(gate: Gate) -> int:
    python_files = [
        path
        for path in ROOT.rglob("*.py")
        if path.is_file() and is_delivery_file(path)
    ]
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            gate.require(False, f"{path.relative_to(ROOT)}: syntax error: {error}")

    requirements = (
        ROOT / "hosted-agent" / "src" / "lra-evidence-agent" / "requirements.txt"
    ).read_text(encoding="utf-8")
    gate.require(
        requirements.splitlines()
        == [
            "azure-ai-agentserver-core==2.1.0b2",
            "azure-ai-agentserver-responses==2.1.0b2",
            "azure-identity==1.25.3",
        ],
        "Python Agent package pins drifted",
    )
    for relative, expected_pins in (
        (
            "hosted-agent-steering/src/resilient-steering/requirements.txt",
            [
                "azure-ai-agentserver-core==2.1.0",
                "azure-ai-agentserver-responses==2.1.0",
                "azure-identity==1.25.3",
            ],
        ),
        (
            "hosted-agent-approval/src/resilient-approval-gate/requirements.txt",
            [
                "azure-ai-agentserver-core==2.0.0",
                "azure-ai-agentserver-invocations==1.0.0b8",
                "azure-identity==1.25.3",
            ],
        ),
    ):
        gate.require(
            (ROOT / relative).read_text(encoding="utf-8").splitlines() == expected_pins,
            f"{relative}: package pins drifted",
        )
    project = (ROOT / "dotnet-agent" / "LraEvidenceAgent.csproj").read_text(
        encoding="utf-8"
    )
    for token in (
        'Azure.AI.AgentServer.Core" Version="1.0.0-beta.28"',
        'Azure.AI.AgentServer.Responses" Version="1.0.0-beta.8"',
        'Microsoft.Extensions.Logging" Version="10.0.0"',
    ):
        gate.require(token in project, f".NET package pin missing: {token}")

    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    gate.require(not loader.errors, f"test discovery errors: {loader.errors}")
    result = unittest.TestResult()
    suite.run(result)
    gate.require(
        result.wasSuccessful(),
        f"unit tests failed: failures={len(result.failures)} errors={len(result.errors)}",
    )
    return result.testsRun


def validate_dynamic_sdk_evidence(gate: Gate) -> None:
    checks = [
        (
            [
                sys.executable,
                str(ROOT / "examples" / "resilience_sdk_usage.py"),
                "--check",
                "--format",
                "json",
            ],
            "evidence/resilience-sdk-usage.json",
            (
                "evidence_type",
                "scenario_type",
                "expected_core_version",
                "installed_core_version",
                "registered_task_type",
                "registered_task_name",
                "passed",
            ),
        ),
        (
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_public_resilience_api.py"),
                "--format",
                "json",
            ],
            "evidence/public-sdk-contract.json",
            (
                "evidence_type",
                "scenario_type",
                "expected_versions",
                "installed_versions",
                "checks",
                "summary",
                "passed",
            ),
        ),
    ]
    for command, relative, fields in checks:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        gate.require(
            completed.returncode == 0,
            f"dynamic SDK check failed: {relative}: "
            f"{completed.stderr.strip() or completed.stdout.strip()}",
        )
        if completed.returncode != 0:
            continue
        try:
            actual = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            gate.require(False, f"{relative}: live check returned invalid JSON: {error}")
            continue
        expected = read_json(gate, relative)
        for field in fields:
            gate.require(
                actual.get(field) == expected.get(field),
                f"{relative}: live field drifted: {field}",
            )


def validate_repository_surface_and_security(gate: Gate) -> None:
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and is_delivery_file(path)
    }
    gate.require(
        actual == ALLOWED_FILES,
        "repository surface differs; unexpected="
        f"{sorted(actual - ALLOWED_FILES)}, missing={sorted(ALLOWED_FILES - actual)}",
    )
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    gate.require(".repo-evidence/" in gitignore, "raw UI inbox must be ignored")
    tracked_raw = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", ".repo-evidence"],
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked_raw.returncode == 0:
        gate.require(not tracked_raw.stdout.strip(), "raw evidence is tracked")

    text_suffixes = {
        ".cs",
        ".csproj",
        ".example",
        ".json",
        ".jsonl",
        ".md",
        ".py",
        ".sh",
        ".txt",
        ".yaml",
        ".yml",
    }
    text_names = {".azdignore", ".dockerignore", ".gitignore", "Dockerfile"}
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or not is_delivery_file(path)
            or (
                path.suffix.lower() not in text_suffixes
                and path.name not in text_names
            )
        ):
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if relative != "scripts/validate_repo.py":
            for pattern in RETIRED_STAGE_PATTERNS:
                gate.require(
                    not pattern.search(text),
                    f"{relative}: retired fixed-stage narrative returned",
                )
            for literal in FORBIDDEN_LITERALS:
                if (
                    literal == PROTOCOL_PARAMETER_LITERAL
                    and relative in PROTOCOL_PARAMETER_FILES
                ):
                    continue
                gate.require(literal not in text, f"{relative}: forbidden literal {literal}")
            for label, pattern in SECRET_PATTERNS.items():
                gate.require(
                    pattern.search(text) is None,
                    f"{relative}: possible {label}",
                )


def main() -> int:
    gate = Gate()
    en, cn = validate_readmes(gate)
    validate_run_contract(gate, en, cn)
    rule_summaries = validate_rule_results(gate)
    validate_scenario_manifest(gate)
    validate_ui_and_run_bundles(gate)
    manifest_count = validate_evidence_manifest(gate)
    event_count = validate_jsonl(gate)
    test_count = validate_code_and_tests(gate)
    validate_dynamic_sdk_evidence(gate)
    validate_repository_surface_and_security(gate)

    if gate.errors:
        for error in gate.errors:
            print(f"ERROR: {error}")
        return 1
    for summary in rule_summaries:
        print(summary)
    print(
        f"PASS: bilingual parity ({len(heading_titles(en))} headings, "
        f"{len(table_shapes(en))} tables), complete run contract, "
        f"{manifest_count} hashed evidence files, {event_count} JSONL events, "
        f"{test_count} tests, public boundary clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
