from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evidence_hash import verify_sha256


class EvidenceHashTests(unittest.TestCase):
    def test_raw_bytes_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evidence.txt"
            path.write_bytes(b"alpha\nbeta\n")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(verify_sha256(path, expected), "raw")

    def test_utf8_crlf_matches_canonical_lf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evidence.txt"
            canonical = b"alpha\nbeta\n"
            path.write_bytes(canonical.replace(b"\n", b"\r\n"))
            expected = hashlib.sha256(canonical).hexdigest()
            self.assertEqual(verify_sha256(path, expected), "canonical_lf")

    def test_binary_file_cannot_use_newline_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evidence.bin"
            path.write_bytes(b"alpha\r\nbeta\r\n")
            expected = hashlib.sha256(b"alpha\nbeta\n").hexdigest()
            with self.assertRaises(ValueError):
                verify_sha256(path, expected)

    def test_lone_carriage_return_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evidence.txt"
            path.write_bytes(b"alpha\rbeta\r\n")
            expected = hashlib.sha256(b"alpha\nbeta\n").hexdigest()
            with self.assertRaises(ValueError):
                verify_sha256(path, expected)

    def test_content_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "evidence.txt"
            path.write_bytes(b"alpha\nchanged\n")
            expected = hashlib.sha256(b"alpha\nbeta\n").hexdigest()
            with self.assertRaises(ValueError):
                verify_sha256(path, expected)


if __name__ == "__main__":
    unittest.main()