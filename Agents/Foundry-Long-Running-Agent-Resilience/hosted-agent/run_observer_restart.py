#!/usr/bin/env python3
"""Stop one observer, resume with another, and prove background work continued."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from client import sha256_text, utc_now, write_json_atomic
from run_local_recovery import (
    SOURCE,
    lifecycle_event,
    sanitize_agent_log,
    seconds_between,
    start_server,
    stop_server,
    wait_ready,
    write_jsonl,
)


CLIENT = Path(__file__).resolve().parent / "client.py"


def run_observer(
    python: Path,
    arguments: list[str],
    timeout_seconds: float,
) -> tuple[subprocess.Popen[str], str, str]:
    process = subprocess.Popen(
        [str(python), str(CLIENT), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise TimeoutError("observer process did not exit before its deadline")
    if process.returncode != 0:
        raise RuntimeError(
            f"observer exited {process.returncode}: {stderr.strip() or stdout.strip()}"
        )
    return process, stdout, stderr


def run(args: argparse.Namespace) -> dict[str, Any]:
    server: subprocess.Popen[bytes] | None = None
    started_at_utc = utc_now()
    started_monotonic = time.monotonic()
    lifecycle: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="lra-observer-restart-") as temporary:
        temporary_path = Path(temporary)
        state_root = temporary_path / "state"
        state_file = temporary_path / "observer-state.json"
        dispatch_report = temporary_path / "dispatch.json"
        resume_report = temporary_path / "resume.json"
        agent_log = temporary_path / "agent.log"
        state_root.mkdir(parents=True)
        try:
            server = start_server(
                [str(args.python), "main.py"],
                SOURCE,
                state_root,
                agent_log,
                enable_fault_injection=False,
            )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "agent_process_started",
            )
            wait_ready(server)
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "agent_server_ready",
            )

            lifecycle_event(
                lifecycle,
                started_monotonic,
                "observer_started",
                observer_role="A",
            )
            observer_a, _, _ = run_observer(
                args.python,
                [
                    "--endpoint",
                    "http://127.0.0.1:8088",
                    "--work-id",
                    args.work_id,
                    "--payload",
                    args.payload,
                    "--stage-delay-ms",
                    str(args.stage_delay_ms),
                    "--deadline-seconds",
                    str(args.deadline_seconds),
                    "--state-file",
                    str(state_file),
                    "--report",
                    str(dispatch_report),
                    "--create-only",
                ],
                timeout_seconds=30,
            )
            dispatch = json.loads(dispatch_report.read_text(encoding="utf-8"))
            response_id_sha256 = dispatch["response_id_sha256"]
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "observer_exited",
                observer_role="A",
                observer_process_sha256=sha256_text(str(observer_a.pid)),
                response_id_sha256=response_id_sha256,
                state_persisted=True,
            )

            detached_at_utc = lifecycle[-1]["at_utc"]
            time.sleep(args.detached_seconds)

            lifecycle_event(
                lifecycle,
                started_monotonic,
                "observer_started",
                observer_role="B",
                response_id_sha256=response_id_sha256,
            )
            observer_b_started_at_utc = lifecycle[-1]["at_utc"]
            observer_b, _, _ = run_observer(
                args.python,
                [
                    "--endpoint",
                    "http://127.0.0.1:8088",
                    "--resume",
                    "--state-file",
                    str(state_file),
                    "--report",
                    str(resume_report),
                ],
                timeout_seconds=args.deadline_seconds + 30,
            )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "observer_exited",
                observer_role="B",
                observer_process_sha256=sha256_text(str(observer_b.pid)),
                exit_code=observer_b.returncode,
            )
            resume = json.loads(resume_report.read_text(encoding="utf-8"))
            acceptance = resume.get("acceptance", {})
            if (
                resume.get("passed") is not True
                or resume.get("response_id_sha256") != response_id_sha256
                or acceptance.get("status") != "completed"
                or acceptance.get("recovery_proven") is not False
                or acceptance.get("process_instance_count") != 1
            ):
                raise RuntimeError(
                    "observer restart did not complete the same background response"
                )

            stop_server(server)
            server = None
            events = sanitize_agent_log(agent_log)
            for event in events:
                at_utc = event.get("at_utc")
                if isinstance(at_utc, str):
                    event["elapsed_seconds"] = seconds_between(
                        started_at_utc,
                        at_utc,
                    )
            write_jsonl(args.log_report, events)
            progressed_while_detached = [
                event
                for event in events
                if event.get("event") == "checkpoint_committed"
                and detached_at_utc < str(event.get("at_utc")) < observer_b_started_at_utc
            ]
            if not progressed_while_detached:
                raise RuntimeError(
                    "no durable progress was recorded while observer A was absent"
                )
            completed_event = next(
                event
                for event in events
                if event.get("event") == "handler_completed"
            )
            timeline = sorted(
                [
                    *lifecycle,
                    progressed_while_detached[0],
                    completed_event,
                ],
                key=lambda event: str(event.get("at_utc")),
            )
            report = {
                "schema_version": 1,
                "evidence_type": "owned-hosted-agent-observer-restart",
                "generated_at_utc": utc_now(),
                "run_started_at_utc": started_at_utc,
                "work_id": args.work_id,
                "response_id_sha256": response_id_sha256,
                "observer_process_count": 2,
                "agent_process_count": 1,
                "background_work_continued": True,
                "observer_state": {
                    "response_id_persisted": True,
                    "absolute_deadline_persisted": True,
                    "same_response_reused": True,
                },
                "milestones": {
                    "observer_a_exited_at_utc": detached_at_utc,
                    "progress_without_observer_at_utc":
                        progressed_while_detached[0]["at_utc"],
                    "observer_b_started_at_utc": observer_b_started_at_utc,
                    "completed_at_utc": completed_event["at_utc"],
                },
                "timeline": timeline,
                "agent_log": args.log_report.as_posix(),
                "acceptance": acceptance,
                "passed": True,
            }
            write_json_atomic(args.report, report)
            return report
        finally:
            stop_server(server)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--work-id", default="owned-agent-observer-restart-001")
    parser.add_argument(
        "--payload",
        default="public-safe observer restart workload",
    )
    parser.add_argument("--stage-delay-ms", type=int, default=500)
    parser.add_argument("--detached-seconds", type=float, default=2)
    parser.add_argument("--deadline-seconds", type=float, default=180)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".demo-state/owned-hosted-agent-observer.json"),
    )
    parser.add_argument(
        "--log-report",
        type=Path,
        default=Path(".demo-state/owned-hosted-agent-observer-events.jsonl"),
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
        "PASS: observer B resumed the same response after observer A exited; "
        "the Agent process stayed alive"
    )
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
