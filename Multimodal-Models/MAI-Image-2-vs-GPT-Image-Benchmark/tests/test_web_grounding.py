import hashlib
import json
import re
import statistics
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_web_grounding


class GroundingPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = ROOT / "data" / "lenovo-web-grounding-20260908"
        cls.archive_prefix = f"data/{cls.archive.name}/"
        cls.summary = summarize_web_grounding.summarize(cls.archive)
        cls.selected = [sample for sample in cls.summary["samples"] if sample["prompt_idx"] in (1, 2)]

    def test_full_evidence_preserves_original_result(self):
        provenance = json.loads((self.archive / "provenance.json").read_text("utf-8"))
        self.assertTrue(self.summary["complete"])
        self.assertEqual(self.summary["recorded_samples"], provenance["original_formal_samples"])
        self.assertEqual(self.summary["result_sha256"], provenance["original_result_sha256"])
        for artifact in provenance["files"]:
            content = (self.archive / artifact["path"]).read_bytes()
            self.assertEqual(len(content), artifact["bytes"])
            self.assertEqual(hashlib.sha256(content).hexdigest(), artifact["sha256"])

    def test_grounding_rendered_inside_main_reports_without_separate_pages(self):
        self.assertFalse((self.archive / "README.md").exists())
        self.assertFalse((self.archive / "README-CN.md").exists())
        expected = {self.archive_prefix + sample["image"] for sample in self.selected}
        self.assertEqual(len(expected), 8)
        for filename, heading, previous in (
                ("README.md", "## Web Grounding Test", "## Side-by-Side Image Comparison"),
                ("README-CN.md", "## 联网信息补充测试", "## 并排图片对比")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertEqual(text.count(heading), 1)
            self.assertLess(text.index(previous), text.index(heading))
            images = {target for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
                      if target.startswith(self.archive_prefix)}
            self.assertEqual(images, expected)
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if target.startswith(self.archive_prefix):
                    self.assertTrue((ROOT / target.split("#")[0]).exists(), target)
            self.assertIn("Tablet Mode", text)
            self.assertNotIn(f"{self.archive_prefix}README", text)
            self.assertNotIn("Supplement", text)
            self.assertNotIn("Lenovo products", text)

    def test_selected_metrics_not_full_run_averages(self):
        rows_by_setting = [[sample for sample in self.selected if sample["web_grounding"] is enabled]
                           for enabled in (False, True)]
        values = []
        for statistic, field in ((statistics.mean, "time"), (statistics.median, "time"),
                                 (statistics.mean, "logical_request_seconds")):
            values.append([f"{statistic(sample[field] for sample in rows):.2f}" for rows in rows_by_setting])
        for filename, unit in (("README.md", "s"), ("README-CN.md", "秒")):
            text = (ROOT / filename).read_text("utf-8")
            for off, on in values:
                self.assertIn(f"| {off} {unit} | {on} {unit} |", text)
            self.assertIn("| 4/4 | 1/4 |", text)
            self.assertIn("| 4 | 7 |", text)
            self.assertIn("| 0 | 3 |", text)


if __name__ == "__main__":
    unittest.main()