from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_public_content", ROOT / "scripts" / "audit_public_content.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PublicBoundaryTests(unittest.TestCase):
    def scan(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.md").write_text(text, encoding="utf-8")
            return MODULE.findings(root)

    def test_safe_placeholders_are_allowed(self) -> None:
        self.assertEqual(
            self.scan("YOUR-SUBSCRIPTION-ID https://<your-account>.openai.azure.com"),
            [],
        )

    def test_concrete_cloud_and_identity_values_are_rejected(self) -> None:
        uuid = "00000000-0000-" + "4000-8000-" + "000000000000"
        samples = (
            uuid,
            "C:" + r"\Users\someone\project",
            "person@" + "microsoft.com",
            "/subscriptions/" + uuid + "/resourceGroups/rg",
            "sk-" + "x" * 30,
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(self.scan(sample))

    def test_common_token_and_azure_secret_formats_are_rejected(self) -> None:
        samples = (
            "github_pat_" + "x" * 40,
            "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20,
            "AccountKey=" + "A" * 64,
            "https://example.invalid/?sv=1&sig=" + "A" * 40,
        )
        for sample in samples:
            with self.subTest(sample=sample[:20]):
                self.assertTrue(self.scan(sample))

    def test_non_utf8_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.md").write_bytes(b"github_pat_" + b"x" * 10 + b"\xff" + b"x" * 30)

            self.assertTrue(
                any("not valid UTF-8" in item for item in MODULE.findings(root))
            )

    def test_same_named_audit_script_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (nested / "audit_public_content.py").write_text(
                "token = 'github_pat_" + "x" * 40 + "'\n",
                encoding="utf-8",
            )

            self.assertTrue(
                any("GitHub fine-grained token" in item for item in MODULE.findings(root))
            )

    def test_symlink_or_reparse_point_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "public"
            target = base / "outside"
            root.mkdir()
            target.mkdir()
            (target / "sample.md").write_text("safe", encoding="utf-8")
            link = root / "linked"
            if os.name == "nt":
                created = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if created.returncode:
                    self.fail(f"unable to create test junction: {created.stderr}")
            else:
                link.symlink_to(target, target_is_directory=True)

            self.assertTrue(
                any("symlink or reparse point" in item for item in MODULE.findings(root))
            )


if __name__ == "__main__":
    unittest.main()