# Quick Start: GPU-Hours Collection in One Command

[中文](QUICKSTART_CN.md) · [Full description](README.md)

This guide is for the operators who set the collection up. When you finish:
- every GPU VM writes one row per GPU per minute into your own Log Analytics workspace;
- your platform reads GPU hours through the Log Analytics query API, per VM, hour, day, Linux user, AML job and submitter.

You fill in one settings file and run one command. The command is safe to re-run: existing resources are updated in place, not created twice.

## 1. Before you start

| Item | Requirement |
|---|---|
| Where you run it | Azure Cloud Shell (Bash), Linux, macOS, or Git Bash on Windows; the Azure CLI, logged in with `az login` |
| Permissions | Contributor on the VM resource group and on the workspace resource group; granting your platform's identity also needs User Access Administrator or Owner |
| AML job attribution (optional) | Write access to subscription diagnostic settings, and Contributor on the AML workspace |
| GPU VMs | Running; NVIDIA driver and DCGM (`datacenter-gpu-manager`) installed; `/usr/bin/python3` and systemd present |
| Network | Outbound HTTPS from the VMs to Azure Monitor; if an NSG restricts outbound traffic, allow the `AzureMonitor` service tag |

The [Azure HPC VM images](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images) include the driver and DCGM. The preflight in section 4 checks every VM for these, without SSH.

Supported VM forms:
- standalone VMs;
- virtual machine scale sets with Flexible orchestration. Their instances are ordinary VMs, and the script lists all of them;
- scale sets with Uniform orchestration are not supported; the script stops with an error.

