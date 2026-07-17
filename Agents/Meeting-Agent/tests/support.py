"""Deterministic test fixtures that must not enter the product runtime."""

from __future__ import annotations

import re
from collections.abc import Callable

from meeting_agent.models import ActionItem, MeetingAnalysis, MindMapNode
from meeting_agent.session import MeetingSession


class DeterministicTestAnalyzer:
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