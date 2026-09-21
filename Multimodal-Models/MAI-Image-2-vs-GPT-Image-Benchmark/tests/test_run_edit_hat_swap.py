import hashlib
import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_edit_hat_swap as runner


class PublicEditRunnerTests(unittest.TestCase):
    def test_round_order_is_reversed_and_only_gpt_gets_size(self):
        round_one = runner.make_specs(1, gpt_deployment="gpt-image-2.5-flare", gpt_qualities=("medium", "high"))
        round_two = runner.make_specs(2, gpt_deployment="gpt-image-2.5-flare", gpt_qualities=("medium", "high"))
        expected = ["mai-image-2.6", "gpt-image-2.5-flare-medium", "gpt-image-2.5-flare-high"]
        self.assertEqual([item["label"] for item in round_one], expected)
        self.assertEqual([item["label"] for item in round_two], list(reversed(expected)))
        self.assertNotIn("size", round_one[0]["data"])
        for item in round_one[1:]:
            self.assertEqual(item["data"]["size"], "auto")
            self.assertEqual(item["data"]["model"], "gpt-image-2.5-flare")

    def test_default_tiers_reproduce_the_original_gpt_image_2_labels(self):
        """Archives before 2026-09-21 recorded no deployment; their labels must still verify."""
        self.assertEqual([item["label"] for item in runner.make_specs(1)],
                         ["mai-image-2.6", "gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high"])
        self.assertEqual(runner.check_output(ROOT / "data" / "edit-hat-swap-20260909-auto")["outputs"], 8)
        self.assertEqual(runner.check_output(ROOT / "data" / "edit-hat-swap-gpt25-20260921")["outputs"], 6)

    def test_validate_input_rejects_non_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.jpg"
            path.write_bytes(b"not a jpeg")
            with self.assertRaises(ValueError):
                runner.validate_input(path)

    def test_completed_two_round_output_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = b"\xff\xd8fixture\xff\xd9"
            (root / "input.jpg").write_bytes(source)
            source_sha = hashlib.sha256(source).hexdigest()
            png = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 16, 16)
            for round_number, relative in ((1, ""), (2, "r2")):
                base = root / relative
                base.mkdir(exist_ok=True)
                attempts = []
                for index, spec in enumerate(runner.make_specs(round_number), start=1):
                    name = f"{index:02d}_{spec['label']}.png"
                    (base / name).write_bytes(png)
                    attempts.append({
                        "label": spec["label"], "status_code": 200,
                        "outcome": "RETURNED_IMAGE", "output_path": name,
                        "output_sha256": hashlib.sha256(png).hexdigest(),
                    })
                (base / "edit-results.json").write_text(json.dumps({
                    "round": round_number,
                    "source_sha256": source_sha,
                    "gpt_size_parameter": "auto",
                    "attempts": attempts,
                }), encoding="utf-8")
            self.assertEqual(runner.check_output(root), {
                "status": "PASS", "rounds": 2, "outputs": 8,
                "gpt_size_parameter": "auto",
            })

    def test_tampered_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.jpg").write_bytes(b"\xff\xd8fixture\xff\xd9")
            for round_number, relative in ((1, ""), (2, "r2")):
                base = root / relative
                base.mkdir(exist_ok=True)
                attempts = []
                for index, spec in enumerate(runner.make_specs(round_number), start=1):
                    name = f"{index:02d}_{spec['label']}.png"
                    data = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 16, 16)
                    (base / name).write_bytes(data)
                    attempts.append({"label": spec["label"], "status_code": 200,
                                     "outcome": "RETURNED_IMAGE", "output_path": name,
                                     "output_sha256": "0" * 64})
                (base / "edit-results.json").write_text(json.dumps({
                    "round": round_number,
                    "source_sha256": hashlib.sha256((root / "input.jpg").read_bytes()).hexdigest(),
                    "gpt_size_parameter": "auto",
                    "attempts": attempts,
                }), encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.check_output(root)

    def test_readmes_expose_a_complete_edit_how_to(self):
        for filename, heading in (("README.md", "### Reproduction and Tests"),
                                  ("README-CN.md", "### 复现与测试")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertIn(heading, text, filename)
            self.assertIn("scripts/run_edit_hat_swap.py", text, filename)
            # One reproduction block per GPT generation that was measured.
            self.assertIn("$env:GPT_DEPLOYMENT = 'gpt-image-2.5-flare'", text, filename)
            self.assertIn("$env:GPT_DEPLOYMENT = 'gpt-image-2'", text, filename)
            self.assertIn("--gpt-size auto --gpt-quality medium --gpt-quality high --dry-run", text, filename)
            self.assertIn("--gpt-size auto --gpt-quality low --gpt-quality medium --gpt-quality high", text, filename)
            self.assertIn("--output $out --check", text, filename)

    def test_edit_scenario_is_not_excluded_by_the_report_boundary(self):
        for filename, marker in (("README.md", "Scenario 12 is an image edit"), ("README-CN.md", "第 12 题为图像编辑")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertIn(marker, text, filename)
            self.assertNotIn("excluding 2K, editing", text, filename)
            self.assertNotIn("不包括 2K、图像编辑", text, filename)

    def test_forced_square_edit_outputs_are_never_rendered(self):
        """The square outputs came from this test's own parameter; only the size=auto runs are shown."""
        for filename in ("README.md", "README-CN.md"):
            text = (ROOT / filename).read_text("utf-8")
            for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
                self.assertNotIn("edit-hat-swap-20260908/", target, filename)
            self.assertNotIn("size-protocol-comparison", text, filename)

    def test_opening_uses_corrected_result_and_stable_how_to_anchor(self):
        # The badge is derived from the number of test functions under tests/, so assert the
        # derivation rather than a literal that drifts every time a test is added.
        expected_count = sum(len(re.findall(r"(?m)^\s+def test_", p.read_text("utf-8")))
                             for p in (ROOT / "tests").glob("test_*.py"))
        for filename in ("README.md", "README-CN.md"):
            text = (ROOT / filename).read_text("utf-8")
            self.assertIn('<a id="reproduction-how-to"></a>', text, filename)
            self.assertIn("](#reproduction-how-to)", text, filename)
            self.assertIn(f"Tests-{expected_count}%20offline", text, filename)
            self.assertNotIn("multi-image input editing", text, filename)
            self.assertNotIn("多图输入编辑两项能力实测", text, filename)


if __name__ == "__main__":
    unittest.main()