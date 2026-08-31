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
    "tests/test_probe_endpoint.py",
    "tests/test_submit_private_aci_probe.py",
    "tests/test_set_public_network_access.py",
    "tests/test_build_evidence.py",
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
    ("clone-and-test", ("git clone --filter=blob:none --sparse", "python -m unittest discover -s tests -v")),
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
    ("does not prove that managed pods are injected", "不能证明托管 Pod 被注入"),
    ("Managed Compute egress traverses", "Managed Compute 出站流量"),
    ("prompts or completions have zero retention", "Prompt/Completion 零留存"),
    ("Temporary resources remain", "临时资源仍保留"),
    ("billing continues", "继续计费"),
    ("private-IP ACI", "private-IP ACI"),
    ("not Azure Bastion", "不是 Azure Bastion"),
    ("do not hard-code `Enabled`", "不要把目标值硬编码为 `Enabled`"),
    ("parent Foundry account", "所属 Foundry account"),
    ("earliest **public-safe sanitized", "最早一层**可公开的脱敏观测"),
    ("dedicated non-production Foundry account", "专用的非生产 Foundry account"),
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


def image_paths(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)


def extract_cli_evidence(text: str) -> str | None:
    match = re.search(
        r"<!-- BEGIN GENERATED CLI EVIDENCE -->\s*```text\s*\n(.*?)```\s*<!-- END GENERATED CLI EVIDENCE -->",
        text,
        flags=re.DOTALL,
    )
    return match.group(1) if match else None


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
        elif hashlib.sha256(image_path.read_bytes()).hexdigest() != image.get("sha256"):
            errors.append(f"UI image hash mismatch: {relative_path}")
        if not image.get("proves") or not image.get("doesNotProve"):
            errors.append(f"UI image claim boundary is incomplete: {relative_path}")
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
            "public-restored.json"
        ].update(identitySha256="0" * 64),
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
            lambda value: value["rules"][0]["checks"][0].update(passed=False)
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
    ui = load_json("evidence/ui-evidence.json")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README-CN.md").read_text(encoding="utf-8")
    cli_transcript = (ROOT / "evidence/cli-transcript.txt").read_text(encoding="utf-8")
    scenario_list = run["scenarios"]
    scenarios = {item["id"]: item for item in run["scenarios"]}
    quick_start = quick_start_stage_results(readme)
    lineage = run.get("lineage", {}).get("executableSha256", {})
    expected_lineage_paths = (
        "infra/main.bicep",
        "scripts/build_evidence.py",
        "scripts/probe_endpoint.py",
        "scripts/submit_private_aci_probe.py",
        "scripts/set_public_network_access.py",
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
                    "generated-cli-evidence-synchronized",
                    extract_cli_evidence(readme) == cli_transcript
                    and extract_cli_evidence(readme_cn) == cli_transcript,
                    {
                        "english": extract_cli_evidence(readme) == cli_transcript,
                        "chinese": extract_cli_evidence(readme_cn) == cli_transcript,
                    },
                ),
                make_check(
                    "five-stage-fingerprint-chain",
                    all(
                        all(
                            scenario.get(field) == run["fingerprints"].get(field)
                            for field in (
                                "probeSourceSha256",
                                "identitySha256",
                                "endpointSha256",
                                "deploymentSha256",
                                "requestSha256",
                            )
                        )
                        for scenario in scenario_list
                    ),
                    {
                        scenario["id"]: all(
                            scenario.get(field) == run.get("fingerprints", {}).get(field)
                            for field in (
                                "probeSourceSha256",
                                "identitySha256",
                                "endpointSha256",
                                "deploymentSha256",
                                "requestSha256",
                            )
                        )
                        for scenario in scenario_list
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
            "The PNA transition and Private Endpoint prerequisite are recorded.",
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
            "English and Chinese preserve facts, assets, boundaries, and commands.",
            [
                make_check(
                    "bilingual-fact-ledger",
                    all(
                        english in readme and chinese in readme_cn
                        for english, chinese in BILINGUAL_FACTS
                    ),
                    {
                        english: english in readme and chinese in readme_cn
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
            ],
            ["README.md", "README-CN.md", "evidence/run-contract.json"],
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
            ],
            [
                "tests/test_build_evidence.py",
                "tests/test_set_public_network_access.py",
                "tests/test_submit_private_aci_probe.py",
                "tests/test_validate_repo.py",
                "scripts/build_evidence.py",
                "scripts/validate_repo.py",
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
    text_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".repo-evidence" not in path.parts
        and path.suffix.lower() in {".md", ".py", ".json", ".bicep", ".txt", ".yml"}
    ]
    for path in text_files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"{label} in {path.relative_to(ROOT)}")

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
    args = parser.parse_args()
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
