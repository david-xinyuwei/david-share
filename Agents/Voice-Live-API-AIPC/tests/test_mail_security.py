from __future__ import annotations

import pytest

from src.tools import mailer


@pytest.fixture
def graph_transport(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    sent: list[tuple[str, str, str]] = []

    def fake_send_mail(to: str, subject: str, body: str) -> dict:
        sent.append((to, subject, body))
        return {"transport": "graph", "status_code": 202}

    monkeypatch.setenv("MAIL_ALLOWED_RECIPIENTS", "user@example.com")
    monkeypatch.setenv("MAIL_DEFAULT_RECIPIENT", "user@example.com")
    monkeypatch.setenv("MAIL_TRANSPORT", "graph")
    monkeypatch.setattr(mailer.graph_mail, "send_mail", fake_send_mail)
    monkeypatch.setattr(mailer.graph_mail, "signed_in_user", lambda: "sender@example.com")
    return sent


def test_mail_limits_allow_boundary_values(graph_transport) -> None:
    result = mailer.send_email(subject="S" * 200, body="B" * 100_000)

    assert result["status_code"] == 202
    assert len(graph_transport) == 1


@pytest.mark.parametrize(
    ("subject", "body", "message"),
    [
        ("S" * 201, "body", "邮件主题超过 200"),
        ("subject", "B" * 100_001, "邮件正文超过 100000"),
        ("subject", "中" * 90_000, "UTF-8 大小超过 256 KiB"),
    ],
    ids=["subject-too-long", "characters-too-long", "bytes-too-large"],
)
def test_mail_limits_reject_before_transport(
    graph_transport,
    subject: str,
    body: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        mailer.send_email(subject=subject, body=body)

    assert graph_transport == []