## 2. Download

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/Azure-GPU-Hours-Monitoring
cd Deep-Learning/Azure-GPU-Hours-Monitoring
chmod +x scripts/*.sh
```

## 3. Fill in the settings file

```bash
cp scripts/gpu-hours.env.example gpu-hours.env
```

Open `gpu-hours.env` in any editor. Three settings are required, and at least one of the two ways to name the GPU VMs:

```bash
WORKSPACE_RG="rg-gpu-hours"       # workspace resource group; created if missing
LOCATION="<region of the GPU VMs>" # for example swedencentral; must match the group's region if it exists
VM_RG="<resource group of the GPU VMs>"
VMSS_NAME="<Flexible scale set>"   # either: every instance of the scale set
VM_NAMES="<vm-1> <vm-2>"           # or: VM names, separated by spaces
```

Two optional settings:

```bash
# Per AML job and per submitter: the AML workspace resource ID
AML_WORKSPACE_ID="/subscriptions/<subscription-id>/resourceGroups/<group>/providers/Microsoft.MachineLearningServices/workspaces/<name>"
# Your platform's query identity (object ID of a managed identity or app service principal); gets Log Analytics Reader
READER_OBJECT_ID="<object-id>"
```

Find the AML workspace resource ID:

```bash
az resource show -g <group> -n <workspace> --resource-type Microsoft.MachineLearningServices/workspaces --query id -o tsv
```

Leave the other settings at their defaults. The comments in the file explain them.

## 4. Preflight (read-only, changes nothing)

```bash
./scripts/configure.sh -c gpu-hours.env -p
```

The script lists every VM it will onboard. Through Run Command, it checks each VM's power state, driver, DCGM and python3. Expected output:

```text
==> [3] preflight: running, NVIDIA driver, DCGM, python3 (Run Command, read-only)
  gpu-vm-1                                 OK gpus: 8 dcgm: 3.3.9
  gpu-vm-2                                 OK gpus: 8 dcgm: 3.3.9

preflight passed; nothing was changed
```

A VM marked `NOT_READY` shows what is missing. Fix it and run the preflight again, or set `SKIP_NOT_READY_VMS=1` to onboard only the VMs that pass.

## 5. Configure in one command

```bash
./scripts/configure.sh -c gpu-hours.env
```

The script runs seven steps. Each VM takes about 2–3 minutes, and five VMs run in parallel by default.
1. Confirm the signed-in account and subscription.
2. List the GPU VMs.
3. Run the preflight.
4. Create the workspace, the `GpuMetrics_CL` table, and the data collection endpoint and rule. With `AML_WORKSPACE_ID`, also add two diagnostic settings:
   - subscription activity log → `AzureActivity`, for job submitters;
   - AML job status → `AmlRunStatusChangedEvent`.
5. Onboard the VMs in parallel. On each VM, the script:
   - enables a system-assigned managed identity;
   - installs the Azure Monitor Agent;
   - associates the rule and the endpoint;
   - enables DCGM and installs the `gpumon` collector service.
6. Grant `READER_OBJECT_ID` the Log Analytics Reader role on the workspace, and write the workspace IDs to `gpu-hours.outputs.env`.
7. Wait until GPU rows from every VM arrive. The script checks this through the Log Analytics query API, the same API your platform calls.

A successful run ends with:

```text
==> [7] wait for GPU rows from every VM (up to 20 minutes; the first rows take about 10 minutes)
  ...
all 20 VM(s) are sending GPU rows

==> done
WORKSPACE_GUID=<workspace GUID>
```

| Exit code | Meaning | What to do |
|---|---|---|
| 0 | Done; every VM is sending rows | Section 6 if needed, then section 7 |
| 1 | Settings error or failed preflight | Fix what the message says and re-run |
| 2 | Some VMs failed to onboard | Read `gpu-hours-logs/<time>/onboard.<vm>.log`, fix, re-run the same command |
| 3 | Timed out waiting for rows | New VMs can take about 15 minutes; run `./scripts/configure.sh -c gpu-hours.env -v` to check the data again |

Each run keeps its full logs in `gpu-hours-logs/<UTC time>/`.

This section was run end to end on Azure against one H100 VM:
- the preflight took about 3 minutes;
- the workspace took about 3 minutes;
- onboarding took about 2.5 minutes;
- the first GPU rows were queryable about 9 minutes after onboarding.

The whole command took 1160 seconds and exited with code 0.

## 6. Pass the job ID to AML job processes (job attribution only)

The collector reads the AML job name from `AZUREML_RUN_ID` in each GPU process's environment. AML sets this variable in the job container.
- If the GPU processes run in the job container, nothing changes.
- If the launcher connects from the job container to the host over SSH and starts `torchrun` or `mpirun`, pass the variable on:

```bash
# SSH to the host: pass it with env
ssh "$HOST" "env AZUREML_RUN_ID=$AZUREML_RUN_ID torchrun --nproc_per_node 8 train.py"

# mpirun across hosts: export it with -x
mpirun -x AZUREML_RUN_ID -np 160 --hostfile hosts ./train.sh

# docker on the host: pass it with -e
docker run -e AZUREML_RUN_ID ... <image> torchrun ...
```

Submit a test job. A few minutes after it starts, the `per_job` query in section 7 shows its name. The submitter comes from the Azure activity log and usually arrives 6–9 minutes after the GPU rows.

## 7. Query from your platform

`WORKSPACE_GUID` in `gpu-hours.outputs.env` is the workspace ID for queries. Your platform sends one HTTPS request per query:

```http
POST https://api.loganalytics.io/v1/workspaces/<WORKSPACE_GUID>/query
Authorization: Bearer <access token for https://api.loganalytics.io>
Content-Type: application/json

{"query": "<full content of one kql/ file>", "timespan": "<start>/<end>"}
```

`timespan` is ISO 8601. Use either two times with a UTC offset, separated by `/`, or a duration such as `P1D` for the last day.

Each of the eight files in [`kql/`](kql/) is one view:

| File | One row per |
|---|---|
| `summary.kql` | the selected period |
| `per_vm.kql` / `per_hour.kql` / `per_day.kql` | VM / hour / day |
| `per_user.kql` | Linux user on a VM |
| `per_job.kql` / `per_submitter.kql` | AML job / Entra submitter |
| `live.kql` | GPU, with its latest process and job |

Python. The client uses a managed identity where the platform runs, and the `az login` session on a workstation:

```bash
pip install -r examples/requirements.txt
source gpu-hours.outputs.env
END=$(date -u +%FT%TZ); START=$(date -u -d '-1 day' +%FT%TZ)   # macOS: date -u -v-1d +%FT%TZ
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_vm --start "$START" --end "$END"
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_job --start "$START" --end "$END"
```

A quick look from the command line, with no extension:

```bash
source gpu-hours.outputs.env
echo '{"query": "GpuMetrics_CL | summarize Rows = count(), Last = max(TimeGenerated) by VmName", "timespan": "PT1H"}' > q.json
az rest --method post --url "https://api.loganalytics.io/v1/workspaces/$WORKSPACE_GUID/query" \
  --resource https://api.loganalytics.io --body @q.json --query "tables[0].rows" -o table
```

If `READER_OBJECT_ID` was empty, grant query access later:

```bash
source gpu-hours.outputs.env
az role assignment create --assignee-object-id <object-id> --assignee-principal-type ServicePrincipal \
  --role "Log Analytics Reader" --scope "$WORKSPACE_RESOURCE_ID"
```

[README.md](README.md#query-from-your-platform) describes the columns of each view and the metric definitions.

## 8. Add, remove or delete

- **Add VMs**: add them to the settings file, or scale out the scale set, and run section 5 again. VMs that are already onboarded are refreshed in place.
- **Remove one VM**: `./scripts/offboard-vm.sh -g <vm-group> -n <vm>`. It removes `gpumon`, both associations and the Azure Monitor Agent. The driver and DCGM stay.
- **Delete everything**:
  1. Offboard each VM.
  2. If you set `AML_WORKSPACE_ID`, delete the two diagnostic settings:

     ```bash
     az monitor diagnostic-settings subscription delete -n gpu-hours-job-submitters --yes
     az monitor diagnostic-settings delete -n gpu-hours-job-status --resource "<AML_WORKSPACE_ID>"
     ```
  3. Delete the workspace resource group: `az group delete -n rg-gpu-hours --yes`.

## 9. Cost and caveats

- **Volume**: one row of about 343 bytes per GPU per minute. That is about 4.74 MB per day for an 8-GPU VM, including `Heartbeat`, or about 95 MB per day for 20 such VMs. Log Analytics charges these as Analytics logs. Data is kept 90 days by default; change it with `RETENTION_DAYS`.
- **Latency**: GPU rows are usually queryable within 1–2 minutes; submitters arrive a few minutes later. This is per-minute accounting, not second-by-second monitoring.
- **Definitions**:
  - allocated GPU hours come from the Azure Monitor Agent's `Heartbeat`, not from the bill; use Cost Management to reconcile;
  - when a job ends partway through a minute, that minute can count as busy without being attributed to any job.
- [README.md](README.md#validation-on-one-h100-vm) shows how this was measured and the evidence.
