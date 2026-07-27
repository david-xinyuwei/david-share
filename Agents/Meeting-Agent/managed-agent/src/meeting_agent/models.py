"""Public event and artifact schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

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


class CoverSlide(BaseModel):
    """Content slots for the cover slide."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["cover"] = "cover"
    title: NonEmptyText = Field(max_length=160)
    subtitle: NonEmptyText = Field(max_length=1_000)


class OverviewSlide(BaseModel):
    """Content slots for the executive overview slide."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["overview"] = "overview"
    summary: NonEmptyText = Field(max_length=20_000)


class TopicsSlide(BaseModel):
    """Content slots for the topic landscape slide."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["topics"] = "topics"
    items: list[NonEmptyText] = Field(default_factory=list, max_length=6)


class DecisionsActionsSlide(BaseModel):
    """Content slots for decisions and the action register."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["decisions_actions"] = "decisions_actions"
    decisions: list[NonEmptyText] = Field(default_factory=list, max_length=5)
    actions: list[ActionItem] = Field(default_factory=list, max_length=5)


class MindMapSlide(BaseModel):
    """Content slots for the evidence-backed mind-map slide."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["mind_map"] = "mind_map"
    title: NonEmptyText = Field(max_length=160)


class NextStepsSlide(BaseModel):
    """Content slots for open questions and the immediate next step."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["next_steps"] = "next_steps"
    questions: list[NonEmptyText] = Field(default_factory=list, max_length=7)
    next_step: NonEmptyText | None = Field(default=None, max_length=1_000)


class DeckPlan(BaseModel):
    """Strict six-slide content contract consumed by the PowerPoint renderer."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    cover: CoverSlide
    overview: OverviewSlide
    topics: TopicsSlide
    decisions_actions: DecisionsActionsSlide
    mind_map: MindMapSlide
    next_steps: NextStepsSlide


class MeetingAnalysis(BaseModel):
    """Structured output consumed by all artifact generators."""

    title: NonEmptyText = Field(max_length=160)
    summary: NonEmptyText = Field(max_length=20_000)
    topics: list[NonEmptyText] = Field(default_factory=list)
    decisions: list[NonEmptyText] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    open_questions: list[NonEmptyText] = Field(default_factory=list)
    mind_map: MindMapNode
    deck_plan: DeckPlan | None = None


MindMapNode.model_rebuild()