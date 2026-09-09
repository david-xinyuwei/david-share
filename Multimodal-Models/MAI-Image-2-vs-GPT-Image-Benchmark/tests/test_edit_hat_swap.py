import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_edit_hat_swap as module
from summarize_paired_run import GROUPS


class EditHatSwapEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = ROOT / "data" / "edit-hat-swap-20260909-auto"
        cls.prefix = f"data/{cls.archive.name}/"
        cls.summary = module.summarize(cls.archive)

    def test_two_rounds_each_with_one_image_per_configuration(self):
        """Same protocol as Tests 1-11: two rounds, round 2 in reversed order."""
        self.assertEqual([r["round"] for r in self.summary["rounds"]], [1, 2])
        for round_item in self.summary["rounds"]:
            groups = [item["group"] for item in round_item["outputs"]]
            self.assertEqual(groups, list(GROUPS))
            base = self.archive if round_item["round"] == 1 else self.archive / f"r{round_item['round']}"
            records = json.loads((base / "edit-results.json").read_text("utf-8"))
            by_label = {a["label"]: a for a in records["attempts"]}
            for item in round_item["outputs"]:
                path = self.archive / item["output"]
                self.assertTrue(path.is_file(), item["output"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 by_label[item["group"]]["output_sha256"])
                self.assertEqual(item["status_code"], 200)
        self.assertEqual(self.summary["rounds"][0]["order_sent"], list(GROUPS))
        self.assertEqual(self.summary["rounds"][1]["order_sent"], list(reversed(GROUPS)))

    def test_published_input_matches_the_request_record(self):
        source = self.archive / "input.jpg"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        records = json.loads((self.archive / "edit-results.json").read_text("utf-8"))
        self.assertEqual(digest, records["source_sha256"])
        self.assertEqual(self.summary["source"]["width"], 553)
        self.assertEqual(self.summary["source"]["height"], 311)

    def _all_outputs(self):
        return [item for r in self.summary["rounds"] for item in r["outputs"]]

    def test_checklist_covers_every_item_in_every_round(self):
        self.assertEqual(self.summary["gpt_size_parameter"], "auto")
        for item in self._all_outputs():
            self.assertEqual(set(item["checks"]), set(module.REVIEW_CHECKS), item["group"])
            self.assertEqual(item["preserved_total"], 5)
            self.assertLessEqual(item["preserved_count"], 5)

    def test_aspect_ratio_flag_matches_measured_dimensions(self):
        """The 'kept aspect ratio' claim must come from pixels, not from the prose."""
        source = self.summary["source"]
        for item in self._all_outputs():
            measured = abs(item["width"] / item["height"] - source["width"] / source["height"]) < 0.02
            self.assertEqual(item["checks"]["input_aspect_ratio_preserved"], measured, item["group"])

    def test_tampered_output_is_rejected(self):
        original = module.hashlib.sha256
        try:
            module.hashlib.sha256 = lambda data: type("H", (), {"hexdigest": lambda self: "0" * 64})()
            with self.assertRaises(ValueError):
                module.summarize(self.archive)
        finally:
            module.hashlib.sha256 = original

    def test_reports_render_test_12_after_test_11_with_both_rounds(self):
        for filename, heading, previous, following in (
                ("README.md", "### Test 12: Headwear Swap (Image Edit)", "### Test 11:",
                 "## Current Run: Both Models and All Quality Tiers"),
                ("README-CN.md", "### Test 12: 换帽子（图像编辑）", "### Test 11:",
                 "## 本轮：两模型与全部质量档位")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertEqual(text.count(heading), 1, filename)
            self.assertLess(text.index(previous), text.index(heading), filename)
            self.assertLess(text.index(heading), text.index(following), filename)
            body = text[text.index(heading):text.index(following)]
            images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)
            # Input once, then four outputs per round — the Test 1-11 shape plus the input.
            self.assertEqual(len(images), 1 + 4 * len(self.summary["rounds"]), filename)
            for target in images:
                self.assertTrue(target.startswith(self.prefix), target)
                self.assertTrue((ROOT / target).is_file(), target)
            collapsed = " ".join(body.split())
            self.assertIn(" ".join(self.summary["prompt"].split()), collapsed, filename)
            round_label = "**第1轮:**" if filename.endswith("CN.md") else "**Round 1:**"
            round_label_2 = "**第2轮:**" if filename.endswith("CN.md") else "**Round 2:**"
            self.assertIn(round_label, body, filename)
            self.assertIn(round_label_2, body, filename)
            self.assertLess(body.index(round_label), body.index(round_label_2), filename)
            for item in self._all_outputs():
                # Same cell format as Tests 1-11: latency, size in KiB, plus pixel size.
                self.assertIn(f"{item['request_seconds']:.2f} s<br>{item['output_kib']:.0f} KiB<br>"
                              f"{item['width']}x{item['height']}", body, item["group"])
            self.assertIn("size=auto" if not filename.endswith("CN.md") else "`size` 传 `auto`", body)
            self.assertIn("Protocol correction" if not filename.endswith("CN.md") else "协议更正", body)
            self.assertIn(f"{self.prefix}title-corner-contact-sheet.png", body)
            self.assertNotIn("data/edit-hat-swap-20260908/", body)
            self.assertNotIn("<details", body)

    def test_superseded_multi_image_section_is_gone(self):
        for filename in ("README.md", "README-CN.md"):
            text = (ROOT / filename).read_text("utf-8")
            self.assertNotIn("mai-multi-image-edit-20260908", text, filename)
            self.assertNotIn("Multi-Image Input Edit Test", text, filename)
            self.assertNotIn("多图输入编辑测试", text, filename)


if __name__ == "__main__":
    unittest.main()
