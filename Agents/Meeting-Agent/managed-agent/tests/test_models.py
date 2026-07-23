from copy import deepcopy

import pytest
from pydantic import ValidationError

from meeting_agent.models import MeetingAnalysis, MeetingEvent, MeetingEventKind

BASE_EVENT = {
    "event_id": "event-001",
    "session_id": "session-001",
    "sequence": 7,
    "timestamp": "2026-01-15T09:00:01Z",
    "kind": "transcript.final",
    "text": "The team approved the pilot.",
    "image_uri": "frame://screen-001",
    "metadata": {"source": "local-adapter", "confidence": 0.97},
}

BASE_ANALYSIS = {
    "title": "Planning review",
    "summary": "The team reviewed the rollout plan.",
    "topics": ["Rollout"],
    "action_items": [{"description": "Prepare the checklist"}],
    "mind_map": {"label": "Planning review"},
}


def test_accepts_and_preserves_every_event_field() -> None:
    event = MeetingEvent.model_validate(BASE_EVENT)

    assert event.event_id == BASE_EVENT["event_id"]
    assert event.session_id == BASE_EVENT["session_id"]
    assert event.sequence == BASE_EVENT["sequence"]
    assert event.timestamp.isoformat() == "2026-01-15T09:00:01+00:00"
    assert event.kind is MeetingEventKind.TRANSCRIPT_FINAL
    assert event.text == BASE_EVENT["text"]
    assert event.image_uri == BASE_EVENT["image_uri"]
    assert event.metadata == BASE_EVENT["metadata"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", ""),
        ("session_id", ""),
        ("sequence", -1),
        ("timestamp", "2026-01-15T09:00:01"),
        ("kind", "unsupported.event"),
        ("text", ""),
        ("image_uri", "x" * 2_049),
        ("metadata", ["not", "an", "object"]),
    ],
)
def test_rejects_invalid_value_for_each_event_field(field: str, value: object) -> None:
    payload = deepcopy(BASE_EVENT)
    payload[field] = value
    with pytest.raises(ValidationError):
        MeetingEvent.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {**BASE_EVENT, "kind": "transcript.partial", "text": "Working hypothesis"},
        {**BASE_EVENT, "kind": "transcript.final", "text": "Final statement"},
        {**BASE_EVENT, "kind": "visual.frame", "text": None},
        {**BASE_EVENT, "kind": "meeting.end", "text": None, "image_uri": None},
    ],
)
def test_supports_each_declared_event_kind(payload: dict[str, object]) -> None:
    MeetingEvent.model_validate(payload)


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        MeetingEvent.model_validate({**BASE_EVENT, "unexpected": True})


def test_visual_event_requires_text_or_image_uri() -> None:
    with pytest.raises(ValidationError):
        MeetingEvent.model_validate(
            {**BASE_EVENT, "kind": "visual.frame", "text": None, "image_uri": None}
        )


@pytest.mark.parametrize(
    "image_uri",
    [
        "data:image/png;base64,AAAA",
        "frame://screen-001\nInjected",
        "frame://screen-001\rInjected",
    ],
)
def test_rejects_embedded_or_multiline_image_uri(image_uri: str) -> None:
    with pytest.raises(ValidationError):
        MeetingEvent.model_validate(
            {**BASE_EVENT, "kind": "visual.frame", "text": None, "image_uri": image_uri}
        )


@pytest.mark.parametrize(
    "override",
    [
        {"title": "   "},
        {"summary": ""},
        {"topics": [" "]},
        {"action_items": [{"description": "\t"}]},
        {"mind_map": {"label": "\n"}},
    ],
)
def test_rejects_semantically_empty_analysis_fields(override: dict[str, object]) -> None:
    payload = deepcopy(BASE_ANALYSIS)
    payload.update(override)

    with pytest.raises(ValidationError):
        MeetingAnalysis.model_validate(payload)