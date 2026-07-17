"""Static test fixtures that must not enter the product runtime."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from meeting_agent.models import MeetingAnalysis
from meeting_agent.session import MeetingSession

ROOT = Path(__file__).resolve().parents[1]

def sample_analysis(name: str) -> MeetingAnalysis:
    path = ROOT / "evidence" / "sample-runs" / name / "meeting-analysis.json"
    return MeetingAnalysis.model_validate_json(path.read_text(encoding="utf-8"))


class StaticFixtureAnalyzer:
    def __init__(
        self,
        analysis: MeetingAnalysis,
        *,
        response_id: str | None = None,
        deltas: tuple[str, ...] = (),
    ) -> None:
        self._analysis = analysis
        self._response_id = response_id
        self._deltas = deltas

    def analyze(self, _session: MeetingSession) -> MeetingAnalysis:
        return self._analysis.model_copy(deep=True)

    def analyze_stream(
        self,
        session: MeetingSession,
        on_delta: Callable[[str], None],
    ) -> tuple[MeetingAnalysis, str | None]:
        for delta in self._deltas:
            on_delta(delta)
        return self.analyze(session), self._response_id