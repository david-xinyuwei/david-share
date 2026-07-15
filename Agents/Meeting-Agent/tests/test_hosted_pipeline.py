from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser

import pytest
from filelock import FileLock

from meeting_agent.analyzers import OfflineContractAnalyzer
from meeting_agent.hosted_models import HostedMeetingRequest
from meeting_agent.hosted_pipeline import build_hosted_run
from meeting_agent.models import MeetingEvent, MeetingEventKind


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
    response = build_hosted_run(request, tmp_path, OfflineContractAnalyzer())

    assert response.session_id == "session-1"
    assert response.analysis.decisions == [
        "The team approved the launch plan and Alice will follow up."
    ]
    assert response.automatic_send is False
    assert response.next_state == "DRAFT_READY_MANUAL_SEND_REQUIRED"
    assert {"analysis", "mind_map_png", "presentation", "eml", "source"} <= set(
        response.artifacts
    )
    for artifact in response.artifacts.values():
        path = tmp_path / artifact.path
        assert path.is_file()
        assert path.stat().st_size == artifact.bytes

    eml_path = tmp_path / response.artifacts["eml"].path
    message = BytesParser(policy=policy.default).parsebytes(eml_path.read_bytes())
    assert message["X-Unsent"] == "1"
    assert str(message["To"]) == "reviewer@example.com"
    assert len(list(message.iter_attachments())) == 2

    repeated = build_hosted_run(request, tmp_path, OfflineContractAnalyzer())
    assert repeated.run_id == response.run_id
    assert repeated.source_sha256 == response.source_sha256


def test_same_run_fails_closed_while_generation_lock_is_held(tmp_path):
    request = _request()
    response = build_hosted_run(request, tmp_path, OfflineContractAnalyzer())
    lock_path = tmp_path / "artifacts" / response.run_id / ".meeting-agent.lock"

    with (
        FileLock(str(lock_path), timeout=0),
        pytest.raises(RuntimeError, match="meeting run is already in progress"),
    ):
        build_hosted_run(request, tmp_path, OfflineContractAnalyzer())