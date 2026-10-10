"""Rendered READMEs, figures and public-content guards, including deliberate breaks that must fail."""
import json
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

    def test_three_sections_in_reader_order(self):
        for lang, path in build_readme.READMES.items():
            heads = [h for level, h in check_repo.headings(path.read_text(encoding="utf-8")) if level == 2]
            self.assertEqual(heads, check_repo.READER_ORDER[lang])

    def test_steps_show_the_customer_commands(self):
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            for needle in ("cp scripts/gpu-hours.env.example gpu-hours.env", "./scripts/configure.sh -c gpu-hours.env -p",
                           "./scripts/configure.sh -c gpu-hours.env\n", "./scripts/configure.sh -c gpu-hours.env -v",
                           "env AZUREML_RUN_ID=", "mpirun -x AZUREML_RUN_ID", "docker run -e AZUREML_RUN_ID",
                           "./scripts/deploy-workbook.sh", "./scripts/create-query-identity.sh", "./scripts/query-gpu-hours.sh",
                           "api.loganalytics.azure.com/v1/workspaces/", "./scripts/offboard-vm.sh", "./scripts/remove-workspace.sh",
                           "systemctl enable --now nvidia-dcgm"):
                with self.subTest(lang=lang, needle=needle):
                    self.assertIn(needle, text)

    def test_steps_document_every_setting_and_exit_code(self):
        settings = re.findall(r"^([A-Z_]+)=", (ROOT / "scripts" / "gpu-hours.env.example").read_text(encoding="utf-8"), re.M)
        script = (ROOT / "scripts" / "configure.sh").read_text(encoding="utf-8")
        codes = sorted({int(c) for c in re.findall(r'die "[^"]*" (\d)', script)} | {0, 1})
        for lang, path in build_readme.READMES.items():
            steps = check_repo.READER_ORDER[lang][1]
            section = path.read_text(encoding="utf-8").split(f"## {steps}", 1)[1].split("\n## ", 1)[0]
            for name in settings:
                with self.subTest(lang=lang, setting=name):
                    self.assertIn(f"`{name}`", section)
            for code in codes:
                with self.subTest(lang=lang, exit_code=code):
                    self.assertRegex(section, rf"\n\| {code} \|")

    def test_commands_use_variables_and_no_secret(self):
        for lang, path in build_readme.READMES.items():
            commands = "\n".join(re.findall(r"```(?:bash|http)\n(.*?)```", path.read_text(encoding="utf-8"), re.S))
            for placeholder in ("<vm-rg>", "<vm-name>", "<workspace-guid>", "<principal-id>", "-g rg-gpu-hours", "-n law-gpu-hours"):
                with self.subTest(lang=lang, placeholder=placeholder):
                    self.assertNotIn(placeholder, commands)
            self.assertNotRegex(commands, r"AZURE_CLIENT_SECRET=\S")

    def test_every_measured_run_is_in_the_results(self):
        runs = json.loads((ROOT / "evidence" / "runs.json").read_text(encoding="utf-8"))["runs"]
        for lang, path in build_readme.READMES.items():
            text = path.read_text(encoding="utf-8")
            for run in runs:
                with self.subTest(lang=lang, run=run):
                    self.assertIn(f"`{run}`", text)

    def test_every_image_is_shown_and_every_shown_image_exists(self):
        shown = set()
        for path in build_readme.READMES.values():
            shown |= set(re.findall(r'src="images/([^"]+)"', path.read_text(encoding="utf-8")))
        stored = {p.name for p in (ROOT / "images").glob("*.png")}
        self.assertEqual(stored, shown, "an image is not shown in a README, or a README shows a missing image")

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
                   "webui/app.py", "see QUICKSTART_CN.md", "configure-1"]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(any(p.search(sample) for p, _ in check_repo.FORBIDDEN), sample)
        for allowed in ("http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01", "gpu-vm-1", "user-2",
                        "azure/workbook.json"):
            with self.subTest(allowed=allowed):
                self.assertFalse(any(p.search(allowed) for p, _ in check_repo.FORBIDDEN), allowed)

    def test_customer_names_are_detected_without_being_published(self):
        """The guard stores only SHA-256 prefixes; prove it fires on a token whose prefix is registered."""
        import hashlib
        probe = "probe-name-" + "x" * 8
        saved = set(check_repo.PRIVATE_TOKEN_SHA256)
        try:
            check_repo.PRIVATE_TOKEN_SHA256.add(hashlib.sha256(probe.encode()).hexdigest()[:16])
            self.assertEqual(check_repo.private_tokens(f"az vm list -g {probe.upper()}"), [probe.upper()])
            self.assertEqual(check_repo.private_tokens("az vm list -g rg-gpu-hours"), [])
        finally:
            check_repo.PRIVATE_TOKEN_SHA256.clear()
            check_repo.PRIVATE_TOKEN_SHA256.update(saved)
        self.assertGreaterEqual(len(check_repo.PRIVATE_TOKEN_SHA256), 6)

    def test_bilingual_number_mismatch_is_detected(self):
        def edit(c):
            cn = c / "README_CN.md"
            cn.write_text(cn.read_text(encoding="utf-8").replace("0.067", "0.068", 1), encoding="utf-8")
        errors = _audit_copy(edit)
        self.assertTrue(any(e.startswith("BILINGUAL_NUMBERS") for e in errors), errors)

    def test_heading_order_is_enforced(self):
        def edit(c):
            en = c / "README.md"
            en.write_text(en.read_text(encoding="utf-8").replace("## Steps", "## Setup"), encoding="utf-8")
        errors = _audit_copy(edit)
        self.assertTrue(any("HEADING_ORDER" in e for e in errors), errors)

    def test_tables_wider_than_four_columns_are_rejected(self):
        errors = []
        check_repo.check_table_shape("en", "| a | b | c | d | e |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n", errors)
        self.assertTrue(any(e.startswith("en: TABLE_TOO_WIDE") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
