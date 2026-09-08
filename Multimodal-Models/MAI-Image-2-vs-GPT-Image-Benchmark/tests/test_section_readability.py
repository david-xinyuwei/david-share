import csv
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GROUNDING_ARCHIVE = ROOT / "data" / "lenovo-web-grounding-20260908"
MULTI_IMAGE_ARCHIVE = ROOT / "data" / "mai-multi-image-edit-20260908"

SECTIONS = {
    "README.md": {
        "grounding": "## Web Grounding Test",
        "multi_image": "## Multi-Image Input Edit Test",
        "asked": "What we asked the model",
        "controlled": "Controlled variable",
        "determines": "What this section determines",
        "highlights": "## What This Run Shows About MAI-Image-2.6",
        "comparison": "## Side-by-Side Image Comparison",
    },
    "README-CN.md": {
        "grounding": "## 联网信息补充测试",
        "multi_image": "## 多图输入编辑测试",
        "asked": "我们向模型提出的问题",
        "controlled": "受控变量",
        "determines": "要回答什么",
        "highlights": "## MAI-Image-2.6 在本轮中体现的能力",
        "comparison": "## 并排图片对比",
    },
}


def normalize(prompt):
    """Prompts render as wrapped quote paragraphs, so compare on collapsed whitespace."""
    return " ".join(prompt.split())


def section_text(text, heading):
    start = text.index(heading)
    remainder = text[start + len(heading):]
    match = re.search(r"(?m)^## ", remainder)
    return remainder[:match.start()] if match else remainder


class SectionReadabilityTests(unittest.TestCase):
    """A section a reader lands on must show the real input before any metric table."""

    @classmethod
    def setUpClass(cls):
        cls.documents = {name: (ROOT / name).read_text("utf-8") for name in SECTIONS}
        with (GROUNDING_ARCHIVE / "source" / "prompts.csv").open(encoding="utf-8-sig",
                                                                newline="") as handle:
            cls.grounding_prompts = [row["prompt"].strip() for row in csv.DictReader(handle)]
        cls.multi = json.loads((MULTI_IMAGE_ARCHIVE / "clean-results.json").read_text("utf-8"))

    def test_grounding_shows_verbatim_prompts_from_the_frozen_csv(self):
        for name, labels in SECTIONS.items():
            body = normalize(section_text(self.documents[name], labels["grounding"]))
            for prompt in self.grounding_prompts[:2]:
                self.assertIn(normalize(prompt), body, f"{name}: prompt not quoted verbatim")
            self.assertNotIn(normalize(self.grounding_prompts[2]), body,
                             f"{name}: unselected subject must not be shown")

    def test_multi_image_shows_every_prompt_actually_sent(self):
        prompts = {attempt["prompt"] for attempt in self.multi["attempts"]}
        for name, labels in SECTIONS.items():
            body = normalize(section_text(self.documents[name], labels["multi_image"]))
            for prompt in prompts:
                self.assertIn(normalize(prompt), body, f"{name}: prompt not quoted verbatim")

    def test_our_own_inputs_and_results_are_never_collapsed(self):
        """External reference material may fold; this project's evidence may not.

        A collapsed block costs the reader a click, which is acceptable for
        borrowed vendor context but not for the prompts, measurements or claim
        boundaries this repository is delivering.
        """
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            for label in ("grounding", "multi_image"):
                body = section_text(text, labels[label])
                self.assertNotIn("<details", body,
                                 f"{name}: our own measurement section must not be collapsed")
            collapsed = re.findall(r"<details>(.*?)</details>", text, re.S)
            for block in collapsed:
                self.assertNotIn("请求耗时" if name.endswith("CN.md") else "Request latency", block,
                                 f"{name}: our own latency table was hidden in a collapsed block")
                for prompt in self.grounding_prompts[:2]:
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
            for marker in (("1 to 5 image files",) if not name.endswith("CN.md")
                           else ("1 to 5 image files",)):
                self.assertIn(marker, opening, f"{name}: multi-image capability not stated")
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

    def test_measurement_sections_follow_the_image_comparison(self):
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            self.assertLess(text.index(labels["comparison"]), text.index(labels["grounding"]))
            self.assertLess(text.index(labels["grounding"]), text.index(labels["multi_image"]))

    def test_generated_images_appear_before_the_metrics_body(self):
        """Readers judge generated pictures by seeing them, not by reading timings first."""
        for name, labels in SECTIONS.items():
            text = self.documents[name]
            metrics_body = ("## 本轮：两模型与全部质量档位" if name.endswith("CN.md")
                            else "## Current Run: Both Models and All Quality Tiers")
            self.assertIn(metrics_body, text)
            self.assertLess(text.index(labels["comparison"]), text.index(metrics_body),
                            f"{name}: image comparison must precede the metrics body")

    def test_quality_observations_lead_with_countable_outcomes(self):
        """A prose wall is unreadable without the scale of the outcome first."""
        for name in SECTIONS:
            text = self.documents[name]
            heading = ("### 逐场景画面观察" if name.endswith("CN.md") else "### Quality Observations")
            body = text[text.index(heading):]
            body = body[:body.index("\n### ", 4)] if "\n### " in body[4:] else body
            counted = ("返回图片 / 计划样本" if name.endswith("CN.md") else "Images returned / planned")
            self.assertIn(counted, body, f"{name}: countable summary missing")
            prose_marker = ("以下为逐场景画面差异描述" if name.endswith("CN.md")
                            else "The per-scenario descriptions follow")
            self.assertLess(body.index(counted), body.index(prose_marker),
                            f"{name}: prose appears before the countable summary")

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

            multi = section_text(self.documents[name], labels["multi_image"])
            self.assertIn(labels["determines"], multi)
            self.assertLess(multi.index(labels["determines"]), multi.index("\n> "),
                            f"{name}: prompt appears before the question")

    def test_terminology_a_conclusion_depends_on_is_explained(self):
        for name, labels in SECTIONS.items():
            multi = section_text(self.documents[name], labels["multi_image"])
            self.assertIn("429", multi)
            explanation = ("配额" if name.endswith("CN.md") else "quota")
            quota_at = multi.index("429")
            self.assertIn(explanation, multi[:quota_at + 400],
                          f"{name}: 429 used before explaining it is a quota refusal")
            alpha = ("alpha 通道" if name.endswith("CN.md") else "alpha channel")
            self.assertIn(alpha, multi, f"{name}: cutout distinction not stated")

    def test_named_subjects_carry_human_readable_labels(self):
        for name, labels in SECTIONS.items():
            multi = section_text(self.documents[name], labels["multi_image"])
            for label in (("深色配色信息图", "浅色规格信息图") if name.endswith("CN.md")
                          else ("colour-lineup infographic", "specification infographic")):
                self.assertIn(label, multi, f"{name}: input image lacks a readable label")
            self.assertNotIn("prompt_idx", multi)

    def test_reused_artifacts_declare_their_provenance(self):
        for name, labels in SECTIONS.items():
            multi = section_text(self.documents[name], labels["multi_image"])
            marker = ("不是官方素材" if name.endswith("CN.md") else "not official assets")
            self.assertIn(marker, multi, f"{name}: reused input provenance missing")


if __name__ == "__main__":
    unittest.main()
