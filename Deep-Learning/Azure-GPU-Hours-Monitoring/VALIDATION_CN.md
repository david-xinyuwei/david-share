# 实测细节与评审

[English](VALIDATION.md) · 客户操作见 [README_CN.md](README_CN.md)

本文给评审和需要核对数字的读者：怎么测的、每次实测的输入和结果、哪些没测、怎样离线复算。客户照着做不需要看本文。

## 架构与指标口径

GPU VM 上只做两件事：
1. NVIDIA DCGM host engine 提供每张卡的计数器；
2. 采集器定时读取这些计数器，每张卡每分钟写一行 JSON 到本地文件。

之后的环节全部由 Azure Monitor 完成：
1. Azure Monitor Agent 读取这个文件，经数据收集终结点和规则写入 `GpuMetrics_CL` 表；
2. 同一个代理在 VM 运行期间每分钟写一行 `Heartbeat`；
3. KQL 把这两张表关联起来，算出卡时。

**VM 上。** [`vm/gpu_collector.py`](vm/gpu_collector.py) 由 [`vm/install_collector.sh`](vm/install_collector.sh) 安装成 systemd 服务 `gpumon`，只依赖 Python 标准库。它执行的命令是：

<!-- BEGIN GENERATED: dcgm-command -->
```bash
dcgmi dmon -e 203,1001,1002,1004,1005,252,250,155,150 -d 10000
```
<!-- END GENERATED: dcgm-command -->

即每 10 秒采一次 9 个 DCGM 字段。采集器每分钟做以下几件事：
1. 把每张卡在这一分钟内的各个字段求平均；
2. 从实例元数据服务读取 VM 名称、规格、资源 ID 和标签；
3. 用 `nvidia-smi --query-compute-apps` 和 `/proc/<pid>` 记录 GPU 上每个进程的 Linux 属主和进程名；
4. 如果启动器传递了 `AZUREML_RUN_ID`，只从进程环境中读取这一项；
5. 每张卡一行，追加到 `/var/log/gpumon/gpu_metrics_<day>.json`，并删除三天前的文件。

<!-- BEGIN GENERATED: dcgm-fields -->
- `203` `DCGM_FI_DEV_GPU_UTIL` → `GpuUtil`：占用判定阈值
- `1001` `DCGM_FI_PROF_GR_ENGINE_ACTIVE` → `GrActive`：参考
- `1002` `DCGM_FI_PROF_SM_ACTIVE` → `SmActive`：有效计算卡时
- `1004` `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` → `TensorActive`：参考
- `1005` `DCGM_FI_PROF_DRAM_ACTIVE` → `DramActive`：参考
- `252` `DCGM_FI_DEV_FB_USED` → `FbUsedMiB`：显存占用
- `250` `DCGM_FI_DEV_FB_TOTAL` → `FbTotalMiB`：显存容量
- `155` `DCGM_FI_DEV_POWER_USAGE` → `PowerW`：参考
- `150` `DCGM_FI_DEV_GPU_TEMP` → `TempC`：参考
<!-- END GENERATED: dcgm-fields -->

被测 VM 上这个文件里的一行（名称已替换）：

<!-- BEGIN GENERATED: json-line -->
```json
{"TimeGenerated": "<minute start, UTC>", "VmName": "<vm-name>", "VmSize": "Standard_NC40ads_H100_v5", "VmResourceId": "<vm resource id>", "Tags": "", "GpuId": 0, "GpuUuid": "<GPU UUID>", "GpuName": "NVIDIA H100 NVL", "Samples": 6, "GpuUtil": 100, "GrActive": 0.9818, "SmActive": 0.9413, "TensorActive": 0.916, "DramActive": 0.1307, "FbUsedMiB": 21618, "FbTotalMiB": 95830, "PowerW": 397.6368, "TempC": 64.1667, "ProcCount": 1, "Users": "<linux user>", "Processes": "python3", "RunId": "<AML run ID>"}
```
<!-- END GENERATED: json-line -->

**Azure Monitor 里。** 数据收集规则 [`azure/dcr-rule.json`](azure/dcr-rule.json) 声明了一个 `Custom-Json-GpuMetrics` 数据流，列与 JSON 行一一对应。它读取 `/var/log/gpumon/*.json`，写入 `GpuMetrics_CL`。代理用 VM 的托管身份认证，经数据收集终结点上传。`Heartbeat` 不需要配置，每个代理都会发送。

**指标口径。** 每个分配的 GPU·分钟先分成“已观测”和“未知”；已观测分钟再分成“占用”和“空闲”。有效计算是已观测分钟内按活跃度加权的量。

| 指标 | 定义 | 来源 |
|---|---|---|
| 分配卡时 | VM 运行分钟数 × GPU 数 ÷ 60 | `Heartbeat` 分钟数 |
| 已观测卡时 | 收到的不同 GPU·分钟数 ÷ 60 | `GpuMetrics_CL` 数据 |
| 占用卡时 | 有计算进程或 GPU Util ≥ 5 % 的 GPU·分钟 ÷ 60 | `ProcCount`、`GpuUtil` |
| 有效计算卡时 | Σ SM Active ÷ 60 | `SmActive` |
| 空闲卡时 | 已观测 − 占用 | 计算得出 |
| 未知卡时 | 分配 − 已观测 | 计算得出；遥测缺失，不能算空闲 |
| 遥测覆盖率 | 已观测 ÷ 分配 | 计算得出 |
| 有效利用率 | 有效计算 ÷ 分配 | 计算得出 |

有效计算卡时用 SM Active，不用 GPU Util：
- `DCGM_FI_DEV_GPU_UTIL` 统计的是“有任意 kernel 在跑”的时间占比，一张卡只跑小 kernel 也会显示 100 %；
- `DCGM_FI_PROF_SM_ACTIVE` 统计的是流式多处理器（SM）真正有活干的时间占比。

两者可能差很多：下面实测的半载阶段，GPU Util 平均 51 %，SM Active 平均只有 35 %。

