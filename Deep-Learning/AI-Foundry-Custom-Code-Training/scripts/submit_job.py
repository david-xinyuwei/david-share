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
from preflight import build_preflight_report, write_json_atomic

# Copied from the public upstream notebook pinned in job_contract.py. It selects the
# product's preview bootstrapper; it is not a customer registry or credential.
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
    if mode == "azure-cli":
        kwargs: dict[str, Any] = {"process_timeout": 120}
        if tenant_id:
            kwargs["tenant_id"] = tenant_id
        return sdk["AzureCliCredential"](**kwargs)
    return sdk["DefaultAzureCredential"]()


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
        report = build_preflight_report(
            config_path,
            overrides_path,
            sample_dir,
            allow_placeholders=args.allow_placeholders,
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

    sdk = _sdk_imports()
    credential = make_credential(sdk, args.credential, args.tenant_id)
    client = sdk["AIProjectClient"](endpoint=config["projectEndpoint"], credential=credential)
    evidence: dict[str, Any] = {
        "startedAt": datetime.now(UTC).isoformat(),
        "action": args.action,
        "preflight": report,
        "status": "STARTED",
    }

    try:
        version = str(int(time.time() * 1000))
        code_dataset = client.datasets.upload_folder(
            name=str(config.get("codeDatasetName", "verl-retail-code")),
            version=version,
            folder=str(sample_dir / "code"),
            connection_name=config["storageConnectionName"],
        )
        data_dataset = client.datasets.upload_folder(
            name=str(config.get("dataDatasetName", "verl-retail-data")),
            version=version,
            folder=str(sample_dir / "data"),
            connection_name=config["storageConnectionName"],
        )
        evidence["datasets"] = {
            "version": version,
            "code": code_dataset.id,
            "data": data_dataset.id,
        }

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
        created = client.beta.jobs.create_or_update(name=job_name, job=job)
        evidence["submission"] = {
            "name": created.name,
            "id": created.id,
            "status": getattr(created, "status", None),
            "portalUrl": getattr(created, "foundry_portal_url", None),
            "submittedAt": datetime.now(UTC).isoformat(),
        }
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
        write_json_atomic(args.evidence, evidence)
        raise
    finally:
        client.close()
        close = getattr(credential, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    raise SystemExit(main())
