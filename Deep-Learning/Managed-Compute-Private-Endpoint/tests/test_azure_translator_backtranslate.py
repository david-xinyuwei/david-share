import argparse
import importlib.util
import json
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "azure_translator_backtranslate.py"
SPEC = importlib.util.spec_from_file_location("azure_translator_backtranslate", MODULE_PATH)
assert SPEC and SPEC.loader
TRANSLATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSLATOR)


class AzureTranslatorBackTranslationTests(unittest.TestCase):
    def test_extracts_chinese_prose_and_skips_fenced_code(self) -> None:
        markdown = """# 标题

第一段包含 `200`。

```bash
echo 不应翻译
```

| 列 | 值 |
|---|---|
| 状态 | 通过 |
"""
        units = TRANSLATOR.extract_translation_units(markdown)
        text = "\n".join(str(unit["text"]) for unit in units)
        self.assertIn("标题", text)
        self.assertIn("第一段包含 200", text)
        self.assertIn("状态", text)
        self.assertNotIn("不应翻译", text)

    def test_batches_respect_item_and_character_limits(self) -> None:
        units = [
            {"lineStart": index, "lineEnd": index, "text": "中文" * 3}
            for index in range(5)
        ]
        batches = TRANSLATOR.batch_units(units, max_items=2, max_characters=20)
        self.assertEqual([len(batch) for batch in batches], [2, 2, 1])

    def test_numeric_drift_detects_missing_and_added_values(self) -> None:
        self.assertEqual(
            TRANSLATOR.numeric_drift("200 then 403", "200 then 403")["count"],
            0,
        )
        drift = TRANSLATOR.numeric_drift("200 then 403", "200 then 401")
        self.assertEqual(drift["missing"], {"403": 1})
        self.assertEqual(drift["added"], {"401": 1})

    def test_numeric_drift_normalizes_stage_words_and_repetition(self) -> None:
        self.assertEqual(
            TRANSLATOR.numeric_drift(
                "第 2 阶段和五阶段实测；200 重复两次：200。",
                "the second phase of the five-stage run returned 200",
            )["count"],
            0,
        )

    def test_checked_in_evidence_matches_current_readmes(self) -> None:
        evidence_path = TRANSLATOR.DEFAULT_OUTPUT
        if not evidence_path.is_file():
            self.skipTest("Live Azure Translator evidence has not been generated")
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(TRANSLATOR.validate_document(document), [])


if __name__ == "__main__":
    unittest.main()