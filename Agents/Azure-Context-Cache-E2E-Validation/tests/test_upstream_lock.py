from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_upstream", ROOT / "scripts" / "verify_upstream.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UpstreamLockTests(unittest.TestCase):
    def test_checked_in_lock_is_complete_and_pinned(self) -> None:
        lock = json.loads((ROOT / "UPSTREAM_LOCK.json").read_text(encoding="utf-8"))

        self.assertEqual(lock["repository"], "https://github.com/Azure/AzureContextCache.git")
        self.assertEqual(lock["commit"], "7d1029a5e8b59b1805e70992c85ffe6798d2f47a")
        self.assertEqual(lock["hashMode"], "git-blob-content-sha256")
        self.assertEqual(len(lock["files"]), 25)
        self.assertEqual(
            {path for path in lock["files"] if path.startswith("demo/diffs/")},
            {f"demo/diffs/{index:02d}-{name}.diff" for index, name in (
                (1, "sql-injection"),
                (2, "disabled-tls"),
                (3, "n-plus-one"),
                (4, "clean-refactor"),
                (5, "logged-token"),
                (6, "mutable-default"),
                (7, "invoke-expression"),
                (8, "tolist-eager"),
                (9, "result-deadlock"),
                (10, "cpp-raw-new"),
                (11, "pickle-untrusted"),
                (12, "magic-numbers"),
                (13, "anonymous-admin"),
                (14, "cors-star"),
                (15, "ts-any"),
                (16, "thread-sleep-test"),
                (17, "path-traversal"),
                (18, "yaml-load"),
                (19, "clean-python"),
                (20, "md5-password"),
            )},
        )
        for digest in lock["files"].values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def create_repository(self, root: Path, content: bytes) -> str:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "core.autocrlf", "false"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        path = root / "demo" / "sample.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_git_blob_verification_accepts_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"pinned bytes\n"
            revision = self.create_repository(root, content)
            expected = hashlib.sha256(content).hexdigest()

            MODULE.verify_git_files(root, revision, {"demo/sample.txt": expected})

    def test_git_blob_verification_rejects_changed_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = self.create_repository(root, b"changed")

            with self.assertRaisesRegex(MODULE.ContractError, "hash mismatch"):
                MODULE.verify_git_files(root, revision, {"demo/sample.txt": "0" * 64})

    def test_verified_blob_bytes_are_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "upstream"
            output = Path(directory) / "output"
            content = b"pinned bytes\n"
            revision = self.create_repository(root, content)

            MODULE.verify_git_files(
                root,
                revision,
                {"demo/sample.txt": hashlib.sha256(content).hexdigest()},
                output,
            )

            self.assertEqual((output / "demo/sample.txt").read_bytes(), content)

    def test_dirty_worktree_materializes_only_pinned_blob_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "upstream"
            output = Path(directory) / "output"
            content = b"pinned bytes\n"
            revision = self.create_repository(root, content)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "remote",
                    "add",
                    "origin",
                    "https://example.invalid/upstream.git",
                ],
                check=True,
            )
            (root / "demo/sample.txt").write_bytes(b"untrusted worktree bytes\n")
            lock = {
                "repository": "https://example.invalid/upstream.git",
                "commit": revision,
                "hashMode": "git-blob-content-sha256",
                "files": {"demo/sample.txt": hashlib.sha256(content).hexdigest()},
            }

            MODULE.verify_checkout(root, lock, output)

            self.assertEqual((output / "demo/sample.txt").read_bytes(), content)


if __name__ == "__main__":
    unittest.main()