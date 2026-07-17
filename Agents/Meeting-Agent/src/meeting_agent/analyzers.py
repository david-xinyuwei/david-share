"""Meeting analyzers for real Azure inference and offline contract tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache
from importlib.resources import files
from typing import Any, Protocol

from openai import OpenAI

from .models import MeetingAnalysis, MeetingEventKind
from .session import MeetingSession

MAX_ANALYSIS_CHARS = 200_000
REASONING_EFFORT = "medium"


@lru_cache(maxsize=1)
def _meeting_skill() -> str:
    return (
        files("meeting_agent")
        .joinpath("skills/meeting-package/SKILL.md")
        .read_text(encoding="utf-8")
    )


class Analyzer(Protocol):
    def analyze(self, session: MeetingSession) -> MeetingAnalysis:
        """Convert one validated session into structured meeting content."""

    def analyze_stream(
        self,
        session: MeetingSession,
        on_delta: Callable[[str], None],
    ) -> tuple[MeetingAnalysis, str | None]:
        """Stream real model deltas and return the final structured analysis."""


class AzureOpenAIAnalyzer:
    """Structured Azure OpenAI analyzer using API key authentication."""

    def __init__(self) -> None:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        if not endpoint or not deployment:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT are required"
            )
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("AZURE_OPENAI_API_KEY is required")
        self._deployment = deployment
        self._client = OpenAI(
            base_url=_azure_v1_base_url(endpoint),
            api_key=api_key,
        )

    def analyze(self, session: MeetingSession) -> MeetingAnalysis:
        return _analyze_with_client(self._client, self._deployment, session)

    def analyze_stream(
        self,
        session: MeetingSession,
        on_delta: Callable[[str], None],
    ) -> tuple[MeetingAnalysis, str | None]:
        return _analyze_stream_with_client(
            self._client,
            self._deployment,
            session,
            on_delta,
        )

def _analyze_with_client(
    client: OpenAI,
    deployment: str,
    session: MeetingSession,
) -> MeetingAnalysis:
    request = _analysis_request(deployment, session)
    try:
        response = client.responses.parse(**request)
    except Exception as error:
        raise RuntimeError(f"Azure OpenAI analysis failed: {error}") from error
    return _parsed_analysis(response)


def _analyze_stream_with_client(
    client: OpenAI,
    deployment: str,
    session: MeetingSession,
    on_delta: Callable[[str], None],
) -> tuple[MeetingAnalysis, str | None]:
    request = _analysis_request(deployment, session)
    try:
        with client.responses.stream(**request) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    on_delta(event.delta)
            response = stream.get_final_response()
    except Exception as error:
        raise RuntimeError(f"Azure OpenAI analysis failed: {error}") from error
    return _parsed_analysis(response), response.id


def _analysis_request(deployment: str, session: MeetingSession) -> dict[str, Any]:
    if not session.finalized_text:
        raise ValueError("at least one transcript.final event is required")
    event_text = "\n".join(
        f"[{event.sequence}] {event.kind}: "
        f"{' '.join((event.text or event.image_uri or '').split())}"
        for event in session.events
        if event.kind is not MeetingEventKind.TRANSCRIPT_PARTIAL
    )
    if len(event_text) > MAX_ANALYSIS_CHARS:
        raise ValueError(
            f"meeting analysis input is {len(event_text)} characters; "
            f"the maximum is {MAX_ANALYSIS_CHARS}"
        )
    return {
        "model": deployment,
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": _meeting_skill()}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": event_text}],
            },
        ],
        "reasoning": {"effort": REASONING_EFFORT},
        "text_format": MeetingAnalysis,
        "store": False,
    }


def _parsed_analysis(response: Any) -> MeetingAnalysis:
    if response.output_parsed is None:
        raise RuntimeError("the model returned no structured meeting analysis")
    return response.output_parsed


def _azure_v1_base_url(endpoint: str) -> str:
    compact = endpoint.strip().rstrip("/")
    if not compact.startswith("https://"):
        raise ValueError("AZURE_OPENAI_ENDPOINT must use HTTPS")
    if compact.endswith("/openai/v1"):
        return f"{compact}/"
    return f"{compact}/openai/v1/"