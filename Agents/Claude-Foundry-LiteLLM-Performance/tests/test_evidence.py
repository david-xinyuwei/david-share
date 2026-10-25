import copy
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze
import render_docs


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = analyze.read_json(ROOT / "evidence/requests.json")
        cls.matrix = analyze.read_json(ROOT / "data/matrix.json")

    def test_full_evidence_and_hashes(self):
        result = analyze.validate()
        self.assertEqual(result["requests"], 50)
        self.assertEqual(result["configurations"], 10)
        self.assertAlmostEqual(result["costUsd"], 0.78989513, places=10)

    def test_missing_turn_rejected(self):
        with self.assertRaisesRegex(ValueError, "fifty"):
            analyze.validate_records(self.records[:-1], self.matrix)

    def test_changed_token_denominator_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["measurement"]["totalInputTokens"] += 1
        with self.assertRaisesRegex(ValueError, "denominator"):
            analyze.validate_records(altered, self.matrix)

    def test_changed_question_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["request"]["messages"][-1]["content"] += " altered"
        with self.assertRaisesRegex(ValueError, "History or questions"):
            analyze.validate_records(altered, self.matrix)

    def test_mode_mismatch_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["providerRequest"]["thinking"]["type"] = "disabled"
        with self.assertRaisesRegex(ValueError, "Thinking mode"):
            analyze.validate_records(altered, self.matrix)

    def test_invalid_timing_rejected(self):
        altered = copy.deepcopy(self.records)
        altered[0]["measurement"]["firstSseSeconds"] = 999
        with self.assertRaisesRegex(ValueError, "Timing order"):
            analyze.validate_records(altered, self.matrix)

    def test_disabled_has_no_thinking(self):
        disabled = [record for record in self.records if record["measurement"]["thinking"] != "adaptive"]
        self.assertEqual(len(disabled), 20)
        self.assertTrue(all(record["response"]["usage"]["output_tokens_details"]["thinking_tokens"] == 0 for record in disabled))

    def test_rendered_pages_match_generator(self):
        for name, content in render_docs.pages(analyze.validate()).items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), content.rstrip() + "\n", name)

    def test_readme_sections_and_no_hidden_results(self):
        for filename, expected in (("README.md", ["Purpose", "Steps", "Results"]), ("README_CN.md", ["目的", "操作步骤", "实现效果"])):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"^## (.+)$", text, re.MULTILINE), expected)
            self.assertNotIn("<details", text)
            self.assertIn("./scripts/run_matrix.ps1", text)

    def test_links_and_images_exist(self):
        for path in list(ROOT.glob("README*.md")) + list((ROOT / "docs").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            links = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'src="([^"]+)"', text)
            for link in links:
                if urlparse(link).scheme or link.startswith("#"):
                    continue
                target = path.parent / unquote(link.split("#", 1)[0])
                self.assertTrue(target.exists(), f"{path.name}: {link}")

    def test_inputs_precede_result_tables(self):
        for path in (ROOT / "docs").glob("results*.md"):
            text = path.read_text(encoding="utf-8")
            for question in self.matrix["questions"]:
                self.assertIn(question, text)
                self.assertLess(text.index(question), text.index("| Model |") if "| Model |" in text else text.index("| 模型 |"))

    def test_public_identity_and_signature_boundary(self):
        forbidden = re.compile(r"[A-Z]:[\\/](?:Users|AI-Super-Agent)[\\/]|@microsoft\.com|https://(?!YOUR-FOUNDRY-RESOURCE\.)[a-z0-9-]+\.(?:services\.ai\.azure\.com|azurecontainerapps\.io|openai\.azure\.com)|\b(?:ghp_[a-z0-9]{20,}|sk-[a-z0-9]{20,})", re.IGNORECASE)
        extensions = {".md", ".py", ".ps1", ".json", ".jsonl", ".yaml", ".svg", ".example"}
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in extensions and "live-runs" not in path.parts and "tests" not in path.parts:
                self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), str(path.relative_to(ROOT)))
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "signature":
                        self.assertIn(child, ("", "[signature omitted]"))
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(self.records)


if __name__ == "__main__":
    unittest.main()