import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_FIELD = re.compile(r"price|pricing|cost|usd", re.IGNORECASE)
PRIVATE_EXECUTION_MARKERS = (
    r"C:\\Users\\",
    ".azure-",
    'WORKSPACE / "password"',
    "gpt-deployment-discovery.json",
)


class PublicArtifactTests(unittest.TestCase):
    def assert_no_financial_fields(self, value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertIsNone(FINANCIAL_FIELD.search(key), f"{path}: {key}")
                self.assert_no_financial_fields(item, path)
        elif isinstance(value, list):
            for item in value:
                self.assert_no_financial_fields(item, path)

    def test_public_data_omits_financial_fields(self):
        for path in (ROOT / "data").rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assert_no_financial_fields(json.loads(path.read_text("utf-8")), path)

    def test_runner_and_archives_have_no_financial_constants(self):
        paths = [ROOT / "scripts" / "benchmark_5way_v2.py",
                 *(ROOT / "data").glob("*/source/benchmark_5way_v2.py")]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text("utf-8")
                ast.parse(source)
                self.assertIsNone(FINANCIAL_FIELD.search(source))

    def test_archived_source_has_no_author_machine_or_credential_dependencies(self):
        for path in (ROOT / "data").rglob("*.py"):
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text("utf-8")
                for marker in PRIVATE_EXECUTION_MARKERS:
                    self.assertNotIn(marker, source, f"{path}: private execution marker {marker}")


if __name__ == "__main__":
    unittest.main()