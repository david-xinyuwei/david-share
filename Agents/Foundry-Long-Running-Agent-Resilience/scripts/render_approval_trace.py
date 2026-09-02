#!/usr/bin/env python3
"""Render an approval-gate recovery report as a concise reader-facing trace.

Input: the JSON report written by ``hosted-agent-approval/run_approval_recovery.py``
(local or Foundry-hosted). Every line is derived from the committed report; the
repository gate regenerates this file and compares it with the committed copy.
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


def find_optional(timeline: list[dict[str, Any]], event_name: str, **expected: Any) -> dict[str, Any] | None:
    try:
        return find_event(timeline, event_name, **expected)
    except ValueError:
        return None


def line(label: str, event: dict[str, Any], details: str) -> str:
    return f"{event['at_utc']}  {label:<{LABEL_WIDTH}} {details}".rstrip()


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3
    )


def render(report: dict[str, Any]) -> str:
    timeline = report["timeline"]
    acceptance = report["acceptance"]
    request = report["request"]
    sample_size = int(request["sample_size"])
    local = report["endpoint_class"] == "local-agentserver"

    started = find_event(timeline, "request_started", action="start")
    first_sample = find_event(timeline, "checkpoint_committed", checkpoint="translation_section_01")
    last_sample = find_event(timeline, "checkpoint_committed", checkpoint=f"translation_section_{sample_size:02d}")
    gate = find_event(timeline, "review_gate_reached")
    fault = find_event(timeline, "fault_injected")
    exited = find_optional(timeline, "process_exited", process_role="A")
    restarted = find_optional(timeline, "process_started", process_role="B")
    replacement = find_event(timeline, "replacement_instance_observed")
    approval = find_event(timeline, "approval_submitted")
    first_remaining = find_event(timeline, "checkpoint_committed", checkpoint=f"translation_section_{sample_size + 1:02d}")
    last_remaining = find_event(timeline, "checkpoint_committed", checkpoint="translation_section_30")
    terminal = find_event(timeline, "terminal_observed")

    header = "local_agentserver" if local else f"foundry_version={report['deployment']['version']}"
    lines = [
        f"RUN {report['work_id']} {header}",
        line("REQUEST_STARTED", started, f"action=start target={request['target']} sample_size={sample_size}"),
        line("CHECKPOINT_COMMITTED", first_sample, f"checkpoint={first_sample['checkpoint']} batch=sample process=P1"),
        line("CHECKPOINT_COMMITTED", last_sample, f"checkpoint={last_sample['checkpoint']} batch=sample process=P1"),
        line("REVIEW_GATE_REACHED", gate, f"sample_sections={gate['sample_sections']} task_sha256={gate['task_id_sha256']} waiting_for=human_reviewer"),
        line("FAULT_INJECTED", fault, f"mode=hard_process_exit exit_code={fault['exit_code']} while=awaiting_review"),
    ]
    if exited is not None:
        lines.append(line("PROCESS_P1_DOWN", exited, f"exit_code={exited['exit_code']}"))
    if restarted is not None:
        lines.append(line("PROCESS_P2_START", restarted, ""))
    lines += [
        line("REPLACEMENT_OBSERVED", replacement, "process=P2 sample_still=awaiting_review"),
        line("APPROVAL_SUBMITTED", approval, f"decision={approval['decision']} landed_on=P2"),
        line("CHECKPOINT_COMMITTED", first_remaining, f"checkpoint={first_remaining['checkpoint']} batch=remaining process=P2"),
        line("CHECKPOINT_COMMITTED", last_remaining, f"checkpoint={last_remaining['checkpoint']} batch=remaining process=P2"),
        line("TASK_STATUS", terminal, f"status={terminal['status']} outcome={terminal['outcome']} sections={terminal['sections']}"),
    ]
    if exited is not None:
        lines.append(f"DURATION fault_to_process_p1_down_seconds={seconds_between(fault['at_utc'], exited['at_utc'])}")
        lines.append(f"DURATION process_p1_down_to_replacement_observed_seconds={seconds_between(exited['at_utc'], replacement['at_utc'])}")
    else:
        lines.append("BOUNDARY exact_instance_down_at=NOT_AVAILABLE reason=platform_replaced_the_instance observed=probe_answered_by_new_process")
        lines.append(f"DURATION fault_request_to_replacement_observed_seconds={seconds_between(fault['at_utc'], replacement['at_utc'])} meaning=observation_window_not_exact_downtime")
    lines += [
        f"DURATION approval_to_completed_seconds={seconds_between(approval['at_utc'], terminal['at_utc'])}",
        f"DURATION total_run_seconds={report['elapsed_seconds']}",
        f"ASSERT same_task_identity={str(acceptance['task_identity_unchanged']).lower()}",
        f"ASSERT process_replaced={str(acceptance['process_replaced']).lower()}",
        f"ASSERT sample_result_hashes_unchanged={str(acceptance['sample_result_hashes_unchanged']).lower()}",
        f"ASSERT sample_on_process_p1={str(acceptance['sample_translated_on_process_a']).lower()} remaining_on_process_p2={str(acceptance['remaining_translated_on_process_b']).lower()}",
        f"ASSERT all_sections_present_once={str(acceptance['all_sections_present_once']).lower()} sections={acceptance['total_sections']}",
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
