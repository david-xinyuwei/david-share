#!/usr/bin/env python3
"""Deterministic quality gate for the public LRA documentation repository.

Checks structure parity between the bilingual READMEs, image references,
link targets, numeric-claim consistency, and public-boundary safety.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
import unittest
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

def parse_root() -> Path:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fail-closed bilingual, authenticity, evidence, security, "
            "and repository-surface gate."
        )
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of scripts/)",
    )
    return parser.parse_args().root.resolve()


ROOT = parse_root()
EN = ROOT / "README.md"
CN = ROOT / "README-CN.md"
START_EN = ROOT / "CUSTOMER-START-HERE.md"
START_CN = ROOT / "CUSTOMER-START-HERE-CN.md"

ALLOWED_FILES = {
    ".gitattributes",
    ".gitignore",
    "LICENSE",
    "README.md",
    "README-CN.md",
    "CUSTOMER-START-HERE.md",
    "CUSTOMER-START-HERE-CN.md",
    "THIRD-PARTY-NOTICES.md",
    "requirements-validation.txt",
    "examples/resilience_handler.py",
    "examples/resilient_responses_agent.py",
    "examples/resilience_sdk_usage.py",
    "scripts/recovery_contract_demo.py",
    "scripts/validate_observations.py",
    "scripts/validate_repo.py",
    "scripts/verify_public_resilience_api.py",
    "tests/test_recovery_contract_demo.py",
    "tests/test_validate_observations.py",
    "evidence/README.md",
    "evidence/historical-observations.json",
    "evidence/manifest.json",
    "evidence/observation-validation.json",
    "evidence/public-sdk-contract.json",
    "evidence/resilience-sdk-usage.json",
    "evidence/recovery-contract-demo.json",
    "evidence/recovery-contract-events.jsonl",
    "evidence/scenario-manifest.json",
    "images/approval-recovery.png",
    "images/approval-recovery-cn.png",
    "images/official-lease-recovery-model.png",
    "images/recovery-decision-guide.png",
    "images/recovery-decision-guide-cn.png",
}

FORBIDDEN_LITERALS = [
    "services.ai.azure.com",
    "cloudapp.azure.com",
    "/mnt/c/",
    "/mnt/g/",
    "@microsoft.com",
    "thread.v2",
    "lra-pp-",
    "caresp_",
    "mcpr_",
    "inv_",
    "agent_session_id",
    "api-version=",
]

SECRET_PATTERNS = {
    "GUID": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "Bearer-like key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Windows path": re.compile(r"\b[A-Za-z]:\\"),
}

# Numbers that must agree across both language versions.
CRITICAL_NUMBERS = [
    "599", "12,248", "1,301", "21.7", "11,584", "47", "56",
    "738", "12,073", "18", "95",
]

REQUIRED_EN_SECTIONS = [
    "## Start here",
    "## What Foundry provides, and what your application owns",
    "## What this repo validates",
    "### Recovery model at a glance",
    "### The repository is executable, not just a write-up",
    "## Measured results",
    "## Deep dive: how recovery works",
    "### Three concepts used below",
    "### Recovery can repeat work after the last checkpoint",
    "### Three integration options",
    "### Official recovery contract and local example",
    "### Four layers required for recovery",
    "## Evaluation: what was actually run",
    "### Current public-preview contract check",
    "### On a deployed agent, on an ordinary subscription",
    "## Acceptance rules",
    "### Reject gaps and duplicates",
    "### A `done` frame is not proof of success",
    "### Classify `424` separately from `403`",
    "### Prevent duplicate approvals and side effects",
    "## Quick start",
    "### Run the local recovery experiment",
    "### Tests and repository gate",
    "### Reproduce on a live Hosted Agent",
    "## Failure and recovery playbook",
    "## Design guidance",
    "## Evidence and boundaries",
    "### Before you call this production-ready",
]

REQUIRED_CN_SECTIONS = [
    "## 从这里开始",
    "## Foundry 提供什么，应用负责什么",
    "## 本仓库验证了什么",
    "### 恢复模型速览",
    "### 本仓库可直接运行，不只是说明文档",
    "## 实测结果",
    "## 深入理解：恢复如何工作",
    "### 先说明三个概念",
    "### 恢复后，最后一个进度点之后的工作可能重做",
    "### 三种接入方式",
    "### 官方恢复机制与本地示例",
    "### 启用恢复需要配置四层",
    "## 评估：到底跑了什么",
    "### 当前 public-preview 契约检查",
    "### 在普通订阅上，验证真实部署的 Agent",
    "## 验收规则",
    "### 同时拒绝缺口和重复",
    "### 一个 `done` 帧不能证明成功",
    "### 把 `424` 和 `403` 分开处理",
    "### 审批决定和外部操作都要防重复",
    "## 快速开始",
    "### 运行本地恢复实验",
    "### 测试与仓库检查",
    "### 在真实 Hosted Agent 上复现",
    "## 故障判断与恢复速查表",
    "## 设计建议",
    "## 证据与边界",
    "### 宣称“可以上生产”之前",
]

REQUIRED_START_EN_SECTIONS = [
    "## Supported path",
    "### Choose the progress strategy",
    "### Prerequisites",
    "### Configure the agent",
    "### Run and deploy",
    "### Configure external state only when needed",
    "### Configure the caller",
    "### Accept the recovery",
]

REQUIRED_START_CN_SECTIONS = [
    "## 支持的路径",
    "### 先选进度策略",
    "### 前置条件",
    "### 配置 Agent",
    "### 运行和部署",
    "### 仅在需要时配置外部状态",
    "### 配置调用方",
    "### 验收恢复",
]

REQUIRED_CONCEPTS = {
    "English": [
        "runtime instance",
        "at-least-once",
        "idempotency",
        "task record",
    ],
    "Chinese": [
        "运行实例",
        "可能再次执行",
        "幂等",
        "任务记录",
    ],
}


# Local tooling artefacts a reader may create by following the README
# (virtual environment, byte-code cache). They are never delivery surface.
LOCAL_ARTEFACT_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".demo-state",
    ".idea",
    ".vscode",
    "node_modules",
}


def is_delivery_file(path: Path) -> bool:
    """True when the path is repository surface rather than a local artefact."""
    return not LOCAL_ARTEFACT_DIRS.intersection(path.parts)


def headings(text: str) -> list[str]:
    return re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE)


def github_heading_anchors(text: str) -> set[str]:
    """Generate the GitHub-style anchors used by this repository's headings."""
    anchors: set[str] = set()
    counts: Counter[str] = Counter()
    for title in re.findall(r"^#{1,6}\s+(.+?)\s*$", text, flags=re.MULTILINE):
        title = re.sub(r"<[^>]+>", "", title)
        title = title.replace("`", "").lower().strip()
        slug = "".join(
            character
            for character in title
            if (
                character in "-_"
                or character.isspace()
                or unicodedata.category(character)[0] in {"L", "M", "N"}
            )
        )
        slug = re.sub(r"\s+", "-", slug)
        if not slug:
            continue
        duplicate_index = counts[slug]
        counts[slug] += 1
        anchors.add(slug if duplicate_index == 0 else f"{slug}-{duplicate_index}")
    return anchors


