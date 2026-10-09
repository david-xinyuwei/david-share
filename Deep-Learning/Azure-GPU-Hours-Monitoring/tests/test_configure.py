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
REMOVE = ROOT / "scripts" / "remove-workspace.sh"

FAKE_AZ = r"""#!/bin/bash
echo "$*" >> "$AZ_LOG"
case "$*" in
  "account show"*) printf 'subscription  user\n' ;;
  "vmss show"*) echo "${FAKE_ORCH:-Flexible}" ;;
  "vmss list-instances"*) printf 'vm-a\nvm-b\n' ;;
  "vm show -d"*) echo "VM running" ;;
  *"vm show "*"--query id"*)
    vm=""; previous=""; for arg in "$@"; do [[ "$previous" == "-n" ]] && vm="$arg"; previous="$arg"; done
    echo "/subscriptions/sub/resourceGroups/rg-vms/providers/Microsoft.Compute/virtualMachines/$vm" ;;
  *"run-command invoke"*preflight.*)
    if [[ " $* " == *" -n ${FAKE_NOT_READY:-none} "* ]]; then printf 'missing: dcgmi (datacenter-gpu-manager package)\nPREFLIGHT_FAIL\n'
    else printf '[stdout]\ngpus: 8\ndcgm: 3.3.9\nPREFLIGHT_OK\n'; fi ;;
  *"run-command invoke"*"gpumon removed"*) printf 'gpumon removed\n' ;;
  *"run-command invoke"*) printf '   Active: active (running) since now\n' ;;
  *"data-collection rule association show"*) echo "${FAKE_EXISTING_DCE:-}" ;;
  *"data-collection rule association list"*"[].name"*)
    printf 'dcra-dcr-test\nconfigurationAccessEndpoint\n' ;;
  *"data-collection rule association list"*"configurationAccessEndpoint"*) echo "${FAKE_EXISTING_DCE:-}" ;;
  *"data-collection rule association list"*"dataCollectionRuleId"*) echo "${FAKE_OTHER_DCRS:-}" ;;
  "role assignment list"*) echo "${FAKE_READER_ASSIGNMENTS:-0}" ;;
  *"--query customerId"*) echo "workspace-guid" ;;
  *"--query id"*) echo "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Fake/things/thing" ;;
  "rest "*) for arg in "$@"; do [[ "$arg" == @* ]] && cat "${arg#@}" >> "$AZ_LOG"; done
    if [[ " $* " == *" error.message "* ]]; then echo "${FAKE_QUERY_ERROR:-}"; exit 0; fi
    for v in ${FAKE_ROWS-vm-a vm-b}; do
    printf '%s\t/subscriptions/sub/resourcegroups/%s/providers/microsoft.compute/virtualmachines/%s\t30\tlast\n' \
      "$v" "${FAKE_ROW_RESOURCE_GROUP:-rg-vms}" "$v"
  done ;;
esac
exit 0
"""

