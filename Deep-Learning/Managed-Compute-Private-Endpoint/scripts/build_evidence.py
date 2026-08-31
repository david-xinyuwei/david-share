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
PROVENANCE = ROOT / "evidence" / "provenance.json"
RAW_FILES = (
    "control-plane.json",
    "public-blocked.json",
    "private-success.json",
    "public-restored.json",
    "cleanup.json",
)
TEXT_HASH_SUFFIXES = {".bicep", ".json", ".md", ".py", ".txt", ".yaml", ".yml"}


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
    public_blocked = observations["public-blocked.json"]
    private_success = observations["private-success.json"]
    public_restored = observations["public-restored.json"]
    cleanup = observations["cleanup.json"]
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
        public_blocked.get("id"),
        private_success.get("id"),
        public_restored.get("id"),
    ]
    if scenario_ids != ["public-blocked", "private-success", "public-restored"]:
        raise ValueError("scenario identity is missing, duplicated, or out of order")
    scenario_sequence = [
        public_blocked.get("sequence"),
        private_success.get("sequence"),
        public_restored.get("sequence"),
    ]
    if scenario_sequence != [1, 2, 3]:
        raise ValueError("scenario sequence is missing, duplicated, or out of order")
    scenario_times = [
        parse_observed_time(observation)
        for observation in (public_blocked, private_success, public_restored)
    ]
    if scenario_times != sorted(scenario_times) or len(set(scenario_times)) != 3:
        raise ValueError("scenario observation times are not strictly increasing")
    if any(
        observation.get("runId") != control["runId"]
        for observation in (public_blocked, private_success, public_restored, cleanup)
    ):
        raise ValueError("raw observation run identity does not match the control plane")
    if any(
        observation.get("sourceType") != "sanitized-live-observation"
        or observation.get("status") != "PASS"
        for observation in (public_blocked, private_success, public_restored)
    ):
        raise ValueError("scenario source type or status is invalid")
    if not (
        public_blocked.get("dnsClass") == "public"
        and public_blocked.get("httpStatus") == 403
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
        and public_restored.get("responseModel") == target_model
        and isinstance(public_restored.get("requestIdSha256"), str)
        and len(public_restored["requestIdSha256"]) == 64
    ):
        raise ValueError("public-restored observation is not a valid public HTTP 200 response")
    if not (
        cleanup.get("sourceType") == "sanitized-live-management-read"
        and cleanup.get("captureDateUtc") == control.get("dateUtc")
        and parse_observed_time(cleanup) > scenario_times[-1]
        and cleanup.get("temporaryResourceCount") == 0
        and cleanup.get("parentPublicNetworkAccess") == "Enabled"
        and cleanup.get("parentProvisioningState") == "Succeeded"
        and cleanup.get("parentPrivateEndpointConnectionCount") == 0
        and cleanup.get("status") == "PASS"
    ):
        raise ValueError("cleanup observation is not the declared safe final state")


def build_connectivity_run(raw_dir: pathlib.Path = RAW_DIR) -> dict[str, object]:
    observations = {name: load_raw(raw_dir, name) for name in RAW_FILES}
    validate_observations(observations)
    control = observations["control-plane.json"]
    scenarios = [
        observations["public-blocked.json"],
        observations["private-success.json"],
        observations["public-restored.json"],
    ]
    return {
        "schemaVersion": 1,
        "runId": control["runId"],
        "dateUtc": control["dateUtc"],
        "scope": "Single-run inbound connectivity differential",
        "target": control["target"],
        "request": control["request"],
        "controlPlane": control["controlPlane"],
        "scenarios": scenarios,
        "cleanup": observations["cleanup.json"],
        "doesNotProve": control["doesNotProve"],
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
                "scripts/probe_endpoint.py": sha256(ROOT / "scripts" / "probe_endpoint.py"),
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
    if args.write:
        OUTPUT.write_text(output, encoding="utf-8", newline="\n")
        print("CONNECTIVITY_EVIDENCE_WRITTEN")
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != output:
            print("CONNECTIVITY_EVIDENCE_STALE")
            return 1
        print("CONNECTIVITY_EVIDENCE_SYNC=PASS")
    if not args.write and not args.check:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
