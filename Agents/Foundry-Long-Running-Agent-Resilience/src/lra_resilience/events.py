"""Reduce JSONL or SSE-derived records to a public-safe event summary."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .evidence import canonical_sha256


PUBLIC_EVENT_FIELDS = {
    "output_index",
    "phase",
    "sequence_number",
    "status",
    "total",
    "type",
}


def _event_from_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = record.get("event")
    return nested if isinstance(nested, Mapping) else record


def _public_event(record: Mapping[str, Any]) -> dict[str, Any]:
    event = _event_from_record(record)
    return {key: event[key] for key in sorted(PUBLIC_EVENT_FIELDS) if key in event}


def summarize_event_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize only protocol-level fields; unknown and identity fields are discarded."""

    public_events = [_public_event(record) for record in records]
    public_events = [event for event in public_events if event]
    if not public_events:
        raise ValueError("no public protocol events found in input records")
    event_types = Counter(str(event.get("type", "unknown")) for event in public_events)
    phases = sorted({event["phase"] for event in public_events if isinstance(event.get("phase"), int)})
    output_indexes = sorted(
        {event["output_index"] for event in public_events if isinstance(event.get("output_index"), int)}
    )
    sequences = [
        event["sequence_number"]
        for event in public_events
        if isinstance(event.get("sequence_number"), int)
    ]
    terminal_statuses = [
        str(event.get("status"))
        for event in public_events
        if event.get("type") in {"done", "response.completed", "response.failed", "response.cancelled"}
    ]
    return {
        "schema_version": 1,
        "source_kind": "event-stream-summary",
        "event_count": len(public_events),
        "event_types": dict(sorted(event_types.items())),
        "phases": phases,
        "output_indexes": output_indexes,
        "sequence": {
            "first": sequences[0] if sequences else None,
            "last": sequences[-1] if sequences else None,
            "monotonic": sequences == sorted(sequences),
        },
        "recovery_observed": any(event.get("type") == "recovered" for event in public_events),
        "in_progress_reset_observed": any(
            event.get("type") == "response.in_progress" for event in public_events
        ),
        "completion_observed": any(
            event.get("type") in {"done", "response.completed"}
            and event.get("status", "completed") == "completed"
            for event in public_events
        ),
        "terminal_statuses": terminal_statuses,
        "public_event_digest": canonical_sha256(public_events),
    }


def load_jsonl(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
            if not isinstance(record, Mapping):
                raise ValueError(f"{path}:{line_number}: each JSONL record must be an object")
            records.append(record)
    return records


def summarize_event_file(path: Path) -> dict[str, Any]:
    return summarize_event_records(load_jsonl(path))
