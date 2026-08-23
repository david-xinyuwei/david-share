from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_official_e2e.ps1"
SUBSCRIPTION_ID = "11111111-1111-" + "4111-8111-" + "111111111111"

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def runner_message(completed: subprocess.CompletedProcess[str]) -> str:
    """Flatten runner output so message assertions survive PowerShell formatting.

    PowerShell renders a terminating error inside a bordered "Line |" block. That
    block adds ANSI colour codes, hard-wraps the message at the console width, and
    prefixes each continuation row with a "|" gutter. A single sentence can therefore
    arrive as "Complete preview | onboarding first.", which defeats a plain substring
    assertion even though the runner behaved correctly.

    Remove the colour codes, drop the gutter characters, and collapse whitespace so
    the assertions test the runner's message rather than the terminal geometry.
    """
    combined = _ANSI.sub("", completed.stderr + completed.stdout)
    without_gutter = combined.replace("|", " ")
    return re.sub(r"\s+", " ", without_gutter)


FAKE_AZ = r'''from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
log = os.environ.get("FAKE_AZ_LOG")
if log:
    with Path(log).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(args) + "\n")
time.sleep(float(os.environ.get("FAKE_AZ_DELAY", "0")))

if args[:2] == ["account", "show"]:
    payload = {"id": os.environ["FAKE_SUBSCRIPTION_ID"], "state": "Enabled"}
elif args[:2] == ["provider", "show"]:
    payload = {"registrationState": os.environ.get("FAKE_PROVIDER_STATE", "Registered")}
elif args[:2] == ["feature", "show"]:
    payload = {"properties": {"state": os.environ.get("FAKE_FEATURE_STATE", "Registered")}}
elif args[:2] == ["group", "exists"]:
    payload = os.environ.get("FAKE_RG_EXISTS", "false").casefold() == "true"
else:
    print(f"unexpected fake az arguments: {args}", file=sys.stderr)
    raise SystemExit(2)
print(json.dumps(payload))
'''


