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
    "evidence/paired-prefix-follow-up.json",
    "evidence/validation-history.json",
    "evidence/verified-run-summary.json",
    "images/customer-architecture.svg",
    "images/verified-observation.svg",
    "requirements.txt",
    "requirements-live-win-py311.lock",
    "scenario-manifest.json",
    "scripts/audit_public_content.py",
    "scripts/demo_code_validator.py",
    "scripts/paired_prefix_probe.py",
    "scripts/parse_demo_output.py",
    "scripts/run_official_e2e.ps1",
    "scripts/validate_arm_summary.py",
    "scripts/validate_repo.py",
    "scripts/verify_upstream.py",
    "tests/test_paired_prefix_evidence.py",
    "tests/test_paired_prefix_probe.py",
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
        "tableRows": [
            line.count("|") - 1
            for line in text.splitlines()
            if line.startswith("|")
            and line.endswith("|")
            and not re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line)
        ],
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


def validate_customer_architecture(path: Path) -> None:
    root = ElementTree.parse(path).getroot()
    text = " ".join(value.strip() for value in root.itertext() if value.strip())
    paths = {element.attrib.get("d") for element in root.iter() if element.tag.endswith("path")}
    for marker in (
        "STABLE PREFIX",
        "DYNAMIC SUFFIX",
        "CUSTOMER RESPONSIBILITY",
        "AZURE-MANAGED SERVICE",
        "lookup / miss: populate",
        "hit: reuse processed prefix",
        "cached_tokens",
        "contextCacheContainerId",
        "Microsoft.Storage/contextCaches",
        "default-container",
        "not Blob Storage",
    ):
        require(marker in text, f"customer architecture missing: {marker}")
    require("M1106 306 H1242" in paths, "miss population must flow deployment to cache")
    require("M1242 376 H1106" in paths, "cache hit must flow cache to deployment")
    for marker in ("PUBLIC RUNNER", "AZURE PREFLIGHT", "PINNED UPSTREAM", "RAW TRANSCRIPT"):
        require(marker not in text, f"internal validation architecture leaked: {marker}")


