# 客户配置手册：一条命令接入 GPU 卡时统计

[English](QUICKSTART.md) · [完整说明](README_CN.md)

本手册面向客户的运维人员。照着做完后：
- 每台 GPU VM 每张卡每分钟会有一行 GPU 数据写入你自己的 Log Analytics 工作区；
- 客户平台通过 Log Analytics 查询 API 读取卡时，可按 VM、小时、天、Linux 用户、AML 作业和提交人统计。

整个过程只需要填写一个配置文件，然后运行一条命令。脚本可以重复运行：已经存在的资源会原地更新，不会重复创建。

## 一、开始前确认

| 项目 | 要求 |
|---|---|
| 运行环境 | Azure Cloud Shell（Bash）、Linux、macOS，或 Windows 上的 Git Bash；已安装 Azure CLI 并执行过 `az login` |
| 配置权限 | VM 所在资源组和工作区资源组的 Contributor；给平台身份授权还需要 User Access Administrator 或 Owner |
| AML 作业统计（可选） | 订阅级诊断设置的写权限，以及 AML 工作区的 Contributor |
| GPU VM | 处于运行状态；已装 NVIDIA 驱动和 DCGM（`datacenter-gpu-manager`），有 `/usr/bin/python3` 和 systemd |
| 网络 | VM 能经 HTTPS 出站访问 Azure Monitor；NSG 限制出站时，放行服务标记 `AzureMonitor` |

[Azure HPC VM 镜像](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images)自带驱动和 DCGM。第四节的预检会逐台检查这些条件，不需要 SSH 登录。

支持的 VM 形式：
- 单独创建的 VM；
- Flexible 编排的虚拟机规模集。实例本身就是普通 VM，脚本会自动列出全部实例；
- Uniform 编排的规模集不支持，脚本会报错退出。

