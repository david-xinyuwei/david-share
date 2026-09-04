#!/usr/bin/env python3
"""Run the exact load_test_endpoint.py bytes inside a private-IP Azure Container Instance.

Reuses the probe launcher's ARM helpers; only the embedded source and arguments differ.
The container prints the result as short marker lines (see load_test_endpoint.emit_lines);
`--collect-log <file>` reassembles a saved `az container logs` capture into the result JSON.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys
import urllib.parse

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import load_test_endpoint
import submit_private_aci_probe as launcher


def build_load_command(source: bytes, endpoint: str, deployment: str, concurrency: list[int],
                       min_requests: int, max_tokens: int) -> tuple[list[str], str]:
    source_sha256 = hashlib.sha256(source).hexdigest()
    encoded = base64.b64encode(source).decode("ascii")
    bootstrap = (
        "import base64,hashlib,sys;"
        f"s=base64.b64decode('{encoded}');"
        "sys.argv+=['--source-sha256',hashlib.sha256(s).hexdigest()];"
        "exec(compile(s,'load_test_endpoint.py','exec'))"
    )
    command = ["python3", "-c", bootstrap, "--endpoint", endpoint, "--deployment", deployment,
               "--label", "private", "--min-requests-per-level", str(min_requests),
               "--max-tokens", str(max_tokens), "--concurrency", *[str(c) for c in concurrency]]
    return command, source_sha256


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect-log", help="Reassemble a saved container log into the result JSON and exit")
    parser.add_argument("--subscription-id")
    parser.add_argument("--resource-group")
    parser.add_argument("--container-group-name")
    parser.add_argument("--location")
    parser.add_argument("--subnet-id")
    parser.add_argument("--endpoint")
    parser.add_argument("--deployment")
    parser.add_argument("--run-id")
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8, 16, 32])
    parser.add_argument("--min-requests-per-level", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--image", default=launcher.DEFAULT_IMAGE)
    parser.add_argument("--az-executable", default="az")
    parser.add_argument("--output")
    return parser


def collect_from_log(log_path: pathlib.Path, output: str | None) -> dict[str, object]:
    text = log_path.read_text(encoding="utf-8-sig")
    result = load_test_endpoint.collect_lines(text.splitlines())
    if output:
        pathlib.Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8", newline="\n")
    return result


def main() -> int:
    args = build_parser().parse_args()
    if args.collect_log:
        result = collect_from_log(pathlib.Path(args.collect_log), args.output)
        print(json.dumps({"passed": result["passed"], "label": result["label"],
                          "requests": len(result["requests"]), "dnsClass": result["dnsClass"]}))
        return 0 if result["passed"] else 1
    required = ("subscription_id", "resource_group", "container_group_name", "location",
                "subnet_id", "endpoint", "deployment", "run_id")
    missing = [name for name in required if not getattr(args, name)]
    if missing:
        raise SystemExit("missing required arguments: " + ", ".join("--" + m.replace("_", "-") for m in missing))
    launcher.validate_name(args.container_group_name, "--container-group-name")
    launcher.validate_subnet_id(args.subnet_id, args.subscription_id)
    load_test_endpoint.validate_endpoint(args.endpoint)
    source = (SCRIPT_DIR / "load_test_endpoint.py").read_bytes()
    command, source_sha256 = build_load_command(source, args.endpoint, args.deployment,
                                                args.concurrency, args.min_requests_per_level, args.max_tokens)
    management_token = launcher.acquire_token(args.az_executable, f"{launcher.MANAGEMENT_ENDPOINT}/")
    provider_url = (f"{launcher.MANAGEMENT_ENDPOINT}/subscriptions/{args.subscription_id}"
                    f"/providers/Microsoft.ContainerInstance?api-version={launcher.PROVIDER_API_VERSION}")
    _, provider = launcher.request_json("GET", provider_url, management_token)
    api_version = launcher.select_container_group_api_version(provider)
    resource_url = (f"{launcher.MANAGEMENT_ENDPOINT}/subscriptions/{args.subscription_id}"
                    f"/resourceGroups/{urllib.parse.quote(args.resource_group)}"
                    "/providers/Microsoft.ContainerInstance/containerGroups/"
                    f"{urllib.parse.quote(args.container_group_name)}?api-version={api_version}")
    api_key = os.getenv("AZURE_AI_API_KEY")
    if api_key:
        data_secret, secret_variable = api_key, "AZURE_AI_API_KEY"
    else:
        data_secret = launcher.acquire_token(args.az_executable, "https://cognitiveservices.azure.com/")
        secret_variable = "AZURE_ACCESS_TOKEN"
    payload = launcher.build_container_group_payload(args.container_group_name, args.location, args.subnet_id,
                                                     args.image, command, data_secret, args.run_id, secret_variable)
    status, response = launcher.create_container_group(resource_url, management_token, payload)
    result = launcher.sanitized_result(status, response, source_sha256, args.image)
    result["secretVariable"] = secret_variable
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
