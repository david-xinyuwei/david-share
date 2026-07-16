"""Meeting analyzers for real Azure inference and offline contract tests."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from functools import lru_cache
from importlib.resources import files
from typing import Any, Protocol

from openai import OpenAI

from .models import ActionItem, MeetingAnalysis, MeetingEventKind, MindMapNode
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


class OfflineContractAnalyzer:
    """Deterministic parser for CI and adapter testing, not AI quality evaluation."""

    decision_terms = ("decided", "agreed", "approved", "决定", "同意", "确认")
    action_terms = ("will", "action", "follow up", "负责", "跟进", "需要")

    def analyze(self, session: MeetingSession) -> MeetingAnalysis:
        segments = session.finalized_text
        if not segments:
            raise ValueError("at least one transcript.final event is required")
        visual = session.visual_context
        title = _shorten(segments[0], 72)
        topics = _unique([_shorten(segment, 90) for segment in segments[:5]])
        decisions = _matching_sentences(segments, self.decision_terms)
        actions = [
            ActionItem(description=_shorten(sentence, 160))
            for sentence in _matching_sentences(segments, self.action_terms)
        ]
        open_questions = [
            _shorten(sentence, 160)
            for segment in segments
            for sentence in _sentences(segment)
            if "?" in sentence or "？" in sentence
        ][:5]
        summary_parts = segments[:3] + ([f"Visual context: {visual[0]}"] if visual else [])
        mind_map = MindMapNode(
            label=title,
            children=[
                MindMapNode(label="Topics", children=[MindMapNode(label=item) for item in topics]),
                MindMapNode(
                    label="Decisions",
                    children=[MindMapNode(label=item) for item in decisions],
                ),
                MindMapNode(
                    label="Actions",
                    children=[MindMapNode(label=item.description) for item in actions],
                ),
            ],
        )
        return MeetingAnalysis(
            title=title,
            summary=" ".join(summary_parts),
            topics=topics,
            decisions=decisions,
            action_items=actions,
            open_questions=_unique(open_questions),
            mind_map=mind_map,
        )

    def analyze_stream(
        self,
        session: MeetingSession,
        on_delta: Callable[[str], None],
    ) -> tuple[MeetingAnalysis, str | None]:
        return self.analyze(session), None


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


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s*", text) if part.strip()]


def _matching_sentences(segments: list[str], terms: tuple[str, ...]) -> list[str]:
    return _unique(
        [
            _shorten(sentence, 160)
            for segment in segments
            for sentence in _sentences(segment)
            if any(term in sentence.casefold() for term in terms)
        ]
    )[:8]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _shorten(text: str, length: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= length else compact[: length - 1].rstrip() + "…"


def _azure_v1_base_url(endpoint: str) -> str:
    compact = endpoint.strip().rstrip("/")
    if not compact.startswith("https://"):
        raise ValueError("AZURE_OPENAI_ENDPOINT must use HTTPS")
    if compact.endswith("/openai/v1"):
        return f"{compact}/"
    return f"{compact}/openai/v1/"