## 二、下载

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/Azure-GPU-Hours-Monitoring
cd Deep-Learning/Azure-GPU-Hours-Monitoring
chmod +x scripts/*.sh
```

## 三、填写配置文件

```bash
cp scripts/gpu-hours.env.example gpu-hours.env
```

用任意编辑器打开 `gpu-hours.env`。必填三项，GPU VM 的两种写法至少填一种：

```bash
WORKSPACE_RG="rg-gpu-hours"     # 工作区所在资源组，不存在会自动创建
LOCATION="<GPU VM 所在区域>"      # 例如 swedencentral；资源组已存在时必须与它的区域一致
VM_RG="<GPU VM 所在资源组>"
VMSS_NAME="<Flexible 规模集名称>"  # 写法一：接入规模集的全部实例
VM_NAMES="<vm-1> <vm-2>"          # 写法二：逐台列出，空格分隔
```

按需填写的两项：

```bash
# 按 AML 作业和提交人统计：AML 工作区的资源 ID
AML_WORKSPACE_ID="/subscriptions/<订阅 ID>/resourceGroups/<资源组>/providers/Microsoft.MachineLearningServices/workspaces/<工作区名>"
# 客户平台用于查询的身份（托管身份或应用注册的服务主体对象 ID），脚本会授予 Log Analytics Reader
READER_OBJECT_ID="<对象 ID>"
```

查 AML 工作区资源 ID：

```bash
az ml workspace show -g <资源组> -n <工作区名> --query id -o tsv
# 没有 ml 扩展时也可以用：
az resource show -g <资源组> -n <工作区名> --resource-type Microsoft.MachineLearningServices/workspaces --query id -o tsv
```

其余选项保持默认即可，含义写在文件注释里。

## 四、预检（只读，不做任何修改）

```bash
./scripts/configure.sh -c gpu-hours.env -p
```

脚本列出要接入的每台 VM，并通过 Run Command 检查 VM 状态、驱动、DCGM 和 python3。期望输出类似：

```text
==> [3] preflight: running, NVIDIA driver, DCGM, python3 (Run Command, read-only)
  gpu-vm-1                                 OK gpus: 8 dcgm: 3.3.9
  gpu-vm-2                                 OK gpus: 8 dcgm: 3.3.9

preflight passed; nothing was changed
```

某台显示 `NOT_READY`，后面会写明缺什么。有两种处理方式：
- 修好这台 VM，再预检一次；
- 在配置文件里设 `SKIP_NOT_READY_VMS=1`，只接入通过预检的 VM。

## 五、一键配置

```bash
./scripts/configure.sh -c gpu-hours.env
```

脚本依次完成以下七步；每台 VM 约需 2–3 分钟，默认 5 台并行：

1. 确认登录的账号和订阅；
2. 列出 GPU VM；
3. 预检；
4. 创建工作区、`GpuMetrics_CL` 表、数据收集终结点和规则。填了 `AML_WORKSPACE_ID` 时，再加两个诊断设置：
   - 订阅活动日志 → `AzureActivity`，用于获取作业提交人；
   - AML 作业状态 → `AmlRunStatusChangedEvent`；
5. 并行接入每台 VM：
   - 开启系统分配托管身份；
   - 安装 Azure Monitor Agent；
   - 关联数据收集规则和终结点；
   - 启用 DCGM，并安装 `gpumon` 采集服务；
6. 给 `READER_OBJECT_ID` 授予工作区的 Log Analytics Reader；把工作区 ID 等结果写入 `gpu-hours.outputs.env`；
7. 通过 Log Analytics 查询 API，等待每台 VM 的 GPU 数据入库。客户平台调用的也是这个 API。

成功时最后输出：

```text
==> [7] wait for GPU rows from every VM (up to 20 minutes; the first rows take about 10 minutes)
  ...
all 20 VM(s) are sending GPU rows

==> done
WORKSPACE_GUID=<工作区 GUID>
```

退出码：

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 全部完成，每台 VM 都已有数据 | 按需做第六节，然后看第七节 |
| 1 | 配置文件有误，或预检未通过 | 按提示修改后重跑 |
| 2 | 部分 VM 接入失败 | 查看 `gpu-hours-logs/<时间>/onboard.<vm>.log`，修好后重跑整条命令 |
| 3 | 等待超时，还有 VM 没有数据 | 新接入的 VM 可能需要约 15 分钟；运行 `./scripts/configure.sh -c gpu-hours.env -v`，只重新检查数据 |

每次运行的完整日志都在 `gpu-hours-logs/<UTC 时间>/` 下。

本节命令已在 Azure 上完整实跑一次，环境为 1 台 H100 VM。各阶段耗时如下：
- 预检约 3 分钟；
- 建工作区约 3 分钟；
- 接入 VM 约 2.5 分钟；
- 接入后约 9 分钟，首批 GPU 数据可查。

整条命令用时 1160 秒，退出码为 0。

## 六、让 AML 作业带上作业 ID（只在需要按作业统计时）

采集器从每个 GPU 进程的环境变量 `AZUREML_RUN_ID` 读取 AML 作业名。AML 会在作业容器里设置这个变量：
- GPU 进程直接在作业容器里运行时，不需要任何改动；
- 启动脚本从作业容器 SSH 到宿主机、再启动 `torchrun` 或 `mpirun` 时，需要把这个变量传下去，否则这些进程没有作业 ID。

需要修改的写法如下：

```bash
# SSH 到宿主机启动：用 env 传递
ssh "$HOST" "env AZUREML_RUN_ID=$AZUREML_RUN_ID torchrun --nproc_per_node 8 train.py"

# mpirun 分发到多台机器：用 -x 导出
mpirun -x AZUREML_RUN_ID -np 160 --hostfile hosts ./train.sh

# 在宿主机上用 docker 启动：用 -e 传入
docker run -e AZUREML_RUN_ID ... <image> torchrun ...
```

改完后提交一个测试作业。作业运行几分钟后，用第七节的 `per_job` 查询就能看到它的作业名。提交人来自 Azure 活动日志，通常比 GPU 数据晚 6–9 分钟出现。

## 七、客户平台查询

`gpu-hours.outputs.env` 里的 `WORKSPACE_GUID` 就是查询要用的工作区 ID。客户平台每个查询发一次 HTTPS 请求：

```http
POST https://api.loganalytics.io/v1/workspaces/<WORKSPACE_GUID>/query
Authorization: Bearer <访问令牌，资源为 https://api.loganalytics.io>
Content-Type: application/json

{"query": "<kql/ 下某个文件的全部内容>", "timespan": "<开始>/<结束>"}
```

`timespan` 用 ISO 8601：既可以是两个带时区的时间，用 `/` 隔开；也可以是时长，例如 `P1D` 表示最近一天。

[`kql/`](kql/) 下的八个文件如下，每个文件对应一个统计视图：

| 文件 | 每行是 |
|---|---|
| `summary.kql` | 所选时段的合计 |
| `per_vm.kql` / `per_hour.kql` / `per_day.kql` | 一台 VM / 一个小时 / 一天 |
| `per_user.kql` | 一个 Linux 用户在一台 VM 上 |
| `per_job.kql` / `per_submitter.kql` | 一个 AML 作业 / 一个 Entra 提交人 |
| `live.kql` | 每张卡最近看到的进程和作业 |

Python 示例。凭据：平台所在环境用托管身份，工作站上用 `az login`：

```bash
pip install -r examples/requirements.txt
source gpu-hours.outputs.env
END=$(date -u +%FT%TZ); START=$(date -u -d '-1 day' +%FT%TZ)   # macOS: date -u -v-1d +%FT%TZ
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_vm --start "$START" --end "$END"
python examples/gpu_hours_client.py --workspace "$WORKSPACE_GUID" --view per_job --start "$START" --end "$END"
```

在命令行里快速看一眼，不装任何扩展：

```bash
source gpu-hours.outputs.env
echo '{"query": "GpuMetrics_CL | summarize Rows = count(), Last = max(TimeGenerated) by VmName", "timespan": "PT1H"}' > q.json
az rest --method post --url "https://api.loganalytics.io/v1/workspaces/$WORKSPACE_GUID/query" \
  --resource https://api.loganalytics.io --body @q.json --query "tables[0].rows" -o table
```

接入时没有填写 `READER_OBJECT_ID`，可以之后再授权：

```bash
source gpu-hours.outputs.env
az role assignment create --assignee-object-id <对象 ID> --assignee-principal-type ServicePrincipal \
  --role "Log Analytics Reader" --scope "$WORKSPACE_RESOURCE_ID"
```

各视图的列和指标口径见 [README_CN.md](README_CN.md#从客户平台查询)。

## 八、新增、下线和删除

- **新增 VM**：把新 VM 加进配置文件，或直接扩容规模集，然后重新运行第五步。已接入的 VM 会原地刷新。
- **下线一台 VM**：运行 `./scripts/offboard-vm.sh -g <VM 资源组> -n <VM 名>`。脚本会删除 `gpumon`、两个关联和 Azure Monitor Agent；驱动和 DCGM 保持不变。
- **全部删除**：
  1. 先对每台 VM 运行一次下线脚本；
  2. 删除两个诊断设置（填过 `AML_WORKSPACE_ID` 时）：

     ```bash
     az monitor diagnostic-settings subscription delete -n gpu-hours-job-submitters --yes
     az monitor diagnostic-settings delete -n gpu-hours-job-status --resource "<AML_WORKSPACE_ID>"
     ```
  3. 删除工作区资源组：`az group delete -n rg-gpu-hours --yes`。

## 九、费用与注意事项

- **数据量**：每张卡每分钟一行，约 343 字节。一台 8 卡 VM 每天约 4.74 MB（含 `Heartbeat`），20 台约 95 MB/天，按 Log Analytics 分析日志的数据量计费。默认保留 90 天，可用 `RETENTION_DAYS` 修改。
- **延迟**：GPU 数据一般在 1–2 分钟内可查，提交人信息要晚几分钟。这是分钟级统计，不是秒级实时监控。
- **口径**：
  - 分配卡时来自 Azure Monitor Agent 的 `Heartbeat`，不是账单，对账请用 Cost Management；
  - 作业在一分钟中途结束时，这一分钟可能只计为占用，而不归属到任何作业。
- 实测过程和验证证据见 [README_CN.md 的实测章节](README_CN.md#单台-h100-vm-上的实测验证)。
