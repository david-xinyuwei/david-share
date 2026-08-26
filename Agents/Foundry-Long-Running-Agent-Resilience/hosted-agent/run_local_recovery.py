#!/usr/bin/env python3
"""Hard-crash the owned agent, restart it, and validate the same response."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from client import (
    create_work,
    poll_work,
    public_acceptance,
    public_poll_events,
    sha256_text,
    utc_now,
    write_json_atomic,
)

SOURCE = Path(__file__).resolve().parent / "src" / "lra-evidence-agent"

sys.path.insert(0, str(SOURCE))
from contract import (  # noqa: E402
    STAGES,
    stage_names_for,
    validate_terminal_response,
)


_LOG_FIELDS = re.compile(r"(\w+)=([^\s]+)")
_LOG_EVENTS = {
    "LRA_ENTRY": "handler_entered",
    "LRA_STAGE_COMMITTED": "checkpoint_committed",
    "LRA_INJECTED_PROCESS_LOSS": "fault_injected",
    "LRA_SHUTDOWN_DEFER": "shutdown_deferred",
    "LRA_COMPLETED": "handler_completed",
}


def lifecycle_event(
    events: list[dict[str, Any]],
    started_monotonic: float,
    event: str,
    **details: Any,
) -> None:
    events.append(
        {
            "at_utc": utc_now(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
            "event": event,
            "source": "runner",
            **details,
        }
    )


def checkpoint_name(
    value: str | None,
    checkpoint_names: Sequence[str] = STAGES,
) -> str | None:
    if value is None:
        return None
    index = int(value)
    return (
        checkpoint_names[index]
        if index in range(len(checkpoint_names))
        else None
    )


def sanitize_agent_log(
    log_path: Path,
    workload: str = "checkpoint_contract",
) -> list[dict[str, Any]]:
    checkpoint_names = stage_names_for(workload)
    events: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        candidate_line = line
        if line.startswith("data: "):
            try:
                envelope = json.loads(line.removeprefix("data: "))
            except json.JSONDecodeError:
                continue
            message = envelope.get("message") if isinstance(envelope, dict) else None
            if not isinstance(message, str):
                continue
            candidate_line = message
        marker_position = candidate_line.find("LRA_")
        if marker_position < 0:
            continue
        marker, _, payload = candidate_line[marker_position:].partition(" ")
        event_name = _LOG_EVENTS.get(marker)
        if event_name is None:
            continue
        fields = dict(_LOG_FIELDS.findall(payload))
        event: dict[str, Any] = {
            "at_utc": fields.get("at_utc"),
            "event": event_name,
            "source": "agent_log",
        }
        if "response_id" in fields:
            event["response_id_sha256"] = sha256_text(fields["response_id"])
        if "work_id" in fields:
            event["work_id"] = fields["work_id"]
        if "instance" in fields:
            event["process_instance_sha256"] = sha256_text(fields["instance"])
        if "mode" in fields:
            event["entry_mode"] = fields["mode"]
        if "start" in fields:
            start = int(fields["start"])
            event["resume_from_checkpoint"] = (
                checkpoint_names[start]
                if start in range(len(checkpoint_names))
                else "terminal"
            )
        checkpoint = fields.get("checkpoint") or checkpoint_name(
            fields.get("stage"),
            checkpoint_names,
        )
        if checkpoint is not None:
            event["checkpoint"] = checkpoint
        after_checkpoint = fields.get("after_checkpoint") or checkpoint_name(
            fields.get("after_stage"),
            checkpoint_names,
        )
        if after_checkpoint is not None:
            event["after_checkpoint"] = after_checkpoint
        if "exit_code" in fields:
            event["exit_code"] = int(fields["exit_code"])
        events.append(event)
    return events


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(),
        3,
    )


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
            for event in events
        ),
        encoding="utf-8",
    )


def start_server(
    command: Sequence[str],
    cwd: Path,
    state_root: Path,
    log_path: Path,
    *,
    enable_fault_injection: bool,
) -> subprocess.Popen:
    environment = os.environ.copy()
    environment.update(
        {
            "AGENTSERVER_STATE_ROOT": str(state_root),
            "LRA_ENABLE_FAULT_INJECTION": (
                "true" if enable_fault_injection else "false"
            ),
            "LRA_STAGE_DELAY_MS": "250",
            "OTEL_SDK_DISABLED": "true",
            "PYTHONUNBUFFERED": "1",
        }
    )
    log_handle = log_path.open("ab")
    try:
        return subprocess.Popen(
            list(command),
            cwd=cwd,
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            ),
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
    started_at_utc = utc_now()
    started_monotonic = time.monotonic()
    lifecycle: list[dict[str, Any]] = []
    interruption_checkpoint = stage_names_for(args.workload)[
        args.crash_after_stage
    ]
    server_command = args.server_command or [str(args.python), "main.py"]
    server_cwd = args.server_cwd or SOURCE
    with tempfile.TemporaryDirectory(prefix="lra-owned-agent-") as temporary:
        state_root = Path(temporary) / "state"
        log_path = Path(temporary) / "agent.log"
        state_root.mkdir(parents=True)
        try:
            process = start_server(
                server_command,
                server_cwd,
                state_root,
                log_path,
                enable_fault_injection=True,
            )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "process_started",
                process_role="A",
            )
            wait_ready(process)
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "server_ready",
                process_role="A",
            )
            created = create_work(
                endpoint="http://127.0.0.1:8088",
                work_id=args.work_id,
                payload=args.payload,
                crash_after_stage=args.crash_after_stage,
                stage_delay_ms=args.stage_delay_ms,
                token=None,
                workload=args.workload,
            )
            response_id = created["id"]
            response_id_sha256 = sha256_text(response_id)
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "response_created",
                process_role="A",
                response_id_sha256=response_id_sha256,
            )
            try:
                process.wait(timeout=args.first_exit_timeout_seconds)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(
                    "first process did not exit after the requested interruption"
                ) from error
            first_exit_code = process.returncode
            if first_exit_code != 86:
                raise RuntimeError(
                    f"first process exited {first_exit_code}, expected injected 86"
                )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "process_exited",
                process_role="A",
                exit_code=first_exit_code,
            )

            process = start_server(
                server_command,
                server_cwd,
                state_root,
                log_path,
                enable_fault_injection=True,
            )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "process_started",
                process_role="B",
            )
            wait_ready(process)
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "server_ready",
                process_role="B",
            )
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
                expected_workload=args.workload,
            )
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "terminal_observed",
                process_role="B",
                status=terminal.get("status"),
                response_id_sha256=response_id_sha256,
            )
            stop_server(process)
            process = None
            lifecycle_event(
                lifecycle,
                started_monotonic,
                "process_stopped",
                process_role="B",
            )

            agent_events = sanitize_agent_log(log_path, args.workload)
            for event in agent_events:
                at_utc = event.get("at_utc")
                if isinstance(at_utc, str):
                    event["elapsed_seconds"] = seconds_between(
                        started_at_utc,
                        at_utc,
                    )
            write_jsonl(args.log_report, agent_events)

            transition_event = next(
                (
                    event
                    for event in agent_events
                    if event.get("event") == "fault_injected"
                ),
                None,
            )
            recovered_event = next(
                (
                    event
                    for event in agent_events
                    if event.get("event") == "handler_entered"
                    and event.get("entry_mode") == "recovered"
                ),
                None,
            )
            completed_event = next(
                (
                    event
                    for event in agent_events
                    if event.get("event") == "handler_completed"
                ),
                None,
            )
            if not transition_event or not recovered_event or not completed_event:
                raise RuntimeError(
                    "agent log did not prove interruption, recovery, and completion"
                )
            first_recovered_checkpoint = next(
                (
                    event.get("checkpoint")
                    for event in agent_events
                    if event.get("event") == "checkpoint_committed"
                    and event.get("process_instance_sha256")
                    == recovered_event.get("process_instance_sha256")
                ),
                None,
            )
            if not isinstance(first_recovered_checkpoint, str):
                raise RuntimeError(
                    "agent log did not record the first recovered checkpoint"
                )

            process_a_exit_event = next(
                event
                for event in lifecycle
                if event.get("event") == "process_exited"
                and event.get("process_role") == "A"
            )
            last_checkpoint_before_loss = interruption_checkpoint
            milestone_agent_events = [
                event
                for event in agent_events
                if event.get("event")
                in {
                    "handler_entered",
                    "fault_injected",
                    "handler_completed",
                }
                or event.get("checkpoint")
                in {last_checkpoint_before_loss, first_recovered_checkpoint}
            ]
            timeline = sorted(
                [*lifecycle, *milestone_agent_events],
                key=lambda event: str(event.get("at_utc")),
            )
            report = {
                "schema_version": 1,
                "evidence_type": "owned-hosted-agent-local-recovery",
                "runtime": args.runtime_label,
                "workload": args.workload,
                "run_started_at_utc": started_at_utc,
                "generated_at_utc": utc_now(),
                "work_id": args.work_id,
                "response_id_sha256": response_id_sha256,
                "first_process_exit_code": first_exit_code,
                "fault_injection_requested": True,
                "interruption": {
                    "mode": "hard_process_exit",
                    "after_checkpoint": last_checkpoint_before_loss,
                    "exit_code": first_exit_code,
                    "signal": None,
                },
                "milestones": {
                    "interruption_at_utc": transition_event["at_utc"],
                    "process_down_at_utc": process_a_exit_event["at_utc"],
                    "recovered_entry_at_utc": recovered_event["at_utc"],
                    "completed_at_utc": completed_event["at_utc"],
                    "down_to_recovered_seconds": seconds_between(
                        process_a_exit_event["at_utc"],
                        recovered_event["at_utc"],
                    ),
                    "down_to_completed_seconds": seconds_between(
                        process_a_exit_event["at_utc"],
                        completed_event["at_utc"],
                    ),
                },
                "durable_state": {
                    "provider": "AgentServer local file-backed state",
                    "same_response_reused": True,
                    "persisted_input_reused": True,
                    "last_checkpoint_before_loss": last_checkpoint_before_loss,
                    "first_checkpoint_after_recovery":
                        first_recovered_checkpoint,
                    "process_memory_survived": False,
                    "checkpointed_response_survived": True,
                },
                "timeline": timeline,
                "agent_log": args.log_report.as_posix(),
                "poll_events": public_poll_events(poll_events),
                "acceptance": public_acceptance(acceptance),
                "passed": True,
            }
            write_json_atomic(args.report, report)
            return report
        finally:
            stop_server(process)
            if log_path.is_file():
                if args.debug_log is not None:
                    args.debug_log.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(log_path, args.debug_log)
                write_jsonl(
                    args.log_report,
                    sanitize_agent_log(log_path, args.workload),
                )
            cleanup_deadline = time.monotonic() + 5
            while log_path.exists():
                try:
                    log_path.unlink()
                    break
                except PermissionError as error:
                    if time.monotonic() >= cleanup_deadline:
                        raise RuntimeError(
                            f"agent log remained locked after shutdown: {log_path}"
                        ) from error
                    time.sleep(0.1)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--runtime-label", default="Python 3.13")
    parser.add_argument(
        "--workload",
        choices=("checkpoint_contract", "translator_batch"),
        default="checkpoint_contract",
    )
    parser.add_argument("--server-command", nargs="+")
    parser.add_argument("--server-cwd", type=Path)
    parser.add_argument("--work-id", default="owned-agent-local-001")
    parser.add_argument(
        "--payload",
        default="public-safe owned Hosted Agent recovery workload",
    )
    parser.add_argument("--crash-after-stage", type=int, default=3)
    parser.add_argument("--stage-delay-ms", type=int, default=250)
    parser.add_argument("--first-exit-timeout-seconds", type=float, default=30)
    parser.add_argument("--deadline-seconds", type=float, default=180)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".demo-state/owned-hosted-agent-local.json"),
    )
    parser.add_argument(
        "--log-report",
        type=Path,
        default=Path(".demo-state/owned-hosted-agent-local-events.jsonl"),
    )
    parser.add_argument("--debug-log", type=Path)
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
