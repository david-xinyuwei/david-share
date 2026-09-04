#!/usr/bin/env python3
"""Deterministic Level 5 gate for this repository subtree."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SELECTED_EXEMPLAR_COMMIT = "f1c72653c900dba73cc272ed006dc26add75203f"
REQUIRED_PATHS = [
    ".gitattributes",
    "README.md",
    "README-CN.md",
    "LICENSE",
    "infra/main.bicep",
    "scripts/probe_endpoint.py",
    "scripts/submit_private_aci_probe.py",
    "scripts/set_public_network_access.py",
    "scripts/build_evidence.py",
    "scripts/azure_translator_backtranslate.py",
    "scripts/load_test_endpoint.py",
    "scripts/submit_private_aci_load_test.py",
    "tests/test_probe_endpoint.py",
    "tests/test_submit_private_aci_probe.py",
    "tests/test_set_public_network_access.py",
    "tests/test_build_evidence.py",
    "tests/test_azure_translator_backtranslate.py",
    "tests/test_load_test_endpoint.py",
    "tests/test_validate_repo.py",
    "evidence/raw/control-plane.json",
    "evidence/raw/public-baseline.json",
    "evidence/raw/private-preflight.json",
    "evidence/raw/public-blocked.json",
    "evidence/raw/private-success.json",
    "evidence/raw/public-restored.json",
    "evidence/raw/post-test-state.json",
    "evidence/connectivity-run.json",
    "evidence/cli-transcript.txt",
    "evidence/run-contract.json",
    "evidence/provenance.json",
    "evidence/source-lock.json",
    "evidence/ui-evidence.json",
    "evidence/rule-results.json",
    "evidence/translator-back-translation.json",
    "images/product-ui/deployment-facts.png",
    "docs/reproduction.md",
    "docs/exemplar-alignment.md",
]
FORBIDDEN_PATTERNS = [
    ("concrete UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("email address", re.compile(r"\b[A-Z0-9._%+-]+@(?!example\.com\b)[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("generated Foundry account name", re.compile(r"\bfoundry(?=[a-z0-9]{12,}\b)(?=[a-z0-9]*\d)[a-z0-9]+\b", re.I)),
    ("concrete resource group", re.compile(r"\brg-[a-z0-9][a-z0-9-]{3,}\b", re.I)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b")),
    ("literal bearer credential", re.compile(r"Bearer\s+(?!\{token\}|<token>)[A-Za-z0-9._~-]{20,}", re.I)),
    ("concrete Azure AI endpoint", re.compile(r"https://(?!<|example|your)[a-z0-9-]+\.(?:services\.ai\.azure\.com|openai\.azure\.com)/", re.I)),
]
RULE_IDS = tuple(f"RUN-{number:03d}" for number in range(1, 16))
LEGAL_RULE_STATUSES = {"PASS", "FAIL", "NOT_VERIFIED", "N/A"}
QUICK_START_STAGES = (
    ("clone", ("git clone --filter=blob:none --sparse", "sparse-checkout set Deep-Learning/Managed-Compute-Private-Endpoint")),
    ("account-guard", ("az account set", "az account show")),
    ("what-if", ("az deployment group what-if", "foundryAccountResourceId", "privateEndpointSubnetResourceId", "privateEndpointLocation", "PE_SUBSCRIPTION_ID", "CURRENT_SUBSCRIPTION_ID")),
    ("deploy-private-endpoint", ("az deployment group create", "foundryAccountResourceId", "privateEndpointSubnetResourceId", "privateEndpointLocation")),
    ("private-before-disable", ("--expect-dns private", "--expect-http 200", "--prompt \"Reply with exactly OK.\"", "--max-tokens 4", "--output private-probe.json")),
    ("disable-and-save", ("--state Disabled", "--confirm-dedicated-test-account", "--private-probe-evidence private-probe.json", "--save-prior-state pna-before.json")),
    ("public-blocked", ("--expect-dns public", "--expect-http 403", "--prompt \"Reply with exactly OK.\"", "--max-tokens 4", "--output public-blocked-probe.json")),
    ("private-after-disable", ("--expect-dns private", "--expect-http 200", "--prompt \"Reply with exactly OK.\"", "--max-tokens 4", "--output private-after-disable-probe.json")),
    ("restore-original", ("--restore-state-from pna-before.json",)),
    ("public-restored", ("--expect-dns public", "--expect-http 200", "--prompt \"Reply with exactly OK.\"", "--max-tokens 4", "--output public-restored-probe.json")),
)
BILINGUAL_FACTS = (
    ("managed-compute-private-link-dedicated-20260831", "managed-compute-private-link-dedicated-20260831"),
    ("2026-08-31", "2026-08-31"),
    ("run on Microsoft-hosted", "跑在微软托管的算力上"),
    ("not observable from the customer network", "从客户网络里观察不到"),
    ("evidence/perf/resource-inventory.json", "evidence/perf/resource-inventory.json"),
    ("Temporary resources remain", "临时资源仍然保留"),
    ("billing continues", "继续产生费用"),
    ("Azure Container Instances (ACI)", "Azure Container Instances（Azure 容器实例，ACI）"),
    ("not Azure Bastion", "不是 Azure Bastion"),
    ("do not hard-code `Enabled`", "不要把目标值硬编码为 `Enabled`"),
    ("parent Foundry resource", "所属 Foundry 资源"),
    ("earliest public-safe sanitized", "最早一层可公开的脱敏观测"),
    ("dedicated non-production Foundry resource", "独立的非生产 Foundry 资源"),
    ("derived after the run", "运行结束后派生"),
    ("no live measurement", "没有实测"),
    ("inferred from the private DNS class", "私网 DNS 解析结果推断"),
    ("other inbound hostname", "其他入站主机名"),
    ("Point-to-site VPN", "点到站点 VPN"),
    ("ExpressRoute or site-to-site VPN", "ExpressRoute 或站点到站点 VPN"),
    ("manual-restore", "manual-restore"),
    ("disableLocalAuth=true", "disableLocalAuth=true"),
    ("`api-key` header", "`api-key` 请求头"),
    ("Only the Entra path was", "只实测了 Entra 这一条"),
    ("### Recommended production access configuration", "### 生产环境建议配置"),
    ("`publicNetworkAccess=Disabled`", "`publicNetworkAccess=Disabled`"),
    ("privatelink.services.ai.azure.com", "privatelink.services.ai.azure.com"),
    ("validation and operator tools", "验证工具和运维入口"),
)
READER_FLOW_HEADINGS_EN = (
    "## Start here",
    "## Responsibility boundary",
    "## What this repository proves",
    "## Measured run",
    "## Product evidence",
    "## Executable assets",
    "## How the validation works",
    "## Quick start",
    "## Tests",
    "## Compatibility notes",
    "## Repository map",
    "## Evidence",
    "## Official sources",
)
READER_FLOW_HEADINGS_CN = (
    "## 从这里开始",
    "## 平台与客户各负责什么",
    "## 本仓库证明了什么",
    "## 五阶段实测",
    "## 产品界面与流量路径",
    "## 可执行资产",
    "## 验证原理",
    "## 复现步骤",
    "## 测试",
    "## 兼容性说明",
    "## 目录说明",
    "## 证据",
    "## 官方资料",
)
START_HERE_TOKENS_EN = (
    "| Goal | Go to |",
    "Python 3.11+",
    "use only the Python standard library",
    "[Quick start](#quick-start)",
    "[Tests](#tests)",
    "[Recommended production access configuration](#recommended-production-access-configuration)",
)
START_HERE_TOKENS_CN = (
    "| 目标 | 入口 |",
    "Python 3.11+",
    "只使用 Python 标准库",
    "[复现步骤](#复现步骤)",
    "[测试](#测试)",
    "[生产环境建议配置](#生产环境建议配置)",
)
RETIRED_CN_PROSE = (
    "这个 Repo",
    "专用 run",
    "下面的 block",
    "live observation",
    "private-IP ACI",
    "业务 subnet",
    "私网 runner",
    "probe 输出",
    "receipt",
    "typed object",
    "三个 key",
    "原生 gate",
)
TEXT_HASH_SUFFIXES = {".bicep", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def sha256(relative_path: str) -> str:
    path = ROOT / relative_path
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_HASH_SUFFIXES:
        text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def make_check(
    check_id: str,
    passed: bool,
    actual: object,
    expected: object = True,
) -> dict[str, object]:
    return {
        "id": check_id,
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
    }


def make_rule(
    rule_id: str,
    description: str,
    checks: list[dict[str, object]],
    evidence: list[str],
) -> dict[str, object]:
    return {
        "id": rule_id,
        "applicable": True,
        "description": description,
        "status": "PASS" if checks and all(check["passed"] for check in checks) else "FAIL",
        "checks": checks,
        "evidence": evidence,
    }


def make_na_rule(rule_id: str, reason: str) -> dict[str, object]:
    return {
        "id": rule_id,
        "applicable": False,
        "status": "N/A",
        "reason": reason,
        "checks": [],
        "evidence": [],
    }


def extract_bash_blocks(text: str) -> list[str]:
    return [
        block.strip()
        for block in re.findall(r"```bash\s*\n(.*?)```", text, flags=re.DOTALL)
    ]


def quick_start_stage_results(text: str) -> dict[str, bool]:
    blocks = extract_bash_blocks(text)
    results: dict[str, bool] = {}
    cursor = -1
    for name, required_tokens in QUICK_START_STAGES:
        match = next(
            (
                index
                for index, block in enumerate(blocks)
                if index > cursor and all(token in block for token in required_tokens)
            ),
            None,
        )
        results[name] = match is not None
        if match is not None:
            cursor = match
    results["no-independent-vnet-parameter"] = "virtualNetworkResourceId=" not in text
    results["no-hard-coded-public-enable"] = "--state Enabled" not in text
    return results


def reader_flow_results(
    text: str,
    headings: tuple[str, ...] = READER_FLOW_HEADINGS_EN,
) -> dict[str, bool]:
    lines = text.splitlines()
    positions = {
        heading: next(
            (index for index, line in enumerate(lines) if line == heading),
            None,
        )
        for heading in headings
    }
    present_positions = [positions[heading] for heading in headings]
    first_h2 = next((line for line in lines if line.startswith("## ")), None)
    return {
        "all-required-headings": all(position is not None for position in present_positions),
        "required-heading-order": all(position is not None for position in present_positions)
        and present_positions == sorted(present_positions),
        "start-here-is-first-section": first_h2 == headings[0],
        "start-here-in-first-80-lines": positions[headings[0]] is not None
        and positions[headings[0]] < 80,
    }


def prose_without_code(text: str) -> str:
    without_fences = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`]+`", "", without_fences)


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def chinese_quality_results(text: str) -> dict[str, bool]:
    prose = prose_without_code(text)
    return {
        "reader-flow": all(
            reader_flow_results(text, READER_FLOW_HEADINGS_CN).values()
        ),
        "start-here-contract": all(token in text for token in START_HERE_TOKENS_CN),
        "official-terms-introduced": all(
            token in text
            for token in (
                "Private Endpoint（私有端点）",
                "public network access（公网访问）",
                "Azure Container Instances（Azure 容器实例，ACI）",
            )
        ),
        "generic-nouns-in-chinese": all(
            token in text for token in ("推理端点", "探针", "子网", "恢复记录")
        ),
        "retired-translation-phrases-absent": not any(
            phrase in prose for phrase in RETIRED_CN_PROSE
        ),
    }


def run_readme_mutation_checks(readme: str, readme_cn: str) -> dict[str, bool]:
    moved_start = readme.replace("## Start here", "## Start-here-moved", 1)
    missing_tests = readme.replace("## Tests", "## Test-details-removed", 1)
    stiff_chinese = f"{readme_cn}\n\n这个 Repo\n"
    chinese_heading_drift = readme_cn.replace("## 从这里开始", "## 开始位置已漂移", 1)
    command_drift = f"{readme_cn}\n\n```bash\necho drift\n```\n"
    return {
        "moved-start-here-rejected": not all(reader_flow_results(moved_start).values()),
        "missing-tests-rejected": not all(reader_flow_results(missing_tests).values()),
        "stiff-chinese-rejected": not all(chinese_quality_results(stiff_chinese).values()),
        "chinese-heading-drift-rejected": not all(
            chinese_quality_results(chinese_heading_drift).values()
        ),
        "bilingual-command-drift-rejected": extract_bash_blocks(readme)
        != extract_bash_blocks(command_drift),
    }


def image_paths(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)


def validate_ui_evidence(
    ui: dict[str, object], root: pathlib.Path = ROOT
) -> list[str]:
    errors = []
    images = ui.get("images")
    if not isinstance(images, list) or len(images) != 1:
        return ["UI evidence must contain exactly one dedicated-run image"]
    for image in images:
        if not isinstance(image, dict):
            errors.append("UI evidence image entry is not an object")
            continue
        relative_path = image.get("path")
        if not isinstance(relative_path, str):
            errors.append("UI evidence image path is invalid")
            continue
        image_path = root / relative_path
        if not image_path.is_file():
            errors.append(f"missing UI image: {relative_path}")
        else:
            image_bytes = image_path.read_bytes()
            if hashlib.sha256(image_bytes).hexdigest() != image.get("sha256"):
                errors.append(f"UI image hash mismatch: {relative_path}")
            if image_bytes[:8] != b"\x89PNG\r\n\x1a\n" or len(image_bytes) < 24:
                errors.append(f"UI image is not a valid PNG: {relative_path}")
            else:
                actual_dimensions = {
                    "width": int.from_bytes(image_bytes[16:20], "big"),
                    "height": int.from_bytes(image_bytes[20:24], "big"),
                }
                if image.get("dimensions") != actual_dimensions:
                    errors.append(f"UI image dimensions mismatch: {relative_path}")
        if image.get("sourceClass") != "LOCAL_MEASUREMENT":
            errors.append(f"UI image source class is invalid: {relative_path}")
        if image.get("runId") != "managed-compute-private-link-dedicated-20260831":
            errors.append(f"UI image run identity is invalid: {relative_path}")
        if image.get("captureDateUtc") != "2026-08-31":
            errors.append(f"UI image capture date is invalid: {relative_path}")
        if not image.get("cropStatus") or not image.get("captureScope"):
            errors.append(f"UI image provenance is incomplete: {relative_path}")
        if not image.get("proves") or not image.get("doesNotProve"):
            errors.append(f"UI image claim boundary is incomplete: {relative_path}")
    diagram = ui.get("explanatoryDiagram")
    if not isinstance(diagram, dict):
        errors.append("explanatory diagram ledger is missing")
    elif not (
        diagram.get("sourceClass") == "AUTHOR_SYNTHESIS"
        and diagram.get("format") == "Mermaid flowchart"
        and isinstance(diagram.get("inputs"), list)
        and "evidence/connectivity-run.json" in diagram["inputs"]
        and any(
            str(value).startswith("https://learn.microsoft.com/")
            for value in diagram["inputs"]
        )
        and diagram.get("incrementalValue")
        and diagram.get("doesNotProve")
    ):
        errors.append("explanatory diagram provenance is incomplete")
    return errors


def validate_evidence_path(relative_path: object, root: pathlib.Path) -> list[str]:
    if not isinstance(relative_path, str) or not relative_path:
        return ["evidence path is not a non-empty string"]
    posix_path = pathlib.PurePosixPath(relative_path)
    windows_path = pathlib.PureWindowsPath(relative_path)
    if posix_path.is_absolute() or windows_path.is_absolute():
        return [f"absolute evidence path: {relative_path}"]
    if ".." in posix_path.parts or ".." in windows_path.parts:
        return [f"parent traversal in evidence path: {relative_path}"]
    candidate = root.joinpath(*posix_path.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
    except FileNotFoundError:
        return [f"missing evidence path: {relative_path}"]
    except ValueError:
        return [f"evidence path resolves outside repository: {relative_path}"]
    if not resolved_candidate.is_file():
        return [f"evidence path is not a file: {relative_path}"]
    return []


def validate_rule_results_document(
    document: object,
    expected_applicability: dict[str, bool] | None = None,
    root: pathlib.Path = ROOT,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("schemaVersion") != 1:
        return ["rule results schemaVersion must be 1"]
    rules = document.get("rules")
    if not isinstance(rules, list):
        return ["rule results rules must be an array"]
    rule_ids = [rule.get("id") if isinstance(rule, dict) else None for rule in rules]
    for rule_id in RULE_IDS:
        count = rule_ids.count(rule_id)
        if count == 0:
            errors.append(f"missing rule: {rule_id}")
        elif count > 1:
            errors.append(f"duplicate rule: {rule_id}")
    for rule_id in rule_ids:
        if rule_id not in RULE_IDS:
            errors.append(f"unknown rule: {rule_id}")

    for rule in rules:
        if not isinstance(rule, dict) or rule.get("id") not in RULE_IDS:
            continue
        rule_id = str(rule["id"])
        applicable = rule.get("applicable")
        status = rule.get("status")
        checks = rule.get("checks")
        evidence = rule.get("evidence")
        if not isinstance(applicable, bool):
            errors.append(f"{rule_id} applicable must be boolean")
            continue
        if expected_applicability is not None and applicable != expected_applicability[rule_id]:
            errors.append(f"false applicability: {rule_id}")
        if status not in LEGAL_RULE_STATUSES:
            errors.append(f"illegal status: {rule_id}={status}")
        if not isinstance(checks, list) or not isinstance(evidence, list):
            errors.append(f"{rule_id} checks and evidence must be arrays")
            continue
        if len(evidence) != len(set(evidence)):
            errors.append(f"duplicate evidence path: {rule_id}")
        for path in evidence:
            errors.extend(validate_evidence_path(path, root))

        if applicable:
            if status in {"N/A", "NOT_VERIFIED"}:
                errors.append(f"applicable rule has non-evaluated status: {rule_id}")
            if not checks:
                errors.append(f"applicable rule has no checks: {rule_id}")
            check_ids = [check.get("id") if isinstance(check, dict) else None for check in checks]
            if len(check_ids) != len(set(check_ids)):
                errors.append(f"duplicate check: {rule_id}")
            check_values = []
            for check in checks:
                if not isinstance(check, dict):
                    errors.append(f"invalid check object: {rule_id}")
                    continue
                if not isinstance(check.get("id"), str) or not check["id"]:
                    errors.append(f"invalid check id: {rule_id}")
                if not isinstance(check.get("passed"), bool):
                    errors.append(f"invalid check result: {rule_id}")
                    continue
                if "actual" not in check or "expected" not in check:
                    errors.append(f"check lacks actual/expected: {rule_id}")
                check_values.append(check["passed"])
            if check_values:
                computed_status = "PASS" if all(check_values) else "FAIL"
                if status != computed_status:
                    errors.append(f"forged status: {rule_id}={status}, expected {computed_status}")
        else:
            if status != "N/A":
                errors.append(f"non-applicable rule must be N/A: {rule_id}")
            if checks:
                errors.append(f"non-applicable rule has checks: {rule_id}")
            if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
                errors.append(f"non-applicable rule lacks reason: {rule_id}")
    return errors


def load_evidence_builder():
    module_path = ROOT / "scripts" / "build_evidence.py"
    spec = importlib.util.spec_from_file_location("build_evidence", module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load evidence builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_translation_validator():
    module_path = ROOT / "scripts" / "azure_translator_backtranslate.py"
    spec = importlib.util.spec_from_file_location(
        "azure_translator_backtranslate",
        module_path,
    )
    if not spec or not spec.loader:
        raise RuntimeError("Unable to load Azure Translator validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_content_errors(root: pathlib.Path = ROOT) -> list[str]:
    errors: list[str] = []
    text_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".repo-evidence" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix.lower() in {".md", ".py", ".json", ".bicep", ".txt", ".yml"}
    ]
    for path in text_files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"{label} in {path.relative_to(root)}")
    return errors


def run_evidence_mutation_checks() -> dict[str, bool]:
    builder = load_evidence_builder()
    baseline = {
        name: builder.load_raw(builder.RAW_DIR, name) for name in builder.RAW_FILES
    }
    mutations = {
        "raw-gap-rejected": lambda value: value.pop("private-success.json"),
        "duplicate-scenario-rejected": lambda value: value[
            "private-success.json"
        ].update(id="public-blocked"),
        "wrong-identity-rejected": lambda value: value[
            "private-success.json"
        ].update(responseModel="different-model"),
        "wrong-run-rejected": lambda value: value["private-success.json"].update(
            runId="different-run"
        ),
        "identity-drift-rejected": lambda value: value[
            "private-success.json"
        ].update(probeSourceSha256="0" * 64),
        "derived-field-in-raw-rejected": lambda value: value[
            "public-restored.json"
        ].update(identitySha256="0" * 64),
        "unlabeled-fingerprint-chain-rejected": lambda value: value[
            "control-plane.json"
        ]["derivedFingerprints"].update(emittedByMeasuredProbe=True),
        "duplicate-sequence-rejected": lambda value: value[
            "private-success.json"
        ].update(sequence=3),
        "non-monotonic-time-rejected": lambda value: value[
            "public-restored.json"
        ].update(observedAtUtc=value["public-blocked.json"]["observedAtUtc"]),
        "missing-output-rejected": lambda value: value[
            "private-success.json"
        ].update(responseObject=None),
        "non-policy-403-rejected": lambda value: value[
            "public-blocked.json"
        ].update(errorCategory="service-error"),
        "false-cleanup-rejected": lambda value: value[
            "post-test-state.json"
        ].update(
            temporaryResourcesRetained=False
        ),
    }
    results = {}
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(baseline)
        mutate(candidate)
        try:
            builder.validate_observations(candidate)
        except (KeyError, TypeError, ValueError):
            results[name] = True
        else:
            results[name] = False
    return results


def run_rule_contract_mutation_checks(
    document: dict[str, object],
) -> dict[str, bool]:
    expected = {rule["id"]: rule["applicable"] for rule in document["rules"]}
    if validate_rule_results_document(document, expected):
        return {"baseline-valid": False}

    def rejected(mutator) -> bool:
        candidate = copy.deepcopy(document)
        mutator(candidate)
        return bool(validate_rule_results_document(candidate, expected))

    passing_rule_index = next(
        index
        for index, rule in enumerate(document["rules"])
        if rule["status"] == "PASS" and rule["checks"]
    )

    return {
        "missing-rule-rejected": rejected(lambda value: value["rules"].pop()),
        "duplicate-rule-rejected": rejected(
            lambda value: value["rules"].append(copy.deepcopy(value["rules"][0]))
        ),
        "unknown-rule-rejected": rejected(
            lambda value: value["rules"][0].update(id="RUN-999")
        ),
        "false-applicability-rejected": rejected(
            lambda value: value["rules"][0].update(
                applicable=False,
                status="N/A",
                reason="mutated",
                checks=[],
                evidence=[],
            )
        ),
        "forged-pass-rejected": rejected(
            lambda value: value["rules"][passing_rule_index]["checks"][0].update(
                passed=False
            )
        ),
        "absolute-evidence-rejected": rejected(
            lambda value: value["rules"][0]["evidence"].__setitem__(
                0, "C:\\outside.json"
            )
        ),
        "parent-evidence-rejected": rejected(
            lambda value: value["rules"][0]["evidence"].__setitem__(
                0, "../outside.json"
            )
        ),
        "missing-evidence-rejected": rejected(
            lambda value: value["rules"][0]["evidence"].__setitem__(
                0, "evidence/not-present.json"
            )
        ),
        "duplicate-check-rejected": rejected(
            lambda value: value["rules"][0]["checks"].append(
                copy.deepcopy(value["rules"][0]["checks"][0])
            )
        ),
    }


def build_rule_results() -> dict[str, object]:
    run = load_json("evidence/connectivity-run.json")
    contract = load_json("evidence/run-contract.json")
    provenance = load_json("evidence/provenance.json")
    ui = load_json("evidence/ui-evidence.json")
    translation = load_json("evidence/translator-back-translation.json")
    translation_validator = load_translation_validator()
    translation_errors = translation_validator.validate_document(translation)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README-CN.md").read_text(encoding="utf-8")
    exemplar_alignment = (ROOT / "docs/exemplar-alignment.md").read_text(
        encoding="utf-8"
    )
    normalized_readme = normalize_whitespace(readme)
    normalized_readme_cn = normalize_whitespace(readme_cn)
    scenario_list = run["scenarios"]
    scenarios = {item["id"]: item for item in run["scenarios"]}
    quick_start = quick_start_stage_results(readme)
    reader_flow = reader_flow_results(readme, READER_FLOW_HEADINGS_EN)
    chinese_quality = chinese_quality_results(readme_cn)
    lineage = run.get("lineage", {}).get("executableSha256", {})
    expected_lineage_paths = (
        "infra/main.bicep",
        "scripts/build_evidence.py",
        "scripts/azure_translator_backtranslate.py",
        "scripts/probe_endpoint.py",
        "scripts/submit_private_aci_probe.py",
        "scripts/set_public_network_access.py",
        "scripts/load_test_endpoint.py",
        "scripts/submit_private_aci_load_test.py",
        "scripts/validate_repo.py",
        "evidence/run-contract.json",
        "evidence/provenance.json",
    )
    raw_paths = {
        "public-baseline": "evidence/raw/public-baseline.json",
        "private-preflight": "evidence/raw/private-preflight.json",
        "public-blocked": "evidence/raw/public-blocked.json",
        "private-success": "evidence/raw/private-success.json",
        "public-restored": "evidence/raw/public-restored.json",
    }
    evidence_mutations = run_evidence_mutation_checks()
    readme_mutations = run_readme_mutation_checks(readme, readme_cn)

    rules = [
        make_rule(
            "RUN-001",
            "Actual request and work identity are visible and synchronized.",
            [
                make_check(
                    "run-id-in-both-readmes",
                    run["runId"] in readme and run["runId"] in readme_cn,
                    run["runId"],
                ),
                make_check(
                    "prompt-synchronized",
                    run["request"]["prompt"] == "Reply with exactly OK."
                    and readme.count('--prompt "Reply with exactly OK."') >= 4,
                    run["request"]["prompt"],
                    "Reply with exactly OK.",
                ),
                make_check(
                    "request-parameters-synchronized",
                    run["request"]["maxTokens"] == 4
                    and run["request"]["temperature"] == 0
                    and readme.count("--max-tokens 4") >= 4,
                    run["request"],
                ),
                make_check(
                    "contract-run-id",
                    contract["runId"] == run["runId"],
                    contract["runId"],
                    run["runId"],
                ),
                make_check(
                    "measured-probe-retrieval-recorded",
                    provenance["measuredProbeSource"]["repositoryBaselineCommit"]
                    == "762b69780da73c9f9ca21c28508349755a980820"
                    and provenance["measuredProbeSource"]["retrieval"].startswith(
                        "git show 762b69780da73c9f9ca21c28508349755a980820:"
                    ),
                    provenance["measuredProbeSource"],
                ),
                make_check(
                    "generated-cli-evidence-linked",
                    "[Generated transcript](evidence/cli-transcript.txt)" in readme
                    and "[自动生成的调用记录](evidence/cli-transcript.txt)" in readme_cn,
                    {
                        "english": "[Generated transcript](evidence/cli-transcript.txt)" in readme,
                        "chinese": "[自动生成的调用记录](evidence/cli-transcript.txt)" in readme_cn,
                    },
                ),
                make_check(
                    "fingerprint-chain-labeled-derived",
                    run["derivedFingerprints"]["class"] == "derived-post-run"
                    and run["derivedFingerprints"]["emittedByMeasuredProbe"] is False
                    and all(
                        field not in scenario
                        for scenario in scenario_list
                        for field in (
                            "identitySha256",
                            "endpointSha256",
                            "deploymentSha256",
                            "requestSha256",
                        )
                    )
                    and all(
                        scenario.get("probeSourceSha256")
                        == run["derivedFingerprints"]["probeSourceSha256"]
                        for scenario in scenario_list
                        if scenario["id"].startswith("private-")
                    )
                    and run["derivedFingerprints"]["derivedAtUtc"]
                    == load_json("evidence/raw/control-plane.json")["derivedFingerprints"]["derivedAtUtc"],
                    {
                        "class": run["derivedFingerprints"]["class"],
                        "emittedByMeasuredProbe": run["derivedFingerprints"]["emittedByMeasuredProbe"],
                        "derivedOnlyFieldsInRaw": sorted(
                            {
                                field
                                for scenario in scenario_list
                                for field in (
                                    "identitySha256",
                                    "endpointSha256",
                                    "deploymentSha256",
                                    "requestSha256",
                                )
                                if field in scenario
                            }
                        ),
                    },
                    {
                        "class": "derived-post-run",
                        "emittedByMeasuredProbe": False,
                        "derivedOnlyFieldsInRaw": [],
                    },
                ),
            ],
            [
                "README.md",
                "README-CN.md",
                "evidence/connectivity-run.json",
                "evidence/run-contract.json",
                "evidence/cli-transcript.txt",
            ],
        ),
        make_rule(
            "RUN-002",
            "The primary workload, input, command, and output are public assets.",
            [
                make_check(
                    "owned-primary-assets",
                    all(
                        (ROOT / path).is_file()
                        for path in (
                            "scripts/probe_endpoint.py",
                            "infra/main.bicep",
                            "evidence/run-contract.json",
                            "evidence/connectivity-run.json",
                        )
                    ),
                    True,
                ),
                make_check(
                    "public-endpoint-placeholder",
                    run["target"]["endpointPattern"].startswith(
                        "https://<foundry-account>"
                    ),
                    run["target"]["endpointPattern"],
                ),
            ],
            [
                "scripts/probe_endpoint.py",
                "infra/main.bicep",
                "evidence/run-contract.json",
                "evidence/connectivity-run.json",
            ],
        ),
        make_rule(
            "RUN-003",
            "README wiring is ordered, complete, and synchronized to source hashes.",
            [
                *[
                    make_check(f"reader-flow-{name}", passed, passed)
                    for name, passed in reader_flow.items()
                ],
                make_check(
                    "start-here-contract",
                    all(token in readme for token in START_HERE_TOKENS_EN),
                    {token: token in readme for token in START_HERE_TOKENS_EN},
                    {token: True for token in START_HERE_TOKENS_EN},
                ),
                make_check(
                    "responsibility-boundary",
                    "| Microsoft Foundry and Azure provide | You provide and verify |"
                    in readme,
                    "| Microsoft Foundry and Azure provide | You provide and verify |"
                    in readme,
                ),
                make_check(
                    "tests-have-offline-contract",
                    "## Tests" in readme
                    and "No Azure credentials, GPU, or live endpoint are required"
                    in readme
                    and "python scripts/validate_repo.py" in readme,
                    True,
                ),
                make_check(
                    "selected-exemplar-locked",
                    "Meeting-Agent" in exemplar_alignment
                    and SELECTED_EXEMPLAR_COMMIT in exemplar_alignment,
                    {
                        "repository": "Meeting-Agent" in exemplar_alignment,
                        "commit": SELECTED_EXEMPLAR_COMMIT in exemplar_alignment,
                    },
                    {"repository": True, "commit": True},
                ),
                *[
                    make_check(f"quick-start-{name}", passed, passed)
                    for name, passed in quick_start.items()
                ],
                make_check(
                    "source-hashes-current",
                    all(lineage.get(path) == sha256(path) for path in expected_lineage_paths),
                    {
                        path: lineage.get(path) == sha256(path)
                        for path in expected_lineage_paths
                    },
                ),
            ],
            [
                "README.md",
                "scripts/probe_endpoint.py",
                "scripts/submit_private_aci_probe.py",
                "scripts/set_public_network_access.py",
                "scripts/build_evidence.py",
                "scripts/validate_repo.py",
                "infra/main.bicep",
                "evidence/run-contract.json",
                "evidence/connectivity-run.json",
            ],
        ),
        make_rule(
            "RUN-004",
            "The public network access transition and Private Endpoint prerequisite are recorded.",
            [
                make_check(
                    "pna-transition",
                    run["controlPlane"]["publicNetworkAccess"]
                    == {
                        "initial": "Enabled",
                        "duringTest": "Disabled",
                        "afterTest": "Enabled",
                    },
                    run["controlPlane"]["publicNetworkAccess"],
                ),
                make_check(
                    "private-endpoint-approved",
                    run["controlPlane"]["privateEndpoint"]["connectionStatus"]
                    == "Approved"
                    and run["controlPlane"]["privateEndpoint"]["provisioningState"]
                    == "Succeeded"
                    and run["controlPlane"]["privateEndpoint"]["groupId"]
                    == "account",
                    run["controlPlane"]["privateEndpoint"],
                ),
            ],
            ["evidence/connectivity-run.json", "evidence/raw/control-plane.json"],
        ),
        make_na_rule("RUN-005", "No process takeover or recovery claim is made."),
        make_na_rule(
            "RUN-006",
            "The connectivity probe has no checkpoint or resume semantics.",
        ),
        make_rule(
            "RUN-007",
            "Every terminal scenario contains the claimed business response.",
            [
                make_check(
                    "public-baseline-completion",
                    scenarios["public-baseline"]["dnsClass"] == "public"
                    and scenarios["public-baseline"]["httpStatus"] == 200
                    and scenarios["public-baseline"]["responseObject"]
                    == "chat.completion"
                    and scenarios["public-baseline"]["responseModel"]
                    == run["target"]["model"],
                    scenarios["public-baseline"],
                ),
                make_check(
                    "private-preflight-completion",
                    scenarios["private-preflight"]["dnsClass"] == "private"
                    and scenarios["private-preflight"]["httpStatus"] == 200
                    and scenarios["private-preflight"]["responseObject"]
                    == "chat.completion"
                    and scenarios["private-preflight"]["responseModel"]
                    == run["target"]["model"]
                    and scenarios["private-preflight"]["runnerExitCode"] == 0,
                    scenarios["private-preflight"],
                ),
                make_check(
                    "public-policy-block",
                    scenarios["public-blocked"]["dnsClass"] == "public"
                    and scenarios["public-blocked"]["httpStatus"] == 403
                    and scenarios["public-blocked"]["errorCategory"]
                    == "public-access-disabled"
                    and scenarios["public-blocked"]["networkPolicyBlocked"] is True,
                    {
                        "dns": scenarios["public-blocked"]["dnsClass"],
                        "http": scenarios["public-blocked"]["httpStatus"],
                        "errorCategory": scenarios["public-blocked"]["errorCategory"],
                        "networkPolicyBlocked": scenarios["public-blocked"][
                            "networkPolicyBlocked"
                        ],
                    },
                ),
                make_check(
                    "private-completion",
                    scenarios["private-success"]["dnsClass"] == "private"
                    and scenarios["private-success"]["httpStatus"] == 200
                    and scenarios["private-success"]["responseObject"]
                    == "chat.completion"
                    and scenarios["private-success"]["responseModel"]
                    == run["target"]["model"]
                    and scenarios["private-success"]["runnerExitCode"] == 0,
                    {
                        "dns": scenarios["private-success"]["dnsClass"],
                        "http": scenarios["private-success"]["httpStatus"],
                        "object": scenarios["private-success"]["responseObject"],
                        "model": scenarios["private-success"]["responseModel"],
                        "exitCode": scenarios["private-success"]["runnerExitCode"],
                    },
                ),
                make_check(
                    "restored-public-http-response",
                    scenarios["public-restored"]["dnsClass"] == "public"
                    and scenarios["public-restored"]["httpStatus"] == 200
                    and scenarios["public-restored"]["responseModel"]
                    == run["target"]["model"],
                    {
                        "dns": scenarios["public-restored"]["dnsClass"],
                        "http": scenarios["public-restored"]["httpStatus"],
                        "model": scenarios["public-restored"]["responseModel"],
                    },
                ),
            ],
            ["evidence/connectivity-run.json", *raw_paths.values()],
        ),
        make_na_rule("RUN-008", "This is not a time-sequenced recovery report."),
        make_na_rule(
            "RUN-009",
            "No crash, recovery, or replacement storyboard is claimed.",
        ),
        make_na_rule("RUN-010", "No latency or duration claim is made."),
        make_rule(
            "RUN-011",
            "UI object proof and behavior proof are paired without conflation.",
            [
                make_check(
                    "ui-hashes-and-boundaries",
                    not validate_ui_evidence(ui),
                    validate_ui_evidence(ui),
                    [],
                ),
                make_check(
                    "deployment-ui-facts",
                    all(
                        value in ui["images"][0]["proves"]
                        for value in (
                            "GlobalManagedCompute",
                            "Succeeded",
                            "H100_80GB",
                            "qwen--qwen3-32b",
                        )
                    ),
                    ui["images"][0]["proves"],
                ),
            ],
            [
                "evidence/ui-evidence.json",
                "images/product-ui/deployment-facts.png",
                "evidence/connectivity-run.json",
            ],
        ),
        make_rule(
            "RUN-012",
            "The scenario matrix covers baseline, safety preflight, block, private allow, and restore exactly once.",
            [
                make_check(
                    "scenario-set",
                    [item["id"] for item in scenario_list]
                    == [
                        "public-baseline",
                        "private-preflight",
                        "public-blocked",
                        "private-success",
                        "public-restored",
                    ]
                    and len(scenarios) == len(scenario_list),
                    [item["id"] for item in scenario_list],
                    [
                        "public-baseline",
                        "private-preflight",
                        "public-blocked",
                        "private-success",
                        "public-restored",
                    ],
                ),
                make_check(
                    "scenario-statuses",
                    all(item["status"] == "PASS" for item in scenarios.values()),
                    {name: item["status"] for name, item in scenarios.items()},
                ),
                make_check(
                    "scenario-evidence-identity",
                    all(
                        load_json(path)["id"] == name
                        and load_json(path)["runId"] == run["runId"]
                        for name, path in raw_paths.items()
                    ),
                    True,
                ),
                make_check(
                    "scenario-order-and-time",
                    [item["sequence"] for item in scenario_list]
                    == [1, 2, 3, 4, 5]
                    and [item["observedAtUtc"] for item in scenario_list]
                    == sorted(item["observedAtUtc"] for item in scenario_list),
                    [
                        {
                            "sequence": item["sequence"],
                            "observedAtUtc": item["observedAtUtc"],
                        }
                        for item in scenario_list
                    ],
                ),
            ],
            [
                "evidence/connectivity-run.json",
                "evidence/provenance.json",
                *raw_paths.values(),
            ],
        ),
        make_rule(
            "RUN-013",
            "The recorded post-test state is restored and does not misrepresent retained resources as cleaned up.",
            [
                make_check(
                    "resources-retained-explicitly",
                    run["postTestState"]["temporaryResourcesRetained"] is True
                    and run["postTestState"]["cleanupStatus"] == "AWAITING_USER"
                    and run["postTestState"]["billingContinues"] is True,
                    {
                        "temporaryResourcesRetained": run["postTestState"]["temporaryResourcesRetained"],
                        "cleanupStatus": run["postTestState"]["cleanupStatus"],
                        "billingContinues": run["postTestState"]["billingContinues"],
                    },
                ),
                make_check(
                    "parent-restored",
                    run["postTestState"]["parentPublicNetworkAccess"]
                    == run["controlPlane"]["publicNetworkAccess"]["afterTest"]
                    == "Enabled",
                    run["postTestState"]["parentPublicNetworkAccess"],
                    "Enabled",
                ),
                make_check(
                    "private-endpoint-retained",
                    run["postTestState"]["approvedAccountPrivateEndpointConnectionCount"]
                    == 1,
                    run["postTestState"]["approvedAccountPrivateEndpointConnectionCount"],
                    1,
                ),
                make_check(
                    "managed-compute-retained",
                    run["postTestState"]["managedComputeProvisioningState"]
                    == "Succeeded"
                    and run["postTestState"]["managedComputeSku"]
                    == "GlobalManagedCompute"
                    and run["postTestState"]["managedComputeCapacity"] == 1,
                    {
                        "state": run["postTestState"]["managedComputeProvisioningState"],
                        "sku": run["postTestState"]["managedComputeSku"],
                        "capacity": run["postTestState"]["managedComputeCapacity"],
                    },
                ),
                make_check(
                    "private-runners-terminated",
                    len(run["postTestState"]["containerGroups"]) == 2
                    and all(
                        item["provisioningState"] == "Succeeded"
                        and item["state"] == "Terminated"
                        and item["exitCode"] == 0
                        for item in run["postTestState"]["containerGroups"]
                    ),
                    run["postTestState"]["containerGroups"],
                ),
            ],
            [
                "evidence/connectivity-run.json",
                "evidence/raw/post-test-state.json",
            ],
        ),
        make_rule(
            "RUN-014",
            "English and Chinese preserve facts and assets; the Chinese README uses native engineering prose.",
            [
                make_check(
                    "bilingual-fact-ledger",
                    all(
                        english in normalized_readme
                        and chinese in normalized_readme_cn
                        for english, chinese in BILINGUAL_FACTS
                    ),
                    {
                        english: english in normalized_readme
                        and chinese in normalized_readme_cn
                        for english, chinese in BILINGUAL_FACTS
                    },
                ),
                make_check(
                    "bilingual-command-parity",
                    extract_bash_blocks(readme) == extract_bash_blocks(readme_cn),
                    len(extract_bash_blocks(readme)),
                    len(extract_bash_blocks(readme_cn)),
                ),
                make_check(
                    "bilingual-image-parity",
                    image_paths(readme) == image_paths(readme_cn),
                    image_paths(readme),
                    image_paths(readme_cn),
                ),
                *[
                    make_check(f"chinese-{name}", passed, passed)
                    for name, passed in chinese_quality.items()
                ],
                make_check(
                    "azure-translator-back-translation",
                    not translation_errors,
                    translation_errors,
                    [],
                ),
            ],
            [
                "README.md",
                "README-CN.md",
                "evidence/run-contract.json",
                "evidence/translator-back-translation.json",
                "scripts/azure_translator_backtranslate.py",
            ],
        ),
        make_rule(
            "RUN-015",
            "Negative evidence and rule-contract mutations fail closed.",
            [
                make_check(
                    "evidence-mutations-rejected",
                    all(evidence_mutations.values()),
                    evidence_mutations,
                    {name: True for name in evidence_mutations},
                ),
                make_check(
                    "rule-contract-mutations-rejected",
                    True,
                    "pending second-pass self-test",
                ),
                make_check(
                    "readme-mutations-rejected",
                    all(readme_mutations.values()),
                    readme_mutations,
                    {name: True for name in readme_mutations},
                ),
            ],
            [
                "tests/test_build_evidence.py",
                "tests/test_azure_translator_backtranslate.py",
                "tests/test_set_public_network_access.py",
                "tests/test_submit_private_aci_probe.py",
                "tests/test_validate_repo.py",
                "scripts/build_evidence.py",
                "scripts/validate_repo.py",
                "README.md",
                "README-CN.md",
            ],
        ),
    ]
    document = {"schemaVersion": 1, "rules": rules}
    rule_mutations = run_rule_contract_mutation_checks(document)
    mutation_check = rules[-1]["checks"][1]
    mutation_check.update(
        passed=bool(rule_mutations) and all(rule_mutations.values()),
        actual=rule_mutations,
        expected={name: True for name in rule_mutations},
    )
    rules[-1]["status"] = (
        "PASS"
        if all(check["passed"] for check in rules[-1]["checks"])
        else "FAIL"
    )
    return document


def validate() -> list[str]:
    errors = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
    attributes = ROOT / ".gitattributes"
    if attributes.is_file() and attributes.read_text(encoding="utf-8").strip() != "*.json !filter !diff !merge text eol=lf":
        errors.append(".gitattributes must keep evidence JSON out of Git LFS")
    errors.extend(public_content_errors())

    if all((ROOT / path).is_file() for path in ("evidence/connectivity-run.json", "evidence/ui-evidence.json")):
        builder = load_evidence_builder()
        generated_connectivity = builder.render(builder.build_connectivity_run())
        if (ROOT / "evidence/connectivity-run.json").read_text(encoding="utf-8") != generated_connectivity:
            errors.append("evidence/connectivity-run.json is stale")
        errors.extend(validate_ui_evidence(load_json("evidence/ui-evidence.json")))

    try:
        generated = build_rule_results()
    except Exception as error:
        errors.append(f"rule evaluator failed: {error}")
        generated = None
    committed_path = ROOT / "evidence/rule-results.json"
    if generated is not None:
        if not committed_path.is_file():
            errors.append("missing evidence/rule-results.json")
        else:
            try:
                committed = json.loads(committed_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                errors.append(f"invalid evidence/rule-results.json: {error}")
            else:
                expected_applicability = {
                    rule["id"]: rule["applicable"] for rule in generated["rules"]
                }
                errors.extend(
                    validate_rule_results_document(
                        committed,
                        expected_applicability,
                    )
                )
                expected_text = json.dumps(
                    generated, indent=2, ensure_ascii=False
                ) + "\n"
                if committed_path.read_text(encoding="utf-8") != expected_text:
                    errors.append("evidence/rule-results.json is stale")
        for rule in generated["rules"]:
            if rule["status"] == "FAIL":
                errors.append(f"failed rule: {rule['id']}")
            print(f"RULE {rule['id']} {rule['status']} {len(rule['evidence'])}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-rule-results", action="store_true")
    parser.add_argument("--public-content-only", action="store_true")
    args = parser.parse_args()
    if args.public_content_only:
        errors = public_content_errors()
        if errors:
            for error in errors:
                print(f"ERROR {error}")
            return 1
        print("PUBLIC_CONTENT_AUDIT=PASS")
        return 0
    if args.write_rule_results:
        generated = build_rule_results()
        expected_applicability = {
            rule["id"]: rule["applicable"] for rule in generated["rules"]
        }
        validation_errors = validate_rule_results_document(
            generated,
            expected_applicability,
        )
        if validation_errors:
            for error in validation_errors:
                print(f"ERROR {error}")
            return 1
        output = json.dumps(generated, indent=2, ensure_ascii=False) + "\n"
        (ROOT / "evidence/rule-results.json").write_text(output, encoding="utf-8")
        print("RULE_RESULTS_WRITTEN")
        return 0

    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print("REPO_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
