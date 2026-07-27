from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser

from meeting_agent.hosted_models import HostedMeetingRequest
from meeting_agent.hosted_pipeline import build_hosted_run, stream_hosted_run
from meeting_agent.models import MeetingEvent, MeetingEventKind
from meeting_agent.presentation import ensure_deck_plan
from tests.support import StaticFixtureAnalyzer, sample_analysis


def _request() -> HostedMeetingRequest:
    return HostedMeetingRequest(
        events=[
            MeetingEvent(
                event_id="event-1",
                session_id="session-1",
                sequence=1,
                timestamp=datetime(2026, 7, 15, 9, 0, tzinfo=UTC),
                kind=MeetingEventKind.TRANSCRIPT_FINAL,
                text="The team approved the launch plan and Alice will follow up.",
            ),
            MeetingEvent(
                event_id="event-2",
                session_id="session-1",
                sequence=2,
                timestamp=datetime(2026, 7, 15, 9, 1, tzinfo=UTC),
                kind=MeetingEventKind.MEETING_END,
            ),
        ],
        recipients=["reviewer@example.com"],
    )


def test_hosted_run_generates_session_downloads(tmp_path):
    request = _request()
    fixture = sample_analysis("product-planning")
    response = build_hosted_run(request, tmp_path, StaticFixtureAnalyzer(fixture))

    assert response.session_id == "session-1"
    assert response.analysis == ensure_deck_plan(fixture)
    assert response.automatic_send is False
    assert response.next_state == "DRAFT_READY_MANUAL_SEND_REQUIRED"
    assert {
        "analysis",
        "deck_plan",
        "mind_map_png",
        "presentation",
        "eml",
        "source",
    } <= set(response.artifacts)
    for artifact in response.artifacts.values():
        path = tmp_path / artifact.path
        assert path.is_file()
        assert path.stat().st_size == artifact.bytes

    eml_path = tmp_path / response.artifacts["eml"].path
    message = BytesParser(policy=policy.default).parsebytes(eml_path.read_bytes())
    assert message["X-Unsent"] == "1"
    assert str(message["To"]) == "reviewer@example.com"
    assert len(list(message.iter_attachments())) == 2

    repeated = build_hosted_run(request, tmp_path, StaticFixtureAnalyzer(fixture))
    assert repeated.run_id != response.run_id
    assert repeated.source_sha256 == response.source_sha256
    assert repeated.artifacts["analysis"].path != response.artifacts["analysis"].path
    assert (tmp_path / response.artifacts["analysis"].path).is_file()
    assert (tmp_path / repeated.artifacts["analysis"].path).is_file()


def test_run_id_keeps_source_prefix_and_unique_nonce(tmp_path):
    request = _request()
    fixture = sample_analysis("product-planning")
    first = build_hosted_run(request, tmp_path, StaticFixtureAnalyzer(fixture))
    second = build_hosted_run(request, tmp_path, StaticFixtureAnalyzer(fixture))

    assert first.run_id[:8] == first.source_sha256[:8]
    assert second.run_id[:8] == second.source_sha256[:8]
    assert len(first.run_id) == 24
    assert first.run_id != second.run_id


def test_streaming_run_emits_only_completed_stages(tmp_path):
    events: list[tuple[str, dict[str, object]]] = []

    def capture(event: str, data: dict[str, object]) -> None:
        if event == "mind_map_ready":
            artifacts = data["artifacts"]
            assert isinstance(artifacts, dict)
            for artifact in artifacts.values():
                assert isinstance(artifact, dict)
                assert (tmp_path / str(artifact["path"])).is_file()
        if event == "presentation_ready":
            artifact = data["artifact"]
            assert isinstance(artifact, dict)
            assert (tmp_path / str(artifact["path"])).is_file()
        events.append((event, data))

    response = stream_hosted_run(
        _request(),
        tmp_path,
        StaticFixtureAnalyzer(
            sample_analysis("product-planning"),
            response_id="resp_test_123",
            deltas=('{"title":"', 'The group approved the plan"}'),
        ),
        capture,
        agent_session_id="stream-session",
        invocation_id="stream-invocation",
    )

    assert [name for name, _ in events] == [
        "accepted",
        "analysis_started",
        "model_delta",
        "model_delta",
        "analysis_ready",
        "mind_map_ready",
        "presentation_ready",
        "complete",
    ]
    assert events[2][1]["delta"] == '{"title":"'
    assert events[4][1]["model_response_id"] == "resp_test_123"
    assert events[-1][1]["run"]["run_id"] == response.run_id
    assert response.agent_session_id == "stream-session"
    evidence = (
        tmp_path / "artifacts" / response.run_id / "evidence.json"
    ).read_text(encoding="utf-8")
    assert '"model_response_id": "resp_test_123"' in evidence