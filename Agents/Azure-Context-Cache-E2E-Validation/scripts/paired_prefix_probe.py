"""Run an isolated-prefix comparison between cache-linked and control deployments."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse


TOKEN_SCOPE = "https://cognitiveservices.azure.com"
API_VERSION = "preview"
ARM_MARKERS = {"linked": "A", "control": "B"}


def build_prefixes(base: bytes, run_id: str) -> tuple[dict[str, bytes], dict[str, str]]:
    if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", run_id):
        raise ValueError("run-id must be 8-64 letters, digits, or hyphens")
    if len(base) < 4_000:
        raise ValueError("base prefix must contain at least 4,000 bytes")

    prefixes = {
        arm: f"CTX-CACHE-ISOLATION/{run_id}/ARM={cohort}\n".encode("ascii") + base
        for arm, cohort in ARM_MARKERS.items()
    }
    if len(prefixes["linked"]) != len(prefixes["control"]):
        raise ValueError("cohort markers must produce equal-length prefixes")
    first_difference = next(
        index
        for index, pair in enumerate(zip(prefixes["linked"], prefixes["control"]))
        if pair[0] != pair[1]
    )
    if first_difference >= 1_024:
        raise ValueError("prefixes must differ before the first 1,024 bytes")
    hashes = {
        arm: hashlib.sha256(prefix).hexdigest() for arm, prefix in prefixes.items()
    }
    return prefixes, hashes


def get_access_token() -> str:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        raise RuntimeError("Azure CLI was not found on PATH")
    result = subprocess.run(
        [
            az,
            "account",
            "get-access-token",
            "--resource",
            TOKEN_SCOPE,
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"Azure CLI token acquisition failed: {result.stderr.strip()}")
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Azure CLI returned an empty access token")
    return token


def run_az_json(arguments: list[str]) -> dict[str, object]:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        raise RuntimeError("Azure CLI was not found on PATH")
    result = subprocess.run(
        [az, *arguments, "-o", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"Azure CLI ARM read failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def validate_arm_documents(
    account: dict[str, object],
    linked: dict[str, object],
    control: dict[str, object],
    container: dict[str, object],
    expected_endpoint: str,
    expected_container_id: str,
    expected_ttl_days: int,
) -> dict[str, object]:
    account_endpoint = (account.get("properties") or {}).get("endpoint")
    if not isinstance(account_endpoint, str) or (
        account_endpoint.rstrip("/").casefold() != expected_endpoint.rstrip("/").casefold()
    ):
        raise ValueError("data-plane endpoint does not match the ARM account")
    for name, deployment in (("linked", linked), ("control", control)):
        properties = deployment.get("properties") or {}
        if properties.get("provisioningState") != "Succeeded":
            raise ValueError(f"{name} deployment is not provisioned")
    linked_properties = linked["properties"]
    control_properties = control["properties"]
    linked_model = linked_properties.get("model")
    if linked_model != control_properties.get("model"):
        raise ValueError("deployment model identities differ")
    if linked.get("sku") != control.get("sku"):
        raise ValueError("deployment SKUs or capacities differ")
    linked_container_id = linked_properties.get("contextCacheContainerId")
    if not isinstance(linked_container_id, str) or (
        linked_container_id.casefold() != expected_container_id.casefold()
    ):
        raise ValueError("linked deployment cache binding does not match")
    if control_properties.get("contextCacheContainerId") is not None:
        raise ValueError("control deployment unexpectedly has a cache binding")
    container_properties = container.get("properties") or {}
    if container_properties.get("provisioningState") != "Succeeded":
        raise ValueError("Context Cache container is not provisioned")
    if container_properties.get("modelName") != linked_model.get("name"):
        raise ValueError("container and deployment model names differ")
    if container_properties.get("timeToLive") != expected_ttl_days:
        raise ValueError("container TTL differs from the experiment contract")
    return {
        "model": linked_model.get("name"),
        "model_version": linked_model.get("version"),
        "capacity": linked.get("sku", {}).get("capacity"),
        "container_ttl_days": container_properties.get("timeToLive"),
    }


def validate_arm_contract(args: argparse.Namespace) -> dict[str, object]:
    account_url = (
        "https://management.azure.com/subscriptions/"
        f"{quote(args.subscription_id, safe='')}/resourceGroups/"
        f"{quote(args.resource_group, safe='')}/providers/"
        "Microsoft.CognitiveServices/accounts/"
        f"{quote(args.account_name, safe='')}"
    )
    account = run_az_json(
        [
            "rest",
            "--method",
            "get",
            "--url",
            f"{account_url}?api-version=2024-10-01",
        ]
    )
    base = f"{account_url}/deployments"
    linked = run_az_json(
        [
            "rest",
            "--method",
            "get",
            "--url",
            f"{base}/{quote(args.linked_deployment, safe='')}?api-version=2026-03-15-preview",
        ]
    )
    control = run_az_json(
        [
            "rest",
            "--method",
            "get",
            "--url",
            f"{base}/{quote(args.control_deployment, safe='')}?api-version=2026-03-15-preview",
        ]
    )
    container = run_az_json(
        [
            "rest",
            "--method",
            "get",
            "--url",
            "https://management.azure.com"
            f"{args.expected_container_id}?api-version=2026-01-01-preview",
        ]
    )
    return validate_arm_documents(
        account,
        linked,
        control,
        container,
        args.endpoint,
        args.expected_container_id,
        args.expected_container_ttl_days,
    )


def read_rows(path: Path, run_id: str) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("run_id") == run_id:
                rows.append(row)
    return rows


def validate_warm_rows(
    rows: list[dict[str, object]], hashes: dict[str, str]
) -> datetime:
    warm = [row for row in rows if row.get("phase") == "WARM"]
    if len(warm) != 4:
        raise ValueError(f"WARM requires exactly four rows, found {len(warm)}")
    by_arm = {
        arm: sorted(
            (row for row in warm if row.get("arm") == arm),
            key=lambda row: int(row["call"]),
        )
        for arm in ARM_MARKERS
    }
    for arm, arm_rows in by_arm.items():
        if len(arm_rows) != 2:
            raise ValueError(f"WARM requires two {arm} rows")
        if [row.get("http_status") for row in arm_rows] != [200, 200]:
            raise ValueError(f"WARM contains a failed {arm} request")
        if arm_rows[0].get("cached_tokens") != 0:
            raise ValueError(f"WARM first {arm} call must be a cache miss")
        if not isinstance(arm_rows[1].get("cached_tokens"), int) or int(
            arm_rows[1]["cached_tokens"]
        ) <= 0:
            raise ValueError(f"WARM second {arm} call must be a cache hit")
        if {row.get("prefix_sha256") for row in arm_rows} != {hashes[arm]}:
            raise ValueError(f"WARM {arm} prefix hash changed")
    input_tokens = {row.get("input_tokens") for row in warm}
    if len(input_tokens) != 1 or None in input_tokens:
        raise ValueError("WARM arms must have identical measurable input-token counts")
    return max(datetime.fromisoformat(str(row["ts"])) for row in warm)


def call_once(
    endpoint: str,
    deployment: str,
    token: str,
    prefix: bytes,
    suffix: str,
) -> dict[str, object]:
    payload = {
        "model": deployment,
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": prefix.decode("utf-8")}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": suffix}],
            },
        ],
        "max_output_tokens": 200,
        "prompt_cache_retention": "24h",
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/openai/v1/responses?api-version={API_VERSION}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = json.load(response)
            status = response.status
    except urllib.error.HTTPError as error:
        return {
            "http_status": error.code,
            "latency_ms": round((time.perf_counter() - started) * 1_000),
            "error": error.read(400).decode("utf-8", errors="replace"),
        }
    usage = body.get("usage", {})
    return {
        "http_status": status,
        "latency_ms": round((time.perf_counter() - started) * 1_000),
        "input_tokens": usage.get("input_tokens"),
        "cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }


def valid_endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(
        ".openai.azure.com"
    ):
        raise argparse.ArgumentTypeError(
            "endpoint must be an https://*.openai.azure.com URL"
        )
    return value.rstrip("/")


def require_private_output(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(Path(__file__).resolve().parents[1])
    except ValueError:
        return resolved
    raise ValueError("output must be outside the public source tree")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, type=valid_endpoint)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account-name", required=True)
    parser.add_argument("--linked-deployment", required=True)
    parser.add_argument("--control-deployment", required=True)
    parser.add_argument("--expected-container-id", required=True)
    parser.add_argument("--expected-container-ttl-days", type=int, default=7)
    parser.add_argument("--prefix-file", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", required=True, choices=("WARM", "VERIFY"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-verify-hours", type=float, default=26.0)
    args = parser.parse_args()

    if not os.environ.get("AZURE_CONFIG_DIR"):
        raise SystemExit("AZURE_CONFIG_DIR must identify an isolated Azure CLI profile")
    try:
        args.output = require_private_output(args.output)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    calls_per_arm = 2 if args.phase == "WARM" else 1
    base = args.prefix_file.read_bytes()
    prefixes, hashes = build_prefixes(base, args.run_id)
    existing_rows = read_rows(args.output, args.run_id)
    if any(row.get("phase") == args.phase for row in existing_rows):
        raise SystemExit(f"{args.phase} already has rows for this run-id")
    if args.phase == "VERIFY":
        try:
            warm_completed = validate_warm_rows(existing_rows, hashes)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        due = warm_completed + timedelta(hours=args.minimum_verify_hours)
        now = datetime.now(timezone.utc)
        if now < due:
            raise SystemExit(f"VERIFY is not due until {due.isoformat()}")
    arm_contract = validate_arm_contract(args)
    token = get_access_token()
    deployments = {
        "linked": args.linked_deployment,
        "control": args.control_deployment,
    }

    failures = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for call_index in range(1, calls_per_arm + 1):
        for arm in ("linked", "control"):
            suffix = (
                f"Review the case under the rules above. Experiment {args.run_id}; "
                f"phase {args.phase}; call {call_index}."
            )
            row = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "lineage": "paired-prefix-context-cache-attribution",
                "run_id": args.run_id,
                "phase": args.phase,
                "arm": arm,
                "call": call_index,
                "deployment": deployments[arm],
                "prefix_sha256": hashes[arm],
                "prompt_cache_retention": "24h",
                "arm_contract_verified": True,
                **arm_contract,
            }
            row.update(
                call_once(
                    args.endpoint,
                    deployments[arm],
                    token,
                    prefixes[arm],
                    suffix,
                )
            )
            failures += row["http_status"] != 200
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"{args.phase} {arm:<7} call={call_index} "
                f"status={row['http_status']} cached={row.get('cached_tokens')} "
                f"input={row.get('input_tokens')} latency={row['latency_ms']}ms",
                flush=True,
            )
    if failures:
        return 1
    if args.phase == "WARM":
        try:
            validate_warm_rows(read_rows(args.output, args.run_id), hashes)
        except ValueError as error:
            print(f"WARM_GATE=FAIL: {error}", file=sys.stderr)
            return 1
        print("WARM_GATE=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
