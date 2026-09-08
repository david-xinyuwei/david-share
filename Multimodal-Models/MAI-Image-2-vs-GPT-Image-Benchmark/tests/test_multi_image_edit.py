import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_multi_image_edit as module


class MultiImageEditEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = ROOT / "data" / "mai-multi-image-edit-20260908"
        cls.prefix = f"data/{cls.archive.name}/"
        cls.summary = module.summarize(cls.archive)

    def test_capability_arms_use_prompts_their_input_count_can_satisfy(self):
        """A plural prompt sent with one image cannot represent single-image quality."""
        by_count = {entry["image_count"]: entry for entry in self.summary["capability"]}
        self.assertEqual(set(by_count), {1, 2})
        self.assertNotIn("both reference images", by_count[1]["prompt"])
        self.assertIn("both reference images", by_count[2]["prompt"])
        self.assertNotEqual(by_count[1]["prompt"], by_count[2]["prompt"])
        for entry in by_count.values():
            self.assertEqual(entry["status_code"], 200)
            self.assertEqual((entry["png"]["width"], entry["png"]["height"]), (1024, 1024))

    def test_attribution_holds_prompt_constant_across_symmetric_arms(self):
        labels = {entry["label"] for entry in self.summary["attribution"]}
        self.assertEqual(labels, {"single_image", "two_image_fields",
                                  "fixed_prompt_image_two_only"})
        counts = sorted(entry["image_count"] for entry in self.summary["attribution"])
        self.assertEqual(counts, [1, 1, 2], "both single-image arms are required")

    def test_outputs_carry_no_alpha_channel_so_cutout_is_not_claimed(self):
        for entry in self.summary["capability"] + self.summary["attribution"]:
            self.assertFalse(entry["png"]["has_alpha_channel"], entry["label"])
            self.assertIn(entry["png"]["colour_type"], (0, 2))
        self.assertFalse(self.summary["transparent_cutout_supported"])

    def test_limit_and_field_rules_quote_the_service(self):
        contract = self.summary["contract"]
        self.assertEqual(contract["service_limit_message"],
                         "Only 1 to 5 image files are supported for edit requests.")
        self.assertIn("name starting with 'image'", contract["field_prefix_message"])
        self.assertIn(9, contract["rejected_counts"])
        self.assertTrue(set(contract["quota_limited_counts"]) <= {3, 5})
        for shape in ("image_array_suffix", "image_plural_field", "numbered_fields",
                      "prefixed_fields", "wrong_field_name_only"):
            self.assertIn(shape, contract["rejected_shapes"])

    def test_evidence_hashes_match_the_published_files(self):
        records = json.loads((self.archive / "clean-results.json").read_text("utf-8"))
        for attempt in records["attempts"]:
            path = self.archive / attempt["output_path"]
            self.assertTrue(path.is_file(), attempt["output_path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, attempt["output_sha256"], attempt["label"])

    def test_reports_render_the_section_with_measured_values_only(self):
        by_count = {entry["image_count"]: entry for entry in self.summary["capability"]}
        for filename, heading, previous in (
                ("README.md", "## Multi-Image Input Edit Test", "## Web Grounding Test"),
                ("README-CN.md", "## 多图输入编辑测试", "## 联网信息补充测试")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertEqual(text.count(heading), 1, filename)
            self.assertLess(text.index(previous), text.index(heading))
            collapsed = " ".join(text.split())
            for entry in by_count.values():
                self.assertIn(" ".join(entry["prompt"].split()), collapsed)
                self.assertIn(f"{entry['request_seconds']} s", text)
            self.assertIn("Only 1 to 5 image files are supported for edit requests.", text)
            self.assertIn("429", text)
            images = {target for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
                      if target.startswith(self.prefix)}
            self.assertEqual(len(images), 5, filename)
            for target in images:
                self.assertTrue((ROOT / target).is_file(), target)
            self.assertNotIn(f"{self.prefix}README", text)

    def test_incomplete_or_alpha_bearing_evidence_is_rejected(self):
        original = module.CAPABILITY_LABELS
        try:
            module.CAPABILITY_LABELS = ("single_image_matched_prompt", "missing_arm")
            with self.assertRaises(ValueError):
                module.summarize(self.archive)
        finally:
            module.CAPABILITY_LABELS = original


if __name__ == "__main__":
    unittest.main()
