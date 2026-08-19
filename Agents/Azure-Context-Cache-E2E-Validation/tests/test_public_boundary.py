from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()