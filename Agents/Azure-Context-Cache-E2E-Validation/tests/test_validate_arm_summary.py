from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_arm_summary", ROOT / "scripts" / "validate_arm_summary.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ArmSummaryTests(unittest.TestCase):
    subscription_id = "TEST-SUBSCRIPTION-ID"
    resource_group = "rg-test"
    name_prefix = "cache123"

    def payload(self) -> dict[str, object]:
        root = (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"
        )
        container_id = (
            f"{root}/providers/Microsoft.Storage/contextCaches/cache123-cache/"
            "contextCacheContainers/default-container"
        )
        return {
            "deployment": {
                "name": "cc-quickstart-20260819-120000",
                "state": "Succeeded",
                "correlationId": "TEST-CORRELATION-ID",
                "azureOpenAIAccountName": "cache123-aoai",
                "aoaiDeploymentName": "context-cache-deployment",
                "contextCacheAccountName": "cache123-cache",
                "contextCacheContainerId": container_id,
                "modelName": "gpt-5.4",
                "modelVersion": "2026-03-05-contextcache",
            },
            "aoaiDeployment": {
                "id": (
                    f"{root}/providers/Microsoft.CognitiveServices/accounts/"
                    "cache123-aoai/deployments/context-cache-deployment"
                ),
                "properties": {
                    "provisioningState": "Succeeded",
                    "contextCacheContainerId": container_id,
                    "model": {
                        "name": "gpt-5.4",
                        "version": "2026-03-05-contextcache",
                    },
                },
            },
            "cacheContainer": {
                "id": container_id,
                "properties": {
                    "provisioningState": "Succeeded",
                    "modelName": "gpt-5.4",
                    "provider": "OpenAI",
                    "timeToLive": 7,
                },
            },
        }

    def validate(self, payload: dict[str, object]) -> dict[str, object]:
        return MODULE.validate(
            payload,
            subscription_id=self.subscription_id,
            resource_group=self.resource_group,
            name_prefix=self.name_prefix,
        )

    def test_complete_binding_is_normalized(self) -> None:
        summary = self.validate(self.payload())

        self.assertEqual(summary["schemaVersion"], 1)
        self.assertEqual(summary["deployment"]["state"], "Succeeded")
        self.assertEqual(summary["resources"]["cacheTtlDays"], 7)

    def test_failed_deployment_is_rejected(self) -> None:
        payload = self.payload()
        payload["deployment"]["state"] = "Failed"

        with self.assertRaisesRegex(MODULE.ValidationError, "not Succeeded"):
            self.validate(payload)

    def test_missing_output_is_rejected(self) -> None:
        payload = self.payload()
        del payload["deployment"]["modelVersion"]

        with self.assertRaisesRegex(MODULE.ValidationError, "missing ARM field"):
            self.validate(payload)

    def test_wrong_cache_binding_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload())
        payload["aoaiDeployment"]["properties"]["contextCacheContainerId"] += "-other"

        with self.assertRaisesRegex(MODULE.ValidationError, "expected resource ID"):
            self.validate(payload)

    def test_wrong_container_contract_is_rejected(self) -> None:
        payload = self.payload()
        payload["cacheContainer"]["properties"]["timeToLive"] = 8

        with self.assertRaisesRegex(MODULE.ValidationError, "TTL"):
            self.validate(payload)


if __name__ == "__main__":
    unittest.main()