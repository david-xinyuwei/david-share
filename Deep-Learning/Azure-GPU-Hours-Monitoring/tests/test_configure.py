"""scripts/configure.sh end to end against a fake `az` that records every call."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_scripts import _bash  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIGURE = ROOT / "scripts" / "configure.sh"

FAKE_AZ = r"""#!/bin/bash
echo "$*" >> "$AZ_LOG"
case "$*" in
  "account show"*) printf 'subscription  user\n' ;;
  "vmss show"*) echo "${FAKE_ORCH:-Flexible}" ;;
  "vmss list-instances"*) printf 'vm-a\nvm-b\n' ;;
  "vm show -d"*) echo "VM running" ;;
  *"run-command invoke"*preflight.*)
    if [[ " $* " == *" -n ${FAKE_NOT_READY:-none} "* ]]; then printf 'missing: dcgmi (datacenter-gpu-manager package)\nPREFLIGHT_FAIL\n'
    else printf '[stdout]\ngpus: 8\ndcgm: 3.3.9\nPREFLIGHT_OK\n'; fi ;;
  *"run-command invoke"*) printf '   Active: active (running) since now\n' ;;
  *"--query customerId"*) echo "workspace-guid" ;;
  *"--query id"*) echo "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Fake/things/thing" ;;
  "rest "*) for v in ${FAKE_ROWS-vm-a vm-b}; do printf '%s\t30\tlast\n' "$v"; done ;;
esac
exit 0
"""

SETTINGS = {
    "WORKSPACE_RG": "rg-gpu-hours", "LOCATION": "region-1", "VM_RG": "rg-vms", "VMSS_NAME": "gpu-vmss",
    "AML_WORKSPACE_ID": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.MachineLearningServices/workspaces/ml",
    "READER_OBJECT_ID": "object-id-1", "WAIT_MINUTES": "0",
}


@unittest.skipUnless(_bash(), "bash not available")
class ConfigureTests(unittest.TestCase):
    def run_configure(self, *flags, env=None, **settings):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        tmp = Path(holder.name)
        stub = tmp / "bin"
        stub.mkdir()
        (stub / "az").write_bytes(FAKE_AZ.encode())
        (stub / "az").chmod(0o755)
        values = {**SETTINGS, **settings}
        # CRLF on purpose: a settings file edited on Windows must still work
        (tmp / "gpu-hours.env").write_bytes("".join(f'{k}="{v}"\r\n' for k, v in values.items()).encode())
        run_env = {**os.environ, **(env or {}), "AZ_LOG": str(tmp / "az.log"),
                   "PATH": str(stub) + os.pathsep + os.environ["PATH"]}
        res = subprocess.run([_bash(), str(CONFIGURE).replace("\\", "/"), "-c", "gpu-hours.env", *flags], cwd=tmp,
                             env=run_env, capture_output=True, text=True, encoding="utf-8", timeout=300)
        log = (tmp / "az.log").read_text(encoding="utf-8") if (tmp / "az.log").exists() else ""
        return res, log, tmp

    def test_preflight_changes_nothing(self):
        res, log, _ = self.run_configure("-p")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("vm-a", res.stdout)
        self.assertIn("OK gpus: 8 dcgm: 3.3.9", res.stdout)
        self.assertIn("preflight passed; nothing was changed", res.stdout)
        for verb in (" create", " set ", " assign", "extension add", "delete"):
            self.assertNotIn(verb, log, verb)

    def test_full_run_onboards_every_instance_and_grants_reader(self):
        res, log, tmp = self.run_configure()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("all 2 VM(s) are sending GPU rows", res.stdout)
        self.assertEqual(log.count("data-collection rule association create"), 4)  # rule and endpoint, two VMs
        self.assertEqual(log.count("extension add"), 1)  # once, before the parallel onboarding
        self.assertIn("diagnostic-settings subscription create", log)
        self.assertIn("role assignment create --assignee-object-id object-id-1", log)
        self.assertIn("rest --method post --url https://api.loganalytics.io/v1/workspaces/workspace-guid/query", log)
        outputs = (tmp / "gpu-hours.outputs.env").read_text(encoding="utf-8")
        self.assertIn("WORKSPACE_GUID=workspace-guid", outputs)
        self.assertIn('ONBOARDED_VMS="vm-a vm-b"', outputs)
        self.assertEqual(sorted(p.name for p in tmp.iterdir() if p.is_file()),
                         ["az.log", "gpu-hours.env", "gpu-hours.outputs.env"], "temporary files left behind")

    def test_a_vm_that_fails_preflight_stops_before_any_change(self):
        res, log, _ = self.run_configure(env={"FAKE_NOT_READY": "vm-b"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("NOT_READY missing: dcgmi", res.stdout)
        self.assertNotIn(" create", log)

    def test_skip_not_ready_onboards_only_ready_vms(self):
        res, log, _ = self.run_configure(env={"FAKE_NOT_READY": "vm-b"}, SKIP_NOT_READY_VMS="1")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("--vm-name vm-a", log)
        self.assertNotIn("--vm-name vm-b", log)
        self.assertEqual(log.count("data-collection rule association create"), 2)
        self.assertIn("all 1 VM(s) are sending GPU rows", res.stdout)

    def test_uniform_scale_set_is_rejected(self):
        res, _, _ = self.run_configure("-p", env={"FAKE_ORCH": "Uniform"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("only Flexible scale set instances", res.stderr)

    def test_missing_rows_time_out_with_exit_3(self):
        res, _, _ = self.run_configure("-v", env={"FAKE_ROWS": "vm-a"})
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)
        self.assertIn("no GPU rows yet from: vm-b", res.stderr)

    def test_settings_without_vms_are_rejected(self):
        res, log, _ = self.run_configure("-p", VMSS_NAME="")
        self.assertEqual(res.returncode, 1)
        self.assertIn("set VMSS_NAME, VM_NAMES or both", res.stderr)
        self.assertEqual(log, "")


if __name__ == "__main__":
    unittest.main()
