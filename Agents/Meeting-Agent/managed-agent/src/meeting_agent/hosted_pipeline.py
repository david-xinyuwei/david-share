"""Build one Foundry-hosted meeting run inside a managed session home."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from .analyzers import Analyzer
from .artifacts import (
    generate_artifacts,
    generate_mind_map_artifacts,
    generate_presentation_artifact,
    mind_map_mermaid,
)
from .draft import build_eml, file_sha256, write_evidence
from .hosted_models import HostedArtifact, HostedMeetingRequest, HostedMeetingResponse
from .presentation import ensure_deck_plan
from .session import MeetingSession, ingest_all

StreamEventCallback = Callable[[str, dict[str, object]], None]


def build_hosted_run(
    request: HostedMeetingRequest,
    session_home: Path,
    analyzer: Analyzer,
) -> HostedMeetingResponse:
    """Generate traceable files under ``session_home`` and return their metadata."""
    session = MeetingSession(request.events[0].session_id)
    ingest_all(session, request.events)
    source_sha256 = session.content_sha256()
    run_id = _new_run_id(source_sha256)
    output_dir = session_home / "artifacts" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    return _build_locked(
        request,
        session,
        session_home,
        output_dir,
        run_id,
        source_sha256,
        analyzer,
    )


def stream_hosted_run(
    request: HostedMeetingRequest,
    session_home: Path,
    analyzer: Analyzer,
    on_event: StreamEventCallback,
    *,
    agent_session_id: str | None = None,
    invocation_id: str | None = None,
) -> HostedMeetingResponse:
    """Build one run while emitting only events backed by completed work."""
    session = MeetingSession(request.events[0].session_id)
    ingest_all(session, request.events)
    source_sha256 = session.content_sha256()
    run_id = _new_run_id(source_sha256)
    output_dir = session_home / "artifacts" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    source_path = output_dir / "meeting-events.json"
    session.save(source_path)
    on_event(
        "accepted",
        {
            "run_id": run_id,
            "session_id": session.session_id,
            "agent_session_id": agent_session_id,
            "source_sha256": source_sha256,
            "event_count": len(session.events),
        },
    )
    on_event("analysis_started", {"run_id": run_id})
    analysis, model_response_id = analyzer.analyze_stream(
        session,
        lambda delta: on_event("model_delta", {"delta": delta}),
    )
    analysis = ensure_deck_plan(analysis)
    mermaid = mind_map_mermaid(analysis.mind_map)
    on_event(
        "analysis_ready",
        {
            "analysis": analysis.model_dump(mode="json"),
            "mermaid": mermaid,
            "model_response_id": model_response_id,
        },
    )

    generated = generate_mind_map_artifacts(analysis, output_dir)
    source_artifact = _artifact(source_path, session_home)
    mind_map_artifacts = {
        name: _artifact(path, session_home)
        for name, path in generated.items()
    }
    on_event(
        "mind_map_ready",
        {
            "artifacts": {
                **{name: artifact.model_dump() for name, artifact in mind_map_artifacts.items()},
                "source": source_artifact.model_dump(),
            }
        },
    )

    presentation_path = generate_presentation_artifact(
        analysis,
        generated["mind_map_png"],
        output_dir,
    )
    presentation_artifact = _artifact(presentation_path, session_home)
    on_event(
        "presentation_ready",
        {"artifact": presentation_artifact.model_dump()},
    )

    eml_path = output_dir / "meeting-follow-up.eml"
    eml_evidence = build_eml(
        analysis,
        [generated["mind_map_png"], presentation_path],
        eml_path,
        request.recipients,
    )
    eml_artifact = _artifact(eml_path, session_home)
    artifacts = {
        **mind_map_artifacts,
        "presentation": presentation_artifact,
        "source": source_artifact,
        "eml": eml_artifact,
    }
    response = HostedMeetingResponse(
        run_id=run_id,
        session_id=session.session_id,
        agent_session_id=agent_session_id,
        invocation_id=invocation_id,
        source_sha256=source_sha256,
        analysis=analysis,
        artifacts=artifacts,
    )
    write_evidence(
        output_dir / "evidence.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "model_response_id": model_response_id,
            "source": {
                "session_id": session.session_id,
                "event_count": len(session.events),
                "content_sha256": source_sha256,
            },
            "artifacts": {
                name: artifact.model_dump() for name, artifact in artifacts.items()
            },
            "eml": eml_evidence,
            "automatic_send": False,
            "next_state": response.next_state,
        },
    )
    on_event("complete", {"run": response.model_dump(mode="json")})
    return response


def _build_locked(
    request: HostedMeetingRequest,
    session: MeetingSession,
    session_home: Path,
    output_dir: Path,
    run_id: str,
    source_sha256: str,
    analyzer: Analyzer,
) -> HostedMeetingResponse:
    source_path = output_dir / "meeting-events.json"
    session.save(source_path)
    analysis = ensure_deck_plan(analyzer.analyze(session))
    generated = generate_artifacts(analysis, output_dir)
    eml_path = output_dir / "meeting-follow-up.eml"
    eml_evidence = build_eml(
        analysis,
        [generated["mind_map_png"], generated["presentation"]],
        eml_path,
        request.recipients,
    )
    artifact_paths = {**generated, "source": source_path, "eml": eml_path}
    artifacts = {
        name: HostedArtifact(
            path=path.relative_to(session_home).as_posix(),
            bytes=path.stat().st_size,
            sha256=file_sha256(path),
            media_type=_media_type(path),
        )
        for name, path in artifact_paths.items()
    }
    response = HostedMeetingResponse(
        run_id=run_id,
        session_id=session.session_id,
        source_sha256=source_sha256,
        analysis=analysis,
        artifacts=artifacts,
    )
    write_evidence(
        output_dir / "evidence.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "source": {
                "session_id": session.session_id,
                "event_count": len(session.events),
                "content_sha256": source_sha256,
            },
            "artifacts": {
                name: artifact.model_dump() for name, artifact in artifacts.items()
            },
            "eml": eml_evidence,
            "automatic_send": False,
            "next_state": response.next_state,
        },
    )
    return response


def _new_run_id(source_sha256: str) -> str:
    return f"{source_sha256[:8]}{uuid4().hex[:16]}"


def _artifact(path: Path, session_home: Path) -> HostedArtifact:
    return HostedArtifact(
        path=path.relative_to(session_home).as_posix(),
        bytes=path.stat().st_size,
        sha256=file_sha256(path),
        media_type=_media_type(path),
    )


def _media_type(path: Path) -> str:
    return {
        ".eml": "message/rfc822",
        ".json": "application/json",
        ".mmd": "text/plain; charset=utf-8",
        ".png": "image/png",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".svg": "image/svg+xml",
    }.get(path.suffix.casefold(), "application/octet-stream")