"""Public request and response models for the Foundry Invocations endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import MeetingAnalysis, MeetingEvent, NonEmptyText


class HostedMeetingRequest(BaseModel):
    """One complete meeting build request submitted through Foundry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    operation: Literal["build"] = "build"
    events: list[MeetingEvent] = Field(min_length=1, max_length=5_000)
    recipients: list[NonEmptyText] = Field(default_factory=list, max_length=50)


class HostedArtifact(BaseModel):
    """A generated file exposed through the Foundry session files API."""

    path: NonEmptyText
    bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: NonEmptyText


class HostedMeetingResponse(BaseModel):
    """Structured result returned by the Foundry Invocations endpoint."""

    schema_version: Literal[1] = 1
    run_id: NonEmptyText
    session_id: NonEmptyText
    agent_session_id: NonEmptyText | None = None
    invocation_id: NonEmptyText | None = None
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis: MeetingAnalysis
    artifacts: dict[str, HostedArtifact]
    automatic_send: Literal[False] = False
    next_state: Literal["DRAFT_READY_MANUAL_SEND_REQUIRED"] = (
        "DRAFT_READY_MANUAL_SEND_REQUIRED"
    )