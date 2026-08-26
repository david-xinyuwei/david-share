#!/usr/bin/env python3
"""Render the primary recovery report as a concise reader-facing terminal trace."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def find_event(
    timeline: list[dict[str, Any]],
    event_name: str,
    **expected: Any,
) -> dict[str, Any]:
    for event in timeline:
        if event.get("event") == event_name and all(
            event.get(key) == value for key, value in expected.items()
        ):
            return event
    raise ValueError(f"timeline event not found: {event_name} {expected}")


def format_line(label: str, event: dict[str, Any], details: str) -> str:
    return f"{event['at_utc']}  {label:<22} {details}".rstrip()


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(),
        3,
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def render(report: dict[str, Any]) -> str:
    timeline = report["timeline"]
    process_a_start = find_event(
        timeline,
        "process_started",
        process_role="A",
    )
    response_created = find_event(timeline, "response_created")
    checkpoint_before = find_event(
        timeline,
        "checkpoint_committed",
        checkpoint=report["durable_state"]["last_checkpoint_before_loss"],
    )
    fault = find_event(timeline, "fault_injected")
    process_a_exit = find_event(
        timeline,
        "process_exited",
        process_role="A",
    )
    process_b_start = find_event(
        timeline,
        "process_started",
        process_role="B",
    )
    recovered = find_event(
        timeline,
        "handler_entered",
        entry_mode="recovered",
    )
    checkpoint_after = find_event(
        timeline,
        "checkpoint_committed",
        checkpoint=report["durable_state"]["first_checkpoint_after_recovery"],
    )
    handler_completed = find_event(timeline, "handler_completed")
    terminal = find_event(timeline, "terminal_observed")

    lines = [
        f"RUN {report['work_id']}",
        format_line("PROCESS_A_START", process_a_start, ""),
        format_line(
            "RESPONSE_CREATED",
            response_created,
            f"response_sha256={report['response_id_sha256']}",
        ),
        format_line(
            "CHECKPOINT_COMMITTED",
            checkpoint_before,
            f"checkpoint={checkpoint_before['checkpoint']}",
        ),
        format_line(
            "FAULT_INJECTED",
            fault,
            f"mode=hard_process_exit exit_code={fault['exit_code']}",
        ),
        format_line(
            "PROCESS_A_DOWN",
            process_a_exit,
            f"exit_code={process_a_exit['exit_code']}",
        ),
        format_line("PROCESS_B_START", process_b_start, ""),
        format_line(
            "HANDLER_RECOVERED",
            recovered,
            f"mode={recovered['entry_mode']} "
            f"resume_from={recovered['resume_from_checkpoint']}",
        ),
        format_line(
            "CHECKPOINT_COMMITTED",
            checkpoint_after,
            f"checkpoint={checkpoint_after['checkpoint']}",
        ),
        format_line("HANDLER_COMPLETED", handler_completed, ""),
        format_line(
            "RESPONSE_STATUS",
            terminal,
            f"status={terminal['status']}",
        ),
        f"ASSERT same_response_reused={str(report['durable_state']['same_response_reused']).lower()}",
        f"ASSERT process_memory_survived={str(report['durable_state']['process_memory_survived']).lower()}",
        f"ASSERT checkpointed_response_survived={str(report['durable_state']['checkpointed_response_survived']).lower()}",
        "ASSERT all_expected_checkpoints_completed_once="
        f"{str(report['acceptance']['all_expected_checkpoints_completed_once']).lower()}",
        f"ASSERT process_instance_count={report['acceptance']['process_instance_count']}",
        f"RESULT {'PASS' if report['passed'] else 'FAIL'}",
    ]
    return "\n".join(lines) + "\n"


def render_hosted(
    report: dict[str, Any],
    events: list[dict[str, Any]],
) -> str:
    poll_events = report["poll_events"]
    timeout_index = next(
        index
        for index, event in enumerate(poll_events)
        if event.get("kind") == "connection_error"
    )
    poll_before = next(
        event
        for event in reversed(poll_events[:timeout_index])
        if event.get("kind") == "poll"
    )
    poll_after = next(
        event
        for event in poll_events[timeout_index + 1 :]
        if event.get("kind") == "poll"
    )
    terminal = next(
        event
        for event in reversed(poll_events)
        if event.get("kind") == "poll" and event.get("status") == "completed"
    )
    timeout = poll_events[timeout_index]
    recovered = find_event(
        events,
        "handler_entered",
        entry_mode="recovered",
    )
    first_checkpoint = find_event(
        events,
        "checkpoint_committed",
        checkpoint="translation_section_05",
    )
    completed = find_event(events, "handler_completed")
    response_hash = report["response_id_sha256"]
    if any(
        event.get("response_id_sha256") != response_hash
        for event in (recovered, first_checkpoint, completed)
    ):
        raise ValueError("hosted trace events do not share the report response hash")
    acceptance = report["acceptance"]
    if (
        report.get("passed") is not True
        or acceptance.get("status") != "completed"
        or acceptance.get("process_instance_count") != 2
        or acceptance.get("entry_modes") != ["fresh", "recovered"]
        or len(acceptance.get("translated_texts", [])) != 12
        or poll_after.get("last_durable_checkpoint") != "translation_section_04"
    ):
        raise ValueError("hosted recovery report does not satisfy the trace contract")

    observation_gap = seconds_between(poll_before["at"], poll_after["at"])
    recovery_to_completion = seconds_between(
        recovered["at_utc"],
        completed["at_utc"],
    )
    completion_to_terminal = seconds_between(
        completed["at_utc"],
        terminal["at"],
    )
    lines = [
        f"RUN {acceptance['work_id']} foundry_version={report['deployment']['version']}",
        f"{report['started_at_utc']}  REQUEST_STARTED        "
        f"workload={acceptance['workload']} response_sha256={response_hash}",
        f"{poll_before['at']}  LAST_SUCCESSFUL_POLL   "
        f"status={poll_before['status']}",
        f"{timeout['at']}  CONNECTION_TIMEOUT     "
        f"detail={timeout['detail']} phase=replacement_window",
        format_line(
            "HANDLER_RECOVERED",
            recovered,
            f"process=B resume_from={recovered['resume_from_checkpoint']}",
        ),
        f"{poll_after['at']}  POLL_AFTER_TIMEOUT     "
        f"status={poll_after['status']} "
        f"last_checkpoint={poll_after['last_durable_checkpoint']}",
        format_line(
            "CHECKPOINT_COMMITTED",
            first_checkpoint,
            f"checkpoint={first_checkpoint['checkpoint']}",
        ),
        format_line("HANDLER_COMPLETED", completed, "process=B"),
        f"{terminal['at']}  RESPONSE_STATUS        "
        f"status={terminal['status']} process_instances=2",
        "BOUNDARY exact_process_a_down_at=NOT_AVAILABLE "
        "reason=prior_container_log_not_retained",
        f"DURATION successful_poll_gap_seconds={observation_gap} "
        "meaning=timeout_plus_polling_plus_replacement_not_exact_hang",
        f"DURATION recovered_to_handler_completed_seconds={recovery_to_completion}",
        f"DURATION handler_completed_to_client_completed_seconds={completion_to_terminal}",
        f"DURATION total_run_seconds={report['elapsed_seconds']}",
        "ASSERT same_response_reused=true",
        "ASSERT checkpoint_continuity=translation_section_04->translation_section_05",
        "ASSERT all_12_translations_present=true",
        "ASSERT entry_modes=fresh+recovered",
        "ASSERT terminal_status=completed",
        "RESULT PASS",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evidence" / "owned-hosted-agent-local.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "owned-hosted-agent-local-trace.txt",
    )
    parser.add_argument(
        "--events",
        type=Path,
        help="sanitized JSONL events required for a hosted recovery report",
    )
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    if "timeline" in report:
        output = render(report)
    else:
        if args.events is None:
            parser.error("--events is required for a hosted recovery report")
        output = render_hosted(report, read_jsonl(args.events))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"wrote recovery trace to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
