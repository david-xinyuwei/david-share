#!/usr/bin/env python3
"""Render the steering recovery report as a concise reader-facing trace.

Input: the JSON report written by ``hosted-agent-steering/run_steering_recovery.py``.
Every line is derived from the committed report; the repository gate regenerates
this file and compares it with the committed copy.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

LABEL_WIDTH = 22


def find_event(timeline: list[dict[str, Any]], event_name: str, **expected: Any) -> dict[str, Any]:
    for event in timeline:
        if event.get("event") == event_name and all(
            event.get(key) == value for key, value in expected.items()
        ):
            return event
    raise ValueError(f"timeline event not found: {event_name} {expected}")


def find_last(timeline: list[dict[str, Any]], event_name: str, **expected: Any) -> dict[str, Any]:
    matches = [
        event
        for event in timeline
        if event.get("event") == event_name
        and all(event.get(key) == value for key, value in expected.items())
    ]
    if not matches:
        raise ValueError(f"timeline event not found: {event_name} {expected}")
    return matches[-1]


def line(label: str, event: dict[str, Any], details: str) -> str:
    return f"{event['at_utc']}  {label:<{LABEL_WIDTH}} {details}".rstrip()


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3
    )


def render(report: dict[str, Any]) -> str:
    timeline = report["timeline"]
    a = report["responses"]["A"]
    b = report["responses"]["B"]
    acceptance = report["acceptance"]
    request = report["request"]

    started = find_event(timeline, "request_started", response_role="A")
    created_a = find_event(timeline, "response_created", response_role="A")
    fresh_entry = find_event(timeline, "handler_entered", response_role="A", entry_mode="fresh")
    last_before = find_event(
        timeline, "checkpoint_committed", response_role="A", checkpoint=a["last_checkpoint_before_loss"]
    )
    closed = find_event(timeline, "stream_ended_without_terminal", response_role="A")
    recovered_entry = find_event(timeline, "handler_entered", response_role="A", entry_mode="recovered")
    first_after = find_event(
        timeline, "checkpoint_committed", response_role="A", checkpoint=a["first_checkpoint_after_recovery"]
    )
    steer = find_event(timeline, "steer_posted", response_role="B")
    created_b = find_event(timeline, "response_created", response_role="B")
    steered_entry = find_event(timeline, "handler_entered", response_role="B", entry_mode="steered")
    first_b = find_event(timeline, "checkpoint_committed", response_role="B", checkpoint="translation_section_01")
    last_b = find_last(timeline, "checkpoint_committed", response_role="B")
    terminal_b = find_event(timeline, "terminal_observed", response_role="B")
    terminal_a = find_last(timeline, "terminal_observed", response_role="A")

    lines = [
        f"RUN {report['work_id']} foundry_version={report['deployment']['version']}",
        line("REQUEST_STARTED", started, f"response=A target={request['original_target']} crash_after_stage={request['crash_after_stage']}"),
        line("RESPONSE_CREATED", created_a, f"response=A response_sha256={a['response_id_sha256']}"),
        line("HANDLER_ENTERED", fresh_entry, "response=A mode=fresh process=P1"),
        line("CHECKPOINT_COMMITTED", last_before, f"response=A checkpoint={last_before['checkpoint']} process=P1"),
        line("STREAM_CLOSED", closed, f"response=A committed_sections={closed['committed_sections']} detail=no_terminal_event_process_gone"),
    ]
    rejected = [event for event in timeline if event.get("event") == "reconnect_rejected"]
    if rejected:
        lines.append(line("RECONNECT_REJECTED", rejected[0], f"response=A http_status={rejected[0]['http_status']} meaning=recovery_scan_not_yet_re_entered"))
    lines += [
        line("HANDLER_RECOVERED", recovered_entry, f"response=A mode=recovered process=P2 resume_from={recovered_entry['resume_from_checkpoint']}"),
        line("CHECKPOINT_COMMITTED", first_after, f"response=A checkpoint={first_after['checkpoint']} process=P2"),
        line("STEER_POSTED", steer, f"response=B from={steer['from_target']} to={steer['to_target']} same_conversation=true original_sections_so_far={steer['original_sections_so_far']}"),
        line("RESPONSE_CREATED", created_b, f"response=B response_sha256={b['response_id_sha256']}"),
        line("HANDLER_ENTERED", steered_entry, "response=B mode=steered process=P2"),
        line("CHECKPOINT_COMMITTED", first_b, f"response=B checkpoint={first_b['checkpoint']} process=P2 meaning=new_language_starts_at_section_1"),
        line("CHECKPOINT_COMMITTED", last_b, f"response=B checkpoint={last_b['checkpoint']} process=P2"),
        line("RESPONSE_STATUS", terminal_b, f"response=B status={terminal_b['status']} sections={b['sections']}"),
        line("RESPONSE_STATUS", terminal_a, f"response=A status={terminal_a['status']} sections={a['fresh_sections'] + a['recovered_sections']}"),
        "BOUNDARY exact_process_p1_down_at=NOT_AVAILABLE reason=hosted_container_exit_not_observable_by_client observed=stream_close",
        f"DURATION stream_close_to_recovered_entry_seconds={seconds_between(closed['at_utc'], recovered_entry['at_utc'])} meaning=observation_window_includes_replacement_scheduling_and_reconnect_polling",
        f"DURATION steer_posted_to_replacement_completed_seconds={seconds_between(steer['at_utc'], terminal_b['at_utc'])}",
        f"DURATION total_run_seconds={report['elapsed_seconds']}",
        f"ASSERT process_replaced={str(acceptance['recovered_on_a_different_process']).lower()}",
        f"ASSERT checkpoint_continuity={a['last_checkpoint_before_loss']}->{a['first_checkpoint_after_recovery']}",
        f"ASSERT steered_on_replacement_process={str(acceptance['steered_entry_on_replacement_process']).lower()}",
        f"ASSERT replacement_starts_at_section_1={str(acceptance['replacement_starts_at_section_1']).lower()}",
        f"ASSERT original_sections_kept={a['fresh_sections'] + a['recovered_sections']} replacement_sections={b['sections']}",
        f"ASSERT terminal_status=A:{a['status']} B:{b['status']}",
        f"RESULT {'PASS' if report['passed'] else 'FAIL'}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
