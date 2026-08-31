#!/usr/bin/env python3
"""Submit the exact endpoint probe to a private-IP Azure Container Instance."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import probe_endpoint


MANAGEMENT_ENDPOINT = "https://management.azure.com"
PROVIDER_API_VERSION = "2021-04-01"
DEFAULT_IMAGE = "mcr.microsoft.com/azure-cli:2.77.0"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def validate_name(value: str, label: str) -> None:
    if not NAME_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must contain 3-63 lowercase letters, numbers, or hyphens")


def validate_subnet_id(subnet_id: str, subscription_id: str) -> None:
    parts = subnet_id.strip("/").split("/")
    expected = (
        len(parts) == 10
        and parts[0].lower() == "subscriptions"
        and parts[2].lower() == "resourcegroups"
        and parts[4].lower() == "providers"
        and parts[5].lower() == "microsoft.network"
        and parts[6].lower() == "virtualnetworks"
        and parts[8].lower() == "subnets"
    )
    if not expected:
        raise ValueError("--subnet-id must be a complete Azure VNet subnet resource ID")
    if parts[1].lower() != subscription_id.lower():
        raise ValueError("The ACI subnet must be in the selected subscription")


def select_container_group_api_version(provider: dict[str, object]) -> str:
    resource_types = provider.get("resourceTypes")
    if not isinstance(resource_types, list):
        raise ValueError("Microsoft.ContainerInstance provider metadata is incomplete")
    container_groups = next(
        (
            item
            for item in resource_types
            if isinstance(item, dict)
            and str(item.get("resourceType", "")).lower() == "containergroups"
        ),
        None,
    )
    if not container_groups:
        raise ValueError("Container group API metadata is missing")
    versions = [str(value) for value in container_groups.get("apiVersions", [])]
    stable = [value for value in versions if "preview" not in value.lower()]
    if not stable and not versions:
        raise ValueError("No container group API version is advertised")
    return sorted(stable or versions, reverse=True)[0]


def acquire_token(az_executable: str, resource: str) -> str:
    completed = subprocess.run(
        [
            az_executable,
            "account",
            "get-access-token",
            "--resource",
            resource,
            "--query",
            "accessToken",
            "--output",
            "tsv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def request_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, object] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "management.azure.com":
        raise ValueError("ARM URL must use https://management.azure.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    headers.update(extra_headers or {})
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    with opener.open(request, timeout=90) as response:
        return response.status, json.loads(response.read() or b"{}")


def create_container_group(
    resource_url: str,
    management_token: str,
    payload: dict[str, object],
    request_function=request_json,
) -> tuple[int, dict[str, object]]:
    try:
        status, _ = request_function("GET", resource_url, management_token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        if status != 404:
            raise RuntimeError(
                "Refusing to update an existing container group; use a unique name"
            )
    return request_function(
        "PUT",
        resource_url,
        management_token,
        payload,
        {"If-None-Match": "*"},
    )


def build_probe_command(
    probe_source: bytes,
    endpoint: str,
    deployment: str,
) -> tuple[list[str], str]:
    probe_source_sha256 = hashlib.sha256(probe_source).hexdigest()
    encoded_source = base64.b64encode(probe_source).decode("ascii")
    bootstrap = (
        "import base64;"
        f"exec(compile(base64.b64decode('{encoded_source}'),"
        "'probe_endpoint.py','exec'))"
    )
    command = [
        "python3",
        "-c",
        bootstrap,
        "--endpoint",
        endpoint,
        "--deployment",
        deployment,
        "--expect-dns",
        "private",
        "--expect-http",
        "200",
        "--prompt",
        "Reply with exactly OK.",
        "--max-tokens",
        "4",
        "--probe-source-sha256",
        probe_source_sha256,
    ]
    return command, probe_source_sha256


def build_container_group_payload(
    name: str,
    location: str,
    subnet_id: str,
    image: str,
    command: list[str],
    data_token: str,
    run_id: str,
) -> dict[str, object]:
    return {
        "location": location,
        "tags": {
            "purpose": "managed-compute-private-endpoint-e2e",
            "runId": run_id,
        },
        "properties": {
            "containers": [
                {
                    "name": "probe",
                    "properties": {
                        "image": image,
                        "command": command,
                        "environmentVariables": [
                            {"name": "AZURE_ACCESS_TOKEN", "secureValue": data_token}
                        ],
                        "ports": [{"port": 80, "protocol": "TCP"}],
                        "resources": {
                            "requests": {"cpu": 1, "memoryInGB": 1}
                        },
                    },
                }
            ],
            "ipAddress": {
                "type": "Private",
                "ports": [{"port": 80, "protocol": "TCP"}],
            },
            "osType": "Linux",
            "restartPolicy": "Never",
            "subnetIds": [{"id": subnet_id}],
        },
    }


def sanitized_result(
    response_status: int,
    response: dict[str, object],
    probe_source_sha256: str,
    image: str,
) -> dict[str, object]:
    properties = response.get("properties", {})
    return {
        "httpStatus": response_status,
        "containerGroupId": response.get("id"),
        "provisioningState": properties.get("provisioningState"),
        "requestedIpAddressType": "Private",
        "observedIpAddressType": properties.get("ipAddress", {}).get("type"),
        "image": image,
        "probeSourceSha256": probe_source_sha256,
        "passed": response_status in {200, 201, 202},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--container-group-name", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--subnet-id", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--az-executable", default="az")
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_name(args.container_group_name, "--container-group-name")
    validate_subnet_id(args.subnet_id, args.subscription_id)
    probe_endpoint.validate_endpoint(args.endpoint)
    probe_source = (pathlib.Path(__file__).parent / "probe_endpoint.py").read_bytes()
    command, probe_source_sha256 = build_probe_command(
        probe_source,
        args.endpoint,
        args.deployment,
    )
    management_token = acquire_token(
        args.az_executable, f"{MANAGEMENT_ENDPOINT}/"
    )
    provider_url = (
        f"{MANAGEMENT_ENDPOINT}/subscriptions/{args.subscription_id}"
        f"/providers/Microsoft.ContainerInstance?api-version={PROVIDER_API_VERSION}"
    )
    _, provider = request_json("GET", provider_url, management_token)
    api_version = select_container_group_api_version(provider)
    resource_url = (
        f"{MANAGEMENT_ENDPOINT}/subscriptions/{args.subscription_id}"
        f"/resourceGroups/{urllib.parse.quote(args.resource_group)}"
        "/providers/Microsoft.ContainerInstance/containerGroups/"
        f"{urllib.parse.quote(args.container_group_name)}?api-version={api_version}"
    )
    data_token = acquire_token(
        args.az_executable, "https://cognitiveservices.azure.com/"
    )
    payload = build_container_group_payload(
        args.container_group_name,
        args.location,
        args.subnet_id,
        args.image,
        command,
        data_token,
        args.run_id,
    )
    status, response = create_container_group(
        resource_url,
        management_token,
        payload,
    )
    result = sanitized_result(status, response, probe_source_sha256, args.image)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.output:
        pathlib.Path(args.output).write_text(output, encoding="utf-8", newline="\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        sys.exit(2)