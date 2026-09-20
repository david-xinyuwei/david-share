"""The text judge's scoring rule and the invoice derivation, checked against the archives.

Both scripts publish a `--check` that recomputes archived numbers from archived raw inputs with no
model or network access. These tests pin the rule itself, so a change to it fails here before it
silently changes every published percentage.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import calibrate_text_judge  # noqa: E402
import effective_prices  # noqa: E402
import score_text_rendering  # noqa: E402


class ScoringRuleTests(unittest.TestCase):
    def test_wrapped_text_is_not_a_spelling_error(self):
        """The 2026-09-20 correction: a phrase the model wrapped onto two lines was still rendered."""
        result = score_text_rendering.score(["JASMINE GREEN TEA"], "JASMINE\nGREEN TEA")
        self.assertEqual((result["matched"], result["chars"]), (15, 15))
        self.assertEqual(result["exact_segments"], 1)

    def test_whitespace_is_excluded_from_the_denominator(self):
        result = score_text_rendering.score(["GOLDEN CRUST"], "GOLDEN CRUST")
        self.assertEqual(result["chars"], 11)

    def test_exact_requires_the_whole_target_and_partial_credit_is_by_character(self):
        result = score_text_rendering.score(["东门大街18号三楼"], "店铺 东门大街18号二楼")
        self.assertEqual(result["exact_segments"], 0)
        self.assertEqual(result["chars"], 9)
        self.assertEqual(result["matched"], 8)

    def test_multi_line_targets_are_scored_per_segment(self):
        result = score_text_rendering.score(["ZHANG WEI", "SENIOR ARCHITECT"], "ZHANG WEI\nSENIOR ARCHITECT")
        self.assertEqual((result["segments"], result["exact_segments"]), (2, 2))
        self.assertEqual(result["chars"], 8 + 15)

    def test_no_text_scores_zero_without_crashing(self):
        result = score_text_rendering.score(["宁静致远"], "NONE")
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["exact_segments"], 0)

    def test_archived_scores_reproduce_from_their_transcriptions(self):
        for scoring in sorted((ROOT / "data").glob("text-*/text-scoring.json")):
            with self.subTest(archive=scoring.parent.name):
                self.assertEqual(score_text_rendering.check(scoring), 0)

    def test_archived_calibrations_reproduce_and_share_the_study_rule(self):
        calibrations = sorted((ROOT / "data").glob("text-*/judge-calibration/calibration.json"))
        self.assertTrue(calibrations, "no judge calibration is archived")
        for path in calibrations:
            with self.subTest(archive=path.parents[1].name):
                self.assertEqual(calibrate_text_judge.check(path), 0)
                data = json.loads(path.read_text("utf-8"))
                self.assertEqual(data["scoring_rule"], score_text_rendering.SCORING_RULE)
                self.assertEqual(data["instruction"], score_text_rendering.READ_INSTRUCTION)
                for record in data["records"]:
                    self.assertTrue((path.parent / record["image"]).is_file(), record["image"])

    def test_every_text_study_has_a_calibration_for_its_own_targets(self):
        """The README attributes gaps to the image models only because the judge read these exact
        targets at a known floor; a study without its own calibration cannot make that claim."""
        for scoring in sorted((ROOT / "data").glob("text-*/text-scoring.json")):
            with self.subTest(archive=scoring.parent.name):
                calibration = scoring.parent / "judge-calibration" / "calibration.json"
                self.assertTrue(calibration.is_file(), "study has no judge calibration")
                prompts = {row[3] for row in calibrate_text_judge.read_prompts(
                    next(scoring.parent.glob("prompts-*.csv")))}
                calibrated = {r["target"] for r in json.loads(calibration.read_text("utf-8"))["records"]}
                self.assertEqual(prompts, calibrated, "calibration targets differ from the study's targets")


class InvoiceDerivationTests(unittest.TestCase):
    MAI_METER = next(m for m, model in effective_prices.IMAGE_METERS.items() if model == "MAI-Image-2.6")

    @staticmethod
    def response(cost, quantity, meter):
        return {"properties": {"columns": [{"name": "PreTaxCost"}, {"name": "UsageQuantity"}, {"name": "Meter"}],
                               "rows": [[cost, quantity, meter]]}}

    def test_archived_prices_reproduce_from_the_cost_management_response(self):
        for archive in sorted(p for p in (ROOT / "data").iterdir() if p.name.startswith("billing-")):
            with self.subTest(archive=archive.name):
                self.assertEqual(effective_prices.check(archive), 0)

    def test_derivation_divides_cost_by_billed_tokens_and_rounds_to_cents(self):
        """Archived prices once read 30.000000000000004; the published number must be the billed rate."""
        prices, _ = effective_prices.derive(self.response(3.0000000000000004, 0.1, self.MAI_METER))
        self.assertEqual(prices["MAI-Image-2.6"], 30.0)

    def test_per_image_cost_uses_measured_tokens_not_list_prices(self):
        _, per_thousand = effective_prices.derive(self.response(38.0, 1.0, self.MAI_METER))
        expected = round(effective_prices.TOKENS_PER_IMAGE["MAI-Image-2.6"] * 38.0 / 1_000_000 * 1000, 2)
        self.assertEqual(per_thousand["MAI-Image-2.6"], expected)
        self.assertNotIn("gpt-image-2 low", per_thousand, "no GPT meter was billed, so no GPT price may appear")

    def test_unbilled_meters_and_unknown_meters_are_ignored(self):
        prices, per_thousand = effective_prices.derive(
            {"properties": {"columns": [{"name": "PreTaxCost"}, {"name": "UsageQuantity"}, {"name": "Meter"}],
                            "rows": [[0.0, 0.0, self.MAI_METER], [5.0, 1.0, "Some Text Model Input Tokens"]]}})
        self.assertEqual((prices, per_thousand), ({}, {}))


if __name__ == "__main__":
    unittest.main()
