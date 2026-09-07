import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize_mai_run.py"
SPEC = importlib.util.spec_from_file_location("summarize_mai_run", SCRIPT)
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


class SummaryTests(unittest.TestCase):
    def test_descriptive_latency_statistics(self):
        result = SUMMARY.latency_statistics([3, 1, 2])
        self.assertEqual(result["samples"], 3)
        self.assertEqual(result["mean_seconds"], 2)
        self.assertEqual(result["p50_seconds"], 2)
        self.assertAlmostEqual(result["p95_seconds"], 2.9)
        self.assertEqual(result["sample_stddev_seconds"], 1)

    def test_missing_usage_does_not_become_zero_cost(self):
        prices = {"text_input": 5, "image_input": 8, "image_output": 38}
        self.assertIsNone(SUMMARY.usage_cost({}, prices))
        self.assertIsNone(SUMMARY.usage_cost(None, prices))
        self.assertIsNone(SUMMARY.usage_cost({"num_output_tokens": 1024}, prices))

    def test_cost_includes_returned_input_and_output_usage(self):
        prices = {"text_input": 5, "image_input": 8, "image_output": 38}
        usage = {"num_input_text_tokens": 43, "num_input_image_tokens": 0, "num_output_tokens": 1024}
        self.assertAlmostEqual(SUMMARY.usage_cost(usage, prices), 0.039127)

    def test_running_measurement_cannot_be_a_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "5way_v2_results.json").write_text(json.dumps({"state": "RUNNING"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "terminal state"):
                SUMMARY.summarize(root, root / "prompts.csv")

    def test_price_schedule_rejects_another_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {"state": "COMPLETED", "config": {"groups": ["mai-image-2.6-flash"]}}
            (root / "5way_v2_results.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MAI-Image-2.6 only"):
                SUMMARY.summarize(root, root / "prompts.csv")


if __name__ == "__main__":
    unittest.main()