"""Verify that an upstream checkout matches the tested immutable contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


class ContractError(RuntimeError):
    """The upstream checkout differs from the pinned contract."""


def normalize_remote(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.casefold().endswith(".git") else normalized


def git(upstream: Path, *arguments: str, executable: str = "git") -> str:
    completed = subprocess.run(
        [
            executable,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-c",
            "core.hooksPath=NUL",
            "-C",
            str(upstream),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise ContractError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def git_blob(
    upstream: Path,
    revision: str,
    relative: str,
    executable: str = "git",
) -> bytes:
    completed = subprocess.run(
        [
            executable,
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(upstream),
            "cat-file",
            "blob",
            f"{revision}:{relative}",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        message = completed.stderr.decode(errors="replace").strip()
        raise ContractError(message or f"unable to read upstream blob: {relative}")

    return completed.stdout


def verify_git_files(
    upstream: Path,
    revision: str,
    expected: dict[str, str],
    output: Path | None = None,
    git_executable: str = "git",
) -> None:
    for relative, expected_hash in expected.items():
        content = git_blob(upstream, revision, relative, git_executable)
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != expected_hash.casefold():
            raise ContractError(
                f"upstream hash mismatch: {relative} expected={expected_hash} actual={actual_hash}"
            )
        if output is not None:
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)


def verify_checkout(
    upstream: Path,
    lock: dict[str, object],
    output: Path | None = None,
    git_executable: str = "git",
) -> None:
    expected_commit = str(lock["commit"])
    expected_remote = str(lock["repository"])
    if git(upstream, "rev-parse", "HEAD", executable=git_executable) != expected_commit:
        raise ContractError("upstream HEAD does not match the pinned commit")
    if normalize_remote(
        git(upstream, "remote", "get-url", "origin", executable=git_executable)
    ) != normalize_remote(expected_remote):
        raise ContractError("upstream origin does not match the pinned repository")
    if lock.get("hashMode") != "git-blob-content-sha256":
        raise ContractError("unsupported upstream hash mode")
    verify_git_files(
        upstream,
        expected_commit,
        dict(lock["files"]),
        output,
        git_executable,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "UPSTREAM_LOCK.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--git-executable", default="git")
    args = parser.parse_args()

    try:
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        output = args.output.resolve() if args.output else None
        if output is not None:
            if output.exists() and any(output.iterdir()):
                raise ContractError("output directory must be empty")
            output.mkdir(parents=True, exist_ok=True)
        verify_checkout(
            args.upstream_dir.resolve(),
            lock,
            output,
            args.git_executable,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ContractError) as error:
        parser.error(str(error))

    suffix = f" output={output}" if output is not None else ""
    print(
        f"UPSTREAM_LOCK_PASS commit={lock['commit']} "
        f"files={len(lock['files'])}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())