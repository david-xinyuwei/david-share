import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_paired_report as report

GROUPS = ("mai-image-2.6", "gpt-image-2.5-flare-medium", "gpt-image-2.5-flare-high")
LABELS = ("MAI-Image-2.6", "GPT-Image-2.5 Flare medium", "GPT-Image-2.5 Flare high")


class ComparisonReportTests(unittest.TestCase):
    def prompt(self, index=1):
        return {"prompt_index": index, "prompt": f"Original prompt {index}", "configurations": [
            {"group": group, "rounds": [
                {"round": round_number, "ok": True, "request_seconds": 1.25,
                 "image": f"{group}/r{round_number}/{index:02d}_test.png", "image_kib": 512,
                 "attempts": 1, "logical_request_seconds": 1.5}
                for round_number in (1, 2)]} for group in GROUPS]}

    def run_fixture(self, prompt):
        return {"archive": "data/offline-fixture", "date": "2026-01-01", "region": "swedencentral",
                "groups": list(GROUPS), "labels": list(LABELS), "summary": {"per_prompt": [prompt]}}

    def cells(self, prompt):
        run = self.run_fixture(prompt)
        return [(label, run, prompt, group) for label, group in zip(LABELS, GROUPS)]

    def test_every_configuration_appears_in_each_round(self):
        for round_number in (1, 2):
            rendered = report.image_table(self.cells(self.prompt()), round_number, "en")
            for group in GROUPS:
                self.assertIn(f"data/offline-fixture/{group}/r{round_number}/01_test.png", rendered)
            self.assertEqual(rendered.count("!["), len(GROUPS))

    def test_failed_sample_is_not_replaced_by_old_image(self):
        prompt = self.prompt()
        prompt["configurations"][2]["rounds"][0].update({"ok": False, "image": None, "attempts": 3})
        rendered = report.image_table(self.cells(prompt), 1, "en")
        self.assertIn("No image returned", rendered)
        self.assertIn("3 attempts", rendered)
        self.assertEqual(rendered.count("!["), len(GROUPS) - 1)
        self.assertNotIn("gpt-image-2.5-flare-high/r1", rendered)

    def test_a_missing_configuration_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"].pop()
        with self.assertRaisesRegex(ValueError, "no configuration"):
            report.image_table(self.cells(prompt), 1, "en")

    def test_image_from_another_quality_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"][1]["rounds"][0]["image"] = "gpt-image-2.5-flare-high/r1/01_test.png"
        with self.assertRaisesRegex(ValueError, "configuration"):
            report.image_table(self.cells(prompt), 1, "en")

    def test_image_from_another_round_is_rejected(self):
        prompt = self.prompt()
        prompt["configurations"][1]["rounds"][0]["image"] = "gpt-image-2.5-flare-medium/r2/01_test.png"
        with self.assertRaisesRegex(ValueError, "configuration"):
            report.image_table(self.cells(prompt), 1, "en")

    def test_dated_headers_mark_cells_from_another_session(self):
        rendered = report.image_table(self.cells(self.prompt()), 1, "en", show_date=True)
        self.assertIn("MAI-Image-2.6<br>(2026-01-01)", rendered)

    def test_latency_table_shows_both_rounds_and_failed_cell(self):
        prompt = self.prompt()
        prompt["configurations"][2]["rounds"][0]["ok"] = False
        rendered = report.prompt_latency_table(self.run_fixture(prompt), "zh")
        self.assertIn("01 / R1", rendered)
        self.assertIn("01 / R2", rendered)
        self.assertIn("失败", rendered)

    def test_reproduction_covers_every_archive_and_the_offline_check(self):
        primary = {"archive": "data/offline-fixture", "region": "swedencentral"}
        supplement = {"archive": "data/offline-supplement"}
        tier = {"archive": "data/offline-tiers"}
        gpt2 = {"archive": "data/offline-gpt2"}
        edits = [({"archive": "data/offline-edit-gpt2", "gpt_deployment": "gpt-image-2",
                   "groups": ["mai-image-2.6", "gpt-image-2-low", "gpt-image-2-high"]}, "GPT-Image-2"),
                 ({"archive": "data/offline-edit", "gpt_deployment": "gpt-image-2.5-flare",
                   "groups": ["mai-image-2.6", "gpt-image-2.5-flare-medium", "gpt-image-2.5-flare-high"]}, "GPT-Image-2.5")]
        study = {"archive": "data/offline-text", "prompts_name": "prompts-text.csv", "calibration": {"summary": {}}}
        billing = {"archive": "data/offline-billing"}
        for language in ("en", "zh"):
            section = report.reproduction_section(primary, supplement, tier, gpt2, edits, {"complete": True}, (study, None), billing, language)
            self.assertIn("--mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high", section)
            self.assertIn("--warmup-only", section)
            self.assertIn("--resume", section)
            for archive in ("data/offline-fixture", "data/offline-supplement", "data/offline-tiers", "data/offline-gpt2",
                            "data/offline-edit-gpt2", "data/offline-edit", "data/offline-text", "data/offline-billing"):
                self.assertIn(archive, section, archive)
            # Each generation keeps its own deployment and its own tier list; neither is inherited from the other.
            self.assertIn("--gpt-quality medium --gpt-quality high", section)
            self.assertIn("--gpt-quality low --gpt-quality high", section)
            self.assertIn("$env:GPT_DEPLOYMENT = 'gpt-image-2'", section)
            self.assertIn("$env:GPT_DEPLOYMENT = 'gpt-image-2.5-flare'", section)
            self.assertIn("--gpt-model gpt-image-2 --gpt-quality all", section)
            self.assertIn("score_text_rendering.py --check data/offline-text/text-scoring.json", section)
            self.assertIn("calibrate_text_judge.py --check data/offline-text/judge-calibration/calibration.json", section)
            self.assertIn("effective_prices.py data/offline-billing --check", section)
            self.assertIn("AZURE_OPENAI_API_KEY", section)

    def test_exception_section_keeps_failures_in_the_denominator(self):
        run = {"summary": {"unsuccessful_attempts": [{"sample_id": "offline-sample", "attempt": 1,
               "exception_type": "ConnectionError", "http_status": None, "request_seconds": 90.25,
               "started_at_utc": "2026-01-01T00:00:00+00:00", "finished_at_utc": "2026-01-01T00:01:31+00:00"}]}}
        rendered = report.exception_section(run, "en")
        self.assertIn("ConnectionError", rendered)
        self.assertIn("90.25", rendered)
        self.assertIn("planned denominator", rendered)

    def test_group_labels_are_human_readable(self):
        self.assertEqual(report.group_label("gpt-image-2.5-flare-medium"), "GPT-Image-2.5 Flare medium")
        self.assertEqual(report.group_label("gpt-image-2.5-sunburst-auto"), "GPT-Image-2.5 Sunburst auto")
        self.assertEqual(report.group_label("mai-image-2.6"), "MAI-Image-2.6")

    def test_document_removes_other_models_and_preserves_all_scenarios(self):
        original = "# Old report\n\n> **Author**: Existing Author\n\nMAI-Image-2e GPT-Image-1.5 GPT-Image-2 low\n"
        prompts = []
        for index in range(1, 12):
            original += f"\n### Test {index}: Original scenario {index}\nold measurements\n"
            prompts.append(self.prompt(index))
        primary = self.run_fixture(prompts[0])
        primary["summary"] = {"per_prompt": prompts, "formal_ended_at_utc": "2026-01-01T02:00:00+00:00",
                              "formal_samples": 66, "successful_samples": 66,
                              "config": {"group_configurations": [{"provider": "mai", "model_version": "2026-07-31"}]},
                              "groups": [{"group": g, "successful_request_latency": {"p50_seconds": 30.0}} for g in GROUPS]}
        for language in ("en", "zh"):
            grounding = "## Web Grounding Test\n\nOffline grounding evidence"
            # The sections that need a full environment/billing fixture are stubbed; this test is about
            # scenario preservation and idempotence, not their content.
            with patch.object(report, "render_overview", return_value=("## Same-Session Run\n\nOffline metrics", "Offline limits")), \
                    patch.object(report, "render_architecture", return_value="## Architecture and Test Topology"), \
                    patch.object(report, "render_tests_doc", return_value="## Tests and Offline Checks"), \
                    patch.object(report, "render_assets", return_value="## Assets and Evidence"), \
                    patch.object(report, "render_grounding_section", return_value=grounding):
                generated = report.update_document(original, primary, None, None, None, [], {"planned_samples": 12}, (None, None), None, language, 7)
                regenerated = report.update_document(generated, primary, None, None, None, [], {"planned_samples": 12}, (None, None), None, language, 7)
            self.assertEqual(generated, regenerated)
            self.assertNotIn("MAI-Image-2e", generated)
            self.assertNotIn("GPT-Image-1.5", generated)
            self.assertNotIn("GPT-Image-2 low", generated)
            self.assertNotIn("old measurements", generated)
            self.assertNotIn("<details>", generated)
            self.assertIn("> **Author**: Existing Author", generated)
            self.assertEqual(generated.count("### Test "), 11)
            self.assertEqual(generated.count("**Round "), 22)
            scenario_images = len(re.findall(r"!\[[^\]]*\]\(data/offline-fixture/[^)]+\)", generated))
            self.assertEqual(scenario_images, 11 * 2 * len(GROUPS))
            self.assertIn("Tests-7%20offline", generated)
            self.assertIn("Offline grounding evidence", generated)
            self.assertLess(generated.index("### Test 1:"), generated.index("Offline metrics"))
            self.assertLess(generated.index("Offline metrics"), generated.index("Offline grounding evidence"))


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