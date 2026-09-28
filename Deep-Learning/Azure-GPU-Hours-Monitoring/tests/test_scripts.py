"""Shell scripts: syntax, strict mode, rule-file placeholder and referenced files."""
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted([*ROOT.glob("scripts/*.sh"), *ROOT.glob("vm/*.sh"), *ROOT.glob("tests/load/*.sh")])


def _bash():
    """A real bash. On Windows, System32\\bash.exe is the WSL launcher, so use Git for Windows' bash."""
    if os.name == "nt":
        for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
            if Path(candidate).is_file():
                return candidate
        return None
    return shutil.which("bash")


class ScriptTests(unittest.TestCase):
    def test_strict_mode_and_lf(self):
        for path in SCRIPTS:
            data = path.read_bytes()
            with self.subTest(script=path.name):
                self.assertNotIn(b"\r\n", data, "CRLF line endings break bash on Linux")
                self.assertRegex(data.decode("utf-8").splitlines()[0], r"^#!/(usr/bin/env bash|bin/bash)$")
                self.assertIn("set -euo pipefail", data.decode("utf-8"))

    @unittest.skipUnless(_bash(), "bash not available")
    def test_bash_syntax(self):
        for path in SCRIPTS:
            with self.subTest(script=path.name):
                res = subprocess.run([_bash(), "-n", path.name], cwd=path.parent, capture_output=True, text=True,
                                     encoding="utf-8")
                self.assertEqual(res.returncode, 0, res.stderr)

    def test_rule_file_has_one_workspace_placeholder_that_setup_replaces(self):
        rule = (ROOT / "azure" / "dcr-rule.json").read_text(encoding="utf-8")
        self.assertEqual(rule.count("__WORKSPACE_RESOURCE_ID__"), 1)
        self.assertIn("s#__WORKSPACE_RESOURCE_ID__#", (ROOT / "scripts" / "setup-workspace.sh").read_text(encoding="utf-8"))

    def test_referenced_repository_files_exist(self):
        for path in SCRIPTS:
            for rel in re.findall(r"\$HERE/((?:\.\./)?[\w./-]+\.(?:py|sh|json))", path.read_text(encoding="utf-8")):
                with self.subTest(script=path.name, file=rel):
                    self.assertTrue((path.parent / rel).resolve().is_file(), rel)


class StorageTests(unittest.TestCase):
    """The repository root sends *.json through Git LFS; a clone without git-lfs must still get real JSON."""

    def test_json_files_are_real_json(self):
        import json
        for path in ROOT.rglob("*.json"):
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                self.assertFalse(text.startswith("version https://git-lfs"), "stored as a Git LFS pointer")
                json.loads(text)

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_json_files_are_not_routed_through_lfs(self):
        files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.json")]
        res = subprocess.run(["git", "check-attr", "filter", "--", *files], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8")
        if res.returncode != 0:
            self.skipTest("not a git checkout")
        self.assertNotIn("filter: lfs", res.stdout)


if __name__ == "__main__":
    unittest.main()
