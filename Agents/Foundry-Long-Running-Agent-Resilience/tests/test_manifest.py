from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lra_resilience.manifest import build_manifest, validate_manifest


class ManifestTests(unittest.TestCase):
    def test_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runs = root / "evidence" / "sanitized-runs"
            runs.mkdir(parents=True)
            run = runs / "run.json"
            run.write_text(json.dumps({"status": "passed"}) + "\n", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertEqual(validate_manifest(root, manifest), [])
            run.write_text(json.dumps({"status": "changed"}) + "\n", encoding="utf-8")
            self.assertTrue(any("mismatch" in error for error in validate_manifest(root, manifest)))

    def test_manifest_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = {
                "schema_version": 1,
                "disclosure": "public-sanitized-attestation",
                "artifacts": [{"path": "../outside.json", "bytes": 0, "sha256": "0" * 64}],
            }
            self.assertTrue(any("unsafe artifact path" in error for error in validate_manifest(root, manifest)))

    def test_manifest_rejects_empty_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = {
                "schema_version": 1,
                "disclosure": "public-sanitized-attestation",
                "artifacts": [{"path": "", "bytes": 0, "sha256": "0" * 64}],
            }
            self.assertTrue(any("path is empty" in error for error in validate_manifest(root, manifest)))

    @unittest.skipIf(os.name == "nt", "creating symlinks is not reliably permitted on Windows runners")
    def test_manifest_rejects_symlinked_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runs = root / "evidence" / "sanitized-runs"
            runs.mkdir(parents=True)
            target = root / "target.json"
            target.write_text("{}\n", encoding="utf-8")
            (runs / "linked.json").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "contains a symlink"):
                build_manifest(root)


if __name__ == "__main__":
    unittest.main()
