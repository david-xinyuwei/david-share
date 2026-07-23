import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from meeting_agent.analyzers import ManagedAgentAnalyzer
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


class Credential:
    def get_token(self, scope: str) -> SimpleNamespace:
        return SimpleNamespace(token="synthetic-token")


def configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MANAGED_AGENT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/test/openai/v1/responses",
    )
    monkeypatch.setenv("MANAGED_AGENT_NAME", "managed-meeting-agent")
    monkeypatch.setenv("MANAGED_AGENT_VERSION", "1")


def test_stream_rejects_non_object_completed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    event = {"type": "response.completed", "response": "invalid"}
    body = f"event: response.completed\ndata: {json.dumps(event)}\n\n"
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=body, headers={"Content-Type": "text/event-stream"}
            )
        )
    )
    analyzer = ManagedAgentAnalyzer(credential=Credential(), http_client=client)

    with pytest.raises(RuntimeError, match="invalid completed response"):
        analyzer.analyze_stream(
            load_jsonl(ROOT / "examples" / "product-planning.jsonl"),
            lambda delta: None,
        )
