import asyncio
import json
import os
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
import meeting_agent.hosted as hosted
from meeting_agent.hosted_models import HostedMeetingRequest


def _request() -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "build",
        "events": [
            {
                "event_id": "event-1",
                "session_id": "hosted-api",
                "sequence": 1,
                "timestamp": datetime(2026, 7, 15, 10, 0, tzinfo=UTC).isoformat(),
                "kind": "transcript.final",
                "text": "The group approved the plan and Mei will follow up.",
                "metadata": {},
            }
        ],
        "recipients": [],
    }


def _post(path: str, payload: dict[str, object]) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=hosted.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(path, json=payload)

    return asyncio.run(send())


def test_invocations_builds_real_session_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETING_AGENT_ANALYZER", "offline-contract")
    monkeypatch.setenv("MEETING_AGENT_ENABLE_OFFLINE_CONTRACT", "1")
    monkeypatch.setenv("MEETING_AGENT_SESSION_HOME", str(tmp_path))
    hosted._get_analyzer.cache_clear()

    response = _post(
        "/invocations?agent_session_id=foundry-session-1",
        _request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "hosted-api"
    assert body["automatic_send"] is False
    assert body["artifacts"]["presentation"]["media_type"].endswith(
        "presentationml.presentation"
    )
    assert (tmp_path / body["artifacts"]["presentation"]["path"]).is_file()
    assert (tmp_path / body["artifacts"]["eml"]["path"]).is_file()


def test_streaming_invocation_emits_real_completed_stages(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETING_AGENT_ANALYZER", "offline-contract")
    monkeypatch.setenv("MEETING_AGENT_ENABLE_OFFLINE_CONTRACT", "1")
    monkeypatch.setenv("MEETING_AGENT_SESSION_HOME", str(tmp_path))
    hosted._get_analyzer.cache_clear()

    response = _post(
        "/invocations_stream?agent_session_id=stream-session-1",
        _request(),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _ndjson_events(response.text)
    assert [event for event, _ in events] == [
        "accepted",
        "analysis_started",
        "analysis_ready",
        "mind_map_ready",
        "presentation_ready",
        "complete",
    ]
    analysis = events[2][1]
    assert analysis["mermaid"].startswith("mindmap\n")
    mind_map = events[3][1]["artifacts"]
    assert (tmp_path / mind_map["mind_map_mermaid"]["path"]).is_file()
    presentation = events[4][1]["artifact"]
    assert (tmp_path / presentation["path"]).is_file()
    run = events[-1][1]["run"]
    assert run["agent_session_id"] == "stream-session-1"
    assert (tmp_path / run["artifacts"]["eml"]["path"]).is_file()


def test_offline_contract_must_be_explicitly_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETING_AGENT_ANALYZER", "offline-contract")
    monkeypatch.delenv("MEETING_AGENT_ENABLE_OFFLINE_CONTRACT", raising=False)
    monkeypatch.setenv("MEETING_AGENT_SESSION_HOME", str(tmp_path))
    hosted._get_analyzer.cache_clear()

    response = _post("/invocations", _request())

    assert response.status_code == 503
    assert response.json()["error"] == "analysis_unavailable"


def test_invocations_rejects_unknown_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETING_AGENT_SESSION_HOME", str(tmp_path))
    payload = _request()
    payload["pretend_success"] = True

    response = _post("/invocations", payload)

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_hosted_request_enforces_event_count_limit():
    event = HostedMeetingRequest.model_validate(_request()).events[0]

    HostedMeetingRequest(events=[event] * 5_000)
    with pytest.raises(ValidationError):
        HostedMeetingRequest(events=[event] * 5_001)


def test_main_rejects_invalid_port(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-port")

    try:
        hosted.main()
    except RuntimeError as error:
        assert str(error) == "PORT must be an integer"
    else:
        raise AssertionError("hosted.main() accepted an invalid PORT")


def _ndjson_events(value: str) -> list[tuple[str, dict[str, object]]]:
    return [
        (event["type"], event["data"])
        for event in (json.loads(line) for line in value.splitlines() if line)
    ]