#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path


REQUIRED_FIELDS = {
    "schema_version": int,
    "run.label": str,
    "model.family": str,
    "model.revision": str,
    "model.weights_sha256": str,
    "model.tokenizer_sha256": str,
    "model.precision": str,
    "agent.name": str,
    "agent.version": str,
    "agent.package_sha256": str,
    "agent.config_sha256": str,
    "agent.system_prompt_sha256": str,
    "agent.tool_schema_sha256": str,
    "agent.step_limit": int,
    "agent.cost_limit": (int, float),
    "agent.wall_time_limit_seconds": int,
    "dataset.name": str,
    "dataset.split": str,
    "dataset.revision": str,
    "dataset.manifest_sha256": str,
    "dataset.execution_images_sha256": str,
    "dataset.expected_cases": int,
    "harness.source_commit": str,
    "harness.python_lock_sha256": str,
    "harness.namespace": str,
    "harness.timeout_seconds": int,
    "harness.cache_level": str,
    "harness.clean": bool,
    "harness.workers": int,
    "generation.workers": int,
    "generation.temperature": (int, float),
    "generation.top_p": (int, float),
    "generation.max_output_tokens": int,
    "generation.seed": int,
    "generation.parallel_tool_calls": bool,
    "orchestration.partition_manifest_sha256": str,
    "orchestration.queue_policy": str,
    "orchestration.retry_policy": str,
    "endpoint.mode": str,
    "endpoint.protocol": str,
    "endpoint.base_url_pattern": str,
    "endpoint.auth_method": str,
    "endpoint.deployment_name": str,
    "endpoint.replay_adapter": str,
    "endpoint.content_filter_policy": str,
    "serving.deployment_type": str,
    "serving.billing_model": str,
    "serving.deployment_scope": str,
    "serving.runtime": str,
    "serving.runtime_version": str,
    "serving.deployment_template": str,
    "serving.deployment_template_version": str,
    "serving.version_upgrade_option": str,
    "serving.launcher_sha256": str,
    "serving.environment_sha256": str,
    "serving.accelerator_family": str,
    "serving.tensor_parallel": int,
    "serving.context_length": int,
    "serving.deterministic_inference": bool,
    "serving.sampling_backend": str,
    "evaluation.required_context_tokens": int,
}

IDENTITY_FIELDS = {
    "model.weights_sha256",
    "model.tokenizer_sha256",
    "agent.package_sha256",
    "agent.config_sha256",
    "agent.system_prompt_sha256",
    "agent.tool_schema_sha256",
    "dataset.manifest_sha256",
    "dataset.execution_images_sha256",
    "harness.python_lock_sha256",
    "orchestration.partition_manifest_sha256",
}

COMMON_ALLOWED_DIFFERENCES = {"run.label"}

SCENARIO_ALLOWED_DIFFERENCES = {
    "platform_migration": {
        "endpoint.mode",
        "endpoint.base_url_pattern",
        "endpoint.auth_method",
        "endpoint.deployment_name",
        "endpoint.replay_adapter",
        "endpoint.content_filter_policy",
        "serving.deployment_type",
        "serving.billing_model",
        "serving.deployment_scope",
        "serving.runtime",
        "serving.runtime_version",
        "serving.deployment_template",
        "serving.deployment_template_version",
        "serving.version_upgrade_option",
        "serving.launcher_sha256",
        "serving.environment_sha256",
        "serving.accelerator_family",
        "serving.tensor_parallel",
        "serving.context_length",
        "serving.deterministic_inference",
        "serving.sampling_backend",
    },
    "finetuning": {
        "model.revision",
        "model.weights_sha256",
        "endpoint.deployment_name",
    },
    "model_selection": {
        "model.family",
        "model.revision",
        "model.weights_sha256",
        "model.tokenizer_sha256",
        "model.precision",
        "endpoint.mode",
        "endpoint.base_url_pattern",
        "endpoint.auth_method",
        "endpoint.deployment_name",
        "endpoint.replay_adapter",
        "endpoint.content_filter_policy",
        "serving.deployment_type",
        "serving.billing_model",
        "serving.deployment_scope",
        "serving.runtime",
        "serving.runtime_version",
        "serving.deployment_template",
        "serving.deployment_template_version",
        "serving.version_upgrade_option",
        "serving.launcher_sha256",
        "serving.environment_sha256",
        "serving.accelerator_family",
        "serving.tensor_parallel",
        "serving.context_length",
        "serving.deterministic_inference",
        "serving.sampling_backend",
    },
}


def flatten(value, prefix="") -> dict[str, object]:
    flattened = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(flatten(item, path))
        else:
            flattened[path] = item
    return flattened


