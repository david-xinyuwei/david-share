from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

import meeting_agent.draft as draft
from meeting_agent.analyzers import OfflineContractAnalyzer
from meeting_agent.artifacts import generate_artifacts
from meeting_agent.draft import build_eml, validate_eml
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_builds_unsent_eml_with_two_attachments_and_no_recipients(tmp_path: Path) -> None:
    analysis = OfflineContractAnalyzer().analyze(
        load_jsonl(ROOT / "examples" / "operations-review.jsonl")
    )
    artifacts = generate_artifacts(analysis, tmp_path)
    eml = tmp_path / "meeting-follow-up.eml"
    evidence = build_eml(
        analysis,
        [artifacts["mind_map_png"], artifacts["presentation"]],
        eml,
    )

    assert evidence["x_unsent"] == "1"
    assert evidence["recipient_count"] == 0
    assert evidence["attachment_count"] == 2
    assert evidence["subject"] == analysis.title

    message = BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
    assert message.get("To") is None
    assert message.get("Cc") is None
    assert message.get("Bcc") is None
    assert validate_eml(eml)["attachment_names"] == ["mind-map.png", "meeting-summary.pptx"]


def test_counts_multiple_valid_recipients(tmp_path: Path) -> None:
    analysis = OfflineContractAnalyzer().analyze(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl")
    )
    artifacts = generate_artifacts(analysis, tmp_path)
    evidence = build_eml(
        analysis,
        [artifacts["mind_map_png"], artifacts["presentation"]],
        tmp_path / "addressed.eml",
        recipients=["alice@example", "bob@example"],
    )

    assert evidence["recipient_count"] == 2


def test_rejects_recipient_header_injection(tmp_path: Path) -> None:
    analysis = OfflineContractAnalyzer().analyze(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl")
    )
    attachment = tmp_path / "attachment.png"
    attachment.write_bytes(b"test")

    with pytest.raises(ValueError, match="cannot contain newlines"):
        build_eml(
            analysis,
            [attachment],
            tmp_path / "unsafe.eml",
            recipients=["alice@example\r\nBcc: hidden@example"],
        )


def test_reports_missing_new_outlook_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eml = tmp_path / "draft.eml"
    eml.write_text("X-Unsent: 1\n", encoding="utf-8")
    monkeypatch.setattr(draft.platform, "system", lambda: "Windows")

    def missing_executable(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("olk.exe")

    monkeypatch.setattr(draft.subprocess, "Popen", missing_executable)
    with pytest.raises(RuntimeError, match="olk.exe was not found"):
        draft.open_in_new_outlook(eml)