#!/usr/bin/env python3
"""Create, reconnect to, and validate one LRA Evidence Agent response."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

SOURCE = Path(__file__).resolve().parent / "src" / "lra-evidence-agent"
sys.path.insert(0, str(SOURCE))

from contract import ContractError, validate_terminal_response  # noqa: E402

# A known response can be temporarily absent while replacement compute starts.
# The deadline still bounds this; an unknown or mistyped ID therefore fails closed.
TRANSIENT_HTTP_STATUSES = {404, 424, 429, 500, 502, 503, 504}
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "incomplete"}


class ResponseRequestError(RuntimeError):
    """An HTTP response that the caller cannot safely ignore."""

    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_acceptance(acceptance: dict[str, Any]) -> dict[str, Any]:
    process_ids = acceptance["process_instance_ids"]
    return {
        key: value
        for key, value in acceptance.items()
        if key != "process_instance_ids"
    } | {
        "process_instance_count": len(process_ids),
        "process_instance_sha256": [sha256_text(value) for value in process_ids],
    }


def responses_url(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    if not path.endswith("/responses"):
        path = f"{path}/responses"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def response_item_url(endpoint: str, response_id: str) -> str:
    parsed = urllib.parse.urlsplit(responses_url(endpoint))
    path = f"{parsed.path}/{urllib.parse.quote(response_id, safe='')}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def azure_cli_token() -> str:
    az = shutil.which("az.exe") or shutil.which("az.cmd") or shutil.which("az")
    if not az:
        raise RuntimeError("Azure CLI executable was not found on PATH")
    command = [
        az,
        "account",
        "get-access-token",
        "--resource",
        "https://ai.azure.com",
        "--query",
        "accessToken",
        "-o",
        "tsv",
    ]
    if Path(az).suffix.lower() in {".cmd", ".bat"}:
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Azure CLI returned an empty access token")
    return token


def request_json(
    method: str,
    url: str,
    body: dict[str, Any] | None,
    token: str | None,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise ResponseRequestError(error.code, error_body) from error
    return json.loads(payload)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def create_work(
    endpoint: str,
    work_id: str,
    payload: str,
    crash_after_stage: int | None,
    stage_delay_ms: int,
    token: str | None,
) -> dict[str, Any]:
    work_input = {
        "work_id": work_id,
        "payload": payload,
        "crash_after_stage": crash_after_stage,
        "stage_delay_ms": stage_delay_ms,
    }
    response = request_json(
        "POST",
        responses_url(endpoint),
        {
            "model": "lra-evidence-agent",
            "input": json.dumps(work_input, sort_keys=True),
            "store": True,
            "background": True,
        },
        token,
    )
    response_id = response.get("id")
    if not isinstance(response_id, str) or not response_id:
        raise RuntimeError(f"create response did not return an ID: {response!r}")
    return response


def poll_work(
    endpoint: str,
    response_id: str,
    token: str | None,
    deadline_seconds: float,
    poll_interval_seconds: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + deadline_seconds
    events: list[dict[str, Any]] = []
    url = response_item_url(endpoint, response_id)
    while time.monotonic() < deadline:
        try:
            response = request_json("GET", url, None, token)
        except ResponseRequestError as error:
            events.append(
                {
                    "at": utc_now(),
                    "kind": "http_error",
                    "status": error.status,
                }
            )
            if error.status not in TRANSIENT_HTTP_STATUSES:
                raise
        except (TimeoutError, urllib.error.URLError) as error:
            reason = getattr(error, "reason", error)
            events.append(
                {
                    "at": utc_now(),
                    "kind": "connection_error",
                    "detail": type(reason).__name__,
                }
            )
        else:
            status = response.get("status")
            events.append(
                {
                    "at": utc_now(),
                    "kind": "poll",
                    "status": status,
                    "output_count": len(response.get("output") or []),
                }
            )
            if status in TERMINAL_STATUSES:
                return response, events
        time.sleep(poll_interval_seconds)
    raise TimeoutError(
        f"response {response_id} did not reach a terminal state "
        f"within {deadline_seconds} seconds"
    )


def run_test(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    started_monotonic = time.monotonic()
    token = azure_cli_token() if args.auth == "azure-cli" else None
    if args.resume:
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        response_id = state["response_id"]
        work_id = state["work_id"]
        crash_after_stage = state["crash_after_stage"]
        stage_delay_ms = state["stage_delay_ms"]
    else:
        created = create_work(
            endpoint=args.endpoint,
            work_id=args.work_id,
            payload=args.payload,
            crash_after_stage=args.crash_after_stage,
            stage_delay_ms=args.stage_delay_ms,
            token=token,
        )
        response_id = created["id"]
        work_id = args.work_id
        crash_after_stage = args.crash_after_stage
        stage_delay_ms = args.stage_delay_ms
        state = {
            "schema_version": 1,
            "created_at": utc_now(),
            "work_id": work_id,
            "response_id": response_id,
            "crash_after_stage": crash_after_stage,
            "stage_delay_ms": stage_delay_ms,
            "deadline_seconds": args.deadline_seconds,
        }
        write_json_atomic(args.state_file, state)
    terminal, events = poll_work(
        endpoint=args.endpoint,
        response_id=response_id,
        token=token,
        deadline_seconds=args.deadline_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    acceptance = validate_terminal_response(
        response=terminal,
        expected_work_id=work_id,
        expect_recovery=crash_after_stage is not None,
    )
    report = {
        "schema_version": 1,
        "evidence_type": "owned-hosted-agent-recovery",
        "generated_at_utc": utc_now(),
        "started_at_utc": started_at,
        "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
        "endpoint_class": (
            "local-loopback"
            if urllib.parse.urlparse(args.endpoint).hostname
            in {"127.0.0.1", "localhost"}
            else "foundry-hosted-agent"
        ),
        "response_id_sha256": sha256_text(response_id),
        "request": {
            "work_id": work_id,
            "crash_after_stage": crash_after_stage,
            "stage_delay_ms": stage_delay_ms,
        },
        "poll_events": events,
        "acceptance": public_acceptance(acceptance),
        "passed": True,
    }
    if args.agent_version or args.deployed_content_sha256:
        report["deployment"] = {
            "agent_name": "lra-evidence-agent",
            "version": args.agent_version,
            "content_sha256": args.deployed_content_sha256,
        }
    write_json_atomic(args.report, report)
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8088")
    parser.add_argument("--auth", choices=("none", "azure-cli"), default="none")
    parser.add_argument("--work-id", default="owned-agent-recovery-001")
    parser.add_argument(
        "--payload",
        default="public-safe deterministic LRA evidence workload",
    )
    parser.add_argument(
        "--crash-after-stage",
        type=int,
        help="inject one process loss after this stage; omitted for a safe run",
    )
    parser.add_argument("--stage-delay-ms", type=int, default=500)
    parser.add_argument("--deadline-seconds", type=float, default=180)
    parser.add_argument("--poll-interval-seconds", type=float, default=1)
    parser.add_argument("--agent-version")
    parser.add_argument("--deployed-content-sha256")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume polling the exact response recorded in --state-file",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path(".demo-state/owned-agent-response.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".demo-state/owned-agent-recovery.json"),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_test(args)
    except (ContractError, ResponseRequestError, RuntimeError, TimeoutError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: same response completed all stages across "
        f"{report['acceptance']['process_instance_count']} process instances"
    )
    print(f"response_id_sha256={report['response_id_sha256']}")
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
