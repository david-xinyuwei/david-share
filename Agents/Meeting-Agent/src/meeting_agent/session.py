"""Ordering, deduplication, and persistence for meeting events."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

from .models import MeetingEvent, MeetingEventKind


class MeetingSession:
    """In-memory event stream with deterministic ordering and deduplication."""

    def __init__(self, session_id: str) -> None:
        if not session_id.strip():
            raise ValueError("session_id is required")
        self.session_id = session_id
        self._events: dict[str, MeetingEvent] = {}

    def ingest(self, event: MeetingEvent) -> bool:
        """Ingest one event; return False for an idempotent duplicate."""
        if event.session_id != self.session_id:
            raise ValueError("event session_id does not match the session")
        existing = self._events.get(event.event_id)
        if existing:
            if existing != event:
                raise ValueError(f"event_id {event.event_id!r} was reused with new content")
            return False
        self._events[event.event_id] = event
        return True

    @property
    def events(self) -> list[MeetingEvent]:
        """Return events in provider sequence order, then timestamp and event ID."""
        return sorted(
            self._events.values(),
            key=lambda event: (event.sequence, event.timestamp, event.event_id),
        )

    @property
    def finalized_text(self) -> list[str]:
        """Return only final ASR segments; partial hypotheses never enter artifacts."""
        return [
            event.text.strip()
            for event in self.events
            if event.kind is MeetingEventKind.TRANSCRIPT_FINAL and event.text
        ]

    @property
    def visual_context(self) -> list[str]:
        """Return textual visual summaries supplied by the visual adapter."""
        return [
            event.text.strip()
            for event in self.events
            if event.kind is MeetingEventKind.VISUAL_FRAME and event.text
        ]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "events": [event.model_dump(mode="json") for event in self.events],
        }

    def content_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(self.canonical_payload(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def load_jsonl(path: Path) -> MeetingSession:
    """Load and validate one provider event stream from JSON Lines."""
    events: list[MeetingEvent] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            events.append(MeetingEvent.model_validate_json(raw_line))
        except Exception as error:
            raise ValueError(f"invalid event at {path}:{line_number}: {error}") from error
    if not events:
        raise ValueError(f"event file is empty: {path}")
    session = MeetingSession(events[0].session_id)
    ingest_all(session, events)
    return session


def ingest_all(session: MeetingSession, events: Iterable[MeetingEvent]) -> None:
    for event in events:
        session.ingest(event)