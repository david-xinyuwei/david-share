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
        self.assertEqual(len(lock["files"]), 11)
        for digest in lock["files"].values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def create_repository(self, root: Path, content: bytes) -> str:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
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


if __name__ == "__main__":
    unittest.main()