#!/usr/bin/env python3
"""Build the public connectivity result from sanitized raw observations."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "evidence" / "raw"
OUTPUT = ROOT / "evidence" / "connectivity-run.json"
CLI_OUTPUT = ROOT / "evidence" / "cli-transcript.txt"
PROVENANCE = ROOT / "evidence" / "provenance.json"
RAW_FILES = (
    "control-plane.json",
    "public-baseline.json",
    "private-preflight.json",
    "public-blocked.json",
    "private-success.json",
    "public-restored.json",
    "post-test-state.json",
)
TEXT_HASH_SUFFIXES = {".bicep", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}
FINGERPRINT_FIELDS = (
    "probeSourceSha256",
    "identitySha256",
    "endpointSha256",
    "deploymentSha256",
    "requestSha256",
)
# Never emitted by the measured probe; their presence in a raw scenario is a provenance leak.
DERIVED_ONLY_FIELDS = FINGERPRINT_FIELDS[1:]
PUBLIC_SCENARIOS = ("public-baseline.json", "public-blocked.json", "public-restored.json")
PRIVATE_SCENARIOS = ("private-preflight.json", "private-success.json")


def sha256(path: pathlib.Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_HASH_SUFFIXES:
        text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_raw(raw_dir: pathlib.Path, name: str) -> dict[str, object]:
    return json.loads((raw_dir / name).read_text(encoding="utf-8"))


def parse_observed_time(observation: dict[str, object]) -> dt.datetime:
    value = dt.datetime.fromisoformat(str(observation.get("observedAtUtc", "")))
    if value.tzinfo is None:
        raise ValueError("observedAtUtc must include a timezone")
    return value


def validate_observations(observations: dict[str, dict[str, object]]) -> None:
    if set(observations) != set(RAW_FILES):
        raise ValueError("raw observation set is incomplete or contains duplicates")
    control = observations["control-plane.json"]
    public_baseline = observations["public-baseline.json"]
    private_preflight = observations["private-preflight.json"]
    public_blocked = observations["public-blocked.json"]
    private_success = observations["private-success.json"]
    public_restored = observations["public-restored.json"]
    post_test_state = observations["post-test-state.json"]
    if not (
        control.get("schemaVersion") == 1
        and control.get("sourceType") == "sanitized-live-observation"
        and isinstance(control.get("runId"), str)
        and control.get("runId")
        and isinstance(control.get("dateUtc"), str)
        and control.get("dateUtc")
        and isinstance(control.get("target"), dict)
        and isinstance(control.get("request"), dict)
    ):
        raise ValueError("control-plane observation has an invalid run contract")
    target_model = control["target"].get("model")
    if not isinstance(target_model, str) or not target_model:
        raise ValueError("control-plane target model is missing")
    scenario_ids = [
        public_baseline.get("id"),
        private_preflight.get("id"),
        public_blocked.get("id"),
        private_success.get("id"),
        public_restored.get("id"),
    ]
    if scenario_ids != [
        "public-baseline",
        "private-preflight",
        "public-blocked",
        "private-success",
        "public-restored",
    ]:
        raise ValueError("scenario identity is missing, duplicated, or out of order")
    scenario_sequence = [
        public_baseline.get("sequence"),
        private_preflight.get("sequence"),
        public_blocked.get("sequence"),
        private_success.get("sequence"),
        public_restored.get("sequence"),
    ]
    if scenario_sequence != [1, 2, 3, 4, 5]:
        raise ValueError("scenario sequence is missing, duplicated, or out of order")
    scenario_times = [
        parse_observed_time(observation)
        for observation in (
            public_baseline,
            private_preflight,
            public_blocked,
            private_success,
            public_restored,
        )
    ]
    if scenario_times != sorted(scenario_times) or len(set(scenario_times)) != 5:
        raise ValueError("scenario observation times are not strictly increasing")
    if any(
        observation.get("runId") != control["runId"]
        for observation in (
            public_baseline,
            private_preflight,
            public_blocked,
            private_success,
            public_restored,
            post_test_state,
        )
    ):
        raise ValueError("raw observation run identity does not match the control plane")
    if any(
        observation.get("sourceType") != "sanitized-live-observation"
        or observation.get("status") != "PASS"
        for observation in (
            public_baseline,
            private_preflight,
            public_blocked,
            private_success,
            public_restored,
        )
    ):
        raise ValueError("scenario source type or status is invalid")
    fingerprints = control.get("derivedFingerprints")
    if not isinstance(fingerprints, dict) or any(
        not isinstance(fingerprints.get(field), str)
        or len(fingerprints[field]) != 64
        for field in FINGERPRINT_FIELDS
    ):
        raise ValueError("control-plane fingerprint chain is incomplete")
    if (
        fingerprints.get("class") != "derived-post-run"
        or fingerprints.get("emittedByMeasuredProbe") is not False
        or not isinstance(fingerprints.get("basis"), str)
        or not isinstance(fingerprints.get("formulas"), dict)
        or set(fingerprints["formulas"]) != set(FINGERPRINT_FIELDS)
        or parse_observed_time({"observedAtUtc": fingerprints.get("derivedAtUtc")})
        <= scenario_times[-1]
    ):
        raise ValueError("control-plane fingerprint chain is not labeled as post-run derived")
    for name in RAW_FILES[1:6]:
        leaked = [field for field in DERIVED_ONLY_FIELDS if field in observations[name]]
        if leaked:
            raise ValueError(f"derived fingerprint leaked into raw observation {name}: {leaked}")
    for name in PUBLIC_SCENARIOS:
        if "probeSourceSha256" in observations[name]:
            raise ValueError(f"derived fingerprint leaked into raw observation {name}: probeSourceSha256")
    for name in PRIVATE_SCENARIOS:
        if observations[name].get("probeSourceSha256") != fingerprints["probeSourceSha256"]:
            raise ValueError("scenario fingerprint chain does not match")
        if not isinstance(observations[name].get("probeSourceSha256Basis"), str):
            raise ValueError(f"{name} probeSourceSha256 has no stated basis")
    if not (
        public_baseline.get("parentPublicNetworkAccess") == "Enabled"
        and public_baseline.get("dnsClass") == "public"
        and public_baseline.get("httpStatus") == 200
        and public_baseline.get("responseObject") == "chat.completion"
        and public_baseline.get("responseModel") == target_model
        and public_baseline.get("choiceCount", 0) > 0
    ):
        raise ValueError("public-baseline observation is not an authenticated public 200")
    if not (
        private_preflight.get("parentPublicNetworkAccess") == "Enabled"
        and private_preflight.get("dnsClass") == "private"
        and private_preflight.get("httpStatus") == 200
        and private_preflight.get("responseObject") == "chat.completion"
        and private_preflight.get("responseModel") == target_model
        and private_preflight.get("choiceCount", 0) > 0
        and private_preflight.get("runnerExitCode") == 0
    ):
        raise ValueError("private-preflight observation is not a private HTTP 200 safety check")
    if not (
        public_blocked.get("dnsClass") == "public"
        and public_blocked.get("httpStatus") == 403
        and public_blocked.get("errorCategory") == "public-access-disabled"
        and public_blocked.get("networkPolicyBlocked") is True
        and isinstance(public_blocked.get("requestIdSha256"), str)
        and len(public_blocked["requestIdSha256"]) == 64
    ):
        raise ValueError("public-blocked observation is not an authenticated 403 policy rejection")
    if not (
        private_success.get("dnsClass") == "private"
        and private_success.get("httpStatus") == 200
        and private_success.get("runnerExitCode") == 0
        and private_success.get("responseObject") == "chat.completion"
        and private_success.get("responseModel") == target_model
        and private_success.get("choiceCount", 0) > 0
        and isinstance(private_success.get("usage"), dict)
        and private_success["usage"].get("totalTokens", 0) > 0
        and isinstance(private_success.get("requestIdSha256"), str)
        and len(private_success["requestIdSha256"]) == 64
    ):
        raise ValueError(
            "private-success observation is not private DNS plus a valid Chat Completions response"
        )
    if not (
        public_restored.get("dnsClass") == "public"
        and public_restored.get("httpStatus") == 200
        and public_restored.get("responseObject") == "chat.completion"
        and public_restored.get("responseModel") == target_model
        and public_restored.get("choiceCount", 0) > 0
        and isinstance(public_restored.get("requestIdSha256"), str)
        and len(public_restored["requestIdSha256"]) == 64
    ):
        raise ValueError("public-restored observation is not a valid public HTTP 200 response")
    if private_preflight.get("probeSourceSha256") != private_success.get(
        "probeSourceSha256"
    ):
        raise ValueError("private probes did not execute the same source")
    if not (
        post_test_state.get("sourceType") == "sanitized-live-management-read"
        and post_test_state.get("captureDateUtc") == control.get("dateUtc")
        and parse_observed_time(post_test_state) > scenario_times[-1]
        and post_test_state.get("parentPublicNetworkAccess") == "Enabled"
        and post_test_state.get("parentProvisioningState") == "Succeeded"
        and post_test_state.get("approvedAccountPrivateEndpointConnectionCount") == 1
        and post_test_state.get("managedComputeProvisioningState") == "Succeeded"
        and post_test_state.get("temporaryResourcesRetained") is True
        and post_test_state.get("cleanupStatus") == "AWAITING_USER"
        and post_test_state.get("billingContinues") is True
        and all(
            container.get("provisioningState") == "Succeeded"
            and container.get("state") == "Terminated"
            and container.get("exitCode") == 0
            for container in post_test_state.get("containerGroups", [])
        )
        and len(post_test_state.get("containerGroups", [])) == 2
        and post_test_state.get("status") == "PASS"
    ):
        raise ValueError("post-test observation is not the declared retained safe state")


def build_cli_transcript(raw_dir: pathlib.Path = RAW_DIR) -> str:
    observations = {name: load_raw(raw_dir, name) for name in RAW_FILES}
    validate_observations(observations)
    control = observations["control-plane.json"]
    public_baseline = observations["public-baseline.json"]
    private_preflight = observations["private-preflight.json"]
    public_blocked = observations["public-blocked.json"]
    private_success = observations["private-success.json"]
    public_restored = observations["public-restored.json"]
    request = control["request"]
    target = control["target"]
    usage = private_success["usage"]
    fingerprints = control["derivedFingerprints"]
    measured_source = json.loads(PROVENANCE.read_text(encoding="utf-8"))["measuredProbeSource"]
    lines = [
        "CODE_PATH_EVIDENCE",
        f"RUN_ID={control['runId']}",
        f"DATE_UTC={control['dateUtc']}",
        "EVIDENCE_CLASS=derived-sanitized-view-of-live-code-observations",
        "ORIGINAL_TERMINAL_CAPTURE=false",
        "CLIENT=Python HTTPS client with Microsoft Entra bearer token",
        "ACTUAL_PROBE_OUTPUT_RETAINED=true",
        "REPRODUCTION_ENTRYPOINT=scripts/probe_endpoint.py (current version; not the bytes that ran)",
        f"MEASURED_PROBE_COMMIT={measured_source['repositoryBaselineCommit']}",
        f"MEASURED_PROBE_RETRIEVAL={measured_source['retrieval']}",
        f"MEASURED_PROBE_EXECUTED_BYTES_SHA256={measured_source['executionBytesSha256']} (CRLF checkout)",
        f"MEASURED_PROBE_LF_SHA256={measured_source['lfCanonicalSha256']}",
        "MODEL_DEPLOYMENT_CHANGED=false",
        f"FINGERPRINT_CLASS={fingerprints['class']}",
        f"FINGERPRINTS_EMITTED_BY_MEASURED_PROBE={str(fingerprints['emittedByMeasuredProbe']).lower()}",
        f"FINGERPRINTS_DERIVED_AT_UTC={fingerprints['derivedAtUtc']}",
        f"PROBE_SOURCE_SHA256={fingerprints['probeSourceSha256']}",
        f"IDENTITY_SHA256={fingerprints['identitySha256']}",
        f"ENDPOINT_SHA256={fingerprints['endpointSha256']}",
        f"DEPLOYMENT_SHA256={fingerprints['deploymentSha256']}",
        f"REQUEST_SHA256={fingerprints['requestSha256']}",
        "NETWORK_CONTROL=parent Foundry account public network access plus Private Endpoint",
        "PRIVATE_RUNNER=private-IP Azure Container Instances in a linked VNet workload subnet (not Bastion)",
        "PRIVATE_PATH_EVIDENCE=dnsClass=private only; resolved address not compared with the Private Endpoint NIC",
        f"ENDPOINT={target['endpointPattern']}",
        "DEPLOYMENT=<managed-compute-deployment>",
        f"PROMPT={json.dumps(request['prompt'], ensure_ascii=False)}",
        f"MAX_TOKENS={request['maxTokens']}",
        f"TEMPERATURE={request['temperature']}",
        "",
        "REPRODUCTION_CLI=python scripts/probe_endpoint.py --endpoint <endpoint> --deployment <deployment> --expect-dns <public|private> --expect-http <status> --prompt \"Reply with exactly OK.\" --max-tokens 4",
        "",
        "[1/5] OUTSIDE_VNET_PNA_ENABLED_BASELINE",
        f"OBSERVED_AT_UTC={public_baseline['observedAtUtc']}",
        f"DNS_CLASS={public_baseline['dnsClass']}",
        f"HTTP_STATUS={public_baseline['httpStatus']}",
        f"RESPONSE_OBJECT={public_baseline['responseObject']}",
        f"RESPONSE_MODEL={public_baseline['responseModel']}",
        "RESULT=PASS",
        "SOURCE=evidence/raw/public-baseline.json",
        "",
        "[2/5] INSIDE_LINKED_VNET_PNA_ENABLED_PREFLIGHT",
        f"OBSERVED_AT_UTC={private_preflight['observedAtUtc']}",
        f"DNS_CLASS={private_preflight['dnsClass']}",
        f"HTTP_STATUS={private_preflight['httpStatus']}",
        f"RESPONSE_OBJECT={private_preflight['responseObject']}",
        f"RUNNER_EXIT_CODE={private_preflight['runnerExitCode']}",
        f"PROBE_SOURCE_SHA256={private_preflight['probeSourceSha256']} (launcher receipt)",
        "RESULT=PASS",
        "SOURCE=evidence/raw/private-preflight.json",
        "",
        "[3/5] OUTSIDE_VNET_PNA_DISABLED",
        f"OBSERVED_AT_UTC={public_blocked['observedAtUtc']}",
        f"DNS_CLASS={public_blocked['dnsClass']}",
        f"HTTP_STATUS={public_blocked['httpStatus']}",
        f"ERROR_CATEGORY={public_blocked['errorCategory']}",
        f"NETWORK_POLICY_BLOCKED={str(public_blocked['networkPolicyBlocked']).lower()}",
        f"REQUEST_ID_SHA256={public_blocked['requestIdSha256']}",
        "RESULT=PASS",
        "SOURCE=evidence/raw/public-blocked.json",
        "",
        "[4/5] INSIDE_LINKED_VNET_PNA_DISABLED",
        f"OBSERVED_AT_UTC={private_success['observedAtUtc']}",
        f"DNS_CLASS={private_success['dnsClass']}",
        f"HTTP_STATUS={private_success['httpStatus']}",
        f"RESPONSE_OBJECT={private_success['responseObject']}",
        f"RESPONSE_MODEL={private_success['responseModel']}",
        f"PROBE_SOURCE_SHA256={private_success['probeSourceSha256']} (launcher receipt)",
        f"TOKENS=prompt:{usage['promptTokens']} completion:{usage['completionTokens']} total:{usage['totalTokens']}",
        f"RUNNER_EXIT_CODE={private_success['runnerExitCode']}",
        f"REQUEST_ID_SHA256={private_success['requestIdSha256']}",
        "RESULT=PASS",
        "SOURCE=evidence/raw/private-success.json",
        "",
        "[5/5] OUTSIDE_VNET_PNA_RESTORED",
        f"OBSERVED_AT_UTC={public_restored['observedAtUtc']}",
        f"DNS_CLASS={public_restored['dnsClass']}",
        f"HTTP_STATUS={public_restored['httpStatus']}",
        f"RESPONSE_MODEL={public_restored['responseModel']}",
        f"REQUEST_ID_SHA256={public_restored['requestIdSha256']}",
        "RESULT=PASS",
        "SOURCE=evidence/raw/public-restored.json",
    ]
    return "\n".join(lines) + "\n"


def build_connectivity_run(raw_dir: pathlib.Path = RAW_DIR) -> dict[str, object]:
    observations = {name: load_raw(raw_dir, name) for name in RAW_FILES}
    validate_observations(observations)
    control = observations["control-plane.json"]
    scenarios = [
        observations["public-baseline.json"],
        observations["private-preflight.json"],
        observations["public-blocked.json"],
        observations["private-success.json"],
        observations["public-restored.json"],
    ]
    cli_transcript = build_cli_transcript(raw_dir)
    return {
        "schemaVersion": 1,
        "runId": control["runId"],
        "dateUtc": control["dateUtc"],
        "scope": "Single-run inbound connectivity differential",
        "target": control["target"],
        "request": control["request"],
        "derivedFingerprints": control["derivedFingerprints"],
        "controlPlane": control["controlPlane"],
        "scenarios": scenarios,
        "postTestState": observations["post-test-state.json"],
        "doesNotProve": control["doesNotProve"],
        "codeEvidence": {
            "path": "evidence/cli-transcript.txt",
            "sha256": hashlib.sha256(cli_transcript.encode("utf-8")).hexdigest(),
            "evidenceClass": "derived-sanitized-view-of-live-code-observations",
        },
        "provenance": {
            "path": "evidence/provenance.json",
            "sha256": sha256(PROVENANCE),
            "publicEvidenceClass": json.loads(
                PROVENANCE.read_text(encoding="utf-8")
            )["publicEvidenceClass"],
        },
        "lineage": {
            "producer": "scripts/build_evidence.py",
            "hashCanonicalization": "UTF-8 text normalized to LF; binary assets use raw bytes",
            "rawSha256": {
                f"raw/{name}": sha256(raw_dir / name) for name in RAW_FILES
            },
            "executableSha256": {
                "infra/main.bicep": sha256(ROOT / "infra" / "main.bicep"),
                "scripts/build_evidence.py": sha256(
                    ROOT / "scripts" / "build_evidence.py"
                ),
                "scripts/azure_translator_backtranslate.py": sha256(
                    ROOT / "scripts" / "azure_translator_backtranslate.py"
                ),
                "scripts/probe_endpoint.py": sha256(ROOT / "scripts" / "probe_endpoint.py"),
                "scripts/submit_private_aci_probe.py": sha256(
                    ROOT / "scripts" / "submit_private_aci_probe.py"
                ),
                "scripts/set_public_network_access.py": sha256(
                    ROOT / "scripts" / "set_public_network_access.py"
                ),
                "scripts/validate_repo.py": sha256(
                    ROOT / "scripts" / "validate_repo.py"
                ),
                "evidence/run-contract.json": sha256(
                    ROOT / "evidence" / "run-contract.json"
                ),
                "evidence/provenance.json": sha256(PROVENANCE),
            },
        },
    }


def render(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = render(build_connectivity_run())
    cli_output = build_cli_transcript()
    if args.write:
        OUTPUT.write_text(output, encoding="utf-8", newline="\n")
        CLI_OUTPUT.write_text(cli_output, encoding="utf-8", newline="\n")
        print("CONNECTIVITY_EVIDENCE_WRITTEN")
        print("CLI_EVIDENCE_WRITTEN")
    if args.check:
        stale = False
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != output:
            print("CONNECTIVITY_EVIDENCE_STALE")
            stale = True
        if not CLI_OUTPUT.is_file() or CLI_OUTPUT.read_text(encoding="utf-8") != cli_output:
            print("CLI_EVIDENCE_STALE")
            stale = True
        if stale:
            return 1
        print("CONNECTIVITY_EVIDENCE_SYNC=PASS")
        print("CLI_EVIDENCE_SYNC=PASS")
    if not args.write and not args.check:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
