#!/usr/bin/env python3
"""Safely change a Foundry account's public network access setting."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable


MANAGEMENT_ENDPOINT = "https://management.azure.com"
PROVIDER_API_VERSION = "2021-04-01"
ACCOUNT_HOST_SUFFIXES = (
    ".services.ai.azure.com",
    ".openai.azure.com",
    ".cognitiveservices.azure.com",
)


def validate_management_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "management.azure.com"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("ARM URL must use https://management.azure.com:443")
    return parsed


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def select_account_api_version(provider: dict[str, object]) -> str:
    resource_types = provider.get("resourceTypes")
    if not isinstance(resource_types, list):
        raise ValueError("Provider metadata has no resourceTypes array")
    account_type = next(
        (
            item
            for item in resource_types
            if isinstance(item, dict)
            and str(item.get("resourceType", "")).lower() == "accounts"
        ),
        None,
    )
    if not account_type:
        raise ValueError("Microsoft.CognitiveServices/accounts metadata is missing")
    versions = [str(version) for version in account_type.get("apiVersions", [])]
    stable_versions = [version for version in versions if "preview" not in version.lower()]
    if not stable_versions and not versions:
        raise ValueError("No account API version is advertised")
    return sorted(stable_versions or versions, reverse=True)[0]


def approved_private_endpoint_count(account: dict[str, object]) -> int:
    properties = account.get("properties")
    if not isinstance(properties, dict):
        return 0
    connections = properties.get("privateEndpointConnections")
    if not isinstance(connections, list):
        return 0
    approved = 0
    for connection in connections:
        if not isinstance(connection, dict):
            continue
        connection_properties = connection.get("properties")
        if not isinstance(connection_properties, dict):
            continue
        state = connection_properties.get("privateLinkServiceConnectionState")
        group_ids = connection_properties.get("groupIds")
        provisioning_state = connection_properties.get("provisioningState")
        if (
            isinstance(state, dict)
            and str(state.get("status", "")).lower() == "approved"
            and (
                provisioning_state is None
                or str(provisioning_state).lower() == "succeeded"
            )
            and isinstance(group_ids, list)
            and "account" in group_ids
        ):
            approved += 1
    return approved


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resource_etag(
    headers: dict[str, str],
    resource: dict[str, object],
) -> str:
    etag = resource.get("etag") or next(
        (value for key, value in headers.items() if key.lower() == "etag"),
        None,
    )
    if not isinstance(etag, str) or not etag:
        raise RuntimeError("Foundry account response has no ETag")
    return etag


def validate_private_probe(
    evidence_path: str,
    account_name: str,
    max_age_seconds: int,
) -> dict[str, object]:
    with open(evidence_path, encoding="utf-8") as evidence_file:
        evidence = json.load(evidence_file)
    expected_hostname_digests = {
        sha256_text(f"{account_name}{suffix}") for suffix in ACCOUNT_HOST_SUFFIXES
    }
    if (
        evidence.get("passed") is not True
        or evidence.get("dnsClass") != "private"
        or evidence.get("httpStatus") != 200
        or evidence.get("object") != "chat.completion"
        or not isinstance(evidence.get("choiceCount"), int)
        or evidence["choiceCount"] < 1
        or evidence.get("hostnameSha256") not in expected_hostname_digests
    ):
        raise RuntimeError("Private probe evidence does not match this account and a private HTTP 200")
    captured_at = dt.datetime.fromisoformat(str(evidence.get("capturedAtUtc", "")))
    if captured_at.tzinfo is None:
        raise RuntimeError("Private probe timestamp must include a timezone")
    age = (dt.datetime.now(dt.timezone.utc) - captured_at).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise RuntimeError("Private probe evidence is stale")
    return evidence


def save_prior_state(
    evidence_path: str,
    account_resource_id: str,
    prior_state: str,
    initial_etag: str,
) -> None:
    evidence = {
        "schemaVersion": 1,
        "accountResourceIdSha256": sha256_text(account_resource_id.lower()),
        "priorState": prior_state,
        "initialEtag": initial_etag,
        "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "prepared",
    }
    with pathlib.Path(evidence_path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")


def mark_state_applied(evidence_path: str, applied_etag: str) -> None:
    path = pathlib.Path(evidence_path)
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence.get("phase") != "prepared":
        raise RuntimeError("Saved PNA state is not in the prepared phase")
    evidence["phase"] = "applied"
    evidence["appliedState"] = "Disabled"
    evidence["appliedEtag"] = applied_etag
    evidence["appliedAtUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary_path.replace(path)


def load_prior_state(
    evidence_path: str,
    account_resource_id: str,
    max_age_seconds: int,
) -> tuple[str, str]:
    with open(evidence_path, encoding="utf-8") as evidence_file:
        evidence = json.load(evidence_file)
    if evidence.get("accountResourceIdSha256") != sha256_text(
        account_resource_id.lower()
    ):
        raise RuntimeError("Saved PNA state belongs to a different Foundry account")
    prior_state = evidence.get("priorState")
    if prior_state not in {"Enabled", "Disabled"}:
        raise RuntimeError("Saved PNA state is invalid")
    if evidence.get("phase") != "applied" or evidence.get("appliedState") != "Disabled":
        raise RuntimeError("Saved PNA state does not prove a completed disable operation")
    applied_etag = evidence.get("appliedEtag")
    if not isinstance(applied_etag, str) or not applied_etag:
        raise RuntimeError("Saved PNA state has no applied account ETag")
    captured_at = dt.datetime.fromisoformat(str(evidence.get("capturedAtUtc", "")))
    if captured_at.tzinfo is None:
        raise RuntimeError("Saved PNA state timestamp must include a timezone")
    applied_at = dt.datetime.fromisoformat(str(evidence.get("appliedAtUtc", "")))
    if applied_at.tzinfo is None or applied_at < captured_at:
        raise RuntimeError("Saved PNA applied timestamp is invalid")
    age = (dt.datetime.now(dt.timezone.utc) - applied_at).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise RuntimeError("Saved PNA state is stale")
    return prior_state, applied_etag


def acquire_management_token(az_executable: str) -> str:
    result = subprocess.run(
        [
            az_executable,
            "account",
            "get-access-token",
            "--resource",
            f"{MANAGEMENT_ENDPOINT}/",
            "--query",
            "accessToken",
            "--output",
            "tsv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def request_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, object] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict[str, object]]:
    validate_management_url(url)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    headers.update(extra_headers or {})
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    with opener.open(request, timeout=60) as response:
        return response.status, dict(response.headers.items()), json.loads(
            response.read() or b"{}"
        )


class OperationInProgress(RuntimeError):
    pass


def wait_for_operation(
    status: int,
    headers: dict[str, str],
    token: str,
    timeout_seconds: int,
    request_function=request_json,
    sleep_function=time.sleep,
    completion_probe: Callable[[], bool] | None = None,
) -> None:
    if status != 202:
        return
    operation_url = next(
        (
            value
            for key, value in headers.items()
            if key.lower() in {"azure-asyncoperation", "operation-location", "location"}
        ),
        None,
    )
    if not operation_url:
        return
    validate_management_url(operation_url)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _, _, operation = request_function("GET", operation_url, token)
        operation_status = str(
            operation.get("status")
            or operation.get("properties", {}).get("provisioningState")
            or ""
        ).lower()
        if operation_status in {"succeeded", "completed"}:
            return
        if operation_status in {"failed", "canceled", "cancelled"}:
            raise RuntimeError(f"Azure operation ended in {operation_status}")
        if completion_probe and completion_probe():
            return
        sleep_function(2)
    raise OperationInProgress("Azure update is still in progress after the polling timeout")


def wait_for_account_state(
    account_url: str,
    token: str,
    expected_state: str,
    timeout_seconds: int,
    request_function=request_json,
    sleep_function=time.sleep,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _, _, account = request_function("GET", account_url, token)
        properties = account.get("properties", {})
        if (
            properties.get("publicNetworkAccess") == expected_state
            and str(properties.get("provisioningState", "")).lower() == "succeeded"
        ):
            return account
        sleep_function(2)
    raise OperationInProgress(
        f"Foundry account has not reached publicNetworkAccess={expected_state}"
    )


def change_public_network_access(
    args: argparse.Namespace,
    token: str,
    request_function=request_json,
) -> dict[str, object]:
    provider_url = (
        f"{MANAGEMENT_ENDPOINT}/subscriptions/{args.subscription_id}"
        f"/providers/Microsoft.CognitiveServices?api-version={PROVIDER_API_VERSION}"
    )
    _, _, provider = request_function("GET", provider_url, token)
    api_version = select_account_api_version(provider)
    account_path = (
        f"/subscriptions/{urllib.parse.quote(args.subscription_id)}"
        f"/resourceGroups/{urllib.parse.quote(args.resource_group)}"
        "/providers/Microsoft.CognitiveServices/accounts/"
        f"{urllib.parse.quote(args.account_name)}"
    )
    account_url = f"{MANAGEMENT_ENDPOINT}{account_path}?api-version={api_version}"
    _, before_headers, before = request_function("GET", account_url, token)
    before_properties = before.get("properties", {})
    before_state = before_properties.get("publicNetworkAccess")
    if str(before_properties.get("provisioningState", "")).lower() != "succeeded":
        raise RuntimeError("Refusing PNA change while the Foundry account is not Succeeded")
    if before_state not in {"Enabled", "Disabled"}:
        raise RuntimeError("Foundry account returned an invalid publicNetworkAccess state")
    restore_state_from = getattr(args, "restore_state_from", None)
    restore_etag = None
    if restore_state_from:
        requested_state, restore_etag = load_prior_state(
            restore_state_from,
            account_path,
            args.max_restore_age_seconds,
        )
    else:
        requested_state = args.state
    if restore_state_from:
        if before_state != "Disabled":
            raise RuntimeError(
                "Refusing restore because current PNA state is not the test state Disabled"
            )
        if requested_state == "Disabled":
            return {
                "requestedState": requested_state,
                "actualState": before_state,
                "priorState": before_state,
                "changed": False,
                "approvedPrivateEndpointCount": approved_private_endpoint_count(before),
                "provisioningState": before_properties.get("provisioningState"),
                "apiVersion": api_version,
                "passed": True,
            }
        current_etag = resource_etag(before_headers, before)
        if current_etag != restore_etag:
            raise RuntimeError(
                "Refusing restore because the Foundry account changed after PNA was disabled"
            )
    approved_count = approved_private_endpoint_count(before)
    if requested_state == "Disabled" and not restore_state_from:
        if not args.confirm_dedicated_test_account:
            raise RuntimeError(
                "Refusing to disable public access: confirm a dedicated non-production Foundry account with --confirm-dedicated-test-account"
            )
        if approved_count == 0:
            raise RuntimeError(
                "Refusing to disable public access: no usable Approved account-group private endpoint exists"
            )
        if not args.private_probe_evidence:
            raise RuntimeError(
                "Refusing to disable public access: --private-probe-evidence is required"
            )
        validate_private_probe(
            args.private_probe_evidence,
            args.account_name,
            args.max_probe_age_seconds,
        )
        if not args.save_prior_state:
            raise RuntimeError(
                "Refusing to disable public access: --save-prior-state is required"
            )
        save_prior_state(
            args.save_prior_state,
            account_path,
            before_state,
            resource_etag(before_headers, before),
        )

    if before_state == requested_state:
        return {
            "requestedState": requested_state,
            "actualState": before_state,
            "priorState": before_state,
            "changed": False,
            "approvedPrivateEndpointCount": approved_count,
            "provisioningState": before_properties.get("provisioningState"),
            "apiVersion": api_version,
            "passed": True,
        }

    status, headers, _ = request_function(
        "PATCH",
        account_url,
        token,
        {"properties": {"publicNetworkAccess": requested_state}},
        {
            "If-Match": restore_etag
            if restore_state_from
            else resource_etag(before_headers, before)
        },
    )

    def account_has_requested_state() -> bool:
        _, _, current = request_function("GET", account_url, token)
        current_properties = current.get("properties", {})
        return (
            current_properties.get("publicNetworkAccess") == requested_state
            and str(current_properties.get("provisioningState", "")).lower()
            == "succeeded"
        )

    wait_for_operation(
        status,
        headers,
        token,
        args.operation_timeout,
        request_function=request_function,
        completion_probe=account_has_requested_state,
    )
    after = wait_for_account_state(
        account_url,
        token,
        requested_state,
        args.operation_timeout,
        request_function=request_function,
    )
    if requested_state == "Disabled" and not restore_state_from:
        mark_state_applied(
            args.save_prior_state,
            resource_etag({}, after),
        )
    properties = after.get("properties", {})
    return {
        "requestedState": requested_state,
        "actualState": properties.get("publicNetworkAccess"),
        "priorState": before_state,
        "changed": True,
        "approvedPrivateEndpointCount": approved_private_endpoint_count(after),
        "provisioningState": properties.get("provisioningState"),
        "apiVersion": api_version,
        "passed": properties.get("publicNetworkAccess") == requested_state,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Disable public access or restore its previously saved state."
    )
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account-name", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--state", choices=("Disabled",))
    action.add_argument("--restore-state-from")
    parser.add_argument(
        "--confirm-dedicated-test-account",
        action="store_true",
        help="Confirm that the parent Foundry account and all child projects are dedicated non-production test assets",
    )
    parser.add_argument("--az-executable", default="az")
    parser.add_argument("--private-probe-evidence")
    parser.add_argument("--save-prior-state")
    parser.add_argument("--max-probe-age-seconds", type=int, default=900)
    parser.add_argument("--max-restore-age-seconds", type=int, default=3600)
    parser.add_argument("--operation-timeout", type=int, default=300)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token = acquire_management_token(args.az_executable)
    result = change_public_network_access(args, token)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        sys.exit(2)
