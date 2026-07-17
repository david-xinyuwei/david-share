"""Validate committed sample runs against source events and artifact hashes."""

from __future__ import annotations

import json
from pathlib import Path

from meeting_agent.draft import file_sha256, validate_eml
from meeting_agent.models import MeetingAnalysis
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]
RUN_NAMES = ("product-planning", "operations-review")


def main() -> int:
    analysis_hashes: set[str] = set()
    for run_name in RUN_NAMES:
        run_dir = ROOT / "evidence" / "sample-runs" / run_name
        evidence = json.loads((run_dir / "evidence.json").read_text(encoding="utf-8"))
        session = load_jsonl(ROOT / "examples" / f"{run_name}.jsonl")

        assert evidence["schema_version"] == 1
        assert evidence["analyzer"] == "test-fixture"
        assert evidence["source"]["session_id"] == session.session_id
        assert evidence["source"]["event_count"] == len(session.events)
        assert evidence["source"]["content_sha256"] == session.content_sha256()
        assert evidence["automatic_send"] is False
        assert evidence["next_state"] == "DRAFT_READY_MANUAL_SEND_REQUIRED"

        for artifact in evidence["artifacts"].values():
            path = run_dir / artifact["path"]
            assert path.is_file()
            assert artifact["bytes"] == path.stat().st_size
            assert artifact["sha256"] == file_sha256(path)

        analysis_path = run_dir / evidence["artifacts"]["analysis"]["path"]
        analysis = MeetingAnalysis.model_validate_json(
            analysis_path.read_text(encoding="utf-8")
        )
        eml = validate_eml(run_dir / evidence["artifacts"]["eml"]["path"])
        assert eml["x_unsent"] == "1"
        assert eml["recipient_count"] == 0
        assert eml["attachment_count"] == 2
        assert eml["subject"] == analysis.title
        for key in (
            "x_unsent",
            "recipient_count",
            "attachment_count",
            "attachment_names",
            "subject",
        ):
            assert evidence["eml"][key] == eml[key]
        assert evidence["eml"]["sha256"] == evidence["artifacts"]["eml"]["sha256"]
        analysis_hashes.add(evidence["artifacts"]["analysis"]["sha256"])

    assert len(analysis_hashes) == len(RUN_NAMES)
    print(f"PASS: {len(RUN_NAMES)} committed sample runs are traceable and distinct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())