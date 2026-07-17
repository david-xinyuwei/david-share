import json
import subprocess
import sys
from pathlib import Path

import pytest
from filelock import FileLock

import meeting_agent.cli as cli
from tests.support import DeterministicTestAnalyzer

ROOT = Path(__file__).resolve().parents[1]


CLI_TIMEOUT_SECONDS = 60


def run_build(
    monkeypatch: pytest.MonkeyPatch,
    events: str,
    output_dir: Path,
    recipients: tuple[str, ...] = (),
) -> dict[str, object]:
    monkeypatch.setattr(cli, "AzureOpenAIAnalyzer", DeterministicTestAnalyzer)
    arguments = [
        "build",
        "--events",
        str(ROOT / "examples" / events),
        "--output-dir",
        str(output_dir),
    ]
    for recipient in recipients:
        arguments.extend(("--recipient", recipient))
    args = cli.parser().parse_args(arguments)
    assert cli._execute(args) == 0
    return json.loads((output_dir / "evidence.json").read_text(encoding="utf-8"))


def test_cli_builds_traceable_outputs_for_two_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    product = run_build(monkeypatch, "product-planning.jsonl", tmp_path / "product")
    operations = run_build(monkeypatch, "operations-review.jsonl", tmp_path / "operations")

    assert product["source"]["content_sha256"] != operations["source"]["content_sha256"]
    product_analysis_hash = product["artifacts"]["analysis"]["sha256"]
    operations_analysis_hash = operations["artifacts"]["analysis"]["sha256"]
    assert product_analysis_hash != operations_analysis_hash
    assert product["source"]["session_id"] == "product-planning"
    assert operations["source"]["session_id"] == "operations-review"
    assert product["eml"]["recipient_count"] == 0
    assert operations["eml"]["recipient_count"] == 0
    assert product["analyzer"] == "azure"
    assert product["automatic_send"] is False
    assert product["next_state"] == "DRAFT_READY_MANUAL_SEND_REQUIRED"


def test_cli_passes_multiple_recipients_to_draft(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    evidence = run_build(
        monkeypatch,
        "product-planning.jsonl",
        tmp_path / "addressed",
        recipients=("reviewer-one@example", "reviewer-two@example"),
    )

    assert evidence["eml"]["recipient_count"] == 2


def test_cli_reports_missing_input_without_traceback(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "meeting_agent.cli",
            "validate-events",
            "--events",
            str(tmp_path / "missing.jsonl"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_SECONDS,
    )

    assert completed.returncode == 1
    assert completed.stderr.startswith("error:")
    assert "Traceback" not in completed.stderr


def test_cli_rejects_concurrent_build_to_same_output_directory(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "shared"
    output_dir.mkdir()
    lock = FileLock(str(output_dir / ".meeting-agent.lock"))
    monkeypatch.setattr(cli, "AzureOpenAIAnalyzer", DeterministicTestAnalyzer)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "meeting-agent",
            "build",
            "--events",
            str(ROOT / "examples" / "product-planning.jsonl"),
            "--output-dir",
            str(output_dir),
        ],
    )
    with lock:
        assert cli.main() == 1

    captured = capsys.readouterr()
    assert "output directory is already in use" in captured.err
    assert "Traceback" not in captured.err


def test_cli_does_not_expose_analyzer_selection() -> None:
    assert "--analyzer" not in cli.parser().format_help()