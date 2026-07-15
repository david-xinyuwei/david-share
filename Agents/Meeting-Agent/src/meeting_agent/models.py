"""Public event and artifact schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MeetingEventKind(StrEnum):
    """Supported provider-neutral event types."""

    TRANSCRIPT_PARTIAL = "transcript.partial"
    TRANSCRIPT_FINAL = "transcript.final"
    VISUAL_FRAME = "visual.frame"
    MEETING_END = "meeting.end"


class MeetingEvent(BaseModel):
    """One ordered event produced by a local ASR or visual provider."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=0)
    timestamp: AwareDatetime
    kind: MeetingEventKind
    text: str | None = Field(default=None, max_length=20_000)
    image_uri: str | None = Field(default=None, max_length=2_048)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if self.kind in {
            MeetingEventKind.TRANSCRIPT_PARTIAL,
            MeetingEventKind.TRANSCRIPT_FINAL,
        } and not (self.text or "").strip():
            raise ValueError("Transcript events require non-empty text.")
        if self.kind is MeetingEventKind.VISUAL_FRAME and not (
            (self.text or "").strip() or (self.image_uri or "").strip()
        ):
            raise ValueError("Visual events require text or image_uri.")
        if self.image_uri:
            if "\r" in self.image_uri or "\n" in self.image_uri:
                raise ValueError("image_uri cannot contain line breaks.")
            if self.image_uri.casefold().startswith("data:"):
                raise ValueError("image_uri cannot contain an embedded data URI.")
        return self


class ActionItem(BaseModel):
    """A follow-up action extracted from the meeting."""

    description: NonEmptyText = Field(max_length=1_000)
    owner: NonEmptyText | None = Field(default=None, max_length=256)
    due: NonEmptyText | None = Field(default=None, max_length=256)


class MindMapNode(BaseModel):
    """A renderer-neutral mind-map node."""

    label: NonEmptyText = Field(max_length=1_000)
    children: list[MindMapNode] = Field(default_factory=list)


class MeetingAnalysis(BaseModel):
    """Structured output consumed by all artifact generators."""

    title: NonEmptyText = Field(max_length=160)
    summary: NonEmptyText = Field(max_length=20_000)
    topics: list[NonEmptyText] = Field(default_factory=list)
    decisions: list[NonEmptyText] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[NonEmptyText] = Field(default_factory=list)
    mind_map: MindMapNode


MindMapNode.model_rebuild()