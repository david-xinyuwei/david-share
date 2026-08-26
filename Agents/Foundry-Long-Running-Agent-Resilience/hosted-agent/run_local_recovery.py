#!/usr/bin/env python3
"""Hard-crash the owned agent, restart it, and validate the same response."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

from client import (
    create_work,
    poll_work,
    public_acceptance,
    sha256_text,
    utc_now,
    write_json_atomic,
)

SOURCE = Path(__file__).resolve().parent / "src" / "lra-evidence-agent"

sys.path.insert(0, str(SOURCE))
from contract import validate_terminal_response  # noqa: E402


def start_server(python: Path, state_root: Path, log_path: Path) -> subprocess.Popen:
    environment = os.environ.copy()
    environment.update(
        {
            "AGENTSERVER_STATE_ROOT": str(state_root),
            "LRA_ENABLE_FAULT_INJECTION": "true",
            "LRA_STAGE_DELAY_MS": "250",
            "OTEL_SDK_DISABLED": "true",
            "PYTHONUNBUFFERED": "1",
        }
    )
    log_handle = log_path.open("ab")
    try:
        return subprocess.Popen(
            [str(python), "main.py"],
            cwd=SOURCE,
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_handle.close()


def wait_ready(process: subprocess.Popen, deadline_seconds: float = 30) -> None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"agent exited before readiness: {process.returncode}")
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8088/readiness",
                timeout=1,
            ) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError("agent did not become ready")


def stop_server(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run(args: argparse.Namespace) -> dict:
    process: subprocess.Popen | None = None
    with tempfile.TemporaryDirectory(prefix="lra-owned-agent-") as temporary:
        state_root = Path(temporary) / "state"
        log_path = Path(temporary) / "agent.log"
        state_root.mkdir(parents=True)
        try:
            process = start_server(args.python, state_root, log_path)
            wait_ready(process)
            created = create_work(
                endpoint="http://127.0.0.1:8088",
                work_id=args.work_id,
                payload=args.payload,
                crash_after_stage=args.crash_after_stage,
                stage_delay_ms=args.stage_delay_ms,
                token=None,
            )
            response_id = created["id"]
            try:
                process.wait(timeout=args.first_exit_timeout_seconds)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(
                    "first process did not exit after the injected checkpoint"
                ) from error
            first_exit_code = process.returncode
            if first_exit_code != 86:
                raise RuntimeError(
                    f"first process exited {first_exit_code}, expected injected 86"
                )

            process = start_server(args.python, state_root, log_path)
            wait_ready(process)
            terminal, poll_events = poll_work(
                endpoint="http://127.0.0.1:8088",
                response_id=response_id,
                token=None,
                deadline_seconds=args.deadline_seconds,
                poll_interval_seconds=0.5,
            )
            acceptance = validate_terminal_response(
                response=terminal,
                expected_work_id=args.work_id,
                expect_recovery=True,
            )
            report = {
                "schema_version": 1,
                "evidence_type": "owned-hosted-agent-local-recovery",
                "generated_at_utc": utc_now(),
                "work_id": args.work_id,
                "response_id_sha256": sha256_text(response_id),
                "first_process_exit_code": first_exit_code,
                "injected_after_stage": args.crash_after_stage,
                "poll_events": poll_events,
                "acceptance": public_acceptance(acceptance),
                "passed": True,
            }
            write_json_atomic(args.report, report)
            return report
        finally:
            stop_server(process)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--work-id", default="owned-agent-local-001")
    parser.add_argument(
        "--payload",
        default="public-safe owned Hosted Agent recovery workload",
    )
    parser.add_argument("--crash-after-stage", type=int, default=1)
    parser.add_argument("--stage-delay-ms", type=int, default=250)
    parser.add_argument("--first-exit-timeout-seconds", type=float, default=30)
    parser.add_argument("--deadline-seconds", type=float, default=180)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".demo-state/owned-hosted-agent-local.json"),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
    except (RuntimeError, TimeoutError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "PASS: owned Hosted Agent recovered the same response across "
        f"{report['acceptance']['process_instance_count']} processes"
    )
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