def tables(lines: list[str]) -> list[int]:
    return [line.count("|") for line in lines if re.fullmatch(r"\|[-:| ]+\|", line)]


def images(text: str) -> list[str]:
    """Local image targets from Markdown and HTML embeds; badge URLs excluded."""
    markdown = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    html = re.findall(r"<img\s[^>]*src=\"([^\"]+)\"", text)
    return [t for t in markdown + html if not t.startswith(("http://", "https://"))]


def image_alt_texts(text: str) -> list[str]:
    """Alt text for every HTML image embed, used to enforce accessibility."""
    return re.findall(r"<img\s[^>]*alt=\"([^\"]*)\"", text)


def local_links(text: str) -> list[str]:
    targets = re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text)
    return [t.split("#", 1)[0] for t in targets
            if t and not t.startswith(("#", "http://", "https://", "mailto:"))]


def markdown_targets(text: str) -> list[str]:
    """Extract Markdown destinations, including outer links around badge images."""
    return re.findall(r"\]\(([^)\s]+)\)", text)


def fenced_blocks(text: str, language: str) -> list[str]:
    return re.findall(rf"^```{language}\s*\n(.*?)^```$", text, flags=re.MULTILINE | re.DOTALL)


def sha256_file(path: Path) -> str:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt"}:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def function_has_substance(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return bool(body) and not all(
        isinstance(item, ast.Pass)
        or (
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Constant)
            and item.value.value is Ellipsis
        )
        for item in body
    )


def validator_self_scan_text(source: str, tree: ast.Module) -> str:
    """Mask only the validator's pattern definitions during self-scanning."""
    ranges: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {
                target.id for target in targets if isinstance(target, ast.Name)
            }
            if names & {"FORBIDDEN_LITERALS", "SECRET_PATTERNS"}:
                ranges.append((node.lineno, node.end_lineno or node.lineno))
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            names = {
                item.id for item in node.target.elts if isinstance(item, ast.Name)
            }
            if names == {"pattern", "label"}:
                ranges.append(
                    (node.iter.lineno, node.iter.end_lineno or node.iter.lineno)
                )

    lines = source.splitlines(keepends=True)
    for start, end in ranges:
        for index in range(start - 1, end):
            lines[index] = "\n"
    return "".join(lines)


def python_redlines(path: Path) -> list[str]:
    """Return authenticity and maintainability red lines for one Python file."""
    source = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT).as_posix()
    findings: list[str] = []
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError as error:
        return [f"{relative}: syntax error: {error}"]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not function_has_substance(node):
                findings.append(
                    f"{relative}:{node.lineno}: function {node.name!r} has no implementation"
                )
        if isinstance(node, ast.Pass):
            findings.append(f"{relative}:{node.lineno}: empty pass statement")
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and node.value.value is Ellipsis
        ):
            findings.append(f"{relative}:{node.lineno}: ellipsis placeholder")
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "NotImplementedError":
                findings.append(
                    f"{relative}:{node.lineno}: NotImplementedError shell"
                )
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "azure" and any(part.startswith("_") for part in parts):
                findings.append(
                    f"{relative}:{node.lineno}: private Azure module import {node.module}"
                )

    scan_source = (
        validator_self_scan_text(source, tree)
        if path.name == "validate_repo.py"
        else source
    )
    for pattern, label in (
        (r"\bTODO\b|\bFIXME\b", "unfinished marker"),
        (r"\b[A-Za-z]:\\", "absolute Windows path"),
        (r"/mnt/[a-z]/|/home/[^/\s]+/", "absolute user path"),
        (r"https://[^/\s]*cloudapp\.azure\.com", "hardcoded cloud endpoint"),
        (r"https://[^/\s]*services\.ai\.azure\.com", "hardcoded Foundry endpoint"),
    ):
        if re.search(pattern, scan_source, flags=re.IGNORECASE):
            findings.append(f"{relative}: {label}")

    if path.parent.name == "scripts":
        if 'if __name__ == "__main__":' not in source:
            findings.append(f"{relative}: missing executable main guard")
    return findings


def count_unittest_cases(suite: unittest.TestSuite) -> int:
    count = 0
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            count += count_unittest_cases(item)
        else:
            count += 1
    return count


