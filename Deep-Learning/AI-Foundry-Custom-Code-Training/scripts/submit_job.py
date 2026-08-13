"""Plan, validate, or submit the verified Foundry GRPO job contract.

`plan` is offline and has no side effects. `validate` uploads versioned code/data assets,
builds the same CommandJob, runs the SDK's `validate().try_raise()` gate, and stops before
submission. `submit` performs those steps and calls `create_or_update()`.

The training payload remains the upstream Microsoft sample pinned in job_contract.py; this
adapter does not fork the trainer, dataset, reward function, or tool definitions.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from job_contract import (
    Contract,
    ContractError,
    build_contract,
    load_json_object,
    validate_overrides,
    validate_sample_layout,
)
from preflight import (
    DEFAULT_INPUT_MANIFEST,
    build_preflight_report,
    create_upload_snapshot,
    require_upload_tree_unchanged,
    write_json_atomic,
)

# Copied from the access-controlled product notebook pinned in job_contract.py. It selects
# the product's preview bootstrapper; it is not a customer registry or credential.
UPSTREAM_BOOTSTRAPPER_CONFIG = (
    '{"capabilities_registry":{"registry":{"url":"foundrycommandjobpreview.azurecr.io",'
    '"username":null,"password":null},"repo_prefix":"cr2026051502_singularity_bootstrapper",'
    '"regional_tag_prefix":false}}'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("plan", "validate", "submit"), default="plan")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--overrides", required=True, type=Path)
    parser.add_argument("--sample-dir", required=True, type=Path)
    parser.add_argument(
        "--expected-input-manifest",
        type=Path,
        default=DEFAULT_INPUT_MANIFEST,
        help="Measured input identity; any byte drift fails before upload",
    )
    parser.add_argument("--evidence", type=Path, default=Path("run-output/submission.json"))
    parser.add_argument("--credential", choices=("default", "azure-cli"), default="default")
    parser.add_argument("--tenant-id", help="Optional tenant constraint for AzureCliCredential")
    parser.add_argument("--allow-placeholders", action="store_true", help="Only valid with --action plan")
    return parser.parse_args()


def _sdk_imports() -> dict[str, Any]:
    try:
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import (
            CommandJob,
            Input,
            JobResourceConfiguration,
            Output,
            RayDistribution,
        )
        from azure.identity import AzureCliCredential, DefaultAzureCredential
    except ImportError as error:
        raise ContractError(
            "Foundry SDK is not installed; run `pip install -r requirements.txt`"
        ) from error
    return locals()


def make_credential(sdk: dict[str, Any], mode: str, tenant_id: str | None) -> Any:
    if tenant_id and mode != "azure-cli":
        raise ContractError("--tenant-id requires --credential azure-cli")
    if mode == "azure-cli":
        kwargs: dict[str, Any] = {"process_timeout": 120}
        if tenant_id:
            kwargs["tenant_id"] = tenant_id
        return sdk["AzureCliCredential"](**kwargs)
    return sdk["DefaultAzureCredential"]()


def close_resources(client: Any, credential: Any) -> list[str]:
    warnings: list[str] = []
    if client is not None:
        try:
            client.close()
        except Exception as error:
            warnings.append(f"client.close failed: {type(error).__name__}: {error}")
    close = getattr(credential, "close", None)
    if callable(close):
        try:
            close()
        except Exception as error:
            warnings.append(f"credential.close failed: {type(error).__name__}: {error}")
    for warning in warnings:
        print(f"CLEANUP_WARNING: {warning}", file=sys.stderr)
    return warnings


def sdk_job_from_contract(sdk: dict[str, Any], config: dict[str, Any], contract: Contract) -> Any:
    inputs = {name: sdk["Input"](**value) for name, value in contract.inputs.items()}
    outputs = {name: sdk["Output"](**value) for name, value in contract.outputs.items()}
    environment = dict(contract.environment)
    environment.update(
        {
            "AZUREML_CR_BOOTSTRAPPER_CONFIG_OVERRIDE": UPSTREAM_BOOTSTRAPPER_CONFIG,
            "SINGULARITY_SIDECAR_CONSOLIDATION": "false",
        }
    )
    distribution = contract.distribution
    return sdk["CommandJob"](
        display_name=(
            f"verl-retail-grpo-{config['nodeCount']}node-{config['gpusPerNode']}gpu"
        ),
        description=contract.metadata["description"],
        command=contract.command,
        environment_image_reference=config["environmentImage"],
        compute=config["computeId"],
        resources=sdk["JobResourceConfiguration"](**contract.resources),
        inputs=inputs,
        outputs=outputs,
        environment_variables=environment,
        user_assigned_identity_id=config["uamiId"],
        distribution=sdk["RayDistribution"](
            port=distribution["port"],
            include_dashboard=distribution["include_dashboard"],
            head_node_additional_args=distribution["head_node_additional_args"],
            worker_node_additional_args=distribution["worker_node_additional_args"],
        ),
        properties={"_azureml.LogTrainingMetricsToAzMon": "true"},
        tags={"scenario": "verl-retail-grpo", "agent": "Qwen/Qwen3-14B"},
    )


def main() -> int:
    args = parse_args()
    if args.allow_placeholders and args.action != "plan":
        print("SUBMIT_FAIL: --allow-placeholders is restricted to --action plan")
        return 1

    config_path = args.config.resolve()
    overrides_path = args.overrides.resolve()
    sample_dir = args.sample_dir.resolve()
    try:
        if args.tenant_id and args.credential != "azure-cli":
            raise ContractError("--tenant-id requires --credential azure-cli")
        report = build_preflight_report(
            config_path,
            overrides_path,
            sample_dir,
            allow_placeholders=args.allow_placeholders,
            expected_input_manifest=args.expected_input_manifest.resolve(),
        )
        config = load_json_object(config_path)
        overrides = validate_overrides(load_json_object(overrides_path))
        validate_sample_layout(sample_dir)
    except ContractError as error:
        print(f"SUBMIT_FAIL: {error}")
        return 1

    if args.action == "plan":
        print(json.dumps(report, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="cct-upload-") as temporary:
        try:
            snapshot_root = Path(temporary)
            snapshot_dir = create_upload_snapshot(sample_dir, snapshot_root / "sample")
            snapshot_config = snapshot_root / "config.json"
            snapshot_overrides = snapshot_root / "overrides.json"
            snapshot_manifest = snapshot_root / "input-manifest.jsonl"
            snapshot_config.write_bytes(config_path.read_bytes())
            snapshot_overrides.write_bytes(overrides_path.read_bytes())
            snapshot_manifest.write_bytes(args.expected_input_manifest.resolve().read_bytes())
            report = build_preflight_report(
                snapshot_config,
                snapshot_overrides,
                snapshot_dir,
                allow_placeholders=False,
                expected_input_manifest=snapshot_manifest,
            )
            config = load_json_object(snapshot_config)
            overrides = validate_overrides(load_json_object(snapshot_overrides))
        except (ContractError, OSError) as error:
            print(f"SUBMIT_FAIL: {error}")
            return 1
        report["config"]["sourcePath"] = str(config_path)
        report["overrides"]["sourcePath"] = str(overrides_path)
        report["sample"]["sourceRoot"] = str(sample_dir)
        report["sample"]["expectedInputManifest"]["sourcePath"] = str(
            args.expected_input_manifest.resolve()
        )
        report["sample"]["snapshot"] = {
            "ephemeral": True,
            "removedAfterAction": True,
        }
        snapshot_inventory = report["sample"]["uploadInventory"]

        evidence: dict[str, Any] = {
            "startedAt": datetime.now(UTC).isoformat(),
            "action": args.action,
            "preflight": report,
            "status": "STARTED",
        }
        version = str(int(time.time() * 1000))
        code_name = str(config.get("codeDatasetName", "verl-retail-code"))
        data_name = str(config.get("dataDatasetName", "verl-retail-data"))
        evidence["datasets"] = {
            "version": version,
            "code": None,
            "data": None,
            "uploads": {
                "code": {"name": code_name, "version": version, "status": "PENDING"},
                "data": {"name": data_name, "version": version, "status": "PENDING"},
            },
            "failurePolicy": {
                "automaticDeletion": False,
                "reason": "Retain uploaded versions for diagnosis; verify references before deletion",
            },
        }
        write_json_atomic(args.evidence, evidence)

        credential = None
        client = None
        try:
            sdk = _sdk_imports()
            credential = make_credential(sdk, args.credential, args.tenant_id)
            client = sdk["AIProjectClient"](
                endpoint=config["projectEndpoint"], credential=credential
            )
            require_upload_tree_unchanged(snapshot_dir, snapshot_inventory)
            evidence["datasets"]["uploads"]["code"]["status"] = "UPLOADING"
            write_json_atomic(args.evidence, evidence)
            code_dataset = client.datasets.upload_folder(
                name=code_name,
                version=version,
                folder=str(snapshot_dir / "code"),
                connection_name=config["storageConnectionName"],
            )
            evidence["datasets"]["code"] = code_dataset.id
            evidence["datasets"]["uploads"]["code"].update(
                {"status": "UPLOADED", "id": code_dataset.id}
            )
            write_json_atomic(args.evidence, evidence)

            require_upload_tree_unchanged(snapshot_dir, snapshot_inventory)
            evidence["datasets"]["uploads"]["data"]["status"] = "UPLOADING"
            write_json_atomic(args.evidence, evidence)
            data_dataset = client.datasets.upload_folder(
                name=data_name,
                version=version,
                folder=str(snapshot_dir / "data"),
                connection_name=config["storageConnectionName"],
            )
            evidence["datasets"]["data"] = data_dataset.id
            evidence["datasets"]["uploads"]["data"].update(
                {"status": "UPLOADED", "id": data_dataset.id}
            )
            write_json_atomic(args.evidence, evidence)
            require_upload_tree_unchanged(snapshot_dir, snapshot_inventory)

            suffix = secrets.token_hex(3)
            contract = build_contract(
                config,
                overrides,
                code_uri=code_dataset.id,
                data_uri=data_dataset.id,
                suffix=suffix,
            )
            job = sdk_job_from_contract(sdk, config, contract)
            client.beta.jobs.validate(job).try_raise()
            evidence["offlineValidate"] = {
                "passed": True,
                "capturedAt": datetime.now(UTC).isoformat(),
            }

            if args.action == "validate":
                evidence["status"] = "VALIDATED_NOT_SUBMITTED"
                write_json_atomic(args.evidence, evidence)
                print(json.dumps(evidence, indent=2, default=str))
                return 0

            job_name = f"{config.get('jobPrefix', 'verl-retail-grpo')}-{secrets.token_hex(2)}"
            evidence["submission"] = {
                "name": job_name,
                "requestStatus": "SUBMITTING",
                "requestedAt": datetime.now(UTC).isoformat(),
            }
            write_json_atomic(args.evidence, evidence)
            created = client.beta.jobs.create_or_update(name=job_name, job=job)
            evidence["submission"].update(
                {
                    "name": created.name,
                    "id": created.id,
                    "requestStatus": "ACCEPTED",
                    "status": getattr(created, "status", None),
                    "portalUrl": getattr(created, "foundry_portal_url", None),
                    "submittedAt": datetime.now(UTC).isoformat(),
                }
            )
            evidence["status"] = "SUBMITTED"
            write_json_atomic(args.evidence, evidence)
            print(json.dumps(evidence["submission"], indent=2, default=str))
            return 0
        except Exception as error:
            evidence["status"] = "FAILED"
            evidence["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "capturedAt": datetime.now(UTC).isoformat(),
            }
            potentially_created = [
                upload
                for upload in evidence["datasets"]["uploads"].values()
                if upload["status"] in {"UPLOADING", "UPLOADED"}
            ]
            evidence["recovery"] = {
                "potentiallyCreatedDatasetVersions": potentially_created,
                "nextAction": (
                    "Query each listed name/version, then inspect job references before choosing reuse "
                    "or client.datasets.delete(name, version)"
                ),
            }
            if evidence.get("submission", {}).get("requestStatus") == "SUBMITTING":
                evidence["recovery"]["potentiallyCreatedJobs"] = [
                    {
                        "name": evidence["submission"]["name"],
                        "status": "SUBMISSION_RESULT_UNKNOWN",
                    }
                ]
                evidence["recovery"]["nextAction"] = (
                    "Query the listed job name before retrying; then inspect dataset references "
                    "before choosing reuse or client.datasets.delete(name, version)"
                )
            write_json_atomic(args.evidence, evidence)
            raise
        finally:
            cleanup_warnings = close_resources(client, credential)
            if cleanup_warnings:
                evidence["cleanupWarnings"] = cleanup_warnings
                try:
                    write_json_atomic(args.evidence, evidence)
                except OSError as error:
                    print(
                        f"CLEANUP_WARNING: cannot persist cleanup warnings: {error}",
                        file=sys.stderr,
                    )


if __name__ == "__main__":
    raise SystemExit(main())
