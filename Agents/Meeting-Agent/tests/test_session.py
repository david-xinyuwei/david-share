from datetime import UTC, datetime

import pytest

from meeting_agent.models import MeetingEvent, MeetingEventKind
from meeting_agent.session import MeetingSession


def event(event_id: str, sequence: int, text: str) -> MeetingEvent:
    return MeetingEvent(
        event_id=event_id,
        session_id="session-1",
        sequence=sequence,
        timestamp=datetime(2026, 1, 1, 0, 0, sequence, tzinfo=UTC),
        kind=MeetingEventKind.TRANSCRIPT_FINAL,
        text=text,
    )


def test_orders_out_of_order_events_and_ignores_identical_duplicate() -> None:
    session = MeetingSession("session-1")
    second = event("event-2", 2, "Second")
    first = event("event-1", 1, "First")
    assert session.ingest(second) is True
    assert session.ingest(first) is True
    assert session.ingest(first) is False
    assert [item.event_id for item in session.events] == ["event-1", "event-2"]
    assert session.finalized_text == ["First", "Second"]


def test_rejects_event_id_reuse_with_new_content() -> None:
    session = MeetingSession("session-1")
    session.ingest(event("event-1", 1, "Original"))
    with pytest.raises(ValueError, match="reused with new content"):
        session.ingest(event("event-1", 1, "Changed"))