def main() -> int:
    errors: list[str] = []

    if not all(path.is_file() for path in (EN, CN, START_EN, START_CN)):
        print("ERROR: both READMEs and both customer-start guides must exist")
        return 1

    en_text = EN.read_text(encoding="utf-8")
    cn_text = CN.read_text(encoding="utf-8")
    start_en_text = START_EN.read_text(encoding="utf-8")
    start_cn_text = START_CN.read_text(encoding="utf-8")
    en_lines = en_text.splitlines()
    cn_lines = cn_text.splitlines()
    start_en_lines = start_en_text.splitlines()
    start_cn_lines = start_cn_text.splitlines()

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    # Structure parity
    require(headings(en_text) == headings(cn_text), "heading level sequence differs")
    require(tables(en_lines) == tables(cn_lines), "table shapes differ")
    require(abs(len(en_lines) - len(cn_lines)) <= 15,
            f"line-count drift too large: {len(en_lines)} vs {len(cn_lines)}")
    require(
        len(headings(en_text)) <= 36,
        f"English main narrative re-fragmented into {len(headings(en_text))} headings",
    )
    require(
        len(headings(cn_text)) <= 36,
        f"Chinese main narrative re-fragmented into {len(headings(cn_text))} headings",
    )
    require(
        headings(start_en_text) == headings(start_cn_text),
        "customer-start heading level sequence differs",
    )
    require(
        tables(start_en_lines) == tables(start_cn_lines),
        "customer-start table shapes differ",
    )
    require(
        abs(len(start_en_lines) - len(start_cn_lines)) <= 12,
        (
            "customer-start line-count drift too large: "
            f"{len(start_en_lines)} vs {len(start_cn_lines)}"
        ),
    )
    require(
        len(headings(start_en_text)) <= 10
        and len(headings(start_cn_text)) <= 10,
        "customer-start guides must remain one compact runbook",
    )

    # Image parity: two project charts are localized; the official CC BY image is shared.
    en_images = images(en_text)
    cn_images = images(cn_text)
    shared_image = "images/official-lease-recovery-model.png"
    require(len(en_images) == len(cn_images) == 3,
            f"each README must embed 3 images, got {len(en_images)}/{len(cn_images)}")
    require(en_images.count(shared_image) == cn_images.count(shared_image) == 1,
            "both READMEs must embed the official lease-recovery diagram once")
    en_localized = [path for path in en_images if path != shared_image]
    cn_localized = [path for path in cn_images if path != shared_image]
    expected_cn = [path.replace(".png", "-cn.png") for path in en_localized]
    require(cn_localized == expected_cn,
            "Chinese README must reference the two localized project charts")

    # Every chart must be centred, width-capped, and carry alt text (CL-006)
    for readme, text in ((EN, en_text), (CN, cn_text)):
        centred = len(re.findall(r"<div align=\"center\"><img ", text))
        require(centred == 3, f"{readme.name}: expected 3 centred image embeds, got {centred}")
        widths = re.findall(r"<img\s[^>]*width=\"(\d+)\"", text)
        require(len(widths) == 3 and all(int(w) <= 820 for w in widths),
                f"{readme.name}: every image needs a width attribute of at most 820")
        alts = image_alt_texts(text)
        require(len(alts) == 3 and all(alt.strip() for alt in alts),
                f"{readme.name}: every image needs non-empty alt text")
        require(
            not re.search(r"^####\s+", text, flags=re.MULTILINE),
            f"{readme.name}: one-paragraph H4 fragments must stay merged",
        )
        require(
            not re.search(r"^---\s*$", text, flags=re.MULTILINE),
            f"{readme.name}: decorative horizontal separators must not return",
        )

    # Link and image targets exist
    documents = (
        (EN, en_text),
        (CN, cn_text),
        (START_EN, start_en_text),
        (START_CN, start_cn_text),
    )
    for readme, text in documents:
        for target in local_links(text) + images(text):
            if target.startswith("../"):
                continue
            require((ROOT / target).exists(), f"{readme.name}: missing target {target}")
        for target in markdown_targets(text):
            if "#" not in target or target.startswith(("http://", "https://", "mailto:")):
                continue
            path_text, fragment = target.split("#", 1)
            if not fragment or path_text.startswith("../"):
                continue
            target_path = readme if not path_text else ROOT / unquote(path_text)
            if target_path.suffix.lower() != ".md" or not target_path.is_file():
                continue
            target_anchors = github_heading_anchors(target_path.read_text(encoding="utf-8"))
            decoded_fragment = unquote(fragment).lower()
            require(
                decoded_fragment in target_anchors,
                f"{readme.name}: missing Markdown anchor {target} in {target_path.name}",
            )

    # Numeric parity
    for number in CRITICAL_NUMBERS:
        require(number in en_text, f"English README missing measured value {number}")
        require(number in cn_text, f"Chinese README missing measured value {number}")
    for number in ("3.13", "2.80", "1.27.1", "2.1.0b2", "2.0.0"):
        require(number in start_en_text,
                f"English customer-start guide missing version {number}")
        require(number in start_cn_text,
                f"Chinese customer-start guide missing version {number}")

    # Customer-first narrative and recovery semantics
    for section in REQUIRED_EN_SECTIONS:
        require(section in en_text, f"English README missing customer-first section: {section}")
    for section in REQUIRED_CN_SECTIONS:
        require(section in cn_text, f"Chinese README missing customer-first section: {section}")
    for section in REQUIRED_START_EN_SECTIONS:
        require(
            section in start_en_text,
            f"English customer-start guide missing section: {section}",
        )
    for section in REQUIRED_START_CN_SECTIONS:
        require(
            section in start_cn_text,
            f"Chinese customer-start guide missing section: {section}",
        )
    en_section_positions = [en_text.index(section) for section in REQUIRED_EN_SECTIONS if section in en_text]
    cn_section_positions = [cn_text.index(section) for section in REQUIRED_CN_SECTIONS if section in cn_text]
    start_en_positions = [
        start_en_text.index(section)
        for section in REQUIRED_START_EN_SECTIONS
        if section in start_en_text
    ]
    start_cn_positions = [
        start_cn_text.index(section)
        for section in REQUIRED_START_CN_SECTIONS
        if section in start_cn_text
    ]
    require(en_section_positions == sorted(en_section_positions),
            "English README does not follow the required reader flow")
    require(cn_section_positions == sorted(cn_section_positions),
            "Chinese README does not follow the required reader flow")
    require(
        start_en_positions == sorted(start_en_positions),
        "English customer-start guide does not follow the required flow",
    )
    require(
        start_cn_positions == sorted(start_cn_positions),
        "Chinese customer-start guide does not follow the required flow",
    )
    for readme, text in documents:
        require(not re.search(r"^#{2,4}\s+\d+(?:\.\d+)*\.", text, flags=re.MULTILINE),
                f"{readme.name}: numbered manual-style headings must not replace reader-flow headings")
        require(not re.search(r"\bPath [ABC]\b|路径 [ABC]", text),
                f"{readme.name}: opaque Path A/B/C labels must not return")
    for concept in REQUIRED_CONCEPTS["English"]:
        require(concept in en_text, f"English README missing recovery concept: {concept}")
    for concept in REQUIRED_CONCEPTS["Chinese"]:
        require(concept in cn_text, f"Chinese README missing recovery concept: {concept}")
    for snippet in (
        "not active-active redundancy",
        "task-level recovery",
        "flush()` is not a durable-write acknowledgement",
        "[Customer Start Here](CUSTOMER-START-HERE.md)",
        "| What you want to do | Go here |",
    ):
        require(snippet in en_text,
                f"English README missing main reader route: {snippet}")
    for snippet in (
        "不是让两个 Agent 同时执行同一任务的 active-active 双活",
        "任务级恢复",
        "不等于“持久化已经确认成功”",
        "[客户快速入口](CUSTOMER-START-HERE-CN.md)",
        "| 你想做什么 | 去哪里 |",
    ):
        require(snippet in cn_text,
                f"Chinese README missing main reader route: {snippet}")
    for snippet in (
        "| Strategy | External progress store? | Use when |",
        "pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2",
        "ResponsesServerOptions(resilient_background=True)",
        "stream.checkpoint()",
        "context.persisted_response",
        "Foundry Project Manager",
        "azd provision",
        "Storage Blob Data Contributor",
        "azd env set CHECKPOINT_ENDPOINT",
        "environmentVariables",
        "DefaultAzureCredential",
        "azd ai agent show",
        "remote create and local ID persistence are not atomic",
    ):
        require(snippet in start_en_text,
                f"English customer-start guide missing adoption guidance: {snippet}")
    for snippet in (
        "| 策略 | 要另配进度存储吗 | 适用场景 |",
        "pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2",
        "ResponsesServerOptions(resilient_background=True)",
        "stream.checkpoint()",
        "context.persisted_response",
        "Foundry Project Manager",
        "azd provision",
        "Storage Blob Data Contributor",
        "azd env set CHECKPOINT_ENDPOINT",
        "environmentVariables",
        "DefaultAzureCredential",
        "azd ai agent show",
        "远端 create 与本地保存 ID 不是一个原子事务",
    ):
        require(snippet in start_cn_text,
                f"Chinese customer-start guide missing adoption guidance: {snippet}")
    for snippet in (
        "Microsoft private-preview `resilient-research` sample",
        "generic deep-research briefing task",
        "phases 1-4",
        "phases 16-18",
        "caller supplied a topic",
        "18 is a property of the July sample run, not a current product requirement",
        "not the only public resilience example",
    ):
        require(snippet in en_text,
                f"English README missing research workload context: {snippet}")
    for snippet in (
        "微软在 **2026 年 7 月 private preview 期间提供的 `resilient-research` 样例",
        "通用的深度研究简报任务",
        "第 1-4 阶段",
        "第 16-18 阶段",
        "调用方提供一个研究主题",
        "18 是 7 月那次样例运行的阶段数，不是当前产品要求",
        "不是 public preview 唯一的韧性样例",
    ):
        require(snippet in cn_text,
                f"Chinese README missing research workload context: {snippet}")

    # The Hosted Agent recovery path must keep official contract and local
    # reference-implementation choices separate.
    required_recovery_pairs = (
        ("later-process reclaim", "另一个进程可以接管"),
        ("local design choices", "示例自己的设计"),
        ("Hosted Agent version", "Hosted Agent version"),
        ("Responses protocol", "Responses protocol"),
        ("framework checkpoint", "framework checkpoint"),
        ("store=True", "store=True"),
        ("background=True", "background=True"),
        ("recovery_contract_demo.py", "recovery_contract_demo.py"),
        ("validate_observations.py", "validate_observations.py"),
        ("not claims about Foundry internals", "不代表 Foundry 内部实现"),
    )
    for en_snippet, cn_snippet in required_recovery_pairs:
        require(
            en_snippet in en_text,
            f"English README missing recovery boundary: {en_snippet}",
        )
        require(
            cn_snippet in cn_text,
            f"Chinese README missing recovery boundary: {cn_snippet}",
        )
    require("set_resilient_tasks_enabled(True)" in en_text,
            "English README missing current resilient-task enablement")
    require("set_resilient_tasks_enabled(True)" in cn_text,
            "Chinese README missing current resilient-task enablement")
    for snippet in (
        "azure-ai-agentserver-core` 2.0.0",
        "TaskContext.task_id",
        "TaskContext.input_id",
        "TaskContext.entry_mode",
        "recovery_count",
        "retry_attempt",
        "TaskContext.metadata",
        "18 of 18",
    ):
        require(snippet in en_text, f"English README missing public-preview API evidence: {snippet}")
    for snippet in (
        "azure-ai-agentserver-core` 2.0.0",
        "TaskContext.task_id",
        "TaskContext.input_id",
        "TaskContext.entry_mode",
        "recovery_count",
        "retry_attempt",
        "TaskContext.metadata",
        "18 / 18 项通过",
    ):
        require(snippet in cn_text, f"Chinese README missing public-preview API evidence: {snippet}")
    require("[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py)" in en_text,
            "English README must link the executable recovery reference")
    require("[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py)" in cn_text,
            "Chinese README must link the executable recovery reference")
    require("[`validate_observations.py`](scripts/validate_observations.py)" in en_text,
            "English README must link the executable observation validator")
    require("[`validate_observations.py`](scripts/validate_observations.py)" in cn_text,
            "Chinese README must link the executable observation validator")
    require("[`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py)" in en_text,
            "English README must link the direct public SDK usage example")
    require("[`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py)" in cn_text,
            "Chinese README must link the direct public SDK usage example")
    require("[`examples/resilience_handler.py`](examples/resilience_handler.py)" in en_text,
            "English README must link the actual public SDK handler")
    require("[`examples/resilience_handler.py`](examples/resilience_handler.py)" in cn_text,
            "Chinese README must link the actual public SDK handler")
    require(
        "[`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py)"
        in en_text,
        "English README must link the complete Responses recovery handler",
    )
    require(
        "[`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py)"
        in cn_text,
        "Chinese README must link the complete Responses recovery handler",
    )
    require("**not** a security sandbox or RBAC boundary" in en_text,
            "English README must scope the facade boundary")
    require("**不是**权限隔离机制（安全沙箱或 RBAC 边界）" in cn_text,
            "Chinese README must scope the facade boundary")
    require(
        "Remote create and local persistence of the response ID are not atomic" in en_text
        and "unknown result instead of creating again" in en_text
        and "deduplication or reconciliation" in en_text,
        "English README must disclose and scope the create/persist crash window",
    )
    require(
        "远端 create 与本地保存 ID 不是一个原子事务" in cn_text
        and "结果未知时不要自动重建任务" in cn_text
        and "去重能力或人工对账" in cn_text,
        "Chinese README must disclose and scope the create/persist crash window",
    )
    handler_example = ROOT / "examples" / "resilient_responses_agent.py"
    handler_text = (
        handler_example.read_text(encoding="utf-8")
        if handler_example.is_file()
        else ""
    )
    snippet_match = re.search(
        r"# README_RESPONSES_SNIPPET_START\n(.*?)# README_RESPONSES_SNIPPET_END",
        handler_text,
        flags=re.DOTALL,
    )
    expected_python_snippet = (
        snippet_match.group(1).strip() if snippet_match else ""
    )
    require(bool(expected_python_snippet),
            "Responses handler README snippet markers are missing")

    for readme, text in ((EN, en_text), (CN, cn_text)):
        python_blocks = fenced_blocks(text, "python")
        require(
            not python_blocks,
            f"{readme.name}: full handler code belongs in examples/, not the main narrative",
        )
        require(not fenced_blocks(text, "yaml"),
                f"{readme.name}: incomplete YAML fragments are forbidden")
        console_blocks = fenced_blocks(text, "console")
        require(len(console_blocks) == 1,
                f"{readme.name}: Quick Start must contain one cross-shell experiment block")
        if len(console_blocks) == 1:
            experiment_block = console_blocks[0]
            for command in (
                "git clone --depth 1 --filter=blob:none --sparse",
                "git -C lra-demo sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience",
                "python scripts/recovery_contract_demo.py demo",
                "--summary-file .demo-state/summary.json",
                "--events-file .demo-state/events.jsonl",
            ):
                require(command in experiment_block,
                        f"{readme.name}: local recovery experiment missing command {command}")
        powershell_blocks = fenced_blocks(text, "powershell")
        require(len(powershell_blocks) == 1,
                f"{readme.name}: Quick Start must contain one PowerShell validation block")
        if len(powershell_blocks) == 1:
            powershell_block = powershell_blocks[0]
            for command in (
                "python -m venv .venv",
                "Resolve-Path .\\.venv\\Scripts\\python.exe",
                "& $python -m pip install --no-input -r requirements-validation.txt",
                "& $python examples\\resilience_sdk_usage.py --check",
                "& $python scripts\\verify_public_resilience_api.py --quiet",
                "& $python scripts\\validate_observations.py self-test",
                "& $python -m unittest discover -s tests -v",
                "& $python scripts\\validate_repo.py",
            ):
                require(command in powershell_block,
                        f"{readme.name}: PowerShell validation missing command {command}")
        bash_blocks = fenced_blocks(text, "bash")
        require(len(bash_blocks) == 1,
                f"{readme.name}: Quick Start must contain one POSIX validation block")
        if len(bash_blocks) == 1:
            validation_block = bash_blocks[0]
            for command in (
                "python3 -m venv .venv",
                'PYTHON=.venv/bin/python',
                '"$PYTHON" -m pip install --no-input -r requirements-validation.txt',
                '"$PYTHON" examples/resilience_sdk_usage.py --check',
                '"$PYTHON" scripts/verify_public_resilience_api.py --quiet',
                '"$PYTHON" scripts/validate_observations.py self-test',
                '"$PYTHON" -m unittest discover -s tests -v',
                '"$PYTHON" scripts/validate_repo.py',
            ):
                require(command in validation_block,
                        f"{readme.name}: POSIX validation missing command {command}")
        require(
            (
                text.count("Done-when is") >= 2
                if readme == EN
                else text.count("**完成标准：**") >= 2
            )
            and "worker_a_exit_code: 9" in text
            and "PASS: imported azure.ai.agentserver.core.tasks" in text
            and "18/18 checks passed" in text,
            f"{readme.name}: reproduction done-when or expected outputs missing",
        )
        require(
            "b9b2cdd67efee6287e4b263f83ed45f18fe892be" in text
            and "2.1.0b2" in text
            and (
                ("do **not** replace" in text)
                if readme == EN
                else ("**不要**改成本仓库历史离线检查使用的 2.0.0" in text)
            ),
            f"{readme.name}: current live-sample version boundary missing",
        )
        for retired in ("pseudocode", "伪代码", "interface sketches", "接口示意"):
            require(retired not in text,
                    f"{readme.name}: retired non-executable content returned: {retired}")
    for guide, text in ((START_EN, start_en_text), (START_CN, start_cn_text)):
        require(
            not fenced_blocks(text, "python"),
            f"{guide.name}: link the executable handler instead of duplicating it",
        )
        require(
            not fenced_blocks(text, "yaml"),
            f"{guide.name}: use the pinned complete azure.yaml instead of fragments",
        )

    # Confirmation identifiers must appear in both
    for token in ("TRIP-182336", "TRIP-749637", "424", "403"):
        require(token in en_text and token in cn_text, f"both READMEs must mention {token}")

    # Boundary statements
    require("private preview" in en_text.lower(), "English boundary statement missing")
    require("private preview" in cn_text.lower(), "Chinese boundary statement missing")
    require("no Microsoft SDK source" in en_text, "English SDK-source boundary missing")
    require("不提供 Microsoft SDK 源码" in cn_text, "Chinese SDK-source boundary missing")
    require("public preview" in en_text.lower(), "English current preview status missing")
    require("public preview" in cn_text.lower(), "Chinese current preview status missing")

    # High-risk claims must retain their scope. Keep these short and semantic so
    # the gate protects boundaries without forcing one editorial sentence.
    required_rigor_pairs = (
        ("Every interruption was deliberate, not an outage",
         "所有中断都是主动注入，不是线上事故"),
        ("not live Hosted Agent evidence", "不是线上 Hosted Agent 证据"),
        ("not proof of universal availability", "不代表所有订阅或区域"),
        ("diagnostic starting point, not a universal mapping from symptom to cause",
         "只是诊断起点，不表示“某个现象必然对应某个原因”"),
        ("do not establish a general exactly-once guarantee",
         "不能证明通用的 exactly-once 保证"),
        ("not product guarantees",
         "不是产品保证"),
        ("not a guarantee for every Responses workload",
         "不代表所有 Responses 任务都有相同行为"),
    )
    for en_boundary, cn_boundary in required_rigor_pairs:
        require(en_boundary in en_text,
                f"English rigor boundary missing: {en_boundary}")
        require(cn_boundary in cn_text,
                f"Chinese rigor boundary missing: {cn_boundary}")

    legacy_overclaims = (
        "Any platform that keeps a workload running for twenty minutes eventually",
        "The barrier that blocked this work in July is gone",
        "A subscription that was never enabled works too",
        "decision sent *after* the replacement was accepted",
        "exactly-once decision handling",
        "By any workload measure that run recovered perfectly",
        "What Happens After the Process Dies",
        "任何让工作负载连续跑二十分钟的平台，早晚都会遇到",
        "7 月挡住这项工作的那道门槛已经没有了",
        "一个从未被开通过的订阅同样可用",
        "进程死了之后，任务怎么活下来",
        "按 workload 的标准衡量，这次运行恢复得完美无缺",
        "证明的是持久化 Graph 状态和“决定只生效一次”",
    )
    for phrase in legacy_overclaims:
        require(phrase not in en_text and phrase not in cn_text,
                f"retired overclaim returned: {phrase}")

    # Badges carry the status on the first screen, so they are delivery surface
    # too. Compare the shields.io URLs, which encode label, message and colour;
    # only the anchor target may differ, because CN section anchors are Chinese.
    en_badges = re.findall(r"!\[[^\]]*\]\((https://img\.shields\.io/[^)]+)\)", en_text)
    cn_badges = re.findall(r"!\[[^\]]*\]\((https://img\.shields\.io/[^)]+)\)", cn_text)
    require(en_badges == cn_badges,
            f"badge rows must match: EN {en_badges} vs CN {cn_badges}")
    require(4 <= len(en_badges) <= 5,
            f"expected 4-5 badges, found {len(en_badges)}")
    require(bool(en_badges) and "public_preview" in en_badges[0],
            "the first badge must state the capability is in public preview")

    require("CC BY 4.0" in en_text and "THIRD-PARTY-NOTICES.md" in en_text,
            "English official-image attribution or notice link missing")
    require("CC BY 4.0" in cn_text and "THIRD-PARTY-NOTICES.md" in cn_text,
            "Chinese official-image attribution or notice link missing")
    require("resilience-architecture" not in en_text and "resilience-architecture" not in cn_text,
            "retired project-authored architecture diagram must not return")
    require(
        "The figure below is the **official Microsoft diagram**, reproduced unmodified"
        in en_text,
        "English README must identify the official diagram",
    )
    require(
        "下图是**微软官方原图**" in cn_text and "未经修改" in cn_text,
        "Chinese README must identify the official diagram",
    )

    notice = ROOT / "THIRD-PARTY-NOTICES.md"
    if notice.is_file():
        notice_text = notice.read_text(encoding="utf-8")
        official_image_sha256 = (
            "a6e6d25c23bbcd745cae0b7e0b17ed0494528fcf01962962cd61d2526244bef2"
        )
        require("320136d7185d71fd122d5c5e75bece175d4d3e65" in notice_text,
                "third-party notice must pin the immutable Microsoft source")
        require(official_image_sha256 in notice_text,
                "third-party notice must record the image SHA-256")
        official_image = ROOT / "images" / "official-lease-recovery-model.png"
        if official_image.is_file():
            require(
                sha256_file(official_image) == official_image_sha256,
                "official Microsoft diagram does not match the pinned SHA-256",
            )

    validation_script = ROOT / "scripts" / "verify_public_resilience_api.py"
    if validation_script.is_file():
        script_text = validation_script.read_text(encoding="utf-8")
        for snippet in ("EntryMode", "TaskContext", "TaskMetadata", "RetryPolicy",
                        "ExitForRecoverySignal", "ResponseExitForRecovery"):
            require(snippet in script_text,
                    f"public SDK validation script missing contract check: {snippet}")

    usage_example = ROOT / "examples" / "resilience_sdk_usage.py"
    if usage_example.is_file():
        example_text = usage_example.read_text(encoding="utf-8")
        for snippet in (
            "from resilience_handler import resilience_api_usage",
            '"evidence_type": "public-resilience-sdk-usage"',
            '"@task handler registered"',
        ):
            require(snippet in example_text,
                    f"public SDK check wrapper missing runtime check: {snippet}")
    task_handler_example = ROOT / "examples" / "resilience_handler.py"
    task_handler_text = (
        task_handler_example.read_text(encoding="utf-8")
        if task_handler_example.is_file()
        else ""
    )
    if task_handler_example.is_file():
        for snippet in (
            "from azure.ai.agentserver.core.tasks import RetryPolicy, TaskContext, task",
            '@task(name="resilience-api-usage", timeout=None, retry=RetryPolicy())',
            "ctx.metadata.get(\"completed_phases\", 0)",
            "return await ctx.exit_for_recovery()",
            "ctx.recovery_count",
            "ctx.retry_attempt",
        ):
            require(snippet in task_handler_text,
                    f"public SDK handler missing runtime code: {snippet}")
    if handler_example.is_file():
        for snippet in (
            "ResponsesServerOptions(resilient_background=True)",
            "set_resilient_tasks_enabled(True)",
            "context.persisted_response",
            "context.is_recovery",
            "yield stream.checkpoint()",
            "await context.exit_for_recovery()",
            'STAGES = ("analyze", "generate", "refine")',
        ):
            require(
                snippet in handler_text,
                f"Responses recovery handler missing runtime code: {snippet}",
            )

    def read_json_evidence(relative: str) -> dict:
        path = ROOT / relative
        require(path.is_file(), f"missing evidence file: {relative}")
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            require(False, f"{relative}: invalid JSON: {error}")
            return {}
        require(isinstance(value, dict), f"{relative}: root must be an object")
        return value if isinstance(value, dict) else {}

    # Scenario Manifest / authenticity boundary.
    scenario_manifest = read_json_evidence("evidence/scenario-manifest.json")
    scenarios = scenario_manifest.get("scenarios", [])
    require(isinstance(scenarios, list),
            "scenario manifest must contain a scenarios array")
    scenario_map = {
        item.get("id"): item
        for item in scenarios
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    expected_scenarios = {
        "public-sdk-contract": "dynamic-runtime",
        "public-resilience-sdk-usage": "dynamic-runtime",
        "local-recovery-contract": "test-fixture",
        "observation-validator": "dynamic-runtime",
        "historical-live-observations": "architecture-explainer",
    }
    require(set(scenario_map) == set(expected_scenarios),
            f"scenario manifest ids differ: {sorted(scenario_map)}")
    for scenario_id, expected_type in expected_scenarios.items():
        item = scenario_map.get(scenario_id, {})
        require(item.get("type") == expected_type,
                f"{scenario_id}: expected scenario type {expected_type}")
        require(bool(item.get("real")),
                f"{scenario_id}: real behavior must be declared")
        require(bool(item.get("not_claimed")),
                f"{scenario_id}: non-claims must be declared")

    # Data Rich: each public claim surface has machine-readable evidence.
    sdk_evidence = read_json_evidence("evidence/public-sdk-contract.json")
    require(sdk_evidence.get("scenario_type") == "dynamic-runtime",
            "SDK evidence must be dynamic-runtime")
    require(sdk_evidence.get("passed") is True,
            "SDK contract evidence must pass")
    expected_package_versions = {
        "azure-ai-agentserver-core": "2.0.0",
        "azure-ai-agentserver-invocations": "1.0.0",
        "azure-ai-agentserver-responses": "2.0.0",
    }
    require(
        sdk_evidence.get("expected_versions") == expected_package_versions
        and sdk_evidence.get("installed_versions") == expected_package_versions,
        "SDK evidence package versions must match the pinned runtime",
    )
    expected_sdk_checks = {
        "azure-ai-agentserver-core version",
        "azure-ai-agentserver-invocations version",
        "azure-ai-agentserver-responses version",
        "EntryMode exposes recovered re-entry",
        "entry_mode and retry_attempt are separate fields",
        "recovery_count is separate from retry_attempt",
        "task_id (work identity) is exposed",
        "input_id (input identity) is exposed",
        "metadata exposes checkpoint operations",
        "cooperative shutdown is exposed",
        "exit-for-recovery is exposed",
        "steering is exposed",
        "RetryPolicy is public",
        "resilient-task enablement is queryable",
        "Responses recovery signals are public",
        "@task accepts name, timeout, and retry",
        "handler first argument must be named ctx",
        "handler requires TaskContext[Input]",
    }
    sdk_checks = sdk_evidence.get("checks", [])
    sdk_check_map = {
        item.get("name"): item
        for item in sdk_checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    require(
        len(sdk_checks) == 18
        and set(sdk_check_map) == expected_sdk_checks
        and all(item.get("passed") is True for item in sdk_check_map.values()),
        "SDK evidence must contain the exact 18 passing checks",
    )
    sdk_summary = sdk_evidence.get("summary", {})
    require(
        sdk_summary.get("passed") == 18
        and sdk_summary.get("failed") == 0
        and sdk_summary.get("total") == 18,
        "SDK evidence must contain 18/18 passing checks",
    )

    usage_evidence = read_json_evidence(
        "evidence/resilience-sdk-usage.json"
    )
    expected_usage_checks = {
        "azure-ai-agentserver-core version",
        "@task handler registered",
    }
    require(
        usage_evidence.get("scenario_type") == "dynamic-runtime"
        and usage_evidence.get("evidence_type")
        == "public-resilience-sdk-usage"
        and usage_evidence.get("passed") is True
        and usage_evidence.get("expected_core_version") == "2.0.0"
        and usage_evidence.get("installed_core_version") == "2.0.0"
        and usage_evidence.get("registered_task_type") == "Task"
        and usage_evidence.get("registered_task_name") == "resilience-api-usage"
        and {
            item.get("name")
            for item in usage_evidence.get("checks", [])
            if isinstance(item, dict) and item.get("passed") is True
        }
        == expected_usage_checks,
        "SDK usage evidence must prove the actual example import and registration",
    )

    if usage_example.is_file():
        completed = subprocess.run(
            [
                sys.executable,
                str(usage_example),
                "--check",
                "--format",
                "json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        require(
            completed.returncode == 0,
            "SDK usage example --check failed: "
            + (completed.stderr.strip() or completed.stdout.strip()),
        )
        try:
            live_usage = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            require(False, f"SDK usage example returned invalid JSON: {error}")
            live_usage = {}
        for field in (
            "evidence_type",
            "scenario_type",
            "expected_core_version",
            "installed_core_version",
            "registered_task_type",
            "registered_task_name",
            "passed",
        ):
            require(
                live_usage.get(field) == usage_evidence.get(field),
                f"SDK usage live check drifted from evidence field {field}",
            )
        require(
            {
                item.get("name"): item.get("passed")
                for item in live_usage.get("checks", [])
                if isinstance(item, dict)
            }
            == {
                item.get("name"): item.get("passed")
                for item in usage_evidence.get("checks", [])
                if isinstance(item, dict)
            },
            "SDK usage live checks drifted from committed evidence",
        )

    recovery_evidence = read_json_evidence("evidence/recovery-contract-demo.json")
    require(recovery_evidence.get("scenario_type") == "test-fixture",
            "recovery demo must be labelled test-fixture")
    require(recovery_evidence.get("passed") is True,
            "recovery contract demo evidence must pass")
    require(recovery_evidence.get("entry_modes") == ["fresh", "recovered"],
            "recovery demo must record fresh then recovered entry")
    require(recovery_evidence.get("worker_a_exit_code") == 9,
            "recovery demo must record the injected hard exit")
    require(recovery_evidence.get("worker_b_exit_code") == 0,
            "recovery demo must record successful worker B completion")
    require(recovery_evidence.get("lease_generation") == 2,
            "recovery demo must advance the lease generation")
    require(recovery_evidence.get("checkpoint") == 5,
            "recovery demo must finish at checkpoint 5")
    require(recovery_evidence.get("committed_phases") == [1, 2, 3, 4, 5],
            "recovery demo must commit the complete phase domain")
    require(
        recovery_evidence.get("phase_workers")
        == {
            "1": "worker-a",
            "2": "worker-b",
            "3": "worker-b",
            "4": "worker-b",
            "5": "worker-b",
        },
        "recovery demo phase ownership must match the injected-loss boundary",
    )
    expected_recovery_checks = {
        "checkpoint_complete",
        "fresh_then_recovered",
        "generation_advanced",
        "no_duplicate_phase_commit",
        "original_worker_stopped_at_injected_phase",
        "payload_affected_every_result",
        "phase_domain_complete",
        "same_work_recovered",
        "worker_a_hard_exit_observed",
        "worker_b_completed",
    }
    recovery_checks = recovery_evidence.get("checks")
    require(
        isinstance(recovery_checks, dict)
        and set(recovery_checks) == expected_recovery_checks
        and all(value is True for value in recovery_checks.values()),
        "recovery evidence must contain the exact ten passing checks",
    )
    phase_result_sha256s = recovery_evidence.get("phase_result_sha256s")
    require(
        isinstance(phase_result_sha256s, list)
        and len(phase_result_sha256s) == 5
        and all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in phase_result_sha256s
        ),
        "recovery evidence must contain five output hashes",
    )

    observation_evidence = read_json_evidence(
        "evidence/observation-validation.json"
    )
    require(observation_evidence.get("passed") is True,
            "observation validator evidence must pass")
    require(
        observation_evidence.get("checks")
        == {
            "materially_different_inputs_change_hash": True,
            "observation_cases_match": True,
            "recovery_actions_match": True,
        },
        "observation evidence must contain the exact three passing checks",
    )
    observation_cases = observation_evidence.get("observation_cases", [])
    require(
        {item.get("name") for item in observation_cases if isinstance(item, dict)}
        == {"clean", "sequence_gap", "duplicate_output", "bare_done"}
        and all(item.get("matched") is True for item in observation_cases),
        "observation evidence must contain the exact matched fixture set",
    )
    require(
        any(item.get("actual") is True for item in observation_cases)
        and any(item.get("actual") is False for item in observation_cases),
        "observation evidence must include positive and negative paths",
    )
    action_cases = {
        item.get("name"): item.get("actual")
        for item in observation_evidence.get("recovery_action_cases", [])
        if isinstance(item, dict)
    }
    require(action_cases.get("unclassified_424") == "fail_closed",
            "unclassified 424 must fail closed")
    require(action_cases.get("unclassified_403") == "fail_closed",
            "unclassified 403 must fail closed")
    require(
        set(action_cases)
        == {
            "confirmed_424",
            "unclassified_424",
            "expired_observer_403",
            "unclassified_403",
            "deadline",
        },
        "recovery action evidence must contain the exact five cases",
    )

    historical = read_json_evidence("evidence/historical-observations.json")
    campaigns = {
        item.get("id"): item
        for item in historical.get("campaigns", [])
        if isinstance(item, dict)
    }
    july = campaigns.get("july-private-preview", {})
    august = campaigns.get("august-public-preview-retest", {})
    require(
        july.get("accepted_main_scenarios") == 8
        and july.get("accepted_runs_per_scenario") == 1
        and july.get("benchmark") is False
        and len(july.get("observations", [])) == 8,
        "July evidence must retain N=1 across eight main scenarios",
    )
    research_workload = july.get("research_workload", {})
    phase_groups = research_workload.get("phase_groups", [])
    require(
        research_workload.get("type") == "generic multi-phase deep-research briefing"
        and research_workload.get("source")
        == "Microsoft July 2026 private-preview resilient-research sample"
        and "caller-supplied topic" in research_workload.get("input", "")
        and "18-phase plan is not a current product requirement"
        in research_workload.get("current_public_relation", "")
        and "not the only public resilience example"
        in research_workload.get("current_public_relation", "")
        and [item.get("phases") for item in phase_groups]
        == ["1-4", "5-9", "10-15", "16-18"]
        and research_workload.get("execution")
        == (
            "one streaming model call per phase; completed-phase count "
            "checkpointed after each phase"
        ),
        "July evidence must retain the public-safe 18-phase workload structure",
    )
    require(
        august.get("benchmark") is False
        and len(august.get("observations", [])) == 8,
        "August evidence must retain eight scoped observations",
    )
    historical_text = json.dumps(historical, ensure_ascii=False)
    for value in CRITICAL_NUMBERS:
        require(value.replace(",", "") in historical_text,
                f"historical evidence missing measured value {value}")
    require(
        "not tenant-, region-, or subscription-wide availability evidence"
        in historical_text,
        "cross-subscription evidence must retain its scope limit",
    )

    # Log Rich: ordered, structured runtime events with correlation fields.
    events_path = ROOT / "evidence" / "recovery-contract-events.jsonl"
    require(events_path.is_file(), "structured recovery event log missing")
    events: list[dict] = []
    if events_path.is_file():
        for line_number, line in enumerate(
            events_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                require(False, f"event log line {line_number}: {error}")
                continue
            require(isinstance(event, dict),
                    f"event log line {line_number}: object required")
            if isinstance(event, dict):
                events.append(event)
    require(
        [item.get("event_index") for item in events]
        == list(range(1, len(events) + 1)),
        "event log indexes must be contiguous",
    )
    required_event_fields = {
        "event_index", "schema_version", "timestamp_utc", "event", "work_id",
        "worker_id", "process_id", "lease_generation", "entry_mode", "phase",
        "checkpoint", "details",
    }
    for index, event in enumerate(events, start=1):
        require(required_event_fields <= set(event),
                f"event {index}: missing correlation fields")
    require(
        [item.get("entry_mode") for item in events
         if item.get("event") == "handler_entry"] == ["fresh", "recovered"],
        "event log must show fresh and recovered handler entries",
    )
    require(
        bool(events)
        and any(item.get("event") == "process_loss_injected" for item in events)
        and events[-1].get("event") == "work_completed",
        "event log must include injected loss and completion",
    )
    require(
        len({item.get("process_id") for item in events
             if item.get("worker_id") in {"worker-a", "worker-b"}}) == 2,
        "event log must show two distinct worker processes",
    )
    phase_events = [
        (
            item.get("phase"),
            item.get("worker_id"),
            item.get("lease_generation"),
            item.get("checkpoint"),
        )
        for item in events
        if item.get("event") == "phase_committed"
    ]
    require(
        phase_events
        == [
            (1, "worker-a", 1, 1),
            (2, "worker-b", 2, 2),
            (3, "worker-b", 2, 3),
            (4, "worker-b", 2, 4),
            (5, "worker-b", 2, 5),
        ],
        "event log phase ownership must agree with the recovery summary",
    )
    loss_events = [
        item for item in events if item.get("event") == "process_loss_injected"
    ]
    require(
        len(loss_events) == 1
        and loss_events[0].get("details", {}).get("exit_code") == 9
        and loss_events[0].get("phase") == 1,
        "event log must record one exit-9 loss after phase 1",
    )

    # Evidence integrity manifest.
    evidence_manifest = read_json_evidence("evidence/manifest.json")
    require(evidence_manifest.get("algorithm") == "sha256",
            "evidence manifest must use SHA-256")
    require(evidence_manifest.get("normalization") == "utf-8-lf",
            "evidence manifest must declare UTF-8/LF normalization")
    manifest_entries = evidence_manifest.get("files", [])
    manifest_map = {
        item.get("path"): item
        for item in manifest_entries
        if isinstance(item, dict)
    }
    expected_evidence_paths = {
        "evidence/README.md",
        "evidence/historical-observations.json",
        "evidence/observation-validation.json",
        "evidence/public-sdk-contract.json",
        "evidence/resilience-sdk-usage.json",
        "evidence/recovery-contract-demo.json",
        "evidence/recovery-contract-events.jsonl",
        "evidence/scenario-manifest.json",
    }
    require(set(manifest_map) == expected_evidence_paths,
            "evidence manifest path set is incomplete")
    for relative in expected_evidence_paths:
        path = ROOT / relative
        entry = manifest_map.get(relative, {})
        if path.is_file():
            require(entry.get("sha256") == sha256_file(path),
                    f"evidence hash mismatch: {relative}")
        require(bool(entry.get("provenance")),
                f"evidence provenance missing: {relative}")

    # Code Rich / Test Rich / four user red lines.
    python_files = (
        sorted((ROOT / "scripts").glob("*.py"))
        + sorted((ROOT / "examples").glob("*.py"))
        + sorted((ROOT / "tests").glob("test_*.py"))
    )
    require(len(python_files) == 9,
            f"expected 4 scripts, 3 examples, and 2 test files, found {len(python_files)}")
    for path in python_files:
        for finding in python_redlines(path):
            require(False, finding)
    static_test_count = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        static_test_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            and function_has_substance(node)
            for node in ast.walk(tree)
        )
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    discovered_test_count = count_unittest_cases(suite)
    require(not loader.errors,
            f"unittest discovery errors: {'; '.join(loader.errors)}")
    require(
        static_test_count == discovered_test_count,
        "every substantive test_* function must be discoverable by unittest",
    )
    test_count = discovered_test_count
    require(test_count >= 10,
            f"expected at least 10 explicit tests, found {test_count}")
    requirements = {
        line.strip()
        for line in (ROOT / "requirements-validation.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    }
    require(
        requirements
        == {
            "azure-ai-agentserver-core==2.0.0",
            "azure-ai-agentserver-invocations==1.0.0",
            "azure-ai-agentserver-responses==2.0.0",
        },
        "requirements-validation.txt must exactly pin the imported Azure packages",
    )

    # Repository surface
    tracked = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and is_delivery_file(path)
    }
    unexpected = sorted(tracked - ALLOWED_FILES)
    require(not unexpected, f"unexpected files present: {', '.join(unexpected)}")
    missing = sorted(ALLOWED_FILES - tracked)
    require(not missing, f"required files missing: {', '.join(missing)}")

    # Public boundary scan across every text delivery surface.
    text_suffixes = {".md", ".py", ".json", ".jsonl", ".txt", ".yaml", ".yml"}
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or not is_delivery_file(path)
            or (path.suffix.lower() not in text_suffixes and path.name != ".gitignore")
        ):
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        if relative == "scripts/validate_repo.py":
            text = validator_self_scan_text(text, ast.parse(text))
        for literal in FORBIDDEN_LITERALS:
            require(literal not in text, f"{relative}: forbidden literal {literal}")
        for name, pattern in SECRET_PATTERNS.items():
            require(not pattern.search(text), f"{relative}: matched {name}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        f"PASS: bilingual parity ({len(headings(en_text))} main headings, "
        f"{len(headings(start_en_text))} customer-start headings, "
        f"{len(tables(en_lines))} main tables, "
        f"{len(tables(start_en_lines))} customer-start tables), "
        f"Data/Log Rich ({len(manifest_map)} hashed evidence files, "
        f"{len(events)} structured events), "
        f"Code/Test Rich ({len(python_files)} Python files, {test_count} tests), "
        f"{len(CRITICAL_NUMBERS)} measured values aligned, public boundary clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
