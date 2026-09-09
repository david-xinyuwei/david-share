import hashlib
import json
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
        round_one = runner.make_specs(1)
        round_two = runner.make_specs(2)
        self.assertEqual([item["label"] for item in round_one], list(runner.GROUPS))
        self.assertEqual([item["label"] for item in round_two], list(reversed(runner.GROUPS)))
        self.assertNotIn("size", round_one[0]["data"])
        for item in round_one[1:]:
            self.assertEqual(item["data"]["size"], "auto")

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
        for filename, heading in (("README.md", "## Reproduction How-to and Tests"),
                                  ("README-CN.md", "## 复现方法（How-to）与测试")):
            text = (ROOT / filename).read_text("utf-8")
            self.assertIn(heading, text, filename)
            self.assertIn("scripts/run_edit_hat_swap.py", text, filename)
            self.assertIn("--gpt-size auto --dry-run", text, filename)
            self.assertIn("--round 2 --gpt-size auto", text, filename)
            self.assertIn("--output runs/edit-hat-swap-reproduction --check", text, filename)
            self.assertIn("Credentials / billing" if filename == "README.md" else "凭据 / 计费",
                          text, filename)

    def test_edit_scenario_is_not_excluded_by_the_report_boundary(self):
        english = (ROOT / "README.md").read_text("utf-8")
        chinese = (ROOT / "README-CN.md").read_text("utf-8")
        self.assertIn("separately reported `size=auto` image-edit test", english)
        self.assertNotIn("excluding 2K, editing", english)
        self.assertIn("单独报告的 `size=auto` 图像编辑测试", chinese)
        self.assertNotIn("不包括 2K、图像编辑", chinese)

    def test_opening_uses_corrected_result_and_stable_how_to_anchor(self):
        for filename in ("README.md", "README-CN.md"):
            text = (ROOT / filename).read_text("utf-8")
            self.assertIn('<a id="reproduction-how-to"></a>', text, filename)
            self.assertIn("](#reproduction-how-to)", text, filename)
            self.assertIn("Tests-61%20offline", text, filename)
            self.assertNotIn("multi-image input editing", text, filename)
            self.assertNotIn("多图输入编辑两项能力实测", text, filename)
            self.assertNotIn("all three GPT tiers add the cap but regenerate the whole frame", text, filename)
            self.assertNotIn("GPT 三档都换上了帽子但整幅重新生成", text, filename)


if __name__ == "__main__":
    unittest.main()