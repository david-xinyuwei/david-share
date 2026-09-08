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
            with patch.object(report, "render_overview", return_value="Current four-configuration evidence"):
                generated = report.update_document(original, {"per_prompt": prompts}, {}, "data/offline-fixture", language)
                regenerated = report.update_document(generated, {"per_prompt": prompts}, {}, "data/offline-fixture", language)
            self.assertEqual(generated, regenerated)
            self.assertNotIn("MAI-Image-2e", generated)
            self.assertNotIn("GPT-Image-1.5", generated)
            self.assertNotIn("old measurements", generated)
            self.assertNotIn("<details>", generated)
            self.assertIn("> **Author**: Existing Author", generated)
            self.assertEqual(generated.count("### Test "), 11)
            self.assertEqual(generated.count("**Round "), 22)
            self.assertEqual(generated.count("!["), 88)
            supplement_page = "README-CN.md" if language == "zh" else "README.md"
            self.assertIn(f"data/lenovo-web-grounding-20260908/{supplement_page}", generated)


if __name__ == "__main__":
    unittest.main()