"""Verify that an upstream checkout matches the tested immutable contract."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


class ContractError(RuntimeError):
    """The upstream checkout differs from the pinned contract."""


def normalize_remote(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.casefold().endswith(".git") else normalized


def git(upstream: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(upstream), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise ContractError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def git_blob_sha256(upstream: Path, revision: str, relative: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(upstream), "cat-file", "blob", f"{revision}:{relative}"],
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        message = completed.stderr.decode(errors="replace").strip()
        raise ContractError(message or f"unable to read upstream blob: {relative}")

    import hashlib

    return hashlib.sha256(completed.stdout).hexdigest()


def verify_git_files(
    upstream: Path, revision: str, expected: dict[str, str]
) -> None:
    for relative, expected_hash in expected.items():
        actual_hash = git_blob_sha256(upstream, revision, relative)
        if actual_hash != expected_hash.casefold():
            raise ContractError(
                f"upstream hash mismatch: {relative} expected={expected_hash} actual={actual_hash}"
            )


def verify_checkout(upstream: Path, lock: dict[str, object]) -> None:
    expected_commit = str(lock["commit"])
    expected_remote = str(lock["repository"])
    if git(upstream, "rev-parse", "HEAD") != expected_commit:
        raise ContractError("upstream HEAD does not match the pinned commit")
    if normalize_remote(git(upstream, "remote", "get-url", "origin")) != normalize_remote(
        expected_remote
    ):
        raise ContractError("upstream origin does not match the pinned repository")
    if git(upstream, "status", "--porcelain"):
        raise ContractError("upstream checkout is not clean")
    if lock.get("hashMode") != "git-blob-content-sha256":
        raise ContractError("unsupported upstream hash mode")
    verify_git_files(upstream, expected_commit, dict(lock["files"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "UPSTREAM_LOCK.json",
    )
    args = parser.parse_args()

    try:
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        verify_checkout(args.upstream_dir.resolve(), lock)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ContractError) as error:
        parser.error(str(error))

    print(f"UPSTREAM_LOCK_PASS commit={lock['commit']} files={len(lock['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())