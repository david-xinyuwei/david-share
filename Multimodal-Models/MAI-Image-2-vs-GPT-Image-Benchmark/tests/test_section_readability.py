import csv
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GROUNDING_ARCHIVE = ROOT / "data" / "lenovo-web-grounding-20260908"
EDIT_ARCHIVE = ROOT / "data" / "edit-hat-swap-20260909-auto"

SECTIONS = {
    "README.md": {
        "grounding": "## Web Grounding Test",
        "edit": "### Test 12: Headwear Swap (Image Edit)",
        "asked": "What we asked the model",
        "controlled": "Controlled variable",
        "highlights": "## What This Run Shows About MAI-Image-2.6",
        "comparison": "## Side-by-Side Image Comparison",
        "metrics_body": "## Current Run: Both Models and All Quality Tiers",
    },
    "README-CN.md": {
        "grounding": "## 联网信息补充测试",
        "edit": "### Test 12: 换帽子（图像编辑）",
        "asked": "我们向模型提出的问题",
        "controlled": "受控变量",
        "highlights": "## MAI-Image-2.6 在本轮中体现的能力",
        "comparison": "## 并排图片对比",
        "metrics_body": "## 本轮：两模型与全部质量档位",
    },
}


def normalize(prompt):
    """Prompts render as wrapped quote paragraphs, so compare on collapsed whitespace."""
    return " ".join(prompt.split())


def section_text(text, heading):
    """Body of a heading up to the next heading of the same or higher level."""
    start = text.index(heading)
    remainder = text[start + len(heading):]
    level = len(heading) - len(heading.lstrip("#"))
    match = re.search(r"(?m)^#{1,%d} " % level, remainder)
    return remainder[:match.start()] if match else remainder


