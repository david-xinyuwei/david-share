"""Build one Foundry-hosted meeting run inside a managed session home."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from filelock import FileLock, Timeout

from .analyzers import Analyzer
from .artifacts import generate_artifacts
from .draft import build_eml, file_sha256, write_evidence
from .hosted_models import HostedArtifact, HostedMeetingRequest, HostedMeetingResponse
from .session import MeetingSession, ingest_all


def build_hosted_run(
    request: HostedMeetingRequest,
    session_home: Path,
    analyzer: Analyzer,
) -> HostedMeetingResponse:
    """Generate traceable files under ``session_home`` and return their metadata."""
    session = MeetingSession(request.events[0].session_id)
    ingest_all(session, request.events)
    source_sha256 = session.content_sha256()
    run_id = _run_id(source_sha256, request.recipients)
    output_dir = session_home / "artifacts" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with FileLock(str(output_dir / ".meeting-agent.lock"), timeout=0):
            return _build_locked(
                request,
                session,
                session_home,
                output_dir,
                run_id,
                source_sha256,
                analyzer,
            )
    except Timeout as error:
        raise RuntimeError(f"meeting run is already in progress: {run_id}") from error


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
    analysis = analyzer.analyze(session)
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


def _run_id(source_sha256: str, recipients: list[str]) -> str:
    payload = json.dumps(
        {"source_sha256": source_sha256, "recipients": recipients},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _media_type(path: Path) -> str:
    return {
        ".eml": "message/rfc822",
        ".json": "application/json",
        ".mmd": "text/plain; charset=utf-8",
        ".png": "image/png",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".svg": "image/svg+xml",
    }.get(path.suffix.casefold(), "application/octet-stream")