"""Rendered READMEs, figures and public-content guards, including deliberate breaks that must fail."""
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

SECTION = {"en": "## Validation on One H100 VM", "cn": "## 单台 H100 VM 上的实测验证"}
LABELS = {"en": ("**Question.**", "**Input.**", "**Result.**", "**Boundary.**"),
          "cn": ("**问题。**", "**输入。**", "**结果。**", "**边界。**")}
RUN_IDS = ("validation-1", "replay-1", "configure-2", "jobs-1", "auth-1")


def _audit_copy(edit) -> list[str]:
    """Run the audit on a temporary copy after `edit(copy_root)`."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / ROOT.name
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
        edit(copy)
        saved = check_repo.ROOT, check_repo.READMES
        try:
            check_repo.ROOT = copy
            check_repo.READMES = {"en": copy / "README.md", "cn": copy / "README_CN.md"}
            return check_repo.run()
        finally:
            check_repo.ROOT, check_repo.READMES = saved


class ReadmeTests(unittest.TestCase):
    def test_committed_readmes_are_refresh_clean(self):
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            self.assertEqual(build_readme.render(text, lang), text, path.name)

    def test_audit_passes(self):
        self.assertEqual(check_repo.run(), [])

    def test_each_run_states_question_and_input_before_results_and_a_boundary(self):
        for lang, path in build_readme.READMES.items():
            section = path.read_text(encoding="utf-8").split(SECTION[lang], 1)[1].split("\n## ", 1)[0]
            runs = [s for s in re.split(r"\n### ", section)[1:] if re.match(r"[a-z]+-\d+", s)]
            self.assertEqual([re.match(r"[a-z]+-\d+", s).group(0) for s in runs], list(RUN_IDS), lang)
            for sub in runs:
                with self.subTest(lang=lang, run=sub.splitlines()[0]):
                    question, inp, result, boundary = LABELS[lang]
                    self.assertIn(result, sub)
                    head = sub[:sub.index(result)]
                    self.assertIn(question, head)
                    self.assertIn(inp, head)
                    self.assertNotIn("\n| ", head, "a table before the result")
                    self.assertIn(boundary, sub[sub.index(result):])

    def test_configuration_steps_show_the_script_commands(self):
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            for needle in ("./scripts/configure.sh -c gpu-hours.env -p", "./scripts/configure.sh -c gpu-hours.env\n",
                           "./scripts/configure.sh -c gpu-hours.env -v", "cp scripts/gpu-hours.env.example gpu-hours.env",
                           "az monitor data-collection rule create", "az monitor data-collection rule association create",
                           "az vm extension set", "az monitor log-analytics query", "dcgmi dmon -e",
                           "env AZUREML_RUN_ID=", "mpirun -x AZUREML_RUN_ID", "docker run -e AZUREML_RUN_ID"):
                with self.subTest(lang=lang, needle=needle):
                    self.assertIn(needle, text)

    def test_configure_section_documents_every_setting_and_exit_code(self):
        settings = re.findall(r"^([A-Z_]+)=", (ROOT / "scripts" / "gpu-hours.env.example").read_text(encoding="utf-8"), re.M)
        script = (ROOT / "scripts" / "configure.sh").read_text(encoding="utf-8")
        codes = sorted({int(c) for c in re.findall(r'die "[^"]*" (\d)', script)} | {1})
        heading = {"en": ("## Configure on Azure", "## Query from Your Platform"), "cn": ("## 在 Azure 上配置", "## 从客户平台查询")}
        for lang, path in build_readme.READMES.items():
            start, end = heading[lang]
            section = path.read_text(encoding="utf-8").split(start, 1)[1].split(end, 1)[0]
            for name in settings:
                with self.subTest(lang=lang, setting=name):
                    self.assertTrue(f"`{name}`" in section, f"{name} is not documented")
            for code in [0, *codes]:
                with self.subTest(lang=lang, exit_code=code):
                    self.assertTrue(re.search(rf"\n\| {code} \|", section), f"exit code {code} is not documented")

    def test_images_match_ledger(self):
        self.assertEqual(draw_diagrams.main(["--check"]), 0)

    def test_retired_files_are_gone(self):
        for rel in ("README-CN.md", "webui", "images/architecture.png", "images/metrics.png",
                    "images/dashboard-webui.png", "images/dashboard-charts.png", "azure/queries.kql",
                    "QUICKSTART.md", "QUICKSTART_CN.md"):
            self.assertFalse((ROOT / rel).exists(), rel)


class GuardTests(unittest.TestCase):
    def test_private_content_in_a_readme_is_rejected(self):
        for probe in ("\nThe VM was sungrow-122b-node0.\n", "\nworkspace 12345678-1234-1234-1234-123456789abc\n",
                      "\nrun as azureuser\n"):
            with self.subTest(probe=probe.strip()):
                errors = _audit_copy(lambda c: (c / "README.md").write_text(
                    (c / "README.md").read_text(encoding="utf-8") + probe, encoding="utf-8"))
                self.assertTrue(any(e.startswith("FORBIDDEN") for e in errors), errors)

    def test_each_forbidden_category_is_detected(self):
        samples = ["GeekPlus", "极智嘉", "rg-geekplus-gpuhours-demo", "trainer-a", "from Kurt", "C:\\Users\\someone\\",
                   "person@example.com", "10.2.3.4", "12345678-1234-1234-1234-123456789abc", "<details>",
                   "run of 2026-05-08", "stage-20260713", "in September", "9 月 28 日", "see README-CN.md",
                   "open the Workbook", "webui/app.py", "see QUICKSTART_CN.md", "configure-1"]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(any(p.search(sample) for p, _ in check_repo.FORBIDDEN), sample)
        for allowed in ("http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01", "gpu-vm-1", "user-2"):
            with self.subTest(allowed=allowed):
                self.assertFalse(any(p.search(allowed) for p, _ in check_repo.FORBIDDEN), allowed)

    def test_bilingual_number_mismatch_is_detected(self):
        def edit(c):
            cn = c / "README_CN.md"
            cn.write_text(cn.read_text(encoding="utf-8").replace("| 8 |", "| 9 |", 1), encoding="utf-8")
        errors = _audit_copy(edit)
        self.assertTrue(any(e.startswith("BILINGUAL_NUMBERS") for e in errors), errors)

    def test_heading_order_is_enforced(self):
        def edit(c):
            en = c / "README.md"
            en.write_text(en.read_text(encoding="utf-8").replace("## Configure on Azure", "## Setup"), encoding="utf-8")
        errors = _audit_copy(edit)
        self.assertTrue(any("HEADING_ORDER" in e for e in errors), errors)

    def test_tables_wider_than_four_columns_are_rejected(self):
        errors = []
        check_repo.check_table_shape("en", "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n", errors)
        self.assertTrue(any(e.startswith("en: TABLE_TOO_WIDE") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
