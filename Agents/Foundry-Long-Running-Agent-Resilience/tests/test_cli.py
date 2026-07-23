from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lra_resilience.cli import _read_json, main


class CliTests(unittest.TestCase):
    def test_read_json_reports_missing_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "file not found"):
            _read_json(Path("missing-matrix.json"))

    def test_read_json_reports_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "broken.json"
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"invalid JSON in .*broken\.json:1"):
                _read_json(path)

    def test_read_json_requires_object(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "array.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected a JSON object"):
                _read_json(path)

    def test_main_returns_one_without_traceback_for_missing_matrix(self) -> None:
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["lra-evidence", "validate", "--matrix", "missing.json"]):
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(), 1)
        self.assertIn("ERROR: file not found", output.getvalue())


if __name__ == "__main__":
    unittest.main()