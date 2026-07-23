import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from meeting_agent.analyzers import MANAGED_AGENT_SCOPE, ManagedAgentAnalyzer
from meeting_agent.models import MeetingAnalysis, MindMapNode
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = (
    "https://example.services.ai.azure.com/api/projects/meeting/"
    "openai/v1/responses"
)


class FakeCredential:
    def __init__(self) -> None:
        self.scopes: list[str] = []

    def get_token(self, scope: str) -> SimpleNamespace:
        self.scopes.append(scope)
        return SimpleNamespace(token="synthetic-entra-token")


def analysis() -> MeetingAnalysis:
    return MeetingAnalysis(
        title="Managed meeting result",
        summary="Grounded in the supplied meeting evidence.",
        topics=["Runtime ownership"],
        decisions=["Use the managed runtime"],
        mind_map=MindMapNode(label="Managed meeting result"),
    )


def completed_response() -> dict[str, object]:
    return {
        "id": "caresp_test_123",
        "status": "completed",
        "agent_reference": {
            "type": "agent_reference",
            "name": "managed-meeting-agent",
            "version": "1",
        },
        "output": [
            {
                "type": "message",
                "agent_reference": {
                    "type": "agent_reference",
                    "name": "managed-meeting-agent",
                    "version": "1",
                },
                "content": [
                    {"type": "output_text", "text": analysis().model_dump_json()}
                ],
            }
        ],
    }


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANAGED_AGENT_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("MANAGED_AGENT_NAME", "managed-meeting-agent")
    monkeypatch.setenv("MANAGED_AGENT_VERSION", "1")


def test_uses_entra_agent_reference_and_strict_analysis_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    credential = FakeCredential()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer synthetic-entra-token"
        assert request.headers["Foundry-Features"] == "HostedAgents=V1Preview"
        assert request.headers["x-model-endpoint"] == "https://example.services.ai.azure.com"
        payload = json.loads(request.content)
        assert payload["agent_reference"] == {
            "type": "agent_reference",
            "name": "managed-meeting-agent",
            "version": "1",
        }
        assert payload["stream"] is False
        assert "MEETING_ANALYSIS_SCHEMA=" in payload["input"]
        assert "untrusted evidence" in payload["input"]
        assert "transcript.partial" not in payload["input"]
        assert "Azure OpenAI API" not in payload["input"]
        return httpx.Response(200, json=completed_response())

    analyzer = ManagedAgentAnalyzer(
        credential=credential,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))

    assert result == analysis()
    assert credential.scopes == [MANAGED_AGENT_SCOPE]


def test_streams_real_sse_deltas_and_returns_response_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    serialized = analysis().model_dump_json()
    midpoint = len(serialized) // 2
    events = [
        {"type": "response.output_text.delta", "delta": serialized[:midpoint]},
        {"type": "response.output_text.delta", "delta": serialized[midpoint:]},
        {"type": "response.completed", "response": completed_response()},
    ]
    body = "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        assert request.headers["Accept"] == "text/event-stream"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    deltas: list[str] = []
    analyzer = ManagedAgentAnalyzer(
        credential=FakeCredential(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result, response_id = analyzer.analyze_stream(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl"),
        deltas.append,
    )

    assert "".join(deltas) == serialized
    assert result == analysis()
    assert response_id == "caresp_test_123"


def test_rejects_unexpected_agent_version(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    body = completed_response()
    body["agent_reference"]["version"] = "2"
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    analyzer = ManagedAgentAnalyzer(credential=FakeCredential(), http_client=client)

    with pytest.raises(RuntimeError, match="unexpected agent version"):
        analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))


def test_rejects_non_object_success_response(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=["unexpected"])
        )
    )
    analyzer = ManagedAgentAnalyzer(credential=FakeCredential(), http_client=client)

    with pytest.raises(RuntimeError, match="non-object response"):
        analyzer.analyze(load_jsonl(ROOT / "examples" / "product-planning.jsonl"))


def test_does_not_emit_delta_before_agent_reference_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure(monkeypatch)
    serialized = analysis().model_dump_json()
    bad = completed_response()
    bad["agent_reference"]["version"] = "2"
    events = [
        {"type": "response.output_text.delta", "delta": serialized},
        {"type": "response.completed", "response": bad},
    ]
    body = "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=body, headers={"Content-Type": "text/event-stream"}
            )
        )
    )
    deltas: list[str] = []
    analyzer = ManagedAgentAnalyzer(credential=FakeCredential(), http_client=client)

    with pytest.raises(RuntimeError, match="unexpected agent version"):
        analyzer.analyze_stream(
            load_jsonl(ROOT / "examples" / "product-planning.jsonl"),
            deltas.append,
        )

    assert deltas == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.services.ai.azure.com/openai/v1/responses",
        "https://external.example/openai/v1/responses",
        "https://user" + "@example.services.ai.azure.com/openai/v1/responses",
        "https://example.services.ai.azure.com:443/openai/v1/responses",
        "https://example.services.ai.azure.com/not-responses",
        "https://example.services.ai.azure.com/openai/v1/responses?api-version=v1",
    ],
)
def test_rejects_invalid_managed_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    configure(monkeypatch)
    monkeypatch.setenv("MANAGED_AGENT_ENDPOINT", endpoint)

    with pytest.raises(ValueError):
        ManagedAgentAnalyzer(credential=FakeCredential())


def test_rejects_unknown_credential_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    monkeypatch.setenv("MANAGED_AGENT_CREDENTIAL", "unexpected")

    with pytest.raises(RuntimeError, match="must be 'azure-cli' or 'default'"):
        ManagedAgentAnalyzer()