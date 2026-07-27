"""Command-line entrypoint for traceable meeting-to-draft runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from filelock import FileLock, Timeout

from .analyzers import ManagedAgentAnalyzer
from .artifacts import generate_artifacts
from .draft import build_eml, file_sha256, open_in_new_outlook, write_evidence
from .models import MeetingAnalysis
from .presentation import ensure_deck_plan
from .session import MeetingSession, load_jsonl


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="meeting-agent")
    subcommands = root.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-events", help="Validate one JSONL event stream")
    validate.add_argument("--events", type=Path, required=True)

    build = subcommands.add_parser("build", help="Generate meeting artifacts and an unsent EML")
    build.add_argument("--events", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--recipient", action="append", default=[])
    build.add_argument("--open-outlook", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return _execute(args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _execute(args: argparse.Namespace) -> int:
    session = load_jsonl(args.events)
    if args.command == "validate-events":
        print(
            json.dumps(
                {
                    "session_id": session.session_id,
                    "event_count": len(session.events),
                    "content_sha256": session.content_sha256(),
                }
            )
        )
        return 0

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(output_dir / ".meeting-agent.lock"), timeout=0):
            analyzer = ManagedAgentAnalyzer()
            analysis = ensure_deck_plan(analyzer.analyze(session))
            return _build(args, session, analysis, output_dir)
    except Timeout as error:
        raise RuntimeError(f"output directory is already in use: {output_dir}") from error


def _build(
    args: argparse.Namespace,
    session: MeetingSession,
    analysis: MeetingAnalysis,
    output_dir: Path,
) -> int:
    artifacts = generate_artifacts(analysis, output_dir)
    eml_path = output_dir / "meeting-follow-up.eml"
    eml_evidence = build_eml(
        analysis,
        [artifacts["mind_map_png"], artifacts["presentation"]],
        eml_path,
        args.recipient,
    )
    evidence = {
        "schema_version": 1,
        "analyzer": "managed",
        "source": {
            "session_id": session.session_id,
            "event_count": len(session.events),
            "content_sha256": session.content_sha256(),
        },
        "artifacts": {
            name: {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for name, path in {**artifacts, "eml": eml_path}.items()
        },
        "eml": eml_evidence,
        "automatic_send": False,
        "next_state": "DRAFT_READY_MANUAL_SEND_REQUIRED",
    }
    write_evidence(output_dir / "evidence.json", evidence)
    if args.open_outlook:
        open_in_new_outlook(eml_path)
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())