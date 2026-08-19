"""Validate the deployed Azure Context Cache resource binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


class ValidationError(RuntimeError):
    """The ARM evidence does not prove the expected deployment contract."""


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a nonempty string")
    return value


def nested(mapping: object, *keys: str) -> object:
    value = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValidationError(f"missing ARM field: {'.'.join(keys)}")
        value = value[key]
    return value


def same_resource_id(actual: object, expected: str, label: str) -> None:
    value = require_string(actual, label).rstrip("/")
    if value.casefold() != expected.rstrip("/").casefold():
        raise ValidationError(f"{label} does not match the expected resource ID")


def validate(
    payload: dict[str, object],
    *,
    subscription_id: str,
    resource_group: str,
    name_prefix: str,
) -> dict[str, object]:
    account_name = f"{name_prefix}-aoai"
    cache_account_name = f"{name_prefix}-cache"
    deployment_name = "context-cache-deployment"
    model_name = "gpt-5.4"
    model_version = "2026-03-05-contextcache"
    resource_root = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
    container_id = (
        f"{resource_root}/providers/Microsoft.Storage/contextCaches/"
        f"{cache_account_name}/contextCacheContainers/default-container"
    )
    aoai_deployment_id = (
        f"{resource_root}/providers/Microsoft.CognitiveServices/accounts/"
        f"{account_name}/deployments/{deployment_name}"
    )

    deployment = nested(payload, "deployment")
    aoai_deployment = nested(payload, "aoaiDeployment")
    cache_container = nested(payload, "cacheContainer")
    if nested(deployment, "state") != "Succeeded":
        raise ValidationError("ARM deployment provisioning state is not Succeeded")
    correlation_id = require_string(
        nested(deployment, "correlationId"), "deployment.correlationId"
    )
    expected_outputs = {
        "azureOpenAIAccountName": account_name,
        "aoaiDeploymentName": deployment_name,
        "contextCacheAccountName": cache_account_name,
        "modelName": model_name,
        "modelVersion": model_version,
    }
    for key, expected in expected_outputs.items():
        if nested(deployment, key) != expected:
            raise ValidationError(f"deployment.{key} does not match the pinned contract")
    same_resource_id(
        nested(deployment, "contextCacheContainerId"),
        container_id,
        "deployment.contextCacheContainerId",
    )

    same_resource_id(nested(aoai_deployment, "id"), aoai_deployment_id, "aoai.id")
    if nested(aoai_deployment, "properties", "provisioningState") != "Succeeded":
        raise ValidationError("AOAI deployment provisioning state is not Succeeded")
    if nested(aoai_deployment, "properties", "model", "name") != model_name:
        raise ValidationError("AOAI deployment model name does not match")
    if nested(aoai_deployment, "properties", "model", "version") != model_version:
        raise ValidationError("AOAI deployment model version does not match")
    same_resource_id(
        nested(aoai_deployment, "properties", "contextCacheContainerId"),
        container_id,
        "aoai.properties.contextCacheContainerId",
    )

    same_resource_id(nested(cache_container, "id"), container_id, "cacheContainer.id")
    if nested(cache_container, "properties", "provisioningState") != "Succeeded":
        raise ValidationError("Context Cache container provisioning state is not Succeeded")
    if nested(cache_container, "properties", "modelName") != model_name:
        raise ValidationError("Context Cache container model name does not match")
    if nested(cache_container, "properties", "provider") != "OpenAI":
        raise ValidationError("Context Cache container provider does not match")
    if nested(cache_container, "properties", "timeToLive") != 7:
        raise ValidationError("Context Cache container TTL does not match")

    return {
        "schemaVersion": 1,
        "deployment": {
            "name": require_string(nested(deployment, "name"), "deployment.name"),
            "state": "Succeeded",
            "correlationId": correlation_id,
        },
        "resources": {
            "azureOpenAIAccountName": account_name,
            "aoaiDeploymentName": deployment_name,
            "contextCacheAccountName": cache_account_name,
            "contextCacheContainerId": container_id,
            "modelName": model_name,
            "modelVersion": model_version,
            "cacheTtlDays": 7,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--name-prefix", required=True)
    args = parser.parse_args()

    try:
        payload = json.loads(args.raw.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValidationError("ARM evidence root must be an object")
        summary = validate(
            payload,
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            name_prefix=args.name_prefix,
        )
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        parser.error(str(error))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("ARM_BINDING_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())