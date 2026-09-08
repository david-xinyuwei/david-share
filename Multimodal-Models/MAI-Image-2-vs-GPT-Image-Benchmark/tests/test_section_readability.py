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
        "grounding": "### Web Grounding Test",
        "multi_image": "### Multi-Image Input Edit Test",
        "asked": "What we asked the model",
        "controlled": "Controlled variable",
        "determines": "What this section determines",
    },
    "README-CN.md": {
        "grounding": "### 联网信息补充测试",
        "multi_image": "### 多图输入编辑测试",
        "asked": "我们向模型提出的问题",
        "controlled": "受控变量",
        "determines": "要回答什么",
    },
}


def section_text(text, heading, level="### "):
    start = text.index(heading)
    remainder = text[start + len(heading):]
    match = re.search(r"(?m)^#{2,3} ", remainder)
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
            body = section_text(self.documents[name], labels["grounding"])
            for prompt in self.grounding_prompts[:2]:
                self.assertIn(prompt, body, f"{name}: prompt not quoted verbatim")
            self.assertNotIn(self.grounding_prompts[2], body,
                             f"{name}: unselected subject must not be shown")

    def test_multi_image_shows_every_prompt_actually_sent(self):
        prompts = {attempt["prompt"] for attempt in self.multi["attempts"]}
        for name, labels in SECTIONS.items():
            body = section_text(self.documents[name], labels["multi_image"])
            for prompt in prompts:
                self.assertIn(prompt, body, f"{name}: prompt not quoted verbatim")

    def test_input_precedes_the_first_metric_table(self):
        """A reader who cannot see the input cannot judge the number."""
        for name, labels in SECTIONS.items():
            grounding = section_text(self.documents[name], labels["grounding"])
            self.assertIn(labels["asked"], grounding)
            self.assertLess(grounding.index(labels["asked"]), grounding.index("| ---"),
                            f"{name}: metric table appears before the question")
            self.assertLess(grounding.index("```text"), grounding.index("| ---"),
                            f"{name}: metric table appears before the prompt")
            self.assertIn(labels["controlled"], grounding)

            multi = section_text(self.documents[name], labels["multi_image"])
            self.assertIn(labels["determines"], multi)
            self.assertLess(multi.index(labels["determines"]), multi.index("```text"),
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
