"""Layout gates on the rendered files and the delivered tree.

These encode the SOP-94 rules that were being checked by hand and therefore drifted: an
in-document anchor that resolves nowhere, a directory nobody references, and content from a
model this report does not compare.
"""
import re
import unicodedata
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("README.md", "README_CN.md")
# Retired with the 2026-04 five-way run (mai-image-2, mai-image-2e, gpt-image-1.5) and the vendor
# charts: none of those objects is compared here, so a later regeneration must not bring them back.
# The one PNG two tests needed as a real image now lives in tests/fixtures/.
RETIRED_PATHS = ("images", "assets", "scripts/benchmark_5way.py",
                 "data/5way_benchmark_results.json", "data/5way_v2_results.json")
# Prose tokens are narrower than tree paths on purpose: a bare "images/" also matches the API
# endpoint `/images/generations`, which is not retired material.
RETIRED_MENTIONS = ("images/gpt-image-1.5", "images/mai-image-2", "assets/official-microsoft-ai",
                    "scripts/benchmark_5way.py", "data/5way_", "gpt-image-1.5", "mai-image-2e")
REQUIRED_SECTIONS = {
    "README.md": ["## Start Here", "## Which Model and Which Tier", "## What This Repository Delivers",
                  "## Architecture and Test Topology", "## Reproduction", "## Tests and Offline Checks",
                  "## Limits and Boundaries", "## Assets and Evidence"],
    "README_CN.md": ["## 从哪里开始", "## 选哪个模型和哪个档位", "## 本仓库交付什么",
                     "## 架构与测试拓扑", "## 客户复现", "## 测试与离线核验",
                     "## 结论边界", "## 仓库资产与证据"],
}


def slug(heading):
    text = re.sub(r"[`*\[\]()]", "", heading).strip().lower()
    return "".join(c if (c.isalnum() or c in "-_" or unicodedata.category(c).startswith("Lo")) else
                   ("-" if c in " \t" else "") for c in text)


def delivered_entries():
    """What a customer sees after cloning this directory, ignoring build artefacts."""
    ignored = {"__pycache__", ".git", ".pytest_cache"}
    return sorted(p.name for p in ROOT.iterdir() if p.name not in ignored)


class LayoutGateTests(unittest.TestCase):
    def test_every_in_document_anchor_resolves_to_a_heading(self):
        """A navigation link must work in any Markdown renderer, not only through GitHub's rewrite."""
        for name in DOCUMENTS:
            text = (ROOT / name).read_text("utf-8")
            headings = {slug(h) for h in re.findall(r"(?m)^#{1,6} (.+)$", text)}
            explicit = set(re.findall(r'<a id="([^"]+)"', text))
            for anchor in sorted(set(re.findall(r"\]\(#([^)]+)\)", text))):
                with self.subTest(document=name, anchor=anchor):
                    self.assertIn(anchor, headings | explicit, f"{name}: #{anchor} matches no heading")

    def test_the_mandatory_reader_sections_exist(self):
        for name, required in REQUIRED_SECTIONS.items():
            text = (ROOT / name).read_text("utf-8")
            for heading in required:
                with self.subTest(document=name, heading=heading):
                    self.assertIn(f"\n{heading}\n", text, f"{name}: missing {heading}")

    def test_architecture_and_topology_are_two_separate_diagrams(self):
        for name in DOCUMENTS:
            text = (ROOT / name).read_text("utf-8")
            start = text.index("## Architecture and Test Topology" if name == "README.md" else "## 架构与测试拓扑")
            section = text[start:text.index("\n## ", start + 10)]
            self.assertEqual(section.count("```mermaid"), 2, f"{name}: call path and measured topology must be separate")

    def test_reproduction_installs_from_the_pinned_requirements(self):
        pinned = (ROOT / "requirements.txt").read_text("utf-8")
        self.assertIn("requests==", pinned)
        self.assertIn("pillow==", pinned)
        for name in DOCUMENTS:
            text = (ROOT / name).read_text("utf-8")
            self.assertIn("pip install -r requirements.txt", text, name)
            self.assertNotIn("pip install requests pillow", text, name)

    def test_every_documented_step_can_name_its_model_version(self):
        """Step 2's metadata sample must cover every deployment a later step tells the reader to run."""
        for name in DOCUMENTS:
            text = (ROOT / name).read_text("utf-8")
            # `--gpt-model <deployment>[:tiers]`; the deployment name itself contains hyphens and dots.
            for argument in re.findall(r"--gpt-model ([^\s]+)", text):
                deployment = argument.split(":")[0]
                with self.subTest(document=name, deployment=deployment):
                    self.assertIn(f'"{deployment}":', text,
                                  f"{name}: {deployment} is run but has no model version in step 2")

    def test_retired_material_is_absent_from_the_tree_and_the_documents(self):
        for retired in RETIRED_PATHS:
            with self.subTest(path=retired):
                self.assertFalse((ROOT / retired).exists(), f"{retired} is still in the delivered tree")
        # In prose, only a path-shaped or model-shaped mention counts.
        for token in RETIRED_MENTIONS:
            for name in DOCUMENTS:
                with self.subTest(token=token, document=name):
                    self.assertNotIn(token, (ROOT / name).read_text("utf-8"),
                                     f"{name} still refers to retired material {token}")

    def test_every_delivered_script_is_named_by_the_readme(self):
        """An untracked helper swept in by `git add -A -- scripts` ships silently otherwise (2026-09-22)."""
        described = (ROOT / "README.md").read_text("utf-8")
        for script in sorted((ROOT / "scripts").glob("*.py")):
            with self.subTest(script=script.name):
                self.assertIn(f"scripts/{script.name}", described,
                              f"{script.name} is delivered but the README never names it")

    def test_every_top_level_entry_is_described_by_the_readme(self):
        """SOP-94 L9: a delivered directory nobody references is an undocumented repository entry."""
        described = (ROOT / "README.md").read_text("utf-8")
        for name in delivered_entries():
            if name in {"README.md", "README_CN.md", ".gitignore"}:
                continue
            with self.subTest(entry=name):
                token = f"`{name}/`" if (ROOT / name).is_dir() else f"`{name}`"
                self.assertIn(token, described, f"{name} is delivered but the README never says what it is")


if __name__ == "__main__":
    unittest.main()
