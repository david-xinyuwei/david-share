"""Command-line interface for public-safe resilience evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import canonical_sha256, validate_matrix
from .events import summarize_event_file
from .manifest import build_manifest, load_manifest, validate_manifest


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as error:
        raise ValueError(f"file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}:{error.lineno}: {error.msg}") from error
    except OSError as error:
        raise OSError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        raise OSError(f"cannot write {path}: {error}") from error


def _validate(matrix_path: Path) -> int:
    matrix = _read_json(matrix_path)
    errors = validate_matrix(matrix)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: validated {len(matrix['scenarios'])} sanitized scenarios")
    print(f"matrix_sha256={canonical_sha256(matrix)}")
    return 0


def _manifest(root: Path, manifest_path: Path, write: bool) -> int:
    if write:
        _write_json(manifest_path, build_manifest(root))
        print(f"WROTE: {manifest_path}")
        return 0
    errors = validate_manifest(root, load_manifest(manifest_path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: verified {len(load_manifest(manifest_path)['artifacts'])} evidence artifacts")
    return 0


def main() -> int:
    root = Path.cwd()
    parser = argparse.ArgumentParser(description="Validate public-safe long-running agent evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate the sanitized evidence matrix.")
    validate_parser.add_argument(
        "--matrix",
        type=Path,
        default=root / "data" / "validation-matrix.json",
    )

    summarize_parser = subparsers.add_parser("summarize", help="Summarize JSONL events without identity fields.")
    summarize_parser.add_argument("events", type=Path)
    summarize_parser.add_argument("--output", type=Path)

    manifest_parser = subparsers.add_parser("manifest", help="Build or verify the evidence manifest.")
    manifest_parser.add_argument("--root", type=Path, default=root)
    manifest_parser.add_argument("--manifest", type=Path, default=root / "evidence" / "manifest.json")
    manifest_parser.add_argument("--write", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "validate":
            return _validate(args.matrix)
        if args.command == "summarize":
            summary = summarize_event_file(args.events)
            if args.output:
                _write_json(args.output, summary)
            else:
                print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
        if args.command == "manifest":
            return _manifest(args.root, args.manifest, args.write)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
