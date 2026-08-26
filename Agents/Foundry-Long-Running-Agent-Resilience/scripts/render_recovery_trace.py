#!/usr/bin/env python3
"""Render the primary recovery report as a concise reader-facing terminal trace."""

from __future__ import annotations

import argparse
import json
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
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(report), encoding="utf-8")
    print(f"wrote recovery trace to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
