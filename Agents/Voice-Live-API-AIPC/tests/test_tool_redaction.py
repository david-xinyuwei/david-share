from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from src import agent_core
from src.backends import voicelive
from src.tools import vision


def test_argument_summary_exposes_names_not_values() -> None:
    arguments = (
        '{"to":"user@example.com","subject":"Private subject",'
        '"body":"Private body","confirmation_token":"one-time-secret"}'
    )

    summary = agent_core._argument_summary(arguments)

    assert summary == "参数: body, subject, to"
    assert "user@example.com" not in summary
    assert "Private" not in summary
    assert "one-time-secret" not in summary


def test_coordinator_events_and_logs_redact_payloads(
    monkeypatch, caplog
) -> None:
    events: list[tuple[str, str, dict]] = []
    sensitive_result = {
        "ok": False,
        "error": "ValueError: user@example.com at C:\\Users\\private\\mail.txt",
        "confirmation_token": "one-time-secret",
        "image_path": "C:\\Users\\private\\camera.png",
    }

    async def fake_dispatch(_name: str, _arguments: str | None) -> dict:
        return sensitive_result

    monkeypatch.setattr(agent_core, "emit", lambda kind, text, meta: events.append((kind, text, meta)))
    monkeypatch.setattr(agent_core.tools, "dispatch", fake_dispatch)
    coordinator = agent_core.ToolCallCoordinator()
    coordinator.register("call-1", "send_email")
    coordinator.set_arguments(
        "call-1",
        '{"to":"user@example.com","body":"Private body","confirmation_token":"one-time-secret"}',
    )

    with caplog.at_level(logging.INFO, logger=agent_core.__name__):
        calls = asyncio.run(coordinator.drain())

    assert calls[0].result is sensitive_result
    rendered = repr(events) + caplog.text
    assert "user@example.com" not in rendered
    assert "Private body" not in rendered
    assert "C:\\Users\\private" not in rendered
    assert "one-time-secret" not in rendered
    assert "参数: body, to" in rendered
    assert "ValueError: 工具执行失败" in rendered


def test_voice_transcript_is_not_written_to_logs(monkeypatch, caplog) -> None:
    transcript = "Email secret-body to user@example.com"
    events: list[tuple[str, str]] = []
    turns: list[str] = []
    agent = voicelive.VoiceLiveAgent("endpoint", object(), "model", "voice")
    agent.audio = object()
    event = SimpleNamespace(
        type=voicelive.ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED,
        transcript=transcript,
    )
    monkeypatch.setattr(voicelive.confirmation, "note_user_turn", turns.append)
    monkeypatch.setattr(voicelive, "emit", lambda kind, text: events.append((kind, text)))

    with caplog.at_level(logging.INFO, logger=voicelive.__name__):
        asyncio.run(agent._handle_event(event))

    assert turns == [transcript]
    assert events == [("user", transcript)]
    assert transcript not in caplog.text
    assert f"transcript_chars={len(transcript)}" in caplog.text


def test_camera_analysis_is_not_written_to_logs(caplog) -> None:
    answer = "Sensitive person and document at a private location"

    with caplog.at_level(logging.INFO, logger=vision.__name__):
        vision._log_vision_metadata(answer, "")

    assert answer not in caplog.text
    assert f"answer_chars={len(answer)}" in caplog.text
    assert "shopping_keyword=False" in caplog.text
