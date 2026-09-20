import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_FIELD = re.compile(r"price|pricing|cost|usd", re.IGNORECASE)
# Measurement archives must not carry prices: a run records tokens, not money, so a later price
# change never invalidates a measurement. The one place money is allowed is the billing archive,
# which is the account's own invoice read from Azure Cost Management, and it must say so.
BILLING_ARCHIVE = "billing-"
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

    def test_measurement_archives_omit_financial_fields(self):
        for path in (ROOT / "data").rglob("*.json"):
            if path.relative_to(ROOT / "data").parts[0].startswith(BILLING_ARCHIVE):
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assert_no_financial_fields(json.loads(path.read_text("utf-8")), path)

    def test_billing_archive_is_an_invoice_reading_not_an_estimate(self):
        """Money may appear only where it was read from the account's own bill."""
        archives = [p for p in (ROOT / "data").iterdir() if p.name.startswith(BILLING_ARCHIVE)]
        for archive in archives:
            with self.subTest(archive=archive.name):
                provenance = json.loads((archive / "provenance.json").read_text("utf-8"))
                self.assertIn("Cost Management", provenance["source"])
                self.assertIn("ActualCost", provenance["source"])
                prices = json.loads((archive / "effective-prices.json").read_text("utf-8"))
                self.assertIn("ActualCost", prices["source"])
                # Every price must be derived from a billed quantity present in the raw response.
                raw = json.loads((archive / "cost-query-response.json").read_text("utf-8"))
                columns = [c["name"] for c in raw["properties"]["columns"]]
                billed_meters = {str(dict(zip(columns, r)).get("Meter", "")) for r in raw["properties"]["rows"]}
                self.assertTrue(any("Image 2.6" in m for m in billed_meters), "MAI meter missing from invoice")
                self.assertTrue(any("Image 2 " in m for m in billed_meters), "gpt-image-2 meter missing from invoice")
                for model in prices["usd_per_million_output_image_tokens"]:
                    self.assertTrue(model.startswith(("MAI", "gpt-image")), model)

    def test_runner_and_archives_have_no_financial_constants(self):
        paths = [ROOT / "scripts" / "benchmark_5way_v2.py",
                 *(ROOT / "data").glob("*/source/benchmark_5way_v2.py")]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text("utf-8")
                ast.parse(source)
                self.assertIsNone(FINANCIAL_FIELD.search(source))

    def test_text_scoring_archives_carry_the_corrected_rule(self):
        """An archive must hold the current scoring, with any superseded pass named beside it.

        On 2026-09-20 the archive still held the line-anchored scores (English 75%) after the rule
        had been corrected in the working directory (English 100%); the rendered README reproduced
        the stale numbers. The report reads only from data/, so data/ must carry the correction.
        """
        for scoring in (ROOT / "data").glob("text-*/text-scoring.json"):
            with self.subTest(archive=scoring.parent.name):
                data = json.loads(scoring.read_text("utf-8"))
                self.assertIn("scoring_rule", data, "archived scoring has no stated rule")
                self.assertIn("Whitespace-insensitive", data["scoring_rule"])
                superseded = data.get("superseded")
                if superseded:
                    self.assertTrue((scoring.parent / superseded["file"]).is_file(),
                                    f"superseded scoring {superseded['file']} is named but not archived")
                    previous = json.loads((scoring.parent / superseded["file"]).read_text("utf-8"))
                    self.assertNotIn("scoring_rule", previous, "the superseded file must be the original pass")

    def test_archived_source_has_no_author_machine_or_credential_dependencies(self):
        for path in (ROOT / "data").rglob("*.py"):
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text("utf-8")
                for marker in PRIVATE_EXECUTION_MARKERS:
                    self.assertNotIn(marker, source, f"{path}: private execution marker {marker}")


if __name__ == "__main__":
    unittest.main()