"""Read one Foundry Custom Code Training job without streaming or changing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_contract import ContractError, load_json_object, validate_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--credential", choices=("default", "azure-cli"), default="default")
    parser.add_argument("--tenant-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json_object(args.config.resolve())
    validate_config(config)
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import AzureCliCredential, DefaultAzureCredential
    except ImportError as error:
        raise ContractError(
            "Foundry SDK is not installed; run `pip install -r requirements.txt`"
        ) from error

    if args.credential == "azure-cli":
        kwargs = {"process_timeout": 120}
        if args.tenant_id:
            kwargs["tenant_id"] = args.tenant_id
        credential = AzureCliCredential(**kwargs)
    else:
        credential = DefaultAzureCredential()

    client = AIProjectClient(endpoint=config["projectEndpoint"], credential=credential)
    try:
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
        client.close()
        close = getattr(credential, "close", None)
        if callable(close):
            close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
