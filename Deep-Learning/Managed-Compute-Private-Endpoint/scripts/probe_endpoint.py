#!/usr/bin/env python3
"""Validate a Foundry model endpoint from the caller's current network."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import os
import pathlib
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


ALLOWED_HOST_SUFFIXES = (
    ".services.ai.azure.com",
    ".openai.azure.com",
    ".cognitiveservices.azure.com",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_identity_sha256(token: str) -> str:
    parts = token.split(".")
    if len(parts) < 2:
        raise RuntimeError("Entra access token is not a JWT")
    encoded_claims = parts[1]
    try:
        claims = json.loads(
            base64.urlsafe_b64decode(encoded_claims + "=" * (-len(encoded_claims) % 4))
        )
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Entra access token claims are not readable") from error
    tenant = claims.get("tid") if isinstance(claims, dict) else None
    subject = (claims.get("oid") or claims.get("sub")) if isinstance(claims, dict) else None
    if not isinstance(tenant, str) or not isinstance(subject, str):
        raise RuntimeError("Entra access token has no stable tenant and subject claims")
    return sha256_text(f"{tenant}:{subject}")


def probe_source_sha256(supplied_digest: str | None) -> str:
    if supplied_digest is not None:
        if len(supplied_digest) != 64 or any(
            character not in "0123456789abcdef" for character in supplied_digest.lower()
        ):
            raise ValueError("--probe-source-sha256 must be a SHA-256 hex digest")
        return supplied_digest.lower()
    path = pathlib.Path(__file__)
    if not path.is_file():
        raise RuntimeError("Probe source hash must be supplied for embedded execution")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_endpoint(endpoint: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(endpoint)
    hostname = parsed.hostname or ""
    if parsed.scheme != "https" or not hostname:
        raise ValueError("--endpoint must be a complete HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Endpoint userinfo is not allowed")
    if parsed.port not in (None, 443):
        raise ValueError("Endpoint port must be 443")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Endpoint IP literals are not allowed")
    if not hostname.lower().endswith(ALLOWED_HOST_SUFFIXES):
        raise ValueError("Endpoint hostname is not an allowed Azure AI service domain")
    if parsed.query or parsed.fragment:
        raise ValueError("Endpoint query strings and fragments are not allowed")
    if not parsed.path.endswith("/openai/v1/chat/completions"):
        raise ValueError("Endpoint path must target /openai/v1/chat/completions")
    return parsed


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def classify_addresses(addresses: list[str]) -> str:
    classes = {
        "private" if ipaddress.ip_address(address).is_private else "public"
        for address in addresses
    }
    return classes.pop() if len(classes) == 1 else "mixed"


def resolve_addresses(hostname: str) -> list[str]:
    return sorted(
        {
            result[4][0]
            for result in socket.getaddrinfo(
                hostname, 443, type=socket.SOCK_STREAM
            )
        }
    )


def acquire_token(az_executable: str, token_environment_variable: str) -> str:
    token = os.getenv(token_environment_variable)
    if token:
        return token

    result = subprocess.run(
        [
            az_executable,
            "account",
            "get-access-token",
            "--resource",
            "https://cognitiveservices.azure.com/",
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


def summarize_body(body: bytes) -> dict[str, object]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"responseFormat": "non-json", "responseBytes": len(body)}

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message", ""))
        network_policy_blocked = "public access is disabled" in message.lower()
        return {
            "errorCode": error.get("code"),
            "errorCategory": (
                "public-access-disabled" if network_policy_blocked else "service-error"
            ),
            "networkPolicyBlocked": network_policy_blocked,
            "errorMessageBytes": len(message.encode("utf-8")),
            "errorMessageSha256": sha256_text(message),
        }

    choices = payload.get("choices") if isinstance(payload, dict) else None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    return {
        "object": payload.get("object") if isinstance(payload, dict) else None,
        "responseModel": payload.get("model") if isinstance(payload, dict) else None,
        "choiceCount": len(choices) if isinstance(choices, list) else None,
        "usage": {
            key: usage.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(usage, dict) and key in usage
        },
    }


def result_satisfies_expectation(
    result: dict[str, object],
    expected_dns: str,
    expected_http: int,
) -> bool:
    if result.get("dnsClass") != expected_dns or result.get("httpStatus") != expected_http:
        return False
    if expected_http == 403:
        return (
            result.get("networkPolicyBlocked") is True
            and result.get("errorCategory") == "public-access-disabled"
        )
    if expected_http == 200:
        return (
            result.get("object") == "chat.completion"
            and isinstance(result.get("choiceCount"), int)
            and result["choiceCount"] > 0
        )
    return True


def build_auth(args: argparse.Namespace) -> tuple[dict[str, str], str, str | None]:
    """Return (headers, authMethod, identitySha256). API key wins when present."""
    api_key = os.getenv(args.api_key_environment_variable)
    if api_key:
        return {"api-key": api_key}, "api-key", None
    token = acquire_token(args.az_executable, args.token_environment_variable)
    return (
        {"Authorization": f"Bearer {token}"},
        "entra-bearer",
        token_identity_sha256(token),
    )


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    parsed_endpoint = validate_endpoint(args.endpoint)

    addresses = resolve_addresses(parsed_endpoint.hostname)
    auth_headers, auth_method, identity_sha256 = build_auth(args)
    request_body = json.dumps(
        {
            "model": args.deployment,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": args.max_tokens,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        args.endpoint,
        data=request_body,
        headers={**auth_headers, "Content-Type": "application/json"},
        method="POST",
    )

    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=args.timeout) as response:
            status = response.status
            response_headers = response.headers
            response_body = response.read(args.max_response_bytes)
    except urllib.error.HTTPError as error:
        status = error.code
        response_headers = error.headers
        response_body = error.read(args.max_response_bytes)

    request_id = response_headers.get("x-request-id") or response_headers.get(
        "apim-request-id"
    )
    result: dict[str, object] = {
        "capturedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hostnameSha256": sha256_text(parsed_endpoint.hostname),
        "endpointSha256": sha256_text(args.endpoint),
        "deploymentSha256": sha256_text(args.deployment),
        "authMethod": auth_method,
        "identitySha256": identity_sha256,
        "probeSourceSha256": probe_source_sha256(args.probe_source_sha256),
        "requestSha256": hashlib.sha256(request_body).hexdigest(),
        "addressCount": len(addresses),
        "dnsClass": classify_addresses(addresses),
        "httpStatus": status,
        "requestIdSha256": sha256_text(request_id) if request_id else None,
        **summarize_body(response_body),
    }
    if args.include_sensitive_diagnostics:
        result["hostname"] = parsed_endpoint.hostname
        result["resolvedAddresses"] = addresses
    result["passed"] = result_satisfies_expectation(
        result,
        args.expect_dns,
        args.expect_http,
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe a Foundry endpoint and assert its DNS and HTTP behavior."
    )
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--expect-dns", choices=("public", "private", "mixed"), required=True)
    parser.add_argument("--expect-http", type=int, required=True)
    parser.add_argument("--prompt", default="Reply with exactly OK.")
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-response-bytes", type=int, default=16_384)
    parser.add_argument("--az-executable", default="az")
    parser.add_argument("--api-key-environment-variable", default="AZURE_AI_API_KEY")
    parser.add_argument("--token-environment-variable", default="AZURE_ACCESS_TOKEN")
    parser.add_argument("--probe-source-sha256")
    parser.add_argument("--output", help="Write the sanitized result to this JSON file")
    parser.add_argument("--include-sensitive-diagnostics", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_probe(args)
    except Exception as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 2

    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(output, end="")
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(output)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())