def load_contract(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        payload = tomllib.load(stream)
    flattened = flatten(payload)
    errors = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in flattened:
            errors.append(f"missing {field}")
            continue
        value = flattened[field]
        if isinstance(value, bool) and expected_type is not bool:
            errors.append(f"{field} has invalid boolean value")
        elif not isinstance(value, expected_type):
            errors.append(f"{field} has invalid type {type(value).__name__}")
    if flattened.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in IDENTITY_FIELDS:
        value = flattened.get(field)
        if value != "UNVERIFIED" and not re.fullmatch(r"[0-9a-f]{64}", str(value)):
            errors.append(f"{field} must be lowercase SHA-256 or UNVERIFIED")
    for field in (
        "agent.step_limit",
        "dataset.expected_cases",
        "harness.timeout_seconds",
        "harness.workers",
        "generation.workers",
        "generation.max_output_tokens",
        "serving.tensor_parallel",
        "serving.context_length",
        "evaluation.required_context_tokens",
    ):
        if isinstance(flattened.get(field), int) and flattened[field] <= 0:
            errors.append(f"{field} must be positive")
    if (
        isinstance(flattened.get("serving.context_length"), int)
        and isinstance(flattened.get("evaluation.required_context_tokens"), int)
        and flattened["serving.context_length"]
        < flattened["evaluation.required_context_tokens"]
    ):
        errors.append("serving.context_length is below evaluation.required_context_tokens")
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    return flattened


def write_report(path: Path | None, report: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare reference and candidate SWE-bench run contracts."
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIO_ALLOWED_DIFFERENCES),
        required=True,
    )
    parser.add_argument("--allow-difference", action="append", default=[])
    parser.add_argument("--accept-adapted", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        reference = load_contract(args.reference)
        candidate = load_contract(args.candidate)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise SystemExit(f"PARITY_CONTRACT_INVALID: {error}") from error

    fields = sorted(set(reference) | set(candidate))
    differences = [
        {
            "field": field,
            "reference": reference.get(field),
            "candidate": candidate.get(field),
        }
        for field in fields
        if reference.get(field) != candidate.get(field)
    ]
    scenario_allowed = (
        COMMON_ALLOWED_DIFFERENCES | SCENARIO_ALLOWED_DIFFERENCES[args.scenario]
    )
    custom_allowed = set(args.allow_difference)
    known_fields = set(REQUIRED_FIELDS)
    unknown_allowances = sorted(custom_allowed - known_fields)
    if unknown_allowances:
        raise SystemExit(
            "Unknown --allow-difference fields: " + ", ".join(unknown_allowances)
        )

    unverified_identity_differences = {
        difference["field"]
        for difference in differences
        if difference["field"] in IDENTITY_FIELDS
        and (
            difference["reference"] == "UNVERIFIED"
            or difference["candidate"] == "UNVERIFIED"
        )
    }
    violations = [
        difference
        for difference in differences
        if difference["field"] not in scenario_allowed | custom_allowed
        and difference["field"] not in unverified_identity_differences
    ]
    custom_adaptations = [
        difference
        for difference in differences
        if difference["field"] in custom_allowed
        and difference["field"] not in scenario_allowed
    ]
    unverified = sorted(
        {
            field
            for field in IDENTITY_FIELDS
            if reference[field] == "UNVERIFIED" or candidate[field] == "UNVERIFIED"
        }
    )

    if violations:
        classification = "NOT_COMPARABLE"
        state = "FAIL"
    elif custom_adaptations:
        classification = "ADAPTED_RUN"
        state = "PASS" if args.accept_adapted else "REVIEW_REQUIRED"
    elif unverified:
        classification = "METHOD_ALIGNED"
        state = "PASS"
    elif args.scenario == "finetuning":
        classification = "FINETUNING_METHOD_ALIGNED"
        state = "PASS"
    elif args.scenario == "model_selection":
        classification = "MODEL_SELECTION_METHOD_ALIGNED"
        state = "PASS"
    else:
        classification = "MODEL_AND_METHOD_ALIGNED"
        state = "PASS"

    report = {
        "schema_version": 1,
        "scenario": args.scenario,
        "state": state,
        "classification": classification,
        "reference_label": reference["run.label"],
        "candidate_label": candidate["run.label"],
        "differences": differences,
        "scenario_allowed_differences": sorted(scenario_allowed),
        "custom_adaptations": custom_adaptations,
        "violations": violations,
        "unverified_identity_fields": unverified,
        "context_gate": {
            "required_tokens": reference["evaluation.required_context_tokens"],
            "reference_capacity": reference["serving.context_length"],
            "candidate_capacity": candidate["serving.context_length"],
        },
    }
    write_report(args.output, report)
    print(
        f"PARITY_GATE={state} scenario={args.scenario} "
        f"classification={classification} differences={len(differences)} "
        f"violations={len(violations)} unverified={len(unverified)}"
    )
    if violations:
        for violation in violations:
            print(f"VIOLATION {violation['field']}", file=sys.stderr)
        raise SystemExit(4)
    if custom_adaptations and not args.accept_adapted:
        for adaptation in custom_adaptations:
            print(f"ADAPTATION {adaptation['field']}", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()