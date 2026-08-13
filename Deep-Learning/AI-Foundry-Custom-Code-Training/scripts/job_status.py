"""Read one Foundry Custom Code Training job without streaming or changing it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from job_contract import ContractError, load_json_object, validate_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--credential", choices=("default", "azure-cli"), default="default")
    parser.add_argument("--tenant-id")
    return parser.parse_args()


def _sdk_imports() -> dict[str, Any]:
    try:
        from azure.ai.projects import AIProjectClient
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


def main() -> int:
    args = parse_args()
    if args.tenant_id and args.credential != "azure-cli":
        raise ContractError("--tenant-id requires --credential azure-cli")
    config = load_json_object(args.config.resolve())
    validate_config(config)
    sdk = _sdk_imports()
    credential = make_credential(sdk, args.credential, args.tenant_id)

    client = None
    try:
        client = sdk["AIProjectClient"](
            endpoint=config["projectEndpoint"], credential=credential
        )
        job = client.beta.jobs.get(name=args.job_name)
        print(
            json.dumps(
                {
                    "name": job.name,
                    "id": job.id,
                    "status": getattr(job, "status", None),
                    "portalUrl": getattr(job, "foundry_portal_url", None),
                },
                indent=2,
                default=str,
            )
        )
    finally:
        close_resources(client, credential)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
