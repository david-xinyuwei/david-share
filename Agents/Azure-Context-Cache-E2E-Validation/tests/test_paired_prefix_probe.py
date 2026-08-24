from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "paired_prefix_probe", ROOT / "scripts" / "paired_prefix_probe.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PairedPrefixProbeTests(unittest.TestCase):
    def test_prefixes_are_equal_length_and_isolated_near_the_start(self) -> None:
        prefixes, hashes = MODULE.build_prefixes(b"x" * 4_000, "example-run-20260824")

        self.assertEqual(len(prefixes["linked"]), len(prefixes["control"]))
        self.assertNotEqual(hashes["linked"], hashes["control"])
        first_difference = next(
            index
            for index, pair in enumerate(zip(prefixes["linked"], prefixes["control"]))
            if pair[0] != pair[1]
        )
        self.assertLess(first_difference, 1_024)

    def test_short_prefix_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 4,000 bytes"):
            MODULE.build_prefixes(b"x" * 3_999, "example-run-20260824")

    def test_invalid_run_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "run-id"):
            MODULE.build_prefixes(b"x" * 4_000, "bad id")

    def test_endpoint_must_be_an_azure_openai_https_url(self) -> None:
        self.assertEqual(
            MODULE.valid_endpoint("https://example.openai.azure.com/"),
            "https://example.openai.azure.com",
        )
        with self.assertRaisesRegex(Exception, "endpoint"):
            MODULE.valid_endpoint("https://example.invalid")

    def test_warm_contract_requires_independent_miss_then_hit(self) -> None:
        prefixes, hashes = MODULE.build_prefixes(b"x" * 4_000, "example-run-20260824")
        del prefixes
        started = datetime.now(timezone.utc) - timedelta(hours=27)
        rows = []
        for call, cached_tokens in ((1, 0), (2, 2304)):
            for arm in ("linked", "control"):
                rows.append(
                    {
                        "ts": (started + timedelta(seconds=len(rows))).isoformat(),
                        "phase": "WARM",
                        "arm": arm,
                        "call": call,
                        "http_status": 200,
                        "cached_tokens": cached_tokens,
                        "input_tokens": 2513,
                        "prefix_sha256": hashes[arm],
                    }
                )

        self.assertGreater(MODULE.validate_warm_rows(rows, hashes), started)
        rows[0]["cached_tokens"] = 2304
        with self.assertRaisesRegex(ValueError, "first linked call"):
            MODULE.validate_warm_rows(rows, hashes)

    def test_rows_are_scoped_to_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(
                '{"run_id":"run-one","phase":"WARM"}\n'
                '{"run_id":"run-two","phase":"VERIFY"}\n',
                encoding="utf-8",
            )

            self.assertEqual(MODULE.read_rows(path, "run-one")[0]["phase"], "WARM")

    def test_arm_contract_requires_only_the_linked_binding(self) -> None:
        endpoint = "https://example.openai.azure.com"
        container_id = "/subscriptions/example/contextCaches/cache/contextCacheContainers/default"
        account = {"properties": {"endpoint": endpoint + "/"}}
        deployment = {
            "sku": {"name": "Standard", "capacity": 100},
            "properties": {
                "provisioningState": "Succeeded",
                "model": {"name": "gpt-5.4", "version": "example-version"},
            },
        }
        linked = {
            **deployment,
            "properties": {
                **deployment["properties"],
                "contextCacheContainerId": container_id,
            },
        }
        control = {**deployment, "properties": {**deployment["properties"]}}
        container = {
            "properties": {
                "provisioningState": "Succeeded",
                "modelName": "gpt-5.4",
                "timeToLive": 7,
            }
        }

        result = MODULE.validate_arm_documents(
            account, linked, control, container, endpoint, container_id, 7
        )
        self.assertEqual(result["capacity"], 100)
        control["properties"]["contextCacheContainerId"] = container_id
        with self.assertRaisesRegex(ValueError, "control deployment"):
            MODULE.validate_arm_documents(
                account, linked, control, container, endpoint, container_id, 7
            )

    def test_arm_contract_rejects_a_different_data_plane_endpoint(self) -> None:
        endpoint = "https://example.openai.azure.com"
        container_id = "/subscriptions/example/contextCaches/cache/contextCacheContainers/default"
        account = {"properties": {"endpoint": endpoint}}
        linked = {
            "sku": {"name": "Standard", "capacity": 100},
            "properties": {
                "provisioningState": "Succeeded",
                "model": {"name": "gpt-5.4", "version": "example-version"},
                "contextCacheContainerId": container_id,
            },
        }
        control = {
            "sku": {"name": "Standard", "capacity": 100},
            "properties": {
                "provisioningState": "Succeeded",
                "model": {"name": "gpt-5.4", "version": "example-version"},
            },
        }
        container = {
            "properties": {
                "provisioningState": "Succeeded",
                "modelName": "gpt-5.4",
                "timeToLive": 7,
            }
        }

        with self.assertRaisesRegex(ValueError, "endpoint"):
            MODULE.validate_arm_documents(
                account,
                linked,
                control,
                container,
                "https://different.openai.azure.com",
                container_id,
                7,
            )

    def test_live_output_is_rejected_inside_the_public_tree(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the public source tree"):
            MODULE.require_private_output(ROOT / "live-results.jsonl")


if __name__ == "__main__":
    unittest.main()