SETTINGS = {
    "SUBSCRIPTION_ID": "sub", "WORKSPACE_RG": "rg-gpu-hours", "LOCATION": "region-1",
    "VM_RG": "rg-vms", "VMSS_NAME": "gpu-vmss",
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

    def run_remove(self, *flags):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        tmp = Path(holder.name)
        stub = tmp / "bin"
        stub.mkdir()
        (stub / "az").write_bytes(FAKE_AZ.encode())
        (stub / "az").chmod(0o755)
        run_env = {**os.environ, "AZ_LOG": str(tmp / "az.log"),
                   "PATH": str(stub) + os.pathsep + os.environ["PATH"]}
        res = subprocess.run([_bash(), str(REMOVE).replace("\\", "/"), "-g", "rg-monitor", "-w", "law-monitor",
                              "-a", "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.MachineLearningServices/workspaces/ml",
                              *flags], cwd=tmp, env=run_env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        log = (tmp / "az.log").read_text(encoding="utf-8") if (tmp / "az.log").exists() else ""
        return res, log

    def run_offboard(self, env=None):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        tmp = Path(holder.name)
        stub = tmp / "bin"
        stub.mkdir()
        (stub / "az").write_bytes(FAKE_AZ.encode())
        (stub / "az").chmod(0o755)
        dce = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Insights/dataCollectionEndpoints/dce-test"
        run_env = {**os.environ, **(env or {}), "AZ_LOG": str(tmp / "az.log"),
                   "PATH": str(stub) + os.pathsep + os.environ["PATH"]}
        res = subprocess.run([_bash(), str(ROOT / "scripts" / "offboard-vm.sh").replace("\\", "/"),
                              "-g", "rg-vms", "-n", "vm-a",
                              "-d", "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Insights/dataCollectionRules/dcr-test",
                              "-e", dce], cwd=tmp, env=run_env, capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
        log = (tmp / "az.log").read_text(encoding="utf-8") if (tmp / "az.log").exists() else ""
        return res, log, dce

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
        self.assertNotIn("account set", log)
        self.assertIn("--subscription ", log)
        self.assertEqual(log.count("data-collection rule association create"), 4)  # rule and endpoint, two VMs
        self.assertEqual(log.count("extension add"), 1)  # once, before the parallel onboarding
        self.assertIn("diagnostic-settings subscription create", log)
        self.assertIn("role assignment create --assignee-object-id object-id-1", log)
        self.assertIn("rest --method post --url https://api.loganalytics.azure.com/v1/workspaces/workspace-guid/query", log)
        self.assertIn("TimeGenerated > datetime(", log)
        outputs = (tmp / "gpu-hours.outputs.env").read_text(encoding="utf-8")
        self.assertIn("WORKSPACE_GUID=workspace-guid", outputs)
        self.assertIn('ONBOARDED_VMS="vm-a vm-b"', outputs)
        self.assertEqual(sorted(p.name for p in tmp.iterdir() if p.is_file()),
                         ["az.log", "gpu-hours.env", "gpu-hours.outputs.env"], "temporary files left behind")

    def test_existing_reader_assignment_is_reused(self):
        res, log, _ = self.run_configure(env={"FAKE_READER_ASSIGNMENTS": "1"})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Log Analytics Reader already granted", res.stdout)
        self.assertIn("role assignment list", log)
        self.assertNotIn("role assignment create", log)

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

    def test_rows_from_same_named_vms_in_another_resource_group_are_rejected(self):
        res, _, _ = self.run_configure("-v", env={"FAKE_ROW_RESOURCE_GROUP": "another-rg"})
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)
        self.assertIn("no GPU rows yet from: vm-a vm-b", res.stderr)

    def test_query_partial_error_is_not_accepted_as_success(self):
        res, _, tmp = self.run_configure("-v", env={"FAKE_QUERY_ERROR": "partial result"})
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)
        verify = next((tmp / "gpu-hours-logs").rglob("verify.log")).read_text(encoding="utf-8")
        self.assertIn("partial result", verify)

    def test_another_dce_association_is_not_overwritten(self):
        res, _, _ = self.run_configure(env={"FAKE_EXISTING_DCE": "/subscriptions/sub/resourceGroups/other/providers/Microsoft.Insights/dataCollectionEndpoints/other"})
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("no VM was onboarded", res.stderr)

    def test_settings_without_vms_are_rejected(self):
        res, log, _ = self.run_configure("-p", VMSS_NAME="")
        self.assertEqual(res.returncode, 1)
        self.assertIn("set VMSS_NAME, VM_NAMES or both", res.stderr)
        self.assertEqual(log, "")

    def test_workspace_removal_is_a_dry_run_by_default(self):
        res, log = self.run_remove()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Dry run only", res.stdout)
        self.assertIn("resource group is not deleted", res.stdout)
        self.assertIn("workspace show", log)
        self.assertNotIn(" delete ", log)
        self.assertNotIn(" create ", log)

    def test_confirmed_workspace_removal_deletes_only_named_resources(self):
        res, log = self.run_remove("-y")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("diagnostic-settings subscription delete -n gpu-hours-job-submitters-", log)
        self.assertIn("data-collection rule delete -g rg-monitor -n dcr-gpu-hours-", log)
        self.assertIn("data-collection endpoint delete -g rg-monitor -n dce-gpu-hours-", log)
        self.assertIn("log-analytics workspace delete -g rg-monitor -n law-monitor", log)
        self.assertNotIn("group delete", log)

    def test_offboard_removes_only_this_deployment_and_keeps_the_agent(self):
        expected = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Insights/dataCollectionEndpoints/dce-test"
        res, log, _ = self.run_offboard({"FAKE_EXISTING_DCE": expected})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("association delete --name dcra-dcr-test", log)
        self.assertIn("association delete --name configurationAccessEndpoint", log)
        self.assertNotIn("vm extension delete", log)

    def test_offboard_keeps_another_dce_association(self):
        res, log, _ = self.run_offboard({"FAKE_EXISTING_DCE": "/subscriptions/sub/resourceGroups/other/providers/Microsoft.Insights/dataCollectionEndpoints/other"})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("another DCE owns", res.stdout)
        self.assertNotIn("association delete --name configurationAccessEndpoint", log)

    def test_offboard_keeps_its_dce_when_another_dcr_uses_it(self):
        expected = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Insights/dataCollectionEndpoints/dce-test"
        res, log, _ = self.run_offboard({"FAKE_EXISTING_DCE": expected, "FAKE_OTHER_DCRS": "other-dcr"})
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("other DCR associations still use the DCE", res.stdout)
        self.assertNotIn("association delete --name configurationAccessEndpoint", log)


if __name__ == "__main__":
    unittest.main()