一个进程占着显存却不跑 kernel，这张卡就算“占用”，但不算“有效计算”。回收 GPU 时，要找的正是这种情况。不能只看空闲卡时就回收：遥测覆盖率要满足客户自己的判定要求，未知卡时表示采集数据缺失。

## 配置命令实际执行了什么

每个分步脚本也可以单独运行，例如由 Azure Policy 或你自己的自动化流程调用。

**`scripts/setup-workspace.sh`**（每个工作区运行一次）：

```bash
./scripts/setup-workspace.sh -g rg-gpu-hours -l <region> [-r <天数>] [-a <AML 工作区资源 ID>]
```

脚本最后打印 `WORKSPACE_GUID`、`DCR_ID` 和 `DCE_ID`。脚本包含以下 Azure CLI 命令；建表与更新表按表是否存在二选一，诊断设置仅在提供 `-a` 时创建：

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
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv)
az monitor data-collection endpoint create -g "$RG" -n "$DCE" -l "$LOC" --public-network-access Enabled -o none
DCE_ID=$(az monitor data-collection endpoint show -g "$RG" -n "$DCE" --query id -o tsv)
az monitor data-collection rule create -g "$RG" -n "$DCR" -l "$LOC" --kind Linux \
  --endpoint-id "$DCE_ID" --rule-file "$RULE_FILE" -o none
DCR_ID=$(az monitor data-collection rule show -g "$RG" -n "$DCR" --query id -o tsv)
WORKSPACE_GUID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)
az monitor diagnostic-settings subscription create -n "$SUB_DIAG" -l "$LOC" \
  --workspace "$LAW_ID" --logs '[{"category":"Administrative","enabled":true}]' -o none
az monitor diagnostic-settings create -n "$AML_DIAG" --resource "$AML_ID" --workspace "$LAW_ID" \
  --export-to-resource-specific true --logs '[{"category":"AmlRunStatusChangedEvent","enabled":true}]' -o none
```
<!-- END GENERATED: setup-commands -->

第一次运行时建表，之后再运行会更新这张表。`-a` 需要在订阅范围和 AML 工作区上创建诊断设置的权限。检查结果：

```bash
az monitor log-analytics workspace table show -g "$WORKSPACE_RG" --workspace-name "$WORKSPACE_NAME" -n GpuMetrics_CL \
  --query "{plan: plan, retention: retentionInDays, columns: length(schema.columns)}" -o json
