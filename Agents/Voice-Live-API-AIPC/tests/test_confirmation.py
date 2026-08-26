from __future__ import annotations

import asyncio

import pytest

from src import confirmation, tools
from src.tools import mailer


@pytest.fixture(autouse=True)
def reset_confirmation_state() -> None:
    confirmation.reset_for_tests()


def dispatch(name: str, arguments: dict) -> dict:
    return asyncio.run(tools.dispatch(name, arguments))


def test_protected_tool_cannot_execute_in_issuing_turn() -> None:
    result = dispatch("send_email", {"subject": "Test", "body": "Body"})
    assert result["confirmation_required"] is True
    token = result["confirmation_token"]

    same_turn = dispatch(
        "send_email",
        {"subject": "Test", "body": "Body", "confirmation_token": token},
    )
    assert same_turn["confirmation_required"] is True
    assert same_turn["confirmation_token"] == token


def test_confirmation_is_bound_to_exact_arguments() -> None:
    first = dispatch("send_email", {"subject": "Test", "body": "Body"})
    confirmation.note_user_turn("确认")
    changed = dispatch(
        "send_email",
        {"subject": "Changed", "body": "Body", "confirmation_token": first["confirmation_token"]},
    )
    assert changed["ok"] is False
    assert "changed" in changed["error"].lower()


def test_non_affirmative_turn_rejects_confirmation() -> None:
    first = dispatch("open_camera", {})
    confirmation.note_user_turn("先不要")
    rejected = dispatch("open_camera", {"confirmation_token": first["confirmation_token"]})
    assert rejected == {
        "ok": False,
        "confirmation_required": False,
        "error": "The latest user utterance was not an explicit confirmation.",
    }


def test_affirmative_turn_authorizes_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[tuple[str, str, str]] = []

    def fake_send_mail(to: str, subject: str, body: str) -> dict:
        executed.append((to, subject, body))
        return {"transport": "graph", "status_code": 202}

    monkeypatch.setenv("MAIL_ALLOWED_RECIPIENTS", "user@example.com")
    monkeypatch.setattr(mailer.graph_mail, "send_mail", fake_send_mail)
    monkeypatch.setattr(mailer.graph_mail, "signed_in_user", lambda: "sender@example.com")
    arguments = {"to": "user@example.com", "subject": "Test", "body": "Body"}
    first = dispatch("send_email", arguments)
    confirmation.note_user_turn("确认")
    authorized = dispatch(
        "send_email", {**arguments, "confirmation_token": first["confirmation_token"]}
    )
    assert authorized["status_code"] == 202
    assert executed == [("user@example.com", "Test", "Body")]

    replay = dispatch(
        "send_email", {**arguments, "confirmation_token": first["confirmation_token"]}
    )
    assert replay["ok"] is False
    assert executed == [("user@example.com", "Test", "Body")]


def test_only_protected_schemas_receive_confirmation_token() -> None:
    schemas = {dict(item)["name"]: dict(item)["parameters"] for item in tools.function_tools()}
    assert "confirmation_token" in schemas["send_email"]["properties"]
    assert "confirmation_token" in schemas["identify_object_with_camera"]["properties"]
    assert "confirmation_token" in schemas["set_power_timeout"]["properties"]
    assert "confirmation_token" not in schemas["get_weather"]["properties"]


def test_confirmation_token_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(confirmation.time, "monotonic", lambda: now[0])
    first = dispatch("open_camera", {})
    confirmation.note_user_turn("确认")
    now[0] += 121.0

    expired = dispatch("open_camera", {"confirmation_token": first["confirmation_token"]})

    assert expired["ok"] is False
    assert "expired" in expired["error"].lower()


def test_competing_protected_action_is_rejected() -> None:
    first = dispatch("open_camera", {})

    competing = dispatch("set_power_mode", {"mode": "recommended"})
    repeated = dispatch("open_camera", {})

    assert first["confirmation_required"] is True
    assert competing["ok"] is False
    assert "another protected action" in competing["error"].lower()
    assert repeated["confirmation_token"] == first["confirmation_token"]
