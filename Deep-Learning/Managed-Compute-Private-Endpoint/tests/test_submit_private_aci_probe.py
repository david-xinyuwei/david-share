import importlib.util
import json
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "submit_private_aci_probe.py"
SPEC = importlib.util.spec_from_file_location("submit_private_aci_probe", MODULE_PATH)
assert SPEC and SPEC.loader
ACI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACI)


class SubmitPrivateAciProbeTests(unittest.TestCase):
    def test_payload_has_private_ip_and_secure_token(self) -> None:
        payload = ACI.build_container_group_payload(
            "aci-example-probe",
            "japaneast",
            "/subscriptions/example-subscription/resourceGroups/example-resource-group/providers/Microsoft.Network/virtualNetworks/example-vnet/subnets/example-subnet",
            ACI.DEFAULT_IMAGE,
            ["python3", "-c", "pass"],
            "secret-token-value",
            "example-run",
        )
        properties = payload["properties"]
        variable = properties["containers"][0]["properties"]["environmentVariables"][0]
        self.assertEqual(properties["ipAddress"]["type"], "Private")
        self.assertEqual(variable, {"name": "AZURE_ACCESS_TOKEN", "secureValue": "secret-token-value"})

    def test_sanitized_result_excludes_token_and_command(self) -> None:
        response = {
            "id": "/subscriptions/example/resourceGroups/example/providers/Microsoft.ContainerInstance/containerGroups/aci-example-probe",
            "properties": {
                "provisioningState": "Creating",
                "ipAddress": {"type": "Private"},
                "environmentVariables": [{"secureValue": "secret-token-value"}],
            },
        }
        result = ACI.sanitized_result(201, response, "a" * 64, ACI.DEFAULT_IMAGE)
        serialized = json.dumps(result)
        self.assertTrue(result["passed"])
        self.assertEqual(result["requestedIpAddressType"], "Private")
        self.assertEqual(result["observedIpAddressType"], "Private")
        self.assertNotIn("secret-token-value", serialized)
        self.assertNotIn("environmentVariables", serialized)

    def test_cross_subscription_subnet_is_rejected(self) -> None:
        subnet_id = "/subscriptions/other/resourceGroups/example/providers/Microsoft.Network/virtualNetworks/example/subnets/runner"
        with self.assertRaisesRegex(ValueError, "selected subscription"):
            ACI.validate_subnet_id(subnet_id, "expected")

    def test_probe_command_uses_exact_source(self) -> None:
        source = b"print('probe')\n"
        command, digest = ACI.build_probe_command(
            source,
            "https://example.services.ai.azure.com/openai/v1/chat/completions",
            "example-deployment",
        )
        self.assertEqual(command[0:2], ["python3", "-c"])
        self.assertIn("--expect-dns", command)
        self.assertIn("private", command)
        self.assertIn("--probe-source-sha256", command)
        self.assertEqual(command[command.index("--probe-source-sha256") + 1], digest)
        self.assertEqual(len(digest), 64)

    def test_existing_container_group_is_never_updated(self) -> None:
        calls = []

        def fake_request(method, url, token, payload=None, extra_headers=None):
            calls.append((method, extra_headers))
            return 200, {"id": "existing-container-group"}

        with self.assertRaisesRegex(RuntimeError, "existing container group"):
            ACI.create_container_group(
                "https://management.azure.com/subscriptions/example/containerGroups/existing",
                "management-token",
                {"properties": {}},
                fake_request,
            )
        self.assertEqual(calls, [("GET", None)])

    def test_create_uses_if_none_match(self) -> None:
        calls = []

        def fake_request(method, url, token, payload=None, extra_headers=None):
            calls.append((method, extra_headers))
            if method == "GET":
                return 404, {}
            return 201, {"properties": {"provisioningState": "Creating"}}

        status, _ = ACI.create_container_group(
            "https://management.azure.com/subscriptions/example/containerGroups/new",
            "management-token",
            {"properties": {}},
            fake_request,
        )
        self.assertEqual(status, 201)
        self.assertEqual(calls, [("GET", None), ("PUT", {"If-None-Match": "*"})])


if __name__ == "__main__":
    unittest.main()