def validate_non_attributed_observation(path: Path) -> None:
    root = ElementTree.parse(path).getroot()
    text = " ".join(value.strip() for value in root.itertext() if value.strip())
    for marker in (
        "Non-Attributed Single-Run Observation",
        "Default prompt caching and Azure Context Cache were both active",
        "Not evidence of incremental Context Cache hit rate, latency, or savings",
    ):
        require(marker in text, f"observation attribution boundary missing: {marker}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        for relative in REQUIRED:
            require((ROOT / relative).is_file(), f"required file missing: {relative}")
        require(CI.is_file(), "monorepo CI workflow is missing")

        english = READMES[0].read_text(encoding="utf-8")
        chinese = READMES[1].read_text(encoding="utf-8")
        require(english.startswith("# Azure Context Cache Customer Evaluation"), "English H1 changed")
        require(chinese.startswith("# Azure Context Cache 客户评估"), "Chinese H1 changed")
        require(markdown_shape(english) == markdown_shape(chinese), "bilingual README shape differs")
        require(
            markdown_shape(english)["images"] == [
                "badge.svg",
                "CPython-3.11%20AMD64-3776AB",
                "PowerShell-7%2B-5391FE",
                "AzureContextCache-7d1029a5-247A45",
                "License-MIT-yellow.svg",
                "customer-architecture.svg",
            ],
            "customer README image contract changed",
        )
        links = sum(validate_links(path, text) for path, text in zip(READMES, (english, chinese)))

        method_en = METHODS[0].read_text(encoding="utf-8")
        method_cn = METHODS[1].read_text(encoding="utf-8")
        require(markdown_shape(method_en) == markdown_shape(method_cn), "bilingual method shape differs")
        method_markers = {
            "METHOD.md": (
                "Paired-Prefix Follow-Up (In Progress)",
                "WARM PASS / VERIFY PENDING",
                "scripts\\paired_prefix_probe.py",
                "at least 26 hours",
            ),
            "METHOD-CN.md": (
                "Paired-Prefix 后续实验（进行中）",
                "WARM PASS / VERIFY PENDING",
                "scripts\\paired_prefix_probe.py",
                "至少等待 26 小时",
            ),
        }
        for text, name in ((method_en, "METHOD.md"), (method_cn, "METHOD-CN.md")):
            for marker in method_markers[name]:
                require(marker in text, f"{name} missing paired-prefix marker: {marker}")
        links += sum(validate_links(path, text) for path, text in zip(METHODS, (method_en, method_cn)))

        for image in (ROOT / "images").glob("*.svg"):
            validate_svg(image)
        require(len(list((ROOT / "images").glob("*.svg"))) == 2, "expected exactly two SVGs")
        validate_customer_architecture(ROOT / "images" / "customer-architecture.svg")
        validate_non_attributed_observation(ROOT / "images" / "verified-observation.svg")

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
        require(len(scenario["scenarios"]) == 6, "scenario count changed")
        paired_scenario = next(
            row
            for row in scenario["scenarios"]
            if row["id"] == "paired-prefix-retention-follow-up"
        )
        require(
            paired_scenario["classification"] == "dynamic-runtime",
            "paired-prefix scenario classification changed",
        )
        customer_architecture = next(
            row
            for row in scenario["scenarios"]
            if row["id"] == "customer-architecture-and-value-boundaries"
        )
        require(
            customer_architecture["classification"] == "architecture-explainer",
            "customer architecture scenario classification changed",
        )
        require(
            "quantified customer savings remain unverified"
            in customer_architecture["proof"],
            "customer value boundary changed",
        )
        evidence = load_json("evidence/verified-run-summary.json")
        paired = load_json("evidence/paired-prefix-follow-up.json")
        evidence_manifest = load_json("evidence/manifest.json")
        history = load_json("evidence/validation-history.json")
        calls = evidence["calls"]
        require(len(calls) == 6, "evidence run count changed")
        warm = calls[1:]
        warm_mean = round(sum(row["latencyMs"] for row in warm) / len(warm), 3)
        speedup = round(calls[0]["latencyMs"] / warm_mean, 6)
        warm_input_tokens = sum(row["inputTokens"] for row in warm)
        warm_cached_tokens = sum(row["cachedTokens"] for row in warm)
        warm_cached_share = round(100 * warm_cached_tokens / warm_input_tokens, 1)
        per_call_cached_shares = [
            100 * row["cachedTokens"] / row["inputTokens"] for row in warm
        ]
        latency_delta = round(calls[0]["latencyMs"] - warm_mean, 1)
        latency_reduction = round(100 * latency_delta / calls[0]["latencyMs"], 1)
        require(warm_mean == evidence["recomputed"]["warmMeanLatencyMs"], "warm mean mismatch")
        require(speedup == evidence["recomputed"]["firstToWarmSpeedup"], "speedup mismatch")
        require(sum(row["cachedTokens"] > 0 for row in warm) == 5, "warm hit count mismatch")
        require({row["cachedTokens"] for row in warm} == {2304}, "cached tokens changed")
        require(warm_input_tokens == 13037, "warm input token total changed")
        require(warm_cached_tokens == 11520, "warm cached token total changed")
        require(warm_cached_share == 88.4, "warm cached share changed")
        require(round(min(per_call_cached_shares), 1) == 85.9, "minimum cached share changed")
        require(round(max(per_call_cached_shares), 1) == 90.7, "maximum cached share changed")
        require(latency_delta == 2177.6, "latency delta changed")
        require(latency_reduction == 37.4, "latency reduction changed")

        evidence_paths = (
            ROOT / "evidence" / "paired-prefix-follow-up.json",
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
            "pass", "pass", "rejected-incomplete", "rejected-incomplete",
            "complete-hypothesis-falsified", "warm-pass-verify-pending",
        ], "validation history verdicts changed")
        require([row["transportErrors"] for row in history["runs"]] == [0, 0, 3, 4, 0, 0], "validation history transport counts changed")

        # The cross-day attribution run is the only phase that can speak to
        # incremental Context Cache value, and it returned a negative result.
        # Pin its decisive numbers so a later edit cannot quietly turn the
        # falsified hypothesis into a benefit claim.
        cross_day = next(row for row in history["runs"] if row["path"] == "cross-day-attribution")
        require(cross_day["path"] == "cross-day-attribution", "cross-day run path changed")
        require(
            cross_day["idleHoursBeforeFirstCall"] > cross_day["documentedDefaultCacheCeilingHours"],
            "cross-day idle window no longer clears the documented default-cache ceiling",
        )
        require(
            cross_day["observed"]["boundArmFirstCallCachedTokens"] == 0,
            "cross-day bound-arm result changed",
        )
        require(
            cross_day["observed"]["unboundControlCachedTokens"] > 0,
            "cross-day cross-deployment reuse observation changed",
        )
        paired_history = next(row for row in history["runs"] if row["path"] == "paired-prefix-follow-up")
        require(paired["status"] == "warm-pass-verify-pending", "paired-prefix status changed")
        require(paired_history["verdict"] == paired["status"], "paired-prefix history status mismatch")
        require(paired["contract"]["minimumVerifyHours"] >= 26, "paired-prefix verify window is too short")
        require(paired["contract"]["linkedArmHasContainerBinding"] is True, "linked arm lost its binding")
        require(paired["contract"]["controlArmHasContainerBinding"] is False, "control arm gained a binding")
        require(paired["isolation"]["prefixesAreDistinct"] is True, "paired prefixes are not isolated")
        require(paired["isolation"]["markersHaveEqualLength"] is True, "paired markers differ in length")
        require(
            paired["isolation"]["firstDifferenceIsWithinTheLeadingMarker"] is True,
            "paired prefix difference is outside the leading marker",
        )
        require(
            paired["isolation"]["markersPrecedeTheOriginalPrompt"] is True,
            "paired markers do not precede the original prompt",
        )
        require(paired["warm"]["linkedCachedTokensByCall"] == [0, 2304], "linked warm evidence changed")
        require(paired["warm"]["controlCachedTokensByCall"] == [0, 2304], "control warm evidence changed")
        require(paired["verify"]["status"] == "pending", "paired-prefix verify status changed")
        require(paired["verify"]["linkedCachedTokens"] is None, "pending linked verify contains a result")
        require(paired["verify"]["controlCachedTokens"] is None, "pending control verify contains a result")

        fixture_summary = summarize(
            parse_rows((ROOT / "tests/fixtures/demo-success.txt").read_text(encoding="utf-8"))
        )
        require(fixture_summary["warm"]["hits"] == 5, "fixture differential changed")
        customer_markers = {
            "README.md": (
                "Customer Problem and Business Value",
                "not unique to Context Cache",
                "What the Benefit Actually Is",
                "default, not a ceiling",
                "What This Validation Does Not Attribute",
                "cache isolation boundary",
                "Workload Fit",
                "Customer Architecture",
                "Where the Data Starts and Where the Cache Lives",
                "Microsoft.Storage/contextCaches/<name-prefix>-cache",
                "application never uploads the prompt to Blob Storage",
                "prompt_cache_retention",
                "Context Cache-Specific Validation",
                "Not established",
                "Does This Require RAG?",
                "Context Cache does not replace document ingestion",
                "official non-RAG Code Reviewer workload",
                "Test Information, Procedure, and Evidence",
                "Test Scripts",
                "Sanitized Test Log",
                "**GO**",
                "**CONDITIONAL**",
                "**LOW PRIORITY**",
                "6/6",
                "current pricing",
                "Microsoft.Storage/contextCaches",
                "contextCacheContainerId",
                "general Azure OpenAI prompt-caching guidance",
                "WARM PASS — VERIFY PENDING",
                "Cache-key isolation",
                "paired-prefix-follow-up.json",
            ),
            "README-CN.md": (
                "客户问题与业务价值",
                "不是 Context Cache 独有",
                "收益到底是什么",
                "默认值，不是上限",
                "本次验证没有归因的部分",
                "缓存隔离边界",
                "适用场景",
                "客户业务架构",
                "数据从哪里来，缓存实际存在哪里",
                "Microsoft.Storage/contextCaches/<name-prefix>-cache",
                "应用不会把 prompt 预先上传到 Blob Storage",
                "prompt_cache_retention",
                "Context Cache 专属验证",
                "尚未建立",
                "是否必须使用 RAG",
                "Context Cache 不能替代文档摄取",
                "官方非 RAG Code Reviewer workload",
                "测试信息、步骤与证据",
                "测试脚本",
                "脱敏测试日志",
                "**建议评估**",
                "**满足条件后评估**",
                "**暂不优先**",
                "6/6",
                "当前价格",
                "Microsoft.Storage/contextCaches",
                "contextCacheContainerId",
                "通用 Azure OpenAI prompt caching 指南",
                "WARM 通过 — VERIFY PENDING",
                "Cache key 隔离",
                "paired-prefix-follow-up.json",
            ),
        }
        for text, name in ((english, "README.md"), (chinese, "README-CN.md")):
            for marker in customer_markers[name]:
                require(marker in text, f"{name} missing customer marker: {marker}")
            require(
                re.search(r"\b\d+(?:\.\d+)?x\b", text, re.IGNORECASE) is None,
                f"{name} exposes an unsupported latency ratio",
            )
            require("images/architecture.svg" not in text, f"{name} references internal validation architecture")

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