@unittest.skipUnless(
    os.name == "nt"
    and sys.version_info[:2] == (3, 11)
    and platform.machine() in {"AMD64", "x86_64"},
    "PowerShell behavior tests require the supported CPython 3.11 AMD64 runtime",
)
class RunnerBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.config = self.root / "azure-config"
        self.config.mkdir()
        self.workspace = self.root / "workspace"
        self.temp = self.root / "temp"
        self.temp.mkdir()
        self.log = self.root / "fake-az.jsonl"
        (self.bin / "fake_az.py").write_text(FAKE_AZ, encoding="utf-8")
        (self.bin / "az.cmd").write_text(
            f'@echo off\r\n"{sys.executable}" "%~dp0fake_az.py" %*\r\n',
            encoding="ascii",
        )
        self.pwsh = shutil.which("pwsh")
        if not self.pwsh:
            self.skipTest("pwsh is not available")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_runner(
        self,
        *,
        resource_group: str = "rg_context_cache",
        location: str = "centralus",
        extra: tuple[str, ...] = (),
        delay: int = 0,
        resource_group_exists: bool = False,
        provider_state: str = "Registered",
        feature_state: str = "Registered",
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "AZURE_CONFIG_DIR": str(self.config),
                "FAKE_AZ_LOG": str(self.log),
                "FAKE_AZ_DELAY": str(delay),
                "FAKE_RG_EXISTS": str(resource_group_exists),
                "FAKE_PROVIDER_STATE": provider_state,
                "FAKE_FEATURE_STATE": feature_state,
                "FAKE_SUBSCRIPTION_ID": SUBSCRIPTION_ID,
                "TEMP": str(self.temp),
                "TMP": str(self.temp),
                "PATH": f"{self.bin}{os.pathsep}{environment['PATH']}",
            }
        )
        # The class-level skipUnless already established that THIS interpreter is
        # CPython 3.11 on AMD64, which is what the runner's runtime guard requires.
        # Pass it explicitly: the runner defaults to resolving "python" from PATH,
        # and on a host whose PATH python is a different version or architecture
        # (for example CPython 3.13 on ARM64) every behavior test would fail on the
        # runtime guard rather than on the behavior under test.
        return subprocess.run(
            [
                self.pwsh,
                "-NoProfile",
                "-File",
                str(RUNNER),
                "-SubscriptionId",
                SUBSCRIPTION_ID,
                "-ResourceGroup",
                resource_group,
                "-Location",
                location,
                "-NamePrefix",
                "cache123",
                "-Workspace",
                str(self.workspace),
                "-PythonExecutable",
                sys.executable,
                *extra,
                "-WhatIf",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=20,
        )

    def test_whatif_executes_read_only_preflight(self) -> None:
        completed = self.run_runner()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(self.workspace.exists())
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 6)
        self.assertIn(["group", "exists"], [call[:2] for call in calls])
        self.assertEqual(list(self.temp.glob("azure-context-cache-*.log")), [])

    def test_whatif_releases_profile_lease(self) -> None:
        first = self.run_runner()
        second = self.run_runner()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)

    def test_zero_hit_threshold_is_rejected_before_preflight(self) -> None:
        completed = self.run_runner(extra=("-MinimumWarmHitRatio", "0"))

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_existing_resource_group_is_rejected(self) -> None:
        completed = self.run_runner(resource_group_exists=True)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("new unique resource group", runner_message(completed))

    def test_unregistered_provider_is_rejected(self) -> None:
        completed = self.run_runner(provider_state="NotRegistered")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Registered", runner_message(completed))

    def test_preview_feature_not_registered_is_rejected(self) -> None:
        completed = self.run_runner(feature_state="Pending")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "Complete preview onboarding first",
            runner_message(completed),
        )

    def test_resource_group_trailing_period_is_rejected(self) -> None:
        completed = self.run_runner(resource_group="rg-invalid.")

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_undocumented_region_is_rejected_before_preflight(self) -> None:
        completed = self.run_runner(location="eastus2")

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_azure_read_timeout_is_enforced(self) -> None:
        started = time.monotonic()
        completed = self.run_runner(
            extra=("-AzureReadTimeoutSeconds", "1"),
            delay=5,
        )
        elapsed = time.monotonic() - started

        self.assertNotEqual(completed.returncode, 0)
        self.assertLess(elapsed, 10)
        self.assertIn("exceeded 1 seconds", runner_message(completed))

    def test_concurrent_profile_use_is_rejected(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "AZURE_CONFIG_DIR": str(self.config),
                "FAKE_AZ_LOG": str(self.log),
                "FAKE_AZ_DELAY": "1",
                "FAKE_RG_EXISTS": "false",
                "FAKE_SUBSCRIPTION_ID": SUBSCRIPTION_ID,
                "TEMP": str(self.temp),
                "TMP": str(self.temp),
                "PATH": f"{self.bin}{os.pathsep}{environment['PATH']}",
            }
        )
        command = [
            self.pwsh,
            "-NoProfile",
            "-File",
            str(RUNNER),
            "-SubscriptionId",
            SUBSCRIPTION_ID,
            "-ResourceGroup",
            "rg_context_cache",
            "-Location",
            "centralus",
            "-NamePrefix",
            "cache123",
            "-Workspace",
            str(self.workspace),
            # Same reason as run_runner: pin the interpreter the skipUnless already
            # validated, instead of whatever "python" PATH happens to resolve to.
            "-PythonExecutable",
            sys.executable,
            "-WhatIf",
        ]
        first = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        try:
            deadline = time.monotonic() + 5
            while not self.log.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(self.log.exists(), "first runner did not reach Azure preflight")

            second = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=10,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn(
                "already using this AZURE_CONFIG_DIR",
                runner_message(second),
            )
            stdout, stderr = first.communicate(timeout=15)
            self.assertEqual(first.returncode, 0, stderr + stdout)
        finally:
            if first.poll() is None:
                first.kill()
                first.communicate()

    def test_workspace_junction_is_rejected(self) -> None:
        target = self.root / "junction-target"
        target.mkdir()
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(self.workspace), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if created.returncode:
            self.skipTest(f"unable to create test junction: {created.stderr}")

        completed = self.run_runner()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("reparse point", runner_message(completed))
        self.assertFalse(self.log.exists())

    def test_object_source_junction_is_allowed_in_whatif(self) -> None:
        target = self.root / "object-source-target"
        target.mkdir()
        junction = self.root / "object-source-junction"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if created.returncode:
            self.fail(f"unable to create test junction: {created.stderr}")

        completed = self.run_runner(
            extra=("-ExistingUpstreamDirectory", str(junction)),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()