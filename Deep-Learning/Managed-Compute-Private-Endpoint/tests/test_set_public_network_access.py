import importlib.util
import argparse
import datetime as dt
import json
import pathlib
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "set_public_network_access.py"
SPEC = importlib.util.spec_from_file_location("set_public_network_access", MODULE_PATH)
assert SPEC and SPEC.loader
PNA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PNA)


class PublicNetworkAccessTests(unittest.TestCase):
    def test_prefers_latest_advertised_stable_api(self) -> None:
        provider = {
            "resourceTypes": [
                {
                    "resourceType": "accounts",
                    "apiVersions": ["2025-01-01", "2026-06-01-preview", "2026-07-01"],
                }
            ]
        }
        self.assertEqual(PNA.select_account_api_version(provider), "2026-07-01")

    def test_counts_only_approved_private_endpoints(self) -> None:
        account = {
            "properties": {
                "privateEndpointConnections": [
                    {
                        "properties": {
                            "privateLinkServiceConnectionState": {"status": "Approved"}
                            ,"provisioningState": "Succeeded",
                            "groupIds": ["account"]
                        },
                    },
                    {
                        "properties": {
                            "privateLinkServiceConnectionState": {"status": "Pending"}
                            ,"provisioningState": "Succeeded",
                            "groupIds": ["account"]
                        },
                    },
                    {
                        "properties": {
                            "privateLinkServiceConnectionState": {"status": "Approved"},
                            "provisioningState": None,
                            "groupIds": ["account"],
                        },
                    },
                    {
                        "properties": {
                            "privateLinkServiceConnectionState": {"status": "Approved"},
                            "provisioningState": "Failed",
                            "groupIds": ["account"],
                        },
                    },
                ]
            }
        }
        self.assertEqual(PNA.approved_private_endpoint_count(account), 2)

    def test_missing_connections_fail_closed(self) -> None:
        self.assertEqual(PNA.approved_private_endpoint_count({"properties": {}}), 0)

    def test_private_probe_must_be_fresh_and_match_account(self) -> None:
        account_name = "exampleaccount123"
        evidence = {
            "passed": True,
            "dnsClass": "private",
            "httpStatus": 200,
            "object": "chat.completion",
            "choiceCount": 1,
            "hostnameSha256": PNA.sha256_text(
                f"{account_name}.services.ai.azure.com"
            ),
            "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(evidence, handle)
            path = handle.name
        self.addCleanup(pathlib.Path(path).unlink)
        self.assertEqual(
            PNA.validate_private_probe(path, account_name, 900)["httpStatus"],
            200,
        )

    def test_private_probe_accepts_every_account_hostname(self) -> None:
        account_name = "exampleaccount123"
        for suffix in PNA.ACCOUNT_HOST_SUFFIXES:
            evidence = {
                "passed": True,
                "dnsClass": "private",
                "httpStatus": 200,
                "object": "chat.completion",
                "choiceCount": 1,
                "hostnameSha256": PNA.sha256_text(f"{account_name}{suffix}"),
                "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False
            ) as handle:
                json.dump(evidence, handle)
                path = handle.name
            self.addCleanup(pathlib.Path(path).unlink)
            PNA.validate_private_probe(path, account_name, 900)

    def test_missing_approved_endpoint_never_patches(self) -> None:
        calls = []
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "properties": {
                "provisioningState": "Succeeded",
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [],
            }
        }

        def fake_request(method, url, token, payload=None):
            calls.append(method)
            if method == "PATCH":
                self.fail("PATCH must not run without an approved private endpoint")
            return 200, {}, provider if "providers/Microsoft.CognitiveServices?" in url else account

        args = argparse.Namespace(
            subscription_id="example-subscription",
            resource_group="example-resource-group",
            account_name="exampleaccount123",
            state="Disabled",
            restore_state_from=None,
            confirm_dedicated_test_account=True,
            save_prior_state="unused.json",
            private_probe_evidence=None,
            max_probe_age_seconds=900,
            max_restore_age_seconds=3600,
            operation_timeout=10,
        )
        with self.assertRaisesRegex(RuntimeError, "no usable Approved"):
            PNA.change_public_network_access(args, "token", fake_request)
        self.assertEqual(calls, ["GET", "GET"])

    def test_invalid_private_probe_variants_never_patch(self) -> None:
        account_name = "exampleaccount123"
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "properties": {
                "provisioningState": "Succeeded",
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [
                    {
                        "properties": {
                            "privateLinkServiceConnectionState": {
                                "status": "Approved"
                            },
                            "provisioningState": "Succeeded",
                            "groupIds": ["account"],
                        }
                    }
                ],
            }
        }
        baseline = {
            "passed": True,
            "dnsClass": "private",
            "httpStatus": 200,
            "object": "chat.completion",
            "choiceCount": 1,
            "hostnameSha256": PNA.sha256_text(
                f"{account_name}.services.ai.azure.com"
            ),
            "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        variants = {
            "public DNS": {"dnsClass": "public"},
            "non-200": {"httpStatus": 403},
            "wrong response": {"object": "error"},
            "empty choices": {"choiceCount": 0},
            "wrong account": {"hostnameSha256": "0" * 64},
            "stale": {
                "capturedAtUtc": (
                    dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
                ).isoformat()
            },
            "future": {
                "capturedAtUtc": (
                    dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)
                ).isoformat()
            },
        }
        for label, mutation in variants.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                evidence = dict(baseline)
                evidence.update(mutation)
                evidence_path = pathlib.Path(directory) / "private-probe.json"
                evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
                calls = []

                def fake_request(method, url, token, payload=None):
                    calls.append(method)
                    if method == "PATCH":
                        self.fail(f"PATCH must not run for {label}")
                    result = (
                        provider
                        if "providers/Microsoft.CognitiveServices?" in url
                        else account
                    )
                    return 200, {}, result

                args = argparse.Namespace(
                    subscription_id="example-subscription",
                    resource_group="example-resource-group",
                    account_name=account_name,
                    state="Disabled",
                    restore_state_from=None,
                    confirm_dedicated_test_account=True,
                    save_prior_state=str(pathlib.Path(directory) / "pna-before.json"),
                    private_probe_evidence=str(evidence_path),
                    max_probe_age_seconds=900,
                    max_restore_age_seconds=3600,
                    operation_timeout=10,
                )
                with self.assertRaises(RuntimeError):
                    PNA.change_public_network_access(args, "token", fake_request)
                self.assertEqual(calls, ["GET", "GET"])

    def test_disable_saves_and_restore_uses_original_state(self) -> None:
        account_name = "exampleaccount123"
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        current_state = "Enabled"
        current_etag = '"etag-1"'
        patches = []
        operation_reads = []

        def account():
            return {
                "etag": current_etag,
                "properties": {
                    "provisioningState": "Succeeded",
                    "publicNetworkAccess": current_state,
                    "privateEndpointConnections": [
                        {
                            "properties": {
                                "privateLinkServiceConnectionState": {
                                    "status": "Approved"
                                },
                                "provisioningState": "Succeeded",
                                "groupIds": ["account"],
                            }
                        }
                    ],
                }
            }

        def fake_request(method, url, token, payload=None, extra_headers=None):
            nonlocal current_etag, current_state
            if "providers/Microsoft.CognitiveServices?" in url:
                return 200, {}, provider
            if url == "https://management.azure.com/operation":
                operation_reads.append(url)
                return 200, {}, {"status": "Running"}
            if method == "PATCH":
                self.assertEqual(extra_headers, {"If-Match": current_etag})
                current_state = payload["properties"]["publicNetworkAccess"]
                patches.append(current_state)
                current_etag = f'"etag-{len(patches) + 1}"'
                return 202, {
                    "Azure-AsyncOperation": "https://management.azure.com/operation"
                }, {}
            return 200, {}, account()

        with tempfile.TemporaryDirectory() as directory:
            private_probe = pathlib.Path(directory) / "private-probe.json"
            private_probe.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "dnsClass": "private",
                        "httpStatus": 200,
                        "object": "chat.completion",
                        "choiceCount": 1,
                        "hostnameSha256": PNA.sha256_text(
                            f"{account_name}.services.ai.azure.com"
                        ),
                        "capturedAtUtc": dt.datetime.now(
                            dt.timezone.utc
                        ).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            saved_state = pathlib.Path(directory) / "pna-before.json"
            common = {
                "subscription_id": "example-subscription",
                "resource_group": "example-resource-group",
                "account_name": account_name,
                "confirm_dedicated_test_account": True,
                "max_probe_age_seconds": 900,
                "max_restore_age_seconds": 3600,
                "operation_timeout": 10,
            }
            disabled = PNA.change_public_network_access(
                argparse.Namespace(
                    **common,
                    state="Disabled",
                    restore_state_from=None,
                    save_prior_state=str(saved_state),
                    private_probe_evidence=str(private_probe),
                ),
                "token",
                fake_request,
            )
            self.assertEqual(disabled["actualState"], "Disabled")
            receipt = json.loads(saved_state.read_text())
            self.assertEqual(receipt["priorState"], "Enabled")
            self.assertEqual(receipt["phase"], "applied")
            self.assertEqual(receipt["appliedState"], "Disabled")
            self.assertEqual(receipt["initialEtag"], '"etag-1"')
            self.assertEqual(receipt["appliedEtag"], '"etag-2"')

            restored = PNA.change_public_network_access(
                argparse.Namespace(
                    **common,
                    state=None,
                    restore_state_from=str(saved_state),
                    save_prior_state=None,
                    private_probe_evidence=None,
                ),
                "token",
                fake_request,
            )
            self.assertEqual(restored["actualState"], "Enabled")
            self.assertEqual(patches, ["Disabled", "Enabled"])
            self.assertEqual(len(operation_reads), 2)

    def test_accepted_operation_is_polled(self) -> None:
        calls = []

        def fake_request(method, url, token, payload=None):
            calls.append((method, url))
            return 200, {}, {"status": "Succeeded"}

        PNA.wait_for_operation(
            202,
            {"Azure-AsyncOperation": "https://management.azure.com/operation"},
            "token",
            10,
            request_function=fake_request,
            sleep_function=lambda _: None,
        )
        self.assertEqual(calls, [("GET", "https://management.azure.com/operation")])

    def test_failed_operation_is_rejected(self) -> None:
        def fake_request(method, url, token, payload=None):
            return 200, {}, {"status": "Failed"}

        with self.assertRaisesRegex(RuntimeError, "ended in failed"):
            PNA.wait_for_operation(
                202,
                {"Operation-Location": "https://management.azure.com/operation"},
                "token",
                10,
                request_function=fake_request,
                sleep_function=lambda _: None,
            )

    def test_cross_host_operation_url_is_rejected_before_request(self) -> None:
        requests = []

        def fake_request(method, url, token, payload=None):
            requests.append(url)
            return 200, {}, {"status": "Succeeded"}

        with self.assertRaisesRegex(ValueError, "management.azure.com"):
            PNA.wait_for_operation(
                202,
                {"Azure-AsyncOperation": "https://attacker.example/operation"},
                "token",
                10,
                request_function=fake_request,
                sleep_function=lambda _: None,
            )
        self.assertEqual(requests, [])

    def test_request_json_disables_redirects(self) -> None:
        opener = mock.Mock()
        opener.open.side_effect = RuntimeError("redirect blocked")
        with mock.patch.object(PNA.urllib.request, "build_opener", return_value=opener) as build:
            with self.assertRaisesRegex(RuntimeError, "redirect blocked"):
                PNA.request_json(
                    "GET",
                    "https://management.azure.com/subscriptions/example",
                    "token",
                )
        self.assertIsInstance(build.call_args.args[0], PNA.NoRedirectHandler)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://management.azure.com/subscriptions/example")

    def test_unstable_account_never_patches(self) -> None:
        calls = []
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "properties": {
                "provisioningState": "Updating",
                "publicNetworkAccess": "Enabled",
            }
        }

        def fake_request(method, url, token, payload=None):
            calls.append(method)
            if method == "PATCH":
                self.fail("PATCH must not run while the account is Updating")
            result = provider if "providers/Microsoft.CognitiveServices?" in url else account
            return 200, {}, result

        args = argparse.Namespace(
            subscription_id="example-subscription",
            resource_group="example-resource-group",
            account_name="exampleaccount123",
            state="Disabled",
            restore_state_from=None,
            confirm_dedicated_test_account=True,
            save_prior_state="unused.json",
            private_probe_evidence="unused.json",
            max_probe_age_seconds=900,
            max_restore_age_seconds=3600,
            operation_timeout=10,
        )
        with self.assertRaisesRegex(RuntimeError, "not Succeeded"):
            PNA.change_public_network_access(args, "token", fake_request)
        self.assertEqual(calls, ["GET", "GET"])

    def test_shared_account_confirmation_is_required_before_patch(self) -> None:
        calls = []
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "properties": {
                "provisioningState": "Succeeded",
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [],
            }
        }

        def fake_request(method, url, token, payload=None):
            calls.append(method)
            if method == "PATCH":
                self.fail("PATCH must not run without dedicated account confirmation")
            result = provider if "providers/Microsoft.CognitiveServices?" in url else account
            return 200, {}, result

        args = argparse.Namespace(
            subscription_id="example-subscription",
            resource_group="example-resource-group",
            account_name="exampleaccount123",
            state="Disabled",
            restore_state_from=None,
            confirm_dedicated_test_account=False,
            save_prior_state="unused.json",
            private_probe_evidence="unused.json",
            max_probe_age_seconds=900,
            max_restore_age_seconds=3600,
            operation_timeout=10,
        )
        with self.assertRaisesRegex(RuntimeError, "dedicated non-production"):
            PNA.change_public_network_access(args, "token", fake_request)
        self.assertEqual(calls, ["GET", "GET"])

    def test_forged_restore_to_disabled_never_patches(self) -> None:
        calls = []
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "properties": {
                "provisioningState": "Succeeded",
                "publicNetworkAccess": "Enabled",
                "privateEndpointConnections": [],
            }
        }

        def fake_request(method, url, token, payload=None):
            calls.append(method)
            if method == "PATCH":
                self.fail("PATCH must not run for a forged restore-to-Disabled file")
            result = provider if "providers/Microsoft.CognitiveServices?" in url else account
            return 200, {}, result

        with tempfile.TemporaryDirectory() as directory:
            restore_path = pathlib.Path(directory) / "forged.json"
            account_path = (
                "/subscriptions/example-subscription/resourceGroups/example-resource-group"
                "/providers/Microsoft.CognitiveServices/accounts/exampleaccount123"
            )
            restore_path.write_text(
                json.dumps(
                    {
                        "accountResourceIdSha256": PNA.sha256_text(account_path.lower()),
                        "priorState": "Disabled",
                        "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "phase": "applied",
                        "appliedState": "Disabled",
                        "appliedEtag": '"etag-after-disable"',
                        "appliedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                subscription_id="example-subscription",
                resource_group="example-resource-group",
                account_name="exampleaccount123",
                state=None,
                restore_state_from=str(restore_path),
                save_prior_state=None,
                private_probe_evidence=None,
                max_probe_age_seconds=900,
                max_restore_age_seconds=3600,
                operation_timeout=10,
            )
            with self.assertRaisesRegex(RuntimeError, "not the test state Disabled"):
                PNA.change_public_network_access(args, "token", fake_request)
        self.assertEqual(calls, ["GET", "GET"])

    def test_restore_rejects_concurrent_or_aba_account_change(self) -> None:
        calls = []
        provider = {
            "resourceTypes": [
                {"resourceType": "accounts", "apiVersions": ["2026-07-01"]}
            ]
        }
        account = {
            "etag": '"etag-after-external-change"',
            "properties": {
                "provisioningState": "Succeeded",
                "publicNetworkAccess": "Disabled",
                "privateEndpointConnections": [],
            },
        }

        def fake_request(method, url, token, payload=None):
            calls.append(method)
            if method == "PATCH":
                self.fail("PATCH must not overwrite a concurrently changed account")
            result = provider if "providers/Microsoft.CognitiveServices?" in url else account
            return 200, {}, result

        with tempfile.TemporaryDirectory() as directory:
            restore_path = pathlib.Path(directory) / "restore.json"
            account_path = (
                "/subscriptions/example-subscription/resourceGroups/example-resource-group"
                "/providers/Microsoft.CognitiveServices/accounts/exampleaccount123"
            )
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            restore_path.write_text(
                json.dumps(
                    {
                        "accountResourceIdSha256": PNA.sha256_text(account_path.lower()),
                        "priorState": "Enabled",
                        "initialEtag": '"etag-before-disable"',
                        "capturedAtUtc": now,
                        "phase": "applied",
                        "appliedState": "Disabled",
                        "appliedEtag": '"etag-after-disable"',
                        "appliedAtUtc": now,
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                subscription_id="example-subscription",
                resource_group="example-resource-group",
                account_name="exampleaccount123",
                state=None,
                restore_state_from=str(restore_path),
                save_prior_state=None,
                private_probe_evidence=None,
                max_probe_age_seconds=900,
                max_restore_age_seconds=3600,
                operation_timeout=10,
            )
            with self.assertRaisesRegex(RuntimeError, "changed after PNA"):
                PNA.change_public_network_access(args, "token", fake_request)
        self.assertEqual(calls, ["GET", "GET"])

    def test_prepared_restore_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "prepared.json"
            account_path = (
                "/subscriptions/example-subscription/resourceGroups/example-resource-group"
                "/providers/Microsoft.CognitiveServices/accounts/exampleaccount123"
            )
            PNA.save_prior_state(
                str(path),
                account_path,
                "Enabled",
                '"etag-before-disable"',
            )
            with self.assertRaisesRegex(RuntimeError, "completed disable"):
                PNA.load_prior_state(str(path), account_path, 3600)


if __name__ == "__main__":
    unittest.main()