class SectionReadabilityTests(unittest.TestCase):
    """A section a reader lands on must show the real input before any metric table."""

    @classmethod
    def setUpClass(cls):
        cls.documents = {name: (ROOT / name).read_text("utf-8") for name in SECTIONS}
        with (GROUNDING_ARCHIVE / "source" / "prompts.csv").open(encoding="utf-8-sig",
                                                                newline="") as handle:
            cls.grounding_prompts = [row["prompt"].strip() for row in csv.DictReader(handle)]
        cls.edit = json.loads((EDIT_ARCHIVE / "edit-results.json").read_text("utf-8"))

    def test_grounding_shows_verbatim_prompts_from_the_frozen_csv(self):
        for name, labels in SECTIONS.items():
            body = normalize(section_text(self.documents[name], labels["grounding"]))
            for prompt in self.grounding_prompts[:2]:
                self.assertIn(normalize(prompt), body, f"{name}: prompt not quoted verbatim")
            self.assertNotIn(normalize(self.grounding_prompts[2]), body,
                             f"{name}: unselected subject must not be shown")

    def test_edit_scenario_shows_the_prompt_actually_sent(self):
        for name, labels in SECTIONS.items():
            body = normalize(section_text(self.documents[name], labels["edit"]))
            self.assertIn(normalize(self.edit["prompt"]), body, f"{name}: prompt not quoted verbatim")

    def test_our_own_inputs_and_results_are_never_collapsed(self):
        """External reference material may fold; this project's evidence may not.

        A collapsed block costs the reader a click, which is acceptable for
        borrowed vendor context but not for the prompts, measurements or claim
        boundaries this repository is delivering.
        """
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            for label in ("grounding", "edit"):
                body = section_text(text, labels[label])
                self.assertNotIn("<details", body,
                                 f"{name}: our own measurement section must not be collapsed")
            collapsed = re.findall(r"<details>(.*?)</details>", text, re.S)
            for block in collapsed:
                self.assertNotIn("请求耗时" if name.endswith("CN.md") else "Request latency", block,
                                 f"{name}: our own latency table was hidden in a collapsed block")
                for prompt in self.grounding_prompts[:2] + [self.edit["prompt"]]:
                    self.assertNotIn(normalize(prompt), normalize(block),
                                     f"{name}: our own prompt was hidden in a collapsed block")

    def test_opening_states_capabilities_before_any_measurement_section(self):
        """A reader must learn what the model can do before reading test detail."""
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            self.assertIn(labels["highlights"], text)
            self.assertLess(text.index(labels["highlights"]), text.index(labels["comparison"]))
            opening = section_text(text, labels["highlights"])
            self.assertIn("web_grounding", opening)
            edit_marker = ("第 12 题" if name.endswith("CN.md") else "Scenario 12")
            self.assertIn(edit_marker, opening, f"{name}: edit capability not stated")
            # A sentence that denies a ranking is required; only an asserted ranking is a defect.
            asserted = ((r"(?<!不声称画质)(?<!没有评出)优于", r"毫不逊色", r"(?<!不)领先")
                        if name.endswith("CN.md")
                        else (r"(?<!does not claim MAI image quality )beats", r"outperforms"))
            for pattern in asserted:
                self.assertIsNone(re.search(pattern, opening),
                                  f"{name}: unsupported quality ranking claimed")
            denial = ("不声称画质优于或等同" if name.endswith("CN.md")
                      else "does not claim MAI image quality beats or matches")
            self.assertIn(denial, opening, f"{name}: quality-ranking boundary missing")

    def test_scenarios_then_metrics_then_grounding(self):
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            self.assertLess(text.index(labels["comparison"]), text.index(labels["edit"]))
            self.assertLess(text.index(labels["edit"]), text.index(labels["metrics_body"]),
                            f"{name}: Test 12 must sit with the scenarios, before the metrics body")
            self.assertLess(text.index(labels["metrics_body"]), text.index(labels["grounding"]))

    def test_generated_images_appear_before_the_metrics_body(self):
        """Readers judge generated pictures by seeing them, not by reading timings first."""
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            self.assertIn(labels["metrics_body"], text)
            self.assertLess(text.index(labels["comparison"]), text.index(labels["metrics_body"]),
                            f"{name}: image comparison must precede the metrics body")

    def test_quality_observations_lead_with_countable_outcomes(self):
        """A prose wall is unreadable without the scale of the outcome first."""
        for name in SECTIONS:
            text = self.documents[name]
            heading = ("### 逐场景画面观察" if name.endswith("CN.md") else "### Quality Observations")
            body = section_text(text, heading)
            counted = ("返回图片 / 计划样本" if name.endswith("CN.md") else "Images returned / planned")
            self.assertIn(counted, body, f"{name}: countable summary missing")
            prose_header = ("| 场景 |" if name.endswith("CN.md") else "| Scenario |")
            self.assertIn(prose_header, body, f"{name}: per-scenario table missing")
            self.assertLess(body.index(counted), body.index(prose_header),
                            f"{name}: prose table appears before the countable summary")

    def test_input_precedes_the_first_metric_table(self):
        """A reader who cannot see the input cannot judge the number."""
        for name, labels in SECTIONS.items():
            grounding = section_text(self.documents[name], labels["grounding"])
            self.assertIn(labels["asked"], grounding)
            self.assertLess(grounding.index(labels["asked"]), grounding.index("| ---"),
                            f"{name}: metric table appears before the question")
            self.assertLess(grounding.index("\n> "), grounding.index("| ---"),
                            f"{name}: metric table appears before the prompt")
            self.assertIn(labels["controlled"], grounding)

            edit = section_text(self.documents[name], labels["edit"])
            self.assertLess(edit.index("\n> "), edit.index("| ---"),
                            f"{name}: Test 12 table appears before its prompt")
            self.assertLess(edit.index(labels["controlled"]), edit.index("| ---"),
                            f"{name}: Test 12 table appears before the controlled variables")

    def test_edit_scenario_states_what_a_departure_means(self):
        """The conclusion rests on 'preserve the input'; the text must say so."""
        for name, labels in SECTIONS.items():
            edit = section_text(self.documents[name], labels["edit"])
            marker = ("要求保持原图" if name.endswith("CN.md") else "asked to preserve the input")
            self.assertIn(marker, edit, f"{name}: preservation criterion not stated")
            alpha = ("alpha 通道" if name.endswith("CN.md") else "alpha channel")
            self.assertIn(alpha, edit, f"{name}: output channel boundary not stated")

    def test_named_subjects_carry_human_readable_labels(self):
        for name, labels in SECTIONS.items():
            edit = section_text(self.documents[name], labels["edit"])
            for label in (("输入图", "MAI-Image-2.6", "GPT-Image-2 high") if name.endswith("CN.md")
                          else ("Input", "MAI-Image-2.6", "GPT-Image-2 high")):
                self.assertIn(label, edit, f"{name}: readable column label missing")
            self.assertNotIn("prompt_idx", edit)

    def test_input_artifact_is_identified_by_hash(self):
        for name, labels in SECTIONS.items():
            edit = section_text(self.documents[name], labels["edit"])
            self.assertIn("SHA-256", edit, f"{name}: input image hash missing")


if __name__ == "__main__":
    unittest.main()