DCR_NAME=${DCR_ID##*/}
az monitor data-collection rule show -g "$WORKSPACE_RG" -n "$DCR_NAME" \
  --query "{kind: kind, files: dataSources.logFiles[0].filePatterns, stream: dataFlows[0].outputStream}" -o json
```

期望结果：
- 表有 24 列，保留天数与设置一致；
- 规则的 kind 为 `Linux`，读取 `/var/log/gpumon/*.json`，输出到 `Custom-GpuMetrics_CL`。

**`scripts/onboard-vm.sh`**（每台 VM 运行一次）：

```bash
./scripts/onboard-vm.sh -g "$VM_RG" -n "$VM_NAME" -d "$DCR_ID" -e "$DCE_ID"
```

脚本做三件事：
1. 开启 VM 的系统分配托管身份，安装 Azure Monitor Agent；
2. 把规则关联到这台 VM。VM 没有 DCE 关联时，再关联本次部署的终结点；已有其他 DCE 占用 `configurationAccessEndpoint` 时，脚本停止，不会改写其他监控配置；
3. 经 Run Command 运行 [`vm/install_collector.sh`](vm/install_collector.sh)，启用 `nvidia-dcgm`，并把 `gpumon` 装成 systemd 服务。

<!-- BEGIN GENERATED: onboard-commands -->
```bash
az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
az vm identity assign -g "$RG" -n "$VM" -o none
az vm extension set -g "$RG" --vm-name "$VM" -n AzureMonitorLinuxAgent --publisher Microsoft.Azure.Monitor \
  --enable-auto-upgrade true -o none
az monitor data-collection rule association create --name "$DCR_ASSOC" --resource "$VM_ID" --rule-id "$DCR_ID" -o none
EXISTING_DCE=$(az monitor data-collection rule association show --name configurationAccessEndpoint --resource "$VM_ID" \
  --query dataCollectionEndpointId -o tsv 2>/dev/null || true)
az monitor data-collection rule association create --name configurationAccessEndpoint --resource "$VM_ID" \
  --endpoint-id "$DCE_ID" -o none
RUN_OUTPUT=$(az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --scripts "@$SCRIPT" \
  --query "value[0].message" -o tsv)
```
<!-- END GENERATED: onboard-commands -->

Run Command 输出的最后是 `systemctl status gpumon`，必须看到 `active (running)` 和上面那条 `dcgmi dmon` 命令。

也可以不逐台运行脚本，改用两条 Azure Policy 内置策略安装代理并关联规则：
- *Configure Linux virtual machines to run Azure Monitor Agent with system-assigned managed identity-based authentication*；
- *Configure Linux Machines to be associated with a Data Collection Rule or a Data Collection Endpoint*。

这时把 `vm/install_collector.sh` 加进 VM 镜像的构建步骤。

**在命令行里查询。** `log-analytics` CLI 扩展只有预览版：

```bash
az extension add --upgrade --yes --name log-analytics
az monitor log-analytics query -w "$WORKSPACE_GUID" -t PT30M -o table --analytics-query \
  "union (Heartbeat | summarize Rows = count(), Last = max(TimeGenerated) by Table = 'Heartbeat', Computer), (GpuMetrics_CL | summarize Rows = count(), Last = max(TimeGenerated) by Table = 'GpuMetrics_CL', Computer)"
```

**`scripts/offboard-vm.sh`**（每台 VM 运行一次）：

<!-- BEGIN GENERATED: offboard-commands -->
```bash
az extension add --upgrade --yes --name monitor-control-service -o none
VM_ID=$(az vm show -g "$RG" -n "$VM" --query id -o tsv)
RUN_OUTPUT=$(az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --query "value[0].message" -o tsv --scripts \
  "set -eu; systemctl disable --now gpumon 2>/dev/null || [ ! -e /etc/systemd/system/gpumon.service ]; rm -rf /opt/gpumon /var/log/gpumon /etc/systemd/system/gpumon.service; systemctl daemon-reload; [ ! -e /etc/systemd/system/gpumon.service ]; echo gpumon removed")
ASSOCIATION_NAMES=$(az monitor data-collection rule association list --resource "$VM_ID" --query "[].name" -o tsv)
az monitor data-collection rule association delete --name "$DCR_ASSOC" --resource "$VM_ID" --yes -o none
EXISTING_DCE=$(az monitor data-collection rule association list --resource "$VM_ID" \
  --query "[?name=='configurationAccessEndpoint'].dataCollectionEndpointId | [0]" -o tsv)
OTHER_DCRS=$(az monitor data-collection rule association list --resource "$VM_ID" \
  --query "[?dataCollectionRuleId != null && name != '$DCR_ASSOC'].name" -o tsv)
az monitor data-collection rule association delete --name configurationAccessEndpoint --resource "$VM_ID" --yes -o none
```
<!-- END GENERATED: offboard-commands -->

## 查询细节

[`kql/`](kql/) 下每个文件都是一条完整的查询。统计时段由查询的 timespan 指定，不写进 KQL。文件开头的 `let` 行是可以修改的默认值：
- `IdlePct`：占用判定阈值，默认 5；
- `TzOffset`：按小时、按天统计用的 UTC 偏移，默认 `8h`；
- `Computers`：只统计这些 VM，留空表示全部。

三个 AML 查询要求每个 GPU 进程都带有作业 ID，做法见 [README_CN.md](README_CN.md) 操作步骤第 5 步；平台登录是第 7 步，按作业查询的实测返回在“实现效果”。`per_job`、`per_submitter` 和 `live` 的 timespan 必须同时覆盖作业提交事件和 GPU 数据。`live` 为每张卡上出现过的每个作业（`RunId`）保留最后一行，所以一张卡在时段内跑过多个作业时会返回多行；要看新鲜度就用短时段，要补全提交人则使用能覆盖提交时刻的较宽时段。

<!-- BEGIN GENERATED: views -->
- [`kql/summary.kql`](kql/summary.kql)，所选 VM 合计：`AllocatedGpuHours`、`ObservedGpuHours`、`BusyGpuHours`、`EffectiveGpuHours`、`IdleGpuHours`、`UnknownGpuHours`、`Vms`、`Gpus`、`TelemetryCoveragePct`、`UtilizationPct`
- [`kql/per_vm.kql`](kql/per_vm.kql)，每台 VM 一行：`Computer`、`VmSize`、`GpuName`、`Gpus`、`RunningHours`、`AllocatedGpuHours`、`ObservedGpuHours`、`BusyGpuHours`、`EffectiveGpuHours`、`IdleGpuHours`、`UnknownGpuHours`、`TelemetryCoveragePct`、`UtilizationPct`
- [`kql/per_hour.kql`](kql/per_hour.kql)，每个本地小时一行：`Hour`、`AllocatedGpuHours`、`ObservedGpuHours`、`BusyGpuHours`、`EffectiveGpuHours`、`IdleGpuHours`、`UnknownGpuHours`、`TelemetryCoveragePct`、`UtilizationPct`
- [`kql/per_day.kql`](kql/per_day.kql)，每个本地日一行：`Day`、`AllocatedGpuHours`、`ObservedGpuHours`、`BusyGpuHours`、`EffectiveGpuHours`、`IdleGpuHours`、`UnknownGpuHours`、`TelemetryCoveragePct`、`UtilizationPct`
- [`kql/per_user.kql`](kql/per_user.kql)，每个进程属主、每台 VM 一行：`User`、`Computer`、`BusyGpuHours`、`EffectiveGpuHours`、`AvgSmActivePct`、`PeakMemoryGiB`、`Processes`
- [`kql/per_job.kql`](kql/per_job.kql)，每个 AML 作业一行：`RunId`、`Submitter`、`SubmitterObjectId`、`Status`、`Vms`、`Gpus`、`StartTime`、`EndTime`、`BusyGpuHours`、`EffectiveGpuHours`、`PeakMemoryGiB`
- [`kql/per_submitter.kql`](kql/per_submitter.kql)，每个 Entra 提交人一行：`Submitter`、`SubmitterObjectId`、`Jobs`、`BusyGpuHours`、`EffectiveGpuHours`
- [`kql/live.kql`](kql/live.kql)，查询时段内，每张卡上每个作业的最后一行：`Computer`、`GpuId`、`RunId`、`Submitter`、`SubmitterObjectId`、`Status`、`LastSeen`、`AgeSeconds`、`GpuUtil`、`SmActive`、`FbUsedMiB`、`ProcCount`、`Processes`
<!-- END GENERATED: views -->

**命令行。** `@` 前缀让 Azure CLI 从文件读取查询。`-t` 接受 ISO 8601 时长（如 `P1D`）或时间区间 `<开始>/<结束>`。它会把所有值都返回成字符串，并多出一列 `TableName`。

```bash
az monitor log-analytics query -w "$WORKSPACE_GUID" --analytics-query @kql/per_vm.kql -t P1D -o table
```

**客户 API：REST。** 把文件内容作为 `query`，统计时段作为 `timespan`，请求发送到当前的 `api.loganalytics.azure.com` 主机，并携带资源为 `https://api.loganalytics.io` 的 Bearer 访问令牌。响应是带类型的 JSON：列定义在 `tables[0].columns`，数据行在 `tables[0].rows`。

```http
POST https://api.loganalytics.azure.com/v1/workspaces/<WORKSPACE_GUID>/query
Authorization: Bearer <access-token>
Content-Type: application/json

{"query": "<content of kql/per_vm.kql>", "timespan": "<start>/<end>"}
```

**客户 API：Python SDK。** [`examples/gpu_hours_client.py`](examples/gpu_hours_client.py) 封装了 `azure-monitor-query`：
- 加 `--credentials gpu-hours.query.env` 时，用文件里的应用注册经 `ClientSecretCredential` 登录，工作区 GUID 也从文件读取；
- 不加时用 `DefaultAzureCredential`：依次尝试 `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` 环境变量、托管身份和 Azure CLI 登录；
- 它会改写 `let` 默认值；某个查询里对应的 `let` 行不是恰好一行时直接报错。

```bash
pip install -r examples/requirements.txt
END=$(date -u +%FT%TZ); START=$(date -u -d '-1 day' +%FT%TZ)
python examples/gpu_hours_client.py --credentials gpu-hours.query.env --view per_user --start "$START" --end "$END"
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_job --start "$START" --end "$END"
```

下面实测中的同一次调用返回：

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

**客户平台调用的接口。** 客户平台和数据之间没有任何自建服务：
- API：上面的 Log Analytics 查询 API，每个查询发一次 `POST`，`query` 填 KQL 文件内容，`timespan` 填统计时段；
- 库：Python 用 `azure-identity` 和 `azure-monitor-query`（[`examples/requirements.txt`](examples/requirements.txt)）；Azure Monitor Query 客户端库也有 .NET、Java、JavaScript 和 Go 版本；
- 权限：只需要工作区上的 `Log Analytics Reader`，不需要 VM 或 AML 工作区的权限。

不用参考客户端、直接调用 SDK 查询作业的写法：

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.monitor.query import LogsQueryClient

# 应用注册：值来自 gpu-hours.query.env；托管身份或环境变量：DefaultAzureCredential()
credential = ClientSecretCredential("<AZURE_TENANT_ID>", "<AZURE_CLIENT_ID>", "<AZURE_CLIENT_SECRET>")
client = LogsQueryClient(credential)
end = datetime.now(timezone.utc)
result = client.query_workspace("<WORKSPACE_GUID>", Path("kql/per_job.kql").read_text(encoding="utf-8"),
                                timespan=(end - timedelta(days=1), end))
jobs = [dict(zip(result.tables[0].columns, row)) for row in result.tables[0].rows]
```

给已有身份（例如托管身份）手动授予工作区读权限：

```bash
source gpu-hours.outputs.env
az role assignment create --assignee "$READER_OBJECT_ID" --role "Log Analytics Reader" --scope "$WORKSPACE_RESOURCE_ID"
```

用 `per_day` 统计完整的本地自然日时，timespan 的起止要设在本地零点，并换算成 UTC。分配卡时来自代理上报的 `Heartbeat`，不是账单；对账请用 Cost Management。

## 单台 H100 VM 上的实测验证

在一张 GPU 上做了四次实测：
- `validation-1`：用时间表已知的负载，检查每一分钟有没有被归到正确的类别；
- `replay-1`：在一个新资源组里逐个执行配置的分步脚本，并让两个属主共用这张卡；
- `configure-2`：在另一个新资源组里，只用一个配置文件和当前的 `configure.sh` 完成配置，再对同一组资源重跑；
- `jobs-1`：三个 AML 作业以同一个 Linux 用户运行，按作业名和提交人归属卡时。

<img src="images/test-topology-cn.png" width="900" alt="被测 VM Standard_NC40ads_H100_v5 位于 Spain Central，运行已知负载、gpumon 和 Azure Monitor Agent；同区域的数据收集终结点、规则和工作区；运维工作站执行脚本和查询">

被测环境：
- VM：`Standard_NC40ads_H100_v5`，1 张 NVIDIA H100 NVL；
- 软件：Ubuntu 24.04.5、驱动 615.71.09、DCGM 3.3.9、Azure Monitor Agent 1.45；
- 工作区：与 VM 同一区域；
- 运维工作站：用 Azure CLI 2.88.0 执行脚本，并调用查询 API。

### validation-1：已知负载，一个属主

**问题。** 时间表已知的负载，每一分钟是否都落在时间表预期的类别里？`summary`、`per_vm`、`per_user` 与原始数据算出来的是否一致？

**输入。** 下面这个脚本以 VM 的管理员账户（下文记作 `user-1`）运行，分三段：
1. bf16 矩阵乘法连续跑 480 秒；
2. 占着 20 GiB 显存、不跑 kernel，持续 180 秒；
3. 按 50 % 占空比再跑 300 秒。

[`tests/load/gpu_load.py`](tests/load/gpu_load.py) 默认就按这个时间表运行。

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

**变量与固定项。** 只变负载阶段。VM、GPU、单进程和 5 % 的占用阈值保持不变。

**结果。**

<img src="images/gpu-minutes-cn.png" width="900" alt="validation-1 每分钟的 SM Active：进程启动时 1 分钟占用，8 分钟满载约 96%，3 分钟占用，5 分钟半载约 35%，之后空闲">

<!-- BEGIN GENERATED: phases -->
| 阶段（起始分钟） | 分钟数 | SM Active | 功耗 |
|---|---:|---:|---:|
| 占用 (13) | 1 | 0.0 % | 65 W |
| 满载 (14) | 8 | 96.3 % | 398 W |
| 占用 (22) | 3 | 0.2 % | 107 W |
| 半载 (25) | 5 | 34.7 % | 280 W |
<!-- END GENERATED: phases -->

<!-- BEGIN GENERATED: summary-v1 -->
- 分配 2.717、已观测 2.700、占用 0.283、有效计算 0.157、空闲 2.417、未知 0.017 卡时；遥测覆盖率 99.39 %。
- 分配时长来自 163 个 Heartbeat 分钟。空闲只算已有 GPU 数据但没有工作的时段；未知是分配了 GPU、却没有 GPU 数据的时段。
- 占用分钟中有 16 / 17 个记到了属主 `user-1`。
<!-- END GENERATED: summary-v1 -->

**边界。**
- 只有一张卡、一段合成负载，没有测量生产负载。
- 开头那 1 分钟“占用”是进程加载、分配显存、还没开始跑 kernel。
- 那一个没有属主的占用分钟，是最后一个半载分钟：任务在这一分钟里退出了，早于分钟末的进程采样。

### replay-1：在新资源组里原样执行配置步骤，两个属主

**问题。** 各个分步脚本和下线步骤，从一份干净的代码副本出发、对着一个原本不存在的资源组，能不能照原样跑通？两个属主共用的 GPU·分钟，是否各记一半？

**输入。** 上文“配置命令实际执行了什么”中的分步脚本，从已提交文件的干净导出逐个执行，目标资源组为 `rg-gpu-hours-replay`。然后用两个新建的系统用户跑下面的负载，第二个用户比第一个晚 120 秒启动：

```bash
./tests/load/run-load.sh -g <vm-rg> -n <vm-name> -u <user-1>,<user-2> -p "--phase full:240" -D 120
```

**变量与固定项。** 资源组是新的，GPU 上有两个属主。VM、采集器、规则和查询保持不变。

**结果。**

<!-- BEGIN GENERATED: replay-steps -->
- **1 工作区、表、DCE、DCR**：退出码 0，181 秒。表 23 列，保留 90 天；规则读取 /var/log/gpumon/*.json。
- **2 接入 VM**：退出码 0，102 秒。gpumon.service 运行中，执行 dcgmi dmon。
- **3 首批数据**：退出码 0。接入后约 8 分钟出现 Heartbeat，约 11 分钟出现 GpuMetrics_CL。
- **4 两个用户的负载**：退出码 0，213 秒。GPU 上 2 个进程，各 21 GiB。
- **5 查询：CLI 与客户端**：退出码 0。CLI 与客户端返回的属主数值相同。
- **6 下线**：退出码 0，98 秒。代理、关联、采集器全部移除；资源组已删除。
<!-- END GENERATED: replay-steps -->

<img src="images/owners-cn.png" width="900" alt="replay-1 每分钟的属主份额：1 分钟只有 user-1，3 分钟两人各一半，1 分钟只有 user-2">

<!-- BEGIN GENERATED: owners -->
| 属主 | 占用卡时 | 有效计算卡时 |
|---|---:|---:|
| `user-1` | 0.042 | 0.036 |
| `user-2` | 0.042 | 0.038 |

- 共 6 个占用分钟：5 个有属主，其中 3 个由两人共用；1 个没有属主。
<!-- END GENERATED: owners -->

**边界。**
- 每个用户各跑了 240 秒，却只各记了 2.5 分钟。原因是属主在每分钟末读取一次：任务开始或结束的那一分钟，只有在那一刻任务还在 GPU 上才会被记入。
- `per_user` 里的 `PeakMemoryGiB` 是这张卡上的显存占用，不是单个进程的：两人同时运行时是 42 GiB。
- VM 释放后再启动时换到了另一台宿主机，所以 GPU UUID 变了。查询按 VM 名称加 GPU 序号分组，这不影响统计结果。

### configure-2：一个配置文件、一条命令、幂等重跑

**问题。** `scripts/configure.sh` 能不能只凭一个配置文件、一条命令，让新工作区收到 GPU 数据，而不留下需要手工补做的步骤？

**输入。** 同一台 VM，GPU 上没有负载。实际使用的配置文件如下，名称和 ID 已换成占位符：

<!-- BEGIN GENERATED: configure-settings -->
```bash
SUBSCRIPTION_ID="<subscription-id>"
WORKSPACE_RG="rg-gpu-hours"
LOCATION="spaincentral"
WORKSPACE_NAME="law-gpu-hours"
RETENTION_DAYS=30
VM_RG="<vm-resource-group>"
VMSS_NAME=""
VM_NAMES="gpu-vm-1"
AML_WORKSPACE_ID=""
READER_OBJECT_ID="<object-id>"
READER_PRINCIPAL_TYPE="User"
SKIP_NOT_READY_VMS=0
PARALLEL=5
WAIT_MINUTES=25
```
<!-- END GENERATED: configure-settings -->

在 Windows 上的 Git Bash 和 Azure CLI 2.88.0 中，两次执行 `./scripts/configure.sh -c gpu-hours.env`，然后执行安全下线。完整的脱敏输出见 [`evidence/runs/configure-2/`](evidence/runs/configure-2/)。

**变量与固定项。**
- 变的是入口：用一个配置文件加一条命令，代替逐个运行分步脚本。
- VM、采集器、规则和查询保持不变。
- 各步耗时取自这条命令在日志目录中写出的文件的修改时间。

**结果。**

<!-- BEGIN GENERATED: configure-steps -->
- **登录、列出 VM、只读预检**：退出码 0，52 秒。这台 VM 通过预检：`gpus: 1 dcgm: 3.3.9`。
- **工作区、表、数据收集终结点和规则**：退出码 0，132 秒。`setup-workspace.sh` 打印出带工作区 hash 的 DCR 和 DCE ID；`AML_WORKSPACE_ID` 为空，作业跟踪未开启。
- **接入 VM**：退出码 0，88 秒。`gpumon.service` 为 active (running)；已有其他 DCE 时会停止，不会覆盖。
- **查询授权**：退出码 0，23 秒。已授予 Log Analytics Reader，并写出 `gpu-hours.outputs.env`。
- **等待 GPU 数据入库**：退出码 0，293 秒。查询 API 返回这台 VM 的 2 行数据（第 5 次检查），最后一行属于开始后 +7:50 那一分钟；VM 资源 ID 相同。
- **幂等重跑**：退出码 0。工作区、DCR、DCE 未变，已有 Reader 角色被复用，441 秒内验证到新数据。
- **安全下线与清理**：退出码 0。删除 gpumon 和新 DCR 关联，保留原 DCE 与 Azure Monitor Agent，删除测试资源。

- 整条命令：588 秒，退出码 0。随后对当前覆盖率查询的实时调用返回 0.183 已观测卡时、0.017 未知卡时，遥测覆盖率 91.7 %；未知时段没有记为空闲。
<!-- END GENERATED: configure-steps -->

**边界。**
- 只有一台 VM，写在 `VM_NAMES` 里。以下三项只在 [`tests/test_configure.py`](tests/test_configure.py) 里用替身 `az` 验证过，没有在 Azure 上实测：
  - 读取 Flexible 规模集的实例；
  - 多台 VM 并行接入；
  - 退出码 1、2、3。
- `AML_WORKSPACE_ID` 为空，所以这次没有再次创建两个诊断设置；下面的 `jobs-1` 已通过 `setup-workspace.sh -a` 实测过它们。
- 一键配置命令内的等待包含代理的启动时间：采集器从接入起就在写数据，但只有代理开始读取这些文件之后，数据才会进入工作区，与 `validation-1` 的现象相同。

### jobs-1：AML 作业与提交人，同一个 Linux 用户

**问题。** 所有 GPU 进程都以同一个 Linux 用户运行时（AML 作业通过 SSH 在宿主机上启动 torchrun 或 mpirun 就是这样），客户平台还能不能按作业、按提交作业的 Entra 账号读出卡时？两个作业共用一张卡的那几分钟怎么算？

**输入。** 上面那台 VM：用 `scripts/setup-workspace.sh -a` 建工作区，用 `scripts/onboard-vm.sh` 接入，并以 `virtualmachine` 计算目标附加到同一订阅里的一个 AML 工作区。一个 Entra 账号（下文记作 `submitter-1`）提交了三个 AML 命令作业。每个作业在自己的 AML 容器里运行下面这个启动脚本：它通过 SSH 在宿主机上，以同一个 Linux 账户（下文记作 `user-1`）启动 [`tests/load/gpu_load.py`](tests/load/gpu_load.py)，参数为 `--phase full:150 --phase partial:90:0.5`，并把 `AZUREML_RUN_ID` 传下去。`job-3` 比 `job-2` 晚约一分钟提交，因此两者共用了这张卡。

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

**变量与固定项。** 变的是作业名，以及其中两个作业的重叠。VM、GPU、Linux 账户、提交人和查询保持不变。

**结果。**

<!-- BEGIN GENERATED: jobs-steps -->
- **1 工作区与作业跟踪**：退出码 0，209 秒。表 24 列，含 RunId；Administrative 活动日志和 AmlRunStatusChangedEvent 写入工作区。
- **2 接入 VM**：退出码 0，160 秒。gpumon.service 运行中，采集器带 RunId。
- **3 VM 附加到 AML**：退出码 0，6 秒。计算目标状态 Succeeded。
- **4 三个 AML 作业**：退出码 0。全部 Completed；job-2 与 job-3 以同一个 Linux 用户共用 GPU，每个进程带各自的 AZUREML_RUN_ID。
- **5 回读：参考客户端执行八个查询**：退出码 0，44 秒。原始数据和全部查询结果导出完成。
- **6 清理**：退出码 0。计算目标已分离，测试账户已删除，诊断设置和资源组已删除，VM 已释放。
<!-- END GENERATED: jobs-steps -->

<!-- BEGIN GENERATED: jobs-result -->
| 作业 | 提交人 | 占用卡时 | 有效计算卡时 |
|---|---|---:|---:|
| `job-1` | `submitter-1` | 0.067 | 0.047 |
| `job-2` | `submitter-1` | 0.042 | 0.032 |
| `job-3` | `submitter-1` | 0.042 | 0.029 |

- 同一时段的 `per_user`：只有一个属主 `user-1`，占用 0.150 卡时，即三个作业之和。
- 共 11 个占用分钟：9 个带作业名，其中 3 个带两个作业名、各记一半；2 个没有作业名。
- 每个作业的状态事件：Running → Finalizing → Completed。
- 入库延迟：GPU 数据中位数 83 秒；状态事件中位数 38 秒，最长 55 秒；提交事件中位数 363 秒，最长 538 秒。
<!-- END GENERATED: jobs-result -->

**边界。**
- 只有一个提交人：测试账号无权给第二个身份授予 AML 工作区的访问权限，所以 `per_submitter` 只有一行。每个作业的提交人取自该作业自己那条 `jobs/write` 事件的 `Caller`，第二个账号会成为第二行。
- 提交人随 Azure 活动日志导出入库，比 GPU 数据晚几分钟；在此之前 `per_job` 里这个作业的提交人为空。状态事件比 GPU 数据到得更快。
- 作业名和属主一样，在每分钟末读取一次：作业结束的那一分钟，记给那一刻仍在 GPU 上的作业，或者不记给任何作业。
- 在附加的 Ubuntu 24.04 VM 上运行 AML 作业，遇到了三个 AML 自身的前提条件，记录在 [`evidence/runs.json`](evidence/runs.json)：附加用的账户要接受 `ssh-rsa`，宿主机上要有 `python` 命令，工作区存储要能被 AML 访问以上传日志。它们属于 AML，不属于本仓库的配置步骤。

### auth-1：客户平台以应用注册登录并查询

**问题。** 一个没有 Azure CLI 的平台，能不能以应用注册的身份登录 Entra ID 并读取各个查询？密钥错误、或者访问没有授权的工作区时，会不会被拒绝？

**输入。**
- 另一个 Entra ID 测试租户，Sweden Central。用 `scripts/setup-workspace.sh` 新建工作区，另建一个没有任何授权的工作区作对照。
- 这个工作区没有接 GPU VM，所以每个查询返回的卡时都是 0。本次只测登录和权限这条链路；数字是否正确由上面几次实测证明。
- 执行的命令：`create-query-identity.sh` 两次；`query-gpu-hours.sh` 分别用正确密钥、错误密钥、没有授权的工作区，以及八个查询各一次；`gpu_hours_client.py --credentials`。最后删除应用注册和测试资源组。脱敏输出见 [`evidence/runs/auth-1/`](evidence/runs/auth-1/)。

**结果。**

| 步骤 | 退出码 | 观察到的结果 |
|---|---|---|
| 创建登录身份 | 0 | 126 秒；新建应用注册和服务主体，只授予工作区上的 Log Analytics Reader；密钥写入权限为 600 的文件，未打印 |
| 重跑 | 0 | 40 秒；复用应用、服务主体、角色和文件中的密钥，文件内容不变 |
| 正确密钥查询 `summary` | 0 | 先从 `login.microsoftonline.com` 取得令牌，再从 `api.loganalytics.azure.com` 得到 HTTP 200，约 7 秒 |
| 错误密钥 | 4 | Entra ID 返回 HTTP 401 `AADSTS7000215`，没有发出查询 |
| 没有授权的工作区 | 5 | 登录成功，查询 API 返回 HTTP 403 `InsufficientAccessError` |
| 八个查询 | 0 | 全部 HTTP 200 |
| Python `ClientSecretCredential` | 0 | 与 curl 返回同一行 `summary` |
| 清理 | 0 | 应用注册剩 0 个，测试资源组已删除 |

**边界。**
- 只测了客户端密钥。托管身份走的是同一个查询 API、同一个角色，`configure-2` 中已用 `READER_OBJECT_ID` 授权过；但这次没有从 Azure 内的托管身份上实际发起查询。
- 创建应用注册需要租户允许用户注册应用，或者执行人有 Application Developer 等目录角色；客户的 Entra ID 管理员可能要先放开或代为执行。
- 证书凭据、联合身份凭据（例如 GitHub Actions、AKS 工作负载身份）没有测试。

### 可以自己重算的数字

<!-- BEGIN GENERATED: checks -->
- KQL 与 Python 比对：第一次实测 13 个值，第二次 15 个，最大差值 0.0。
- `jobs-1`：原有查询 13 个值，作业查询 11 个数值、28 个字段，最大差值 0.0。
- GpuMetrics_CL 入库延迟：中位数 76 秒，p95 125 秒。
- 计费大小：每行 GPU 数据 343 字节，每行 Heartbeat 547 字节。
<!-- END GENERATED: checks -->

## 测试与离线校验

离线校验只需要 Python 3.10 或更新版本，不需要连接 Azure：

```bash
pip install -r examples/requirements.txt
python -m unittest discover -s tests -v
python tools/build_evidence.py --check
python tools/build_rule_results.py --check
python tools/build_readme.py --check
python tools/build_workbook.py --check
python tools/draw_diagrams.py --check
python tools/check_repo.py
```

全部测试通过、每个检查都打印 `PASS`，即为完成。

- **`python -m unittest discover -s tests -v`** 测试以下内容：
  - 采集器：解析真实的 `dcgmi dmon` 输出、按分钟求平均，以及 JSON 行的字段与规则数据流、表的列完全一致；
  - 查询：共用的 `let` 行完全相同，`summary` 是 `per_vm` 的合计，AML 查询按 `RunId` 关联；
  - 参考客户端：`let` 改写，以及发出的 timespan；
  - 证据：重算逻辑，包括属主和作业的 1/N 分摊、首个提交人和最后状态；
  - `scripts/configure.sh`（[`tests/test_configure.py`](tests/test_configure.py)）：用 bash 运行，`az` 换成记录每次调用的替身。测试覆盖以下情形：
    - 预检不做任何修改；
    - 完整运行会接入 Flexible 规模集的每个实例，在并行接入之前只安装一次 CLI 扩展，并授予查询角色；
    - 有 VM 未通过预检时，在任何修改之前停止，除非设置了 `SKIP_NOT_READY_VMS=1`；
    - 拒绝 Uniform 规模集；
    - 等不到数据时以退出码 3 结束；
    - Windows 换行的配置文件也能使用；
  - 公开内容：`tools/check_repo.py` 的每一条规则，并故意制造违规，确认它会报错。
- **`tools/build_evidence.py --check`** 用已提交的原始数据重新生成 [`evidence/measurements.json`](evidence/measurements.json)。以下两种情况报错：
  - KQL 结果与 Python 重算不一致；
  - `configure-2` 的控制台输出、receipt 时间、幂等重跑或安全下线结果与运行记录不一致。
- **`tools/build_rule_results.py --check`** 重新执行适用的 SOP-68 运行规则，检查每个证据路径都位于仓库内且文件存在，再与 [`evidence/rule-results.json`](evidence/rule-results.json) 逐字节比较。反例测试会拒绝以下情况：规则缺失、重复或未知，伪造 PASS，没有理由的 N/A，以及绝对路径、上级路径或不存在的证据。
- **`tools/build_readme.py --check`** 两份 README 里任何数字、表格或命令，与从证据和脚本重新生成的结果不一致时报错。
- **`tools/draw_diagrams.py --check`** 把每张图与 [`images/SOURCES.json`](images/SOURCES.json) 里记录的 SHA-256 比对。
- **`tools/check_repo.py`** 检查链接、标题顺序、表格宽度、中英文数字是否一致，以及私有内容防护。

CI 在 Ubuntu 和 Windows 上、分别用 Python 3.10 和 3.12 执行同样的命令（[workflow](../../.github/workflows/azure-gpu-hours-monitoring-ci.yml)）。

需要连接 Azure 的实时检查有三项：
- `./scripts/configure.sh -c gpu-hours.env -v`：等待配置文件里每台 VM 的数据，不做任何修改；以及 [README_CN.md](README_CN.md) 中验证数据入库的查询；
- 参考客户端；
- 负载测试（需要 GPU VM 和 PyTorch）：`./tests/load/run-load.sh -g <vm-rg> -n <vm-name> -u <user>`，测完用 `-x` 删除测试用户。

本仓库没有测试：多卡 VM、MIG、DCGM 4.x、Azure Private Link、主权云、多个提交账号，以及在 Azure 上对规模集或多台 VM 运行 `configure.sh`。

## 边界、目录与资料

**边界。**

- `LOCAL_MEASUREMENT`：属主在每分钟末采一次。任务在一分钟中途退出，这一分钟算占用但没有属主；任务在一分钟中途启动，从它的第一个分钟末开始计入。
- `LOCAL_MEASUREMENT`：分配时长从代理的第一条 `Heartbeat` 算起。代理开始采集之前采集器写下的行没有入库（`validation-1` 的第 5–10 分钟）。
- `LOCAL_MEASUREMENT`：缺少 GPU 数据的时段记为 `UnknownGpuHours`，不算空闲；`configure-2` 附带了这一区别的实时检查。客户需要先设定自己的最低覆盖率要求，再用空闲卡时作回收决策。
- `LOCAL_MEASUREMENT`：`PeakMemoryGiB` 是整张卡的显存占用，不是按进程统计的。
- `LOCAL_MEASUREMENT`：作业的提交人随 Azure 活动日志导出入库，比它的 GPU 数据晚几分钟（`jobs-1`）。
- `LOCAL_MEASUREMENT`：作业 ID 在每分钟末采一次。同一个 GPU·分钟有多个作业 ID 时，由于 DCGM 不提供每进程 SM 活跃度，每个作业得到相同份额。
- `NOT_MEASURED`：8 卡 VM。采集器读取 `nvidia-smi` 列出的每一张卡，查询也按 VM 统计卡数，但实测只有一张卡。
- `NOT_MEASURED`：MIG 实例、DCGM 4.x，以及没有传递标识符的任务。AML 使用 `AZUREML_RUN_ID`；其他调度器需要定义等价的采集和查询约定。
- `NOT_MEASURED`：已装好代理的 VM，从开机到第一条 `Heartbeat` 的延迟。
- `NOT_MEASURED`：在 Azure 上用 `configure.sh` 接入规模集，或同时接入多台 VM。
  - `configure-2` 只接入了一台列出名字的 VM；规模集和并行接入这两条路径只用替身 `az` 跑过。
  - 全量推广前，先对整批 VM 运行预检（`-p`），再运行完整命令。
  - 某台失败时，命令以退出码 2 结束，并为这台 VM 单独留下日志；修好后可以重跑。
- `NOT_MEASURED`：以 Azure Cloud Shell 作为运行环境。实测用的是 Windows 上的 Git Bash。
- `SOURCE_FACT`：Azure CLI 的 `log-analytics` 扩展没有正式版（本次为 1.0.0b2）。客户平台应通过 REST 或 SDK 调用查询 API。
- 分配卡时反映的是代理上报的 VM 运行时间，不是账单记录；对账请用 Cost Management。

**目录。**

- [`vm/`](vm/)：`gpu_collector.py`（把 DCGM 数据写成 JSON 行），`install_collector.sh`（systemd 服务，启用 `nvidia-dcgm`）。
- [`azure/`](azure/)：`dcr-rule.json`，供 `az monitor data-collection rule create --rule-file` 使用的数据收集规则。
- [`scripts/`](scripts/)：`configure.sh`（一条命令完成全部步骤，配置模板为 `gpu-hours.env.example`）、`setup-workspace.sh`、`onboard-vm.sh`、`offboard-vm.sh`，以及默认只预览的 `remove-workspace.sh`。
- [`kql/`](kql/)：八个查询。
- [`examples/`](examples/)：`gpu_hours_client.py`，调用查询 API 的参考客户端，以及它的 `requirements.txt`。
- [`evidence/`](evidence/)：
  - 运行说明（`runs.json`）；
  - `runs/` 下各次实测经过脱敏投影的数据，每份都附私有原件的 SHA-256：
    - `validation-1`、`replay-1`、`jobs-1`：原始数据和查询结果；
    - `configure-2`：控制台输出、配置文件、receipt、幂等重跑和安全下线结果；
  - `measurements.json`。
- [`tests/`](tests/)：离线测试；`tests/load/` 下是负载生成器和它的 Run Command 包装脚本。
- [`tools/`](tools/)：证据、规则结果、README 和图的生成工具，以及公开内容审计。
- [`images/`](images/)：中英文配图及其台账 `SOURCES.json`。

**资料。**

- [用 Azure Monitor Agent 采集 JSON 日志](https://learn.microsoft.com/azure/azure-monitor/vm/data-collection-log-json)、[数据收集规则的结构](https://learn.microsoft.com/azure/azure-monitor/data-collection/data-collection-rule-structure)
- [Azure HPC VM 镜像](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images)（自带 DCGM）
- [`az monitor data-collection rule`](https://learn.microsoft.com/cli/azure/monitor/data-collection/rule)、[`az monitor log-analytics query`](https://learn.microsoft.com/cli/azure/monitor/log-analytics#az-monitor-log-analytics-query)
- [Log Analytics 查询 API](https://learn.microsoft.com/azure/azure-monitor/logs/api/overview)、[Azure Monitor Query 的 Python 客户端库](https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme)、[`Heartbeat`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/heartbeat)、[`AzureActivity`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/azureactivity) 和 [`AmlRunStatusChangedEvent`](https://learn.microsoft.com/azure/azure-monitor/reference/tables/amlrunstatuschangedevent)
- [DCGM 字段 ID](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-api/dcgm-api-field-ids.html)、[DCGM profiling 指标](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html#profiling-metrics)
- AKS 上的 GPU 节点池，请改用 Azure Monitor 托管 Prometheus 的 [DCGM exporter 集成](https://learn.microsoft.com/azure/azure-monitor/containers/prometheus-dcgm-integration)，不要用本采集器。
