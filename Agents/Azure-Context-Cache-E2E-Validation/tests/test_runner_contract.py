from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_official_e2e.ps1"


class RunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNNER.read_text(encoding="utf-8")

    def test_runner_uses_pinned_official_path_and_independent_parser(self) -> None:
        required = (
            "UPSTREAM_LOCK.json",
            "verify_upstream.py",
            "scripts/quickstart.ps1",
            "parse_demo_output.py",
            "PYTHONIOENCODING",
            "ProcessStartInfo",
            "OpenAI.ContextCacheAllowed",
            "AZURE_CONFIG_DIR",
            "-SkipPython",
            "SupportsShouldProcess",
            "Invoke-BoundedProcess",
            "Workspace must be outside the public source tree",
            "Use a new unique resource group",
            "ExistingUpstreamDirectory",
            "--no-input",
            "Demo exited with code",
            "--stderr",
            "manifest.json",
            "process.Kill($true)",
            "process.WaitForExit(5000)",
            "validate_arm_summary.py",
            "verified-upstream",
            "AzureReadTimeoutSeconds",
            "azure-context-cache-e2e.lock",
            "--git-executable",
            "[AllowEmptyString()][AllowEmptyCollection()][string[]] $Arguments",
        )
        for marker in required:
            self.assertIn(marker, self.source)

    def test_runner_does_not_hide_auth_or_preview_onboarding(self) -> None:
        forbidden = (
            "az login",
            "feature register",
            "--api-key",
            "AOAI_API_KEY",
            "Start-Sleep",
        )
        for marker in forbidden:
            self.assertNotIn(marker, self.source)

    def test_runner_contains_no_concrete_cloud_identifier(self) -> None:
        uuid = re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        )
        self.assertIsNone(uuid.search(self.source))

    def test_runner_creates_unique_owned_run_directory(self) -> None:
        self.assertIn("[guid]::NewGuid()", self.source)
        self.assertIn("$RunDirectory", self.source)
        self.assertIn("$VenvDirectory = Join-Path $RunDirectory", self.source)

    def test_runner_preserves_timeout_and_artifact_evidence(self) -> None:
        for marker in (
            "timeoutSeconds",
            "processTerminated",
            "Partial evidence",
            "Get-FileSha256",
            "artifacts = $Artifacts",
            "upstreamQuickstartGitBlobContentSha256",
        ):
            self.assertIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()