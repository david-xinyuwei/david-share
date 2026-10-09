# Azure GPU-Hours Monitoring with DCGM and Azure Monitor

[![Collection](https://img.shields.io/badge/Azure%20Monitor-Agent%20%2B%20Log%20Analytics-0078D4)](#architecture-and-metrics)
[![GPU metrics](https://img.shields.io/badge/NVIDIA%20DCGM-3.3.9-76B900)](#architecture-and-metrics)
[![Tested on](https://img.shields.io/badge/tested-NC40ads%20H100%20v5-0078D4)](#validation-on-one-h100-vm)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-gpu-hours-monitoring-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-gpu-hours-monitoring-ci.yml)

**Of the GPU hours you pay for on Azure GPU VMs, how many ran real work, and whose work was it?** This repository measures that with NVIDIA DCGM inside each VM and Azure Monitor services outside it: the Azure Monitor Agent, a data collection rule and a Log Analytics workspace. It gives you the one collector that runs on the VM, every Azure configuration step as an `az` command, and eight KQL views that a platform API calls through the Log Analytics Query API. There is no custom storage and no user interface to run.

<img src="images/architecture-en.png" width="900" alt="Data path: DCGM host engine, gpumon collector, JSON lines on disk and Azure Monitor Agent on the GPU VM; data collection endpoint, data collection rule and Log Analytics workspace in Azure Monitor; views in kql/, the Log Analytics Query API and operators on the platform side">

<!-- BEGIN GENERATED: glance -->
- On one H100 VM running a load with a known schedule, the pipeline recorded 8 full, 3 held and 5 partial GPU-minutes, the same split the load script scheduled; the five views and an independent Python recomputation of the raw rows agree on all 28 compared values.
- Three AML jobs ran there as one Linux user: `per_user` shows a single owner with 0.150 busy GPU-hours, while `per_job` splits them by job name (0.067, 0.042, 0.042), counts the 3 minutes two jobs shared as half each and names the Entra account that submitted them; KQL and Python agree on 11 values and 28 fields.
- The configuration steps below ran verbatim against a new resource group: workspace setup 181 s, VM onboarding 102 s, removal 98 s.
- Log Analytics bills 343 bytes per GPU-minute row, about 4.74 MB per day for an 8-GPU VM including its Heartbeat.
- Main limit: process owners are sampled once per minute, so a job that exits mid-minute leaves that minute busy but unattributed (1 of 17 busy minutes in the first run, 1 of 6 in the second).
<!-- END GENERATED: glance -->

Author: Xinyu Wei · [中文](README_CN.md) · [Architecture](#architecture-and-metrics) · [Configure](#configure-on-azure) · [Query](#query-from-your-platform) · [Validation](#validation-on-one-h100-vm)

## Start Here

| Goal | Entry |
|---|---|
| Understand what is measured and how | [Architecture and Metrics](#architecture-and-metrics) |
| Set up a workspace and onboard GPU VMs | [Quick start: one settings file, one command](QUICKSTART.md), or step by step in [Configure on Azure](#configure-on-azure) |
| Read the numbers from your platform API | [Query from Your Platform](#query-from-your-platform) |
| See the evidence that the numbers are right | [Validation on One H100 VM](#validation-on-one-h100-vm) |
| Run the checks without Azure | [Tests and Offline Checks](#tests-and-offline-checks) |

## What This Repository Delivers

- **GPU telemetry**: NVIDIA DCGM, installed with the driver stack. The repository reads it; it does not replace it.
- **Collection, storage and query**: Azure Monitor Agent, data collection endpoint and rule, Log Analytics and its Query API, all Azure-managed.
- **This repository adds**:
  - the collector that runs on each VM ([`vm/`](vm/));
  - the data collection rule ([`azure/`](azure/));
  - the configuration steps as scripts of `az` commands ([`scripts/`](scripts/));
  - eight views ([`kql/`](kql/)), including AML job and Entra submitter attribution;
  - a reference client for your API ([`examples/`](examples/));
  - the evidence and tests that check them ([`evidence/`](evidence/), [`tests/`](tests/), [`tools/`](tools/)).

You supply: GPU VMs with the NVIDIA driver and the DCGM package; Azure CLI with Contributor on the resource group; for the platform, an identity with the Log Analytics Reader role on the workspace.

Not provided: a dashboard or UI, alerting, reconciliation with your invoice, automatic attribution for jobs that do not propagate a run ID, and MIG instances.

## Architecture and Metrics

The GPU VM does two things. First, the NVIDIA DCGM host engine exposes each GPU's counters. Second, the collector samples them and appends one JSON line per GPU per minute to a local file. From there everything is Azure Monitor:

1. The Azure Monitor Agent reads the file and ingests the lines into the `GpuMetrics_CL` table through the data collection endpoint and rule.
2. The same agent writes one `Heartbeat` row per minute while the VM runs.
3. KQL joins the two tables into GPU hours.

**On the VM.** [`vm/gpu_collector.py`](vm/gpu_collector.py) is a systemd service (`gpumon`) installed by [`vm/install_collector.sh`](vm/install_collector.sh). It needs only Python's standard library. It runs:

<!-- BEGIN GENERATED: dcgm-command -->
```bash
dcgmi dmon -e 203,1001,1002,1004,1005,252,250,155,150 -d 10000
```
<!-- END GENERATED: dcgm-command -->

That is nine DCGM fields sampled every 10 s. Every minute, the collector averages each field per GPU and adds:
- the VM name, size, resource ID and tags from the instance metadata service;
- the Linux owner and name of every process on the GPU (`nvidia-smi --query-compute-apps` and `/proc/<pid>`);
- the `AZUREML_RUN_ID` value from each GPU process, when its launcher propagated that one variable.

It then appends one line per GPU to `/var/log/gpumon/gpu_metrics_<day>.json` and deletes files older than three days.

<!-- BEGIN GENERATED: dcgm-fields -->
- `203` `DCGM_FI_DEV_GPU_UTIL` → `GpuUtil`: busy threshold
- `1001` `DCGM_FI_PROF_GR_ENGINE_ACTIVE` → `GrActive`: reference
- `1002` `DCGM_FI_PROF_SM_ACTIVE` → `SmActive`: effective GPU-hours
- `1004` `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` → `TensorActive`: reference
- `1005` `DCGM_FI_PROF_DRAM_ACTIVE` → `DramActive`: reference
- `252` `DCGM_FI_DEV_FB_USED` → `FbUsedMiB`: memory in use
- `250` `DCGM_FI_DEV_FB_TOTAL` → `FbTotalMiB`: memory size
- `155` `DCGM_FI_DEV_POWER_USAGE` → `PowerW`: reference
- `150` `DCGM_FI_DEV_GPU_TEMP` → `TempC`: reference
<!-- END GENERATED: dcgm-fields -->

One line of that file, from the measured VM (names replaced):

<!-- BEGIN GENERATED: json-line -->
```json
{"TimeGenerated": "<minute start, UTC>", "VmName": "<vm-name>", "VmSize": "Standard_NC40ads_H100_v5", "VmResourceId": "<vm resource id>", "Tags": "", "GpuId": 0, "GpuUuid": "<GPU UUID>", "GpuName": "NVIDIA H100 NVL", "Samples": 6, "GpuUtil": 100, "GrActive": 0.9818, "SmActive": 0.9413, "TensorActive": 0.916, "DramActive": 0.1307, "FbUsedMiB": 21618, "FbTotalMiB": 95830, "PowerW": 397.6368, "TempC": 64.1667, "ProcCount": 1, "Users": "<linux user>", "Processes": "python3", "RunId": "<AML run ID>"}
```
<!-- END GENERATED: json-line -->

**In Azure Monitor.** The data collection rule [`azure/dcr-rule.json`](azure/dcr-rule.json) declares a `Custom-Json-GpuMetrics` stream with the same columns as the JSON line. It reads `/var/log/gpumon/*.json` and sends the rows to `GpuMetrics_CL`. The agent authenticates with the VM's managed identity and sends through the data collection endpoint. `Heartbeat` needs no configuration: every agent sends it.

**The metrics.** Every GPU-minute falls into nested classes: allocated ⊇ busy ⊇ effective.

| Metric | Definition | Source |
|---|---|---|
| Allocated GPU-hours | VM running minutes × GPUs ÷ 60 | `Heartbeat` minutes |
| Busy GPU-hours | GPU-minutes with a compute process or GPU util ≥ 5 % ÷ 60 | `ProcCount`, `GpuUtil` |
| Effective GPU-hours | Σ SM active ÷ 60 | `SmActive` |
| Idle GPU-hours | allocated − busy | derived |
| Utilization | effective ÷ allocated | derived |

Effective hours use SM active, not GPU util. `DCGM_FI_DEV_GPU_UTIL` reports the share of time any kernel ran, so a GPU running small kernels shows 100 %. `DCGM_FI_PROF_SM_ACTIVE` is the share of time the streaming multiprocessors had work. The two can differ: in the partial phase below, GPU util averaged 51 % while SM active averaged 35 %.

A process that keeps GPU memory without running kernels makes the GPU busy but not effective. That is the pattern to look for when reclaiming GPUs.

## Configure on Azure

**Fastest path: one settings file, one command.** [`scripts/configure.sh`](scripts/configure.sh) runs every step below in order:
- a read-only preflight of each VM;
- the workspace and the rule, plus AML job tracking;
- every VM of a Flexible scale set or a VM list, onboarded in parallel;
- Log Analytics Reader for your platform's identity;
- a wait until each VM's GPU rows arrive.

The [quick start](QUICKSTART.md) walks through it. The steps below show what it runs.

```bash
cp scripts/gpu-hours.env.example gpu-hours.env   # fill in the resource groups, region, VMs
./scripts/configure.sh -c gpu-hours.env -p       # preflight only, changes nothing
./scripts/configure.sh -c gpu-hours.env          # configure, then wait for data
```

Run the steps from Bash with the Azure CLI logged in (`az login`). Azure Cloud Shell, Linux or macOS all work. On Windows, Git Bash also works: the scripts set `MSYS_NO_PATHCONV=1` so resource IDs are not rewritten as paths.

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/Azure-GPU-Hours-Monitoring
cd Deep-Learning/Azure-GPU-Hours-Monitoring
```

**Before you start: DCGM on each GPU VM.** The collector needs the `dcgmi` command and the DCGM host engine. The [Azure HPC VM images](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images) include DCGM. On other images, install NVIDIA's `datacenter-gpu-manager` package, with the DCGM major version that matches your CUDA driver. The measured VM used an Ubuntu 24.04 image with that package. Check one VM without SSH:

```bash
az vm run-command invoke -g <vm-rg> -n <vm-name> --command-id RunShellScript \
  --scripts "dcgmi --version | head -2; systemctl is-enabled nvidia-dcgm" --query "value[0].message" -o tsv
```

**Step 1: workspace, table, data collection endpoint and rule** (once per workspace).

```bash
./scripts/setup-workspace.sh -g rg-gpu-hours -l <region>
# Add AML job submitter and status tracking:
./scripts/setup-workspace.sh -g rg-gpu-hours -l <region> -a <aml-workspace-resource-id>
```

The script prints `WORKSPACE_GUID`, `DCR_ID` and `DCE_ID`; keep them for the next steps. It runs these commands:

<!-- BEGIN GENERATED: setup-commands -->
```bash
az extension add --upgrade --yes --name monitor-control-service -o none
az group create -n "$RG" -l "$LOC" -o none
az monitor log-analytics workspace create -g "$RG" -n "$LAW" -l "$LOC" --retention-time "$RETENTION" -o none
az monitor log-analytics workspace table show -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL -o none 2>/dev/null
az monitor log-analytics workspace table update -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL \
  --retention-time "$RETENTION" --columns "${COLUMNS[@]}" -o none
az monitor log-analytics workspace table create -g "$RG" --workspace-name "$LAW" -n GpuMetrics_CL \
  --retention-time "$RETENTION" --columns "${COLUMNS[@]}" -o none
az monitor data-collection endpoint create -g "$RG" -n "$DCE" -l "$LOC" --public-network-access Enabled -o none
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv)
DCE_ID=$(az monitor data-collection endpoint show -g "$RG" -n "$DCE" --query id -o tsv)
az monitor data-collection rule create -g "$RG" -n "$DCR" -l "$LOC" --kind Linux \
  --endpoint-id "$DCE_ID" --rule-file "$RULE_FILE" -o none
DCR_ID=$(az monitor data-collection rule show -g "$RG" -n "$DCR" --query id -o tsv)
WORKSPACE_GUID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)
az monitor diagnostic-settings subscription create -n gpu-hours-job-submitters -l "$LOC" \
  --workspace "$LAW_ID" --logs '[{"category":"Administrative","enabled":true}]' -o none
az monitor diagnostic-settings create -n gpu-hours-job-status --resource "$AML_ID" --workspace "$LAW_ID" \
  --export-to-resource-specific true --logs '[{"category":"AmlRunStatusChangedEvent","enabled":true}]' -o none
```
<!-- END GENERATED: setup-commands -->

Put the workspace in the same region as the VMs. Retention is 90 days by default; change it with `-r <days>`. The table is created on the first run and updated on later runs. With `-a`, the script also sends subscription `Administrative` events to `AzureActivity` and AML run status events to the resource-specific `AmlRunStatusChangedEvent` table. That option needs permission to create diagnostic settings at subscription scope and on the AML workspace.

Check it:

```bash
az monitor log-analytics workspace table show -g rg-gpu-hours --workspace-name law-gpu-hours -n GpuMetrics_CL \
  --query "{plan: plan, retention: retentionInDays, columns: length(schema.columns)}" -o json
az monitor data-collection rule show -g rg-gpu-hours -n dcr-gpu-hours \
  --query "{kind: kind, files: dataSources.logFiles[0].filePatterns, stream: dataFlows[0].outputStream}" -o json
```

Expected: 24 columns and the retention you chose; the rule has kind `Linux`, reads `/var/log/gpumon/*.json` and outputs `Custom-GpuMetrics_CL`.

**Step 2: onboard each GPU VM.**

```bash
./scripts/onboard-vm.sh -g <vm-rg> -n <vm-name> -d "$DCR_ID" -e "$DCE_ID"
```

The script enables the VM's system-assigned managed identity, installs the Azure Monitor Agent and associates the rule and the endpoint with the VM. It then uses Run Command, so no SSH is needed, to run [`vm/install_collector.sh`](vm/install_collector.sh) on the VM. That installer enables `nvidia-dcgm` and installs `gpumon` as a systemd service.

<!-- BEGIN GENERATED: onboard-commands -->
```bash
az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
az vm identity assign -g "$RG" -n "$VM" -o none
az vm extension set -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true -o none
az monitor data-collection rule association create --name dcra-gpu-hours --resource "$VM_ID" --rule-id "$DCR_ID" -o none
az monitor data-collection rule association create --name configurationAccessEndpoint --resource "$VM_ID" \
  --endpoint-id "$DCE_ID" -o none
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$SCRIPT" --query "value[0].message" -o tsv
```
<!-- END GENERATED: onboard-commands -->

The Run Command output ends with `systemctl status gpumon`: it must show `active (running)` and the `dcgmi dmon` command above.

For many VMs, loop over `az vm list`, or use two Azure Policy built-ins together: *Configure Linux virtual machines to run Azure Monitor Agent with system-assigned managed identity-based authentication* and *Configure Linux Machines to be associated with a Data Collection Rule or a Data Collection Endpoint*. Then install the collector in your VM image. `vm/install_collector.sh` also works as an image build step.

**Step 3: confirm that data arrives.** Expect the first `Heartbeat` about 8 minutes after onboarding and the first `GpuMetrics_CL` rows a few minutes later. Querying from the CLI needs the `log-analytics` extension, which exists only as a preview.

```bash
az extension add --upgrade --yes --name log-analytics
az monitor log-analytics query -w "$WORKSPACE_GUID" -t PT30M -o table --analytics-query \
  "union (Heartbeat | summarize Rows = count(), Last = max(TimeGenerated) by Table = 'Heartbeat', Computer), (GpuMetrics_CL | summarize Rows = count(), Last = max(TimeGenerated) by Table = 'GpuMetrics_CL', Computer)"
```

Each onboarded VM should appear under both tables, with `Last` within the last few minutes.

**Remove a VM, or everything.**

```bash
./scripts/offboard-vm.sh -g <vm-rg> -n <vm-name>
az group delete -n rg-gpu-hours --yes
```

`offboard-vm.sh` stops and removes `gpumon`, deletes both associations and removes the agent. The NVIDIA driver, DCGM and the managed identity stay.

<!-- BEGIN GENERATED: offboard-commands -->
```bash
az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --query "value[0].message" -o tsv --scripts \
  "systemctl disable --now gpumon 2>/dev/null; rm -rf /opt/gpumon /var/log/gpumon /etc/systemd/system/gpumon.service; systemctl daemon-reload; echo gpumon removed"
az monitor data-collection rule association delete --name dcra-gpu-hours --resource "$VM_ID" --yes -o none || true
az monitor data-collection rule association delete --name configurationAccessEndpoint --resource "$VM_ID" --yes -o none || true
az vm extension delete -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent -o none
```
<!-- END GENERATED: offboard-commands -->

## Query from Your Platform

Each view in [`kql/`](kql/) is a complete query. The time window is the query's timespan, not something edited into the KQL. The `let` lines at the top hold the defaults you can change:
- `IdlePct`: busy threshold, default 5;
- `TzOffset`: UTC offset for hours and days, default `8h`;
- `Computers`: VM names to include, empty means all.

The three AML views require every GPU process to carry the AML job name in `AZUREML_RUN_ID`. Preserve it across every boundary in your launcher: pass it in the remote `env`, use Docker `-e AZUREML_RUN_ID`, and add `-x AZUREML_RUN_ID` to `mpirun`. The collector reads only that variable from `/proc/<pid>/environ`; it does not ingest the rest of the process environment. If several run IDs share one GPU-minute, the job views split that minute evenly.

The timespan for `per_job`, `per_submitter` and `live` must include the job submission event as well as the GPU rows. `live` returns the last process seen on each GPU in that window; use a short window for freshness or a wider one when submitter enrichment is required.

<!-- BEGIN GENERATED: views -->
- [`kql/summary.kql`](kql/summary.kql), all selected VMs together: `AllocatedGpuHours`, `BusyGpuHours`, `EffectiveGpuHours`, `IdleGpuHours`, `Vms`, `Gpus`, `UtilizationPct`
- [`kql/per_vm.kql`](kql/per_vm.kql), one row per VM: `Computer`, `VmSize`, `GpuName`, `Gpus`, `RunningHours`, `AllocatedGpuHours`, `BusyGpuHours`, `EffectiveGpuHours`, `IdleGpuHours`, `UtilizationPct`
- [`kql/per_hour.kql`](kql/per_hour.kql), one row per local hour: `Hour`, `AllocatedGpuHours`, `BusyGpuHours`, `EffectiveGpuHours`, `IdleGpuHours`, `UtilizationPct`
- [`kql/per_day.kql`](kql/per_day.kql), one row per local day: `Day`, `AllocatedGpuHours`, `BusyGpuHours`, `EffectiveGpuHours`, `IdleGpuHours`, `UtilizationPct`
- [`kql/per_user.kql`](kql/per_user.kql), one row per process owner and VM: `User`, `Computer`, `BusyGpuHours`, `EffectiveGpuHours`, `AvgSmActivePct`, `PeakMemoryGiB`, `Processes`
- [`kql/per_job.kql`](kql/per_job.kql), one row per AML job: `RunId`, `Submitter`, `SubmitterObjectId`, `Status`, `Vms`, `Gpus`, `StartTime`, `EndTime`, `BusyGpuHours`, `EffectiveGpuHours`, `PeakMemoryGiB`
- [`kql/per_submitter.kql`](kql/per_submitter.kql), one row per Entra submitter: `Submitter`, `SubmitterObjectId`, `Jobs`, `BusyGpuHours`, `EffectiveGpuHours`
- [`kql/live.kql`](kql/live.kql), latest GPU process seen in the query window: `Computer`, `GpuId`, `RunId`, `Submitter`, `SubmitterObjectId`, `Status`, `LastSeen`, `AgeSeconds`, `GpuUtil`, `SmActive`, `FbUsedMiB`, `ProcCount`, `Processes`
<!-- END GENERATED: views -->

**From a shell.** The `@` prefix makes the Azure CLI read the query from the file. `-t` takes an ISO 8601 duration such as `P1D`, or an interval `<start>/<end>`. The CLI returns every value as a string and adds a `TableName` column.

```bash
az monitor log-analytics query -w "$WORKSPACE_GUID" --analytics-query @kql/per_vm.kql -t P1D -o table
```

**From your API: REST.** Send the file content as `query` and the window as `timespan`, with a bearer token for `https://api.loganalytics.io`. The response is typed JSON: `tables[0].columns` and `tables[0].rows`.

```http
POST https://api.loganalytics.io/v1/workspaces/<workspace-guid>/query
Authorization: Bearer <token>
Content-Type: application/json

{"query": "<content of kql/per_vm.kql>", "timespan": "<start>/<end>"}
```

**From your API: Python SDK.** [`examples/gpu_hours_client.py`](examples/gpu_hours_client.py) wraps `azure-monitor-query`. Credentials come from `DefaultAzureCredential`: a managed identity where your API runs, or the Azure CLI login on a workstation. It overrides the `let` defaults and fails if a view does not have exactly one such line.

```bash
pip install -r examples/requirements.txt
END=$(date -u +%FT%TZ); START=$(date -u -d '-1 day' +%FT%TZ)
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_user --start "$START" --end "$END"
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_job --start "$START" --end "$END"
```

The same call returned this during the replay below:

<!-- BEGIN GENERATED: per-user-json -->
```json
[
 {
  "User": "user-1",
  "Computer": "gpu-vm-1",
  "BusyGpuHours": 0.0417,
  "EffectiveGpuHours": 0.0362,
  "AvgSmActivePct": 87.55,
  "PeakMemoryGiB": 41.9707,
  "Processes": "python3"
 },
 {
  "User": "user-2",
  "Computer": "gpu-vm-1",
  "BusyGpuHours": 0.0417,
  "EffectiveGpuHours": 0.038,
  "AvgSmActivePct": 90.24,
  "PeakMemoryGiB": 41.9707,
  "Processes": "python3"
 }
]
```
<!-- END GENERATED: per-user-json -->

**Which interface your platform calls.** Nothing custom sits between your platform and the data:
- API: the Log Analytics Query API above, one `POST` per view, the KQL file content in `query`, the window in `timespan`;
- library: `azure-identity` and `azure-monitor-query` ([`examples/requirements.txt`](examples/requirements.txt)) for Python; the Azure Monitor Query client library also exists for .NET, Java, JavaScript and Go;
- permission: `Log Analytics Reader` on the workspace, nothing on the VMs or the AML workspace.

The same job query without the reference client:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient

client = LogsQueryClient(DefaultAzureCredential())
end = datetime.now(timezone.utc)
result = client.query_workspace("<workspace-guid>", Path("kql/per_job.kql").read_text(encoding="utf-8"),
                                timespan=(end - timedelta(days=1), end))
jobs = [dict(zip(result.tables[0].columns, row)) for row in result.tables[0].rows]
```

Give the identity of your API read access to the workspace:

```bash
az role assignment create --assignee <principal-id> --role "Log Analytics Reader" \
  --scope "$(az monitor log-analytics workspace show -g rg-gpu-hours -n law-gpu-hours --query id -o tsv)"
```

For whole local days in `per_day`, start and end the timespan at local midnight, written in UTC. Allocated hours come from the agent's `Heartbeat`, not from your bill. Reconcile invoices with Cost Management.

## Validation on One H100 VM

Three runs checked the pipeline on one GPU. In `validation-1`, a load with a known schedule showed whether each minute is classified correctly. In `replay-1`, the configuration steps above ran verbatim against a new resource group, with two owners sharing the GPU. In `jobs-1`, three AML jobs ran as one Linux user and were attributed by job name and submitter.

<img src="images/test-topology-en.png" width="900" alt="Measured VM Standard_NC40ads_H100_v5 in Spain Central running the known load, gpumon and the Azure Monitor Agent; data collection endpoint, rule and workspace in the same region; operator workstation running the scripts and queries">

The VM was a `Standard_NC40ads_H100_v5` with one NVIDIA H100 NVL: Ubuntu 24.04.5, driver 615.71.09, DCGM 3.3.9 and Azure Monitor Agent 1.45. The workspace was in the same region. The operator workstation ran the scripts with Azure CLI 2.88.0 and called the Query API.

### validation-1: a known load with one owner

**Question.** Does every GPU-minute of a load with a known schedule land in the class the schedule predicts, and do the views return the same numbers as the raw rows?

**Input.** This script ran as the VM's administrator account (`user-1` below): 480 s of back-to-back bf16 matrix multiplication, 180 s holding 20 GiB of GPU memory with no kernels, and 300 s at a 50 % duty cycle. [`tests/load/gpu_load.py`](tests/load/gpu_load.py) runs the same schedule by default.

<!-- BEGIN GENERATED: load-input -->
```python
# Demo load: 8 min heavy bf16 matmul, 3 min idle (process holds memory), 5 min ~50% duty cycle
import time, torch
a = torch.randn(8192, 8192, device="cuda", dtype=torch.bfloat16)
b = torch.randn(8192, 8192, device="cuda", dtype=torch.bfloat16)
buf = torch.empty(20 * 1024**3 // 2, device="cuda", dtype=torch.bfloat16)  # hold ~20GB
def run(sec, duty=1.0):
    end = time.time() + sec
    while time.time() < end:
        t0 = time.time()
        while time.time() - t0 < duty:
            for _ in range(20): c = a @ b
            torch.cuda.synchronize()
        if duty < 1.0: time.sleep(1.0 - duty)
run(480); time.sleep(180); run(300, 0.5)
print("done")
```
<!-- END GENERATED: load-input -->

**Varied and fixed.** Only the load phase changed. The VM, the GPU, the single process and the 5 % busy threshold stayed the same.

**Result.**

<img src="images/gpu-minutes-en.png" width="900" alt="Per-minute SM active of validation-1: one held minute while the process started, eight full minutes near 96 percent, three held minutes, five partial minutes near 35 percent, then idle minutes">

<!-- BEGIN GENERATED: phases -->
| Phase (first minute) | Minutes | SM active | Power |
|---|---:|---:|---:|
| held (13) | 1 | 0.0 % | 65 W |
| full (14) | 8 | 96.3 % | 398 W |
| held (22) | 3 | 0.2 % | 107 W |
| partial (25) | 5 | 34.7 % | 280 W |
<!-- END GENERATED: phases -->

<!-- BEGIN GENERATED: summary-v1 -->
- Allocated 2.717, busy 0.283, effective 0.157 and idle 2.433 GPU-hours; utilization 5.80 %.
- Allocated time is 163 Heartbeat minutes: the VM kept running after the load, which is what the idle hours show.
- 16 of the 17 busy minutes carry the owner `user-1`.
<!-- END GENERATED: summary-v1 -->

**Boundary.**
- One GPU and one synthetic load; no production workload was measured.
- The single held minute at the start is the process loading and allocating before it ran kernels.
- The busy minute without an owner is the last partial minute. The job exited during it, before the end-of-minute process sample.

### replay-1: the published steps on a new resource group, two owners

**Question.** Do steps 1–3 and the removal work exactly as written, from a clean copy, against a resource group that did not exist? Does a GPU-minute shared by two owners count half for each?

**Input.** The commands in [Configure on Azure](#configure-on-azure), run from a clean export of the committed files against `rg-gpu-hours-replay`. Then this load, as two new OS users, the second starting 120 s after the first:

```bash
./tests/load/run-load.sh -g <vm-rg> -n <vm-name> -u <user-1>,<user-2> -p "--phase full:240" -D 120
```

**Varied and fixed.** The resource group was new, and the GPU had two owners. The VM, collector, rule and queries stayed the same.

**Result.**

<!-- BEGIN GENERATED: replay-steps -->
- **1 workspace, table, DCE, DCR**: exit 0, 181 s. Table 23 columns, 90-day retention; rule reads /var/log/gpumon/*.json.
- **2 VM onboarding**: exit 0, 102 s. gpumon.service active, running dcgmi dmon.
- **3 first rows**: exit 0. Heartbeat about 8 min, GpuMetrics_CL about 11 min after onboarding.
- **4 two-user load**: exit 0, 213 s. 2 processes of 21 GiB each on the GPU.
- **5 queries: CLI and client**: exit 0. CLI and client return the same per-owner values.
- **6 removal**: exit 0, 98 s. No agent, association or collector left; resource group deleted.
<!-- END GENERATED: replay-steps -->

<img src="images/owners-en.png" width="900" alt="Per-minute owner shares of replay-1: one minute user-1 only, three minutes shared half and half, one minute user-2 only">

<!-- BEGIN GENERATED: owners -->
| Owner | Busy GPU-h | Effective GPU-h |
|---|---:|---:|
| `user-1` | 0.042 | 0.036 |
| `user-2` | 0.042 | 0.038 |

- 6 busy minutes: 5 with an owner, of which 3 shared by both, and 1 without an owner.
<!-- END GENERATED: owners -->

**Boundary.**
- Each user ran for 240 s, but only 2.5 minutes each were attributed. Owners are read at the end of each minute, so the minute in which a job starts or ends counts only if the job is still on the GPU at that moment.
- `PeakMemoryGiB` in `per_user` is the memory in use on the GPU, not per process: 42 GiB while both ran.
- After the VM was deallocated and started again, it ran on a different host, so the GPU UUID changed. The views group by VM name and GPU index, so this does not change the numbers.

### jobs-1: AML jobs and their submitter, one Linux user

**Question.** When every GPU process runs as the same Linux user, as it does when an AML job starts torchrun or mpirun on its hosts over SSH, can a platform still read GPU-hours per job and per submitting Entra account, including the minutes two jobs share one GPU?

**Input.** The VM above, onboarded with `scripts/onboard-vm.sh` to a workspace set up with `scripts/setup-workspace.sh -a`, and attached to an AML workspace in the same subscription as a `virtualmachine` compute. One Entra account (`submitter-1` below) submitted three AML command jobs. In its AML container, each job ran the launcher below, which starts [`tests/load/gpu_load.py`](tests/load/gpu_load.py) with `--phase full:150 --phase partial:90:0.5` on the host over SSH, as one Linux account (`user-1` below), and passes `AZUREML_RUN_ID` on. `job-3` was submitted about a minute after `job-2`, so the two shared the GPU.

<!-- BEGIN GENERATED: jobs-launcher -->
```bash
#!/bin/bash
# Runs in the AML job container on the attached VM. Starts the GPU load on the VM host over SSH and passes the
# AML job name on in AZUREML_RUN_ID, the way a multi-node launcher starts torchrun or mpirun on its hosts.
set -euo pipefail
HOST=${GPU_HOST:?}; PORT=${GPU_HOST_PORT:-22}; USER_ON_HOST=${GPU_HOST_USER:-amljob}
KEY=/tmp/aml_host_key; cp ./aml_host_key "$KEY"; chmod 600 "$KEY"
OPTS=(-i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o LogLevel=ERROR)
REMOTE=/tmp/gpu_load_${AZUREML_RUN_ID}.py
echo "[launcher] job=${AZUREML_RUN_ID} container=$(hostname) host=${HOST}:${PORT} start=$(date -u +%FT%TZ)"
scp -q -P "$PORT" "${OPTS[@]}" ./gpu_load.py "${USER_ON_HOST}@${HOST}:${REMOTE}"
set +e
ssh -p "$PORT" "${OPTS[@]}" "${USER_ON_HOST}@${HOST}" "env AZUREML_RUN_ID=${AZUREML_RUN_ID} /usr/bin/python3 ${REMOTE} $*; rc=\$?; rm -f ${REMOTE}; exit \$rc"
rc=$?
echo "[launcher] job=${AZUREML_RUN_ID} rc=${rc} end=$(date -u +%FT%TZ)"
exit $rc
```
<!-- END GENERATED: jobs-launcher -->

**Varied and fixed.** The job name changed, and two of the jobs overlapped. The VM, the GPU, the Linux account, the submitter and the queries stayed the same.

**Result.**

<!-- BEGIN GENERATED: jobs-steps -->
- **1 workspace with job tracking**: exit 0, 209 s. Table 24 columns including RunId; Administrative activity and AmlRunStatusChangedEvent go to the workspace.
- **2 VM onboarding**: exit 0, 160 s. gpumon.service active with the RunId collector.
- **3 VM attached to AML**: exit 0, 6 s. Compute provisioning state Succeeded.
- **4 three AML jobs**: exit 0. All Completed; job-2 and job-3 shared the GPU as one Linux user, each process with its own AZUREML_RUN_ID.
- **5 read back: the eight views through the client**: exit 0, 44 s. Raw rows and all views exported.
- **6 cleanup**: exit 0. Compute detached, test account removed, diagnostic settings and resource group deleted, VM deallocated.
<!-- END GENERATED: jobs-steps -->

<!-- BEGIN GENERATED: jobs-result -->
| Job | Submitter | Busy GPU-h | Effective GPU-h |
|---|---|---:|---:|
| `job-1` | `submitter-1` | 0.067 | 0.047 |
| `job-2` | `submitter-1` | 0.042 | 0.032 |
| `job-3` | `submitter-1` | 0.042 | 0.029 |

- `per_user` over the same window: one owner, `user-1`, with 0.150 busy GPU-hours, the three jobs added together.
- 11 busy minutes: 9 with a job name, of which 3 carried two names and counted half for each, and 2 without a name.
- Status events of every job: Running → Finalizing → Completed.
- Ingestion delay: GPU rows median 83 s; status events median 38 s, at most 55 s; submissions median 363 s, at most 538 s.
<!-- END GENERATED: jobs-result -->

**Boundary.**
- One submitter: the test account could not grant a second identity access to the AML workspace, so `per_submitter` has one row. Each job's submitter comes from the `Caller` of that job's own `jobs/write` event, so a second account would be a second row.
- The submitter arrives with the Azure Activity export, minutes after the GPU rows. Until then `per_job` lists the job with an empty submitter. Status events arrive faster than the GPU rows.
- Job names, like owners, are read once at the end of each minute. A minute in which a job ends counts for the jobs still on the GPU at that moment, or for none.
- Running AML jobs on an attached Ubuntu 24.04 VM needed three AML prerequisites, recorded in [`evidence/runs.json`](evidence/runs.json): `ssh-rsa` accepted for the attach account, `python` on the host, and workspace storage that AML can reach for logs. They belong to AML, not to the steps in this repository.

### Numbers you can recompute

<!-- BEGIN GENERATED: checks -->
- KQL against Python: 13 values in the first run and 15 in the second, largest difference 0.0.
- `jobs-1`: 13 values of the classic views, and 11 values and 28 fields of the job views, largest difference 0.0.
- Ingestion delay of GpuMetrics_CL rows: median 76 s, p95 125 s.
- Billed size: 343 bytes per GPU row, 547 bytes per Heartbeat row.
<!-- END GENERATED: checks -->

## Tests and Offline Checks

The offline checks need Python 3.10 or newer and no Azure access:

```bash
pip install -r examples/requirements.txt
python -m unittest discover -s tests -v
python tools/build_evidence.py --check
python tools/build_readme.py --check
python tools/draw_diagrams.py --check
python tools/check_repo.py
```

Done when all tests pass and each check prints `PASS`.

- **`python -m unittest discover -s tests -v`** tests:
  - collector: `dcgmi dmon` line parsing on real output, averaging, and a JSON line whose keys equal the rule's stream and the table columns;
  - views: shared `let` lines are identical, `summary` is `per_vm` summed, and AML views join by `RunId`;
  - reference client: `let` overrides and the timespan sent;
  - evidence: recomputation, including the 1/N owner and job splits, the first submitter and the last status;
  - public content: every rule of `tools/check_repo.py`, with deliberate breaks that must fail.
- **`tools/build_evidence.py --check`** rebuilds [`evidence/measurements.json`](evidence/measurements.json) from the committed rows and fails if a KQL result differs from the Python recomputation.
- **`tools/build_readme.py --check`** fails if a number, table or command in either README differs from a fresh render of the evidence and the scripts.
- **`tools/draw_diagrams.py --check`** compares every image with its SHA-256 in [`images/SOURCES.json`](images/SOURCES.json).
- **`tools/check_repo.py`** checks links, heading order, table width, English/Chinese number parity and private-content guards.

CI runs the same commands on Ubuntu and Windows with Python 3.10 and 3.12 ([workflow](../../.github/workflows/azure-gpu-hours-monitoring-ci.yml)).

The live checks need Azure:
- the step 3 query;
- the reference client;
- the load test, which needs a GPU VM and PyTorch: `./tests/load/run-load.sh -g <vm-rg> -n <vm-name> -u <user>`. Remove the test users afterwards with `-x`.

Not tested here: VMs with more than one GPU, MIG, DCGM 4.x, Azure Private Link, sovereign clouds, and more than one submitter account.

## Limits, Assets and Sources

**Limits.**

- `LOCAL_MEASUREMENT`: owners are sampled once, at the end of each minute. A job that exits mid-minute leaves that minute busy but unattributed, and a job that starts mid-minute is counted from the end of its first minute.
- `LOCAL_MEASUREMENT`: allocated time starts at the agent's first `Heartbeat`. Lines the collector wrote before the agent began collecting were not ingested (minutes 5–10 of `validation-1`).
- `LOCAL_MEASUREMENT`: `PeakMemoryGiB` is the GPU's memory in use, not a per-process figure.
- `LOCAL_MEASUREMENT`: a job's submitter arrives with the Azure Activity export, several minutes after its GPU rows (`jobs-1`).
- `LOCAL_MEASUREMENT`: a run ID is sampled at the end of each minute. If several run IDs share a GPU-minute, each receives an equal fraction because DCGM does not expose per-process SM activity.
- `NOT_MEASURED`: 8-GPU VMs. The collector reads every GPU that `nvidia-smi` lists and the views count GPUs per VM, but only one GPU was measured.
- `NOT_MEASURED`: MIG instances, DCGM 4.x, and jobs that do not propagate an identifier. AML uses `AZUREML_RUN_ID`; other schedulers need an equivalent collector and query convention.
- `NOT_MEASURED`: the delay from VM start to first `Heartbeat` for a VM that already has the agent.
- `SOURCE_FACT`: the `log-analytics` Azure CLI extension has no stable version (1.0.0b2 in this run). A platform should call the Query API through REST or the SDK.
- Allocated hours follow VM running time as the agent reports it. They are not billing records: reconcile invoices with Cost Management.

**Assets.**

- [`vm/`](vm/): `gpu_collector.py` (DCGM to JSON lines) and `install_collector.sh` (systemd unit, enables `nvidia-dcgm`).
- [`azure/`](azure/): `dcr-rule.json`, the data collection rule for `az monitor data-collection rule create --rule-file`.
- [`scripts/`](scripts/): `configure.sh` (every step in one command, driven by `gpu-hours.env.example`), `setup-workspace.sh`, `onboard-vm.sh`, `offboard-vm.sh`.
- [`kql/`](kql/): the eight views.
- [`examples/`](examples/): `gpu_hours_client.py`, the reference Query API client, and its `requirements.txt`.
- [`evidence/`](evidence/): run contracts (`runs.json`), the projected rows and view results of the three runs (`runs/`), with SHA-256 of their private sources, and `measurements.json`.
- [`tests/`](tests/): offline tests, and `tests/load/` with the load generator and its Run Command wrapper.
- [`tools/`](tools/): evidence, README and diagram builders, and the public-content audit.
- [`images/`](images/): English and Chinese figures and their ledger `SOURCES.json`.

**Sources.**

- [Collect JSON logs with Azure Monitor Agent](https://learn.microsoft.com/azure/azure-monitor/vm/data-collection-log-json) and [data collection rule structure](https://learn.microsoft.com/azure/azure-monitor/data-collection/data-collection-rule-structure)
- [Azure HPC VM images](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images), which include DCGM
- [`az monitor data-collection rule`](https://learn.microsoft.com/cli/azure/monitor/data-collection/rule) and [`az monitor log-analytics query`](https://learn.microsoft.com/cli/azure/monitor/log-analytics#az-monitor-log-analytics-query)
- [Log Analytics Query API](https://learn.microsoft.com/azure/azure-monitor/logs/api/overview), [Azure Monitor Query client library for Python](https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme), [`Heartbeat`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/heartbeat), [`AzureActivity`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/azureactivity) and [`AmlRunStatusChangedEvent`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/amlrunstatuschangedevent)
- [DCGM field identifiers](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-api/dcgm-api-field-ids.html) and [DCGM profiling metrics](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html#profiling-metrics)
- For GPU node pools on AKS, use Azure Monitor managed Prometheus with the [DCGM exporter integration](https://learn.microsoft.com/azure/azure-monitor/containers/prometheus-dcgm-integration) instead of this collector.
