from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import meeting_agent.analyzers as analyzers
from meeting_agent.models import MeetingAnalysis, MeetingEvent, MindMapNode
from meeting_agent.session import MeetingSession, load_jsonl

ROOT = Path(__file__).resolve().parents[1]


class FakeResponses:
    def __init__(self, analysis: MeetingAnalysis) -> None:
        self.analysis = analysis
        self.request: dict[str, Any] = {}

    def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.analysis)

    def stream(self, **kwargs: Any):
        self.request = kwargs
        analysis = self.analysis

        class Stream:
            def __iter__(self):
                return iter(
                    [
                        SimpleNamespace(
                            type="response.output_text.delta",
                            delta='{"title":"Structured',
                        ),
                        SimpleNamespace(type="response.in_progress"),
                        SimpleNamespace(
                            type="response.output_text.delta",
                            delta=' result"}',
                        ),
                    ]
                )

            def get_final_response(self):
                return SimpleNamespace(
                    id="resp_stream_123",
                    output_parsed=analysis,
                )

        class Manager:
            def __enter__(self):
                return Stream()

            def __exit__(self, exc_type, exc, traceback):
                return False

        return Manager()


class FakeOpenAI:
    analysis = MeetingAnalysis(
        title="Structured result",
        summary="Generated from the supplied event evidence.",
        mind_map=MindMapNode(label="Structured result"),
    )
    instances: list["FakeOpenAI"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.configuration = kwargs
        self.responses = FakeResponses(self.analysis)
        self.instances.append(self)


def test_uses_official_v1_key_path_and_non_stored_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeOpenAI.instances.clear()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "meeting-model")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(analyzers, "OpenAI", FakeOpenAI)

    analyzer = analyzers.AzureOpenAIAnalyzer()
    result = analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))

    client = FakeOpenAI.instances[0]
    assert client.configuration == {
        "base_url": "https://example.openai.azure.com/openai/v1/",
        "api_key": "synthetic-test-key",
    }
    assert client.responses.request["model"] == "meeting-model"
    assert client.responses.request["text_format"] is MeetingAnalysis
    assert client.responses.request["store"] is False
    assert client.responses.request["reasoning"] == {"effort": "medium"}
    system_message = client.responses.request["input"][0]
    assert system_message["type"] == "message"
    assert system_message["content"][0]["type"] == "input_text"
    assert "untrusted data" in system_message["content"][0]["text"]
    assert "six-slide customer-ready deck" in system_message["content"][0]["text"]
    assert result == FakeOpenAI.analysis


def test_key_authentication_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "meeting-model")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY is required"):
        analyzers.AzureOpenAIAnalyzer()


def test_streams_real_text_deltas_and_returns_structured_result() -> None:
    client = FakeOpenAI()
    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = client
    deltas: list[str] = []

    analysis, response_id = analyzer.analyze_stream(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl"),
        deltas.append,
    )

    assert deltas == ['{"title":"Structured', ' result"}']
    assert analysis == FakeOpenAI.analysis
    assert response_id == "resp_stream_123"
    assert client.responses.request["model"] == "meeting-model"
    assert client.responses.request["text_format"] is MeetingAnalysis
    assert client.responses.request["reasoning"] == {"effort": "medium"}
    assert client.responses.request["store"] is False


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (
            "https://example.openai.azure.com/",
            "https://example.openai.azure.com/openai/v1/",
        ),
        (
            "https://example.openai.azure.com/openai/v1/",
            "https://example.openai.azure.com/openai/v1/",
        ),
    ],
)
def test_normalizes_azure_v1_base_url(endpoint: str, expected: str) -> None:
    assert analyzers._azure_v1_base_url(endpoint) == expected


def test_rejects_non_https_endpoint() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        analyzers._azure_v1_base_url("http://example.openai.azure.com")


def test_wraps_external_analysis_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingResponses:
        def parse(self, **kwargs: Any) -> None:
            raise ConnectionError("network unavailable")

    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = SimpleNamespace(responses=FailingResponses())

    with pytest.raises(RuntimeError, match="Azure OpenAI analysis failed"):
        analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))


def test_normalizes_multiline_event_text_before_analysis() -> None:
    session = MeetingSession("multiline")
    session.ingest(
        MeetingEvent.model_validate(
            {
                "event_id": "event-0",
                "session_id": "multiline",
                "sequence": 0,
                "timestamp": "2026-01-15T09:00:00Z",
                "kind": "transcript.partial",
                "text": "This hypothesis must not enter analysis",
            }
        )
    )
    session.ingest(
        MeetingEvent.model_validate(
            {
                "event_id": "event-1",
                "session_id": "multiline",
                "sequence": 1,
                "timestamp": "2026-01-15T09:00:01Z",
                "kind": "transcript.final",
                "text": "First line\nSecond line\r\nThird line",
            }
        )
    )
    client = FakeOpenAI()
    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = client

    analyzer.analyze(session)

    user_message = client.responses.request["input"][1]
    assert user_message["type"] == "message"
    assert user_message["content"][0]["type"] == "input_text"
    user_content = user_message["content"][0]["text"]
    assert user_content == "[1] transcript.final: First line Second line Third line"


def test_requires_finalized_transcript_before_azure_call() -> None:
    session = MeetingSession("visual-only")
    session.ingest(
        MeetingEvent.model_validate(
            {
                "event_id": "event-1",
                "session_id": "visual-only",
                "sequence": 1,
                "timestamp": "2026-01-15T09:00:01Z",
                "kind": "visual.frame",
                "text": "A roadmap is visible.",
            }
        )
    )
    client = FakeOpenAI()
    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = client

    with pytest.raises(ValueError, match="transcript.final"):
        analyzer.analyze(session)

    assert client.responses.request == {}


def test_rejects_analysis_input_over_character_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzers, "MAX_ANALYSIS_CHARS", 20)
    analyzer = object.__new__(analyzers.AzureOpenAIAnalyzer)
    analyzer._deployment = "meeting-model"
    analyzer._client = FakeOpenAI()

    with pytest.raises(ValueError, match="maximum is 20"):
        analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))