"""Tests for the rendered READMEs, diagrams and public-content guards."""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_readme  # noqa: E402
import check_repo  # noqa: E402
import draw_diagrams  # noqa: E402


class ReadmeTests(unittest.TestCase):
    def test_committed_readmes_are_refresh_clean(self):
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            self.assertEqual(build_readme.render(text, lang), text, path.name)

    def test_audit_passes(self):
        self.assertEqual(check_repo.run(), [])

    def test_each_measurement_section_states_its_input_before_its_table(self):
        text = build_readme.READMES["en"].read_text(encoding="utf-8")
        section = text.split("## Measured Results on MI300X", 1)[1].split("\n## ", 1)[0]
        for sub in re.split(r"\n### ", section)[1:5]:
            with self.subTest(section=sub.splitlines()[0]):
                first_table = sub.find("\n| ")
                self.assertGreater(first_table, 0)
                self.assertIn("**Input.**", sub[:first_table])
                self.assertIn("**Boundary.**", sub)

    def test_every_technique_has_a_card_under_its_own_heading(self):
        import json
        cat = json.loads((ROOT / "profiles" / "techniques.json").read_text(encoding="utf-8"))
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            for t in cat["techniques"]:
                with self.subTest(lang=lang, technique=t["id"]):
                    self.assertIn(f"#### {t[lang]}\n\n<!-- BEGIN GENERATED: card-{t['id']} -->", text)

    def test_images_match_ledger(self):
        self.assertEqual(draw_diagrams.main(["--check"]), 0)

    def test_retired_or_private_content_is_rejected(self):
        """Break one guarded fact and confirm the audit turns red."""
        probes = {
            "README.md": "\nThroughput versus H200 was 70%.\n",
            "README_CN.md": "\n客户材料来自小米。\n",
        }
        for name, injected in probes.items():
            with self.subTest(file=name):
                with tempfile.TemporaryDirectory() as tmp:
                    copy = Path(tmp) / ROOT.name
                    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
                    target = copy / name
                    target.write_text(target.read_text(encoding="utf-8") + injected, encoding="utf-8")
                    original_root = check_repo.ROOT
                    try:
                        check_repo.ROOT = copy
                        check_repo.READMES = {"en": copy / "README.md", "cn": copy / "README_CN.md"}
                        errors = check_repo.run()
                    finally:
                        check_repo.ROOT = original_root
                        check_repo.READMES = {"en": original_root / "README.md", "cn": original_root / "README_CN.md"}
                    self.assertTrue(any(e.startswith("FORBIDDEN") for e in errors), errors)

    def test_each_forbidden_category_is_detected(self):
        samples = ["versus A100", "on MI350X", "on MI355X", "SWE-bench Verified", "swebench run", "xiaomi customer", "C:\\Users\\someone\\", "person@example.com", "10.2.3.4",
                   "12345678-1234-1234-1234-123456789abc", "<details>", "from Jessica"]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(any(p.search(sample) for p, _ in check_repo.FORBIDDEN), sample)

    def test_generated_tables_keep_a_constant_column_count(self):
        for lang, path in build_readme.READMES.items():
            errors = []
            check_repo.check_table_shape(lang, path.read_text(encoding="utf-8"), errors)
            self.assertEqual(errors, [])

    def test_accuracy_section_lists_every_lossy_switch_in_both_languages(self):
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            block = text.split("<!-- BEGIN GENERATED: precision-summary -->", 1)[1].split("<!-- END GENERATED: precision-summary -->", 1)[0]
            lossy = [l for l in block.splitlines() if l.startswith("- **")][0]
            block = lossy
            for needle in ("FP8", "INT8 Quick Reduce", "router"):
                self.assertIn(needle, block, (lang, needle))
            self.assertIn("ROCM_QUICK_REDUCE_QUANTIZATION=INT8", text, lang)

    def test_tables_wider_than_four_columns_are_rejected(self):
        wide = "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n"
        errors = []
        check_repo.check_table_shape("en", wide, errors)
        self.assertTrue(any(e.startswith("en: TABLE_TOO_WIDE") for e in errors), errors)

    def test_bilingual_number_mismatch_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / ROOT.name
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
            cn = copy / "README_CN.md"
            cn.write_text(cn.read_text(encoding="utf-8").replace("933.75", "993.75", 1), encoding="utf-8")
            original_root = check_repo.ROOT
            try:
                check_repo.ROOT = copy
                check_repo.READMES = {"en": copy / "README.md", "cn": cn}
                errors = check_repo.run()
            finally:
                check_repo.ROOT = original_root
                check_repo.READMES = {"en": original_root / "README.md", "cn": original_root / "README_CN.md"}
            self.assertTrue(any(e.startswith("BILINGUAL_NUMBERS") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
