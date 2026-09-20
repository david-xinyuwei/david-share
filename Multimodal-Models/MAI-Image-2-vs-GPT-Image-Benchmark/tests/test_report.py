import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_paired_report as report


class ComparisonReportTests(unittest.TestCase):
    def prompt(self):
        return {"prompt_index": 1, "configurations": [
            {"group": group, "rounds": [
                {"round": round_number, "ok": True, "request_seconds": 1.25,
                 "image": f"{group}/r{round_number}/01_test.png", "image_kib": 512,
                 "attempts": 1, "logical_request_seconds": 1.5}
                for round_number in (1, 2)]} for group in report.GROUPS]}

    def test_all_four_configurations_appear_in_each_round(self):
        for round_number in (1, 2):
            rendered = report.comparison_table(self.prompt(), round_number, "data/offline-fixture", "en")
            for group in report.GROUPS:
                self.assertIn(f"data/offline-fixture/{group}/r{round_number}/01_test.png", rendered)
            self.assertEqual(rendered.count("!["), 4)

    def test_failed_high_sample_is_not_replaced_by_old_image(self):
        prompt = self.prompt()
        prompt["configurations"][3]["rounds"][0].update({"ok": False, "image": None, "attempts": 3})
        rendered = report.comparison_table(prompt, 1, "data/offline-fixture", "en")
        self.assertIn("No image returned", rendered)
        self.assertIn("3 attempts", rendered)
        self.assertEqual(rendered.count("!["), 3)
        self.assertNotIn("gpt-image-2-high/r1", rendered)

    def test_a_missing_configuration_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"].pop()
        with self.assertRaisesRegex(ValueError, "four configurations"):
            report.comparison_table(prompt, 1, "data/offline-fixture", "en")

    def test_image_from_another_quality_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"][1]["rounds"][0]["image"] = "gpt-image-2-high/r1/01_test.png"
        with self.assertRaisesRegex(ValueError, "configuration"):
            report.comparison_table(prompt, 1, "data/offline-fixture", "en")

    def test_latency_table_shows_both_rounds_and_failed_cell(self):
        prompt = self.prompt()
        prompt["configurations"][3]["rounds"][0]["ok"] = False
        rendered = report.prompt_latency_table({"per_prompt": [prompt]}, "zh")
        self.assertIn("01 / R1", rendered)
        self.assertIn("01 / R2", rendered)
        self.assertIn("失败", rendered)

    def test_image_from_another_round_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"][1]["rounds"][0]["image"] = "gpt-image-2-low/r2/01_test.png"
        with self.assertRaisesRegex(ValueError, "configuration"):
            report.comparison_table(prompt, 1, "data/offline-fixture", "en")

    def test_reproduction_covers_all_quality_settings_and_offline_check(self):
        for language in ("en", "zh"):
            section = report.reproduction_section("data/offline-fixture", language)
            self.assertIn("--mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all", section)
            self.assertIn("--warmup-only", section)
            self.assertIn("--resume", section)
            self.assertIn("summarize_paired_run.py data/offline-fixture", section)
            self.assertIn("AZURE_OPENAI_API_KEY", section)

    def test_quality_review_cannot_use_a_previous_run(self):
        with self.assertRaisesRegex(ValueError, "current measured results"):
            report.validate_quality({"result_sha256": "new-run"}, {"result_sha256": "old-run"})

    def test_token_table_needs_no_financial_fields(self):
        summary = {"groups": [{"returned_output_tokens": [tokens], "successful_samples": successes,
                               "planned_samples": 22} for tokens, successes in
                              ((1024, 22), (196, 22), (1756, 22), (7024, 21))]}
        for language in ("en", "zh"):
            rendered = report.usage_table(summary, language)
            self.assertIn("7024", rendered)
            self.assertIn("21/22", rendered)
            self.assertNotRegex(rendered.lower(), r"usd|price|cost|价格|费用|美元")

    def test_connection_wait_is_disclosed_separately_from_inference(self):
        summary = {"unsuccessful_attempts": [{"sample_id": "offline-sample", "attempt": 1,
                    "exception_type": "ConnectionError", "http_status": None, "request_seconds": 90.25,
                    "started_at_utc": "2026-01-01T00:00:00+00:00", "finished_at_utc": "2026-01-01T00:01:31+00:00"}]}
        rendered = report.exception_section(summary, "en")
        self.assertIn("ConnectionError", rendered)
        self.assertIn("90.25", rendered)
        self.assertIn("not server-side GPU inference duration", rendered)
        self.assertIn("planned denominator", rendered)

    def test_document_removes_other_models_and_preserves_all_scenarios(self):
        original = "# Old report\n\n> **Author**: Existing Author\n\nMAI-Image-2e GPT-Image-1.5 MAI-Image-2\n"
        prompts = []
        for prompt_index in range(1, 12):
            original += f"\n### Test {prompt_index}: Original scenario {prompt_index}\nold measurements\n"
            prompt = self.prompt()
            prompt.update({"prompt_index": prompt_index, "prompt": f"Original prompt {prompt_index}"})
            for configuration in prompt["configurations"]:
                for row in configuration["rounds"]:
                    row["image"] = f"{configuration['group']}/r{row['round']}/{prompt_index:02d}_test.png"
            prompts.append(prompt)
        for language in ("en", "zh"):
            grounding = "### Web Grounding Test\n\nOffline grounding evidence"
            with patch.object(report, "render_overview",
                              side_effect=lambda *_args, section=grounding, **_kwargs:
                              "Current four-configuration evidence\n\n" + section):
                generated = report.update_document(original, {"per_prompt": prompts}, {}, "data/offline-fixture", language, grounding)
                regenerated = report.update_document(generated, {"per_prompt": prompts}, {}, "data/offline-fixture", language, grounding)
            self.assertEqual(generated, regenerated)
            self.assertNotIn("MAI-Image-2e", generated)
            self.assertNotIn("GPT-Image-1.5", generated)
            self.assertNotIn("old measurements", generated)
            self.assertNotIn("<details>", generated)
            self.assertIn("> **Author**: Existing Author", generated)
            self.assertEqual(generated.count("### Test "), 11)
            self.assertEqual(generated.count("**Round "), 22)
            # Count only scenario comparison images, so masthead badges cannot mask a
            # missing or duplicated per-scenario picture.
            scenario_images = len(re.findall(r"!\[[^\]]*\]\(data/offline-fixture/[^)]+\)", generated))
            self.assertEqual(scenario_images, 88)
            self.assertIn("### Web Grounding Test\n\nOffline grounding evidence", generated)
            self.assertNotIn("web-grounding-20260908/README", generated)
            self.assertNotIn("Supplement", generated)
            self.assertNotIn("Lenovo products", generated)
            # Images now precede the metrics body, so the overview content that
            # carries the grounding section appears after the scenario comparisons.
            self.assertLess(generated.index("### Test 1:"), generated.index("Offline grounding evidence"))


class TierCoverageClaimTests(unittest.TestCase):
    """The title may claim full tier coverage only when the data covers every accepted tier.

    The 2026-09-17 publication shipped a title reading "All Quality Tiers" while the run covered
    low/medium/high only: the runner's tier list had been written for gpt-image-2, and
    gpt-image-2.5-* accepts three more. These assertions tie the claim to the measurements.
    """

    def summary(self, *pairs):
        return {"config": {"group_configurations": [
            {"provider": "gpt", "model": model, "quality": quality} for model, quality in pairs]}}

    def test_three_tiers_on_a_six_tier_model_is_not_full_coverage(self):
        coverage = report.tier_coverage(self.summary(
            *(("gpt-image-2.5-flare", tier) for tier in ("low", "medium", "high"))))
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["missing"]["gpt-image-2.5-flare"], ["xhigh", "max", "auto"])

    def test_every_accepted_tier_is_full_coverage(self):
        coverage = report.tier_coverage(self.summary(
            *(("gpt-image-2.5-flare", tier)
              for tier in ("low", "medium", "high", "xhigh", "max", "auto")),
            *(("gpt-image-2", tier) for tier in ("low", "medium", "high"))))
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["missing"], {})

    def test_gpt_image_2_is_complete_at_three_tiers(self):
        """gpt-image-2 does not accept xhigh/max/auto, so three tiers is all of them."""
        self.assertTrue(report.tier_coverage(self.summary(
            *(("gpt-image-2", tier) for tier in ("low", "medium", "high"))))["complete"])

    def test_coverage_spans_the_primary_run_and_the_supplement(self):
        coverage = report.tier_coverage(
            self.summary(*(("gpt-image-2", tier) for tier in ("low", "medium", "high"))),
            self.summary(*(("gpt-image-2.5-flare", tier)
                           for tier in ("low", "medium", "high", "xhigh", "max", "auto"))))
        self.assertTrue(coverage["complete"])

    def test_an_unknown_model_cannot_silently_claim_coverage(self):
        with self.assertRaisesRegex(ValueError, "official tier list"):
            report.tier_coverage(self.summary(("gpt-image-9-unknown", "low")))

    def test_mai_has_no_tiers_and_does_not_affect_coverage(self):
        coverage = report.tier_coverage({"config": {"group_configurations": [
            {"provider": "mai", "model": "MAI-Image-2.6", "quality": None},
            *({"provider": "gpt", "model": "gpt-image-2", "quality": tier}
              for tier in ("low", "medium", "high"))]}})
        self.assertTrue(coverage["complete"])
        self.assertNotIn("MAI-Image-2.6", coverage["measured"])


class AutoTierAttributionTests(unittest.TestCase):
    """quality=auto must be reported as what the service said, not inferred from tokens.

    Measured 2026-09-18 over 132 samples: every explicitly requested tier returned one constant
    output-token count across all 22 of its samples, but auto's self-reported medium came back at
    both 439 and 781 tokens. Token counts therefore do not identify a tier under auto, and the
    renderer must read the echoed quality instead.
    """

    def test_tokens_are_not_used_to_infer_the_tier(self):
        self.assertFalse(hasattr(report, "TOKENS_TO_TIER"),
                         "token-to-tier inference is unsound under quality=auto")

    def test_auto_is_an_accepted_tier_but_never_a_coverage_signature(self):
        for model, tiers in report.OFFICIAL_TIERS.items():
            if "auto" in tiers:
                self.assertIn("xhigh", tiers, f"{model} lists auto without the explicit tiers")
        self.assertEqual(report.TIER_ORDER[-1], "auto",
                         "auto sorts last because it is not a quality level")


if __name__ == "__main__":
    unittest.main()