# 用 DCGM 和 Azure Monitor 统计 Azure GPU 卡时

[![GPU 指标](https://img.shields.io/badge/NVIDIA%20DCGM-3.3.9-76B900)](#目的)
[![实测环境](https://img.shields.io/badge/tested-NC40ads%20H100%20v5-0078D4)](#实现效果)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-gpu-hours-monitoring-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-gpu-hours-monitoring-ci.yml)

作者：魏新宇 · [English](README.md)

## 目的

Azure GPU VM 上付了钱的卡时，有多少真正在算、算的是谁的任务？本仓库在每台 GPU VM 上用 NVIDIA DCGM 采集指标，其余全部交给 Azure Monitor，统计结果可以：
- 按 VM、小时、天、Linux 用户、AML 作业、提交人查看卡时；
- 在 Azure 门户的报表里查看；
- 由客户平台通过 Log Analytics 查询 API 读取。

不需要自建存储、自建服务或自建界面。

<img src="images/architecture-cn.png" width="900" alt="数据链路：GPU VM 上的 DCGM、gpumon 采集器和 Azure Monitor Agent；Azure Monitor 中的数据收集终结点、规则和 Log Analytics 工作区；客户平台经查询 API 读取">

指标口径：

| 指标 | 定义 |
|---|---|
| 分配卡时 | VM 运行分钟数 × 卡数 ÷ 60，来自 Azure Monitor Agent 的 `Heartbeat` |
| 已观测 / 未知卡时 | 收到 GPU 数据的卡·分钟 / 没收到的卡·分钟；未知不算空闲 |
| 占用卡时 | 有计算进程或 GPU Util ≥ 5 % 的卡·分钟 |
| 有效计算卡时 | SM Active 的累计，反映 GPU 实际在算的程度 |

## 操作步骤

**部署顺序。** 先在 Azure 侧部署 Azure Monitor，再逐台接入 GPU VM；第 4 步的一条命令按这个顺序完成前四项：

| 顺序 | 在哪里 | 做什么 | 脚本 |
|---|---|---|---|
| 1 | Azure 订阅 | 部署 Azure Monitor：Log Analytics 工作区、`GpuMetrics_CL` 表、数据收集终结点和规则 | [`scripts/setup-workspace.sh`](scripts/setup-workspace.sh) |
| 2 | 每台 GPU VM（Azure 侧） | 托管身份、Azure Monitor Agent，关联规则和终结点 | [`scripts/onboard-vm.sh`](scripts/onboard-vm.sh) |
| 3 | 每台 GPU VM（VM 内，经 Run Command） | 启动 DCGM（`systemctl enable --now nvidia-dcgm`），安装并启动 `gpumon` 采集服务 | [`vm/gpu_collector.py`](vm/gpu_collector.py) |
| 4 | Log Analytics | 等每台 VM 的数据入库 | [`scripts/configure.sh`](scripts/configure.sh) |

**前提。**
- 在 Azure Cloud Shell（Bash）里操作，不需要 SSH 登录任何 VM；
- 执行人对 VM 所在资源组有 Contributor 权限；按 AML 作业统计还需要订阅级诊断设置权限；给平台授权需要 Owner 或 User Access Administrator；
- GPU VM 已装 NVIDIA 驱动和 DCGM（[Azure HPC 镜像](https://learn.microsoft.com/azure/virtual-machines/azure-hpc-vm-images)自带）；单独的 VM 或 Flexible 规模集均可；
- VM 能经 HTTPS 出站访问 Azure Monitor。

**1. 下载脚本。**

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share && git sparse-checkout set Deep-Learning/Azure-GPU-Hours-Monitoring
cd Deep-Learning/Azure-GPU-Hours-Monitoring && chmod +x scripts/*.sh
```

**2. 填写配置文件。** 订阅、资源组、ID 只在这里填一次，后面的命令都从这个文件和它生成的 `gpu-hours.outputs.env` 读取变量：

```bash
cp scripts/gpu-hours.env.example gpu-hours.env
```

| 配置项 | 填什么 |
|---|---|
| `SUBSCRIPTION_ID` | GPU VM 所在订阅；留空则用当前订阅 |
| `WORKSPACE_RG`、`LOCATION`、`WORKSPACE_NAME` | 新建的监控资源组、区域（与 VM 相同）、工作区名；默认 `rg-gpu-hours`、`law-gpu-hours` |
| `RETENTION_DAYS` | 数据保留天数，默认 90 |
| `VM_RG`、`VMSS_NAME`、`VM_NAMES` | VM 所在资源组；Flexible 规模集名（自动列出全部实例），或空格分隔的 VM 名 |
| `AML_WORKSPACE_ID` | AML 工作区资源 ID；填了才有按作业、按提交人的统计 |
| `READER_OBJECT_ID`、`READER_PRINCIPAL_TYPE` | 客户平台查询身份的对象 ID 和类型；可以留空，第 7 步再建 |
| `SKIP_NOT_READY_VMS`、`PARALLEL`、`WAIT_MINUTES` | 是否跳过没准备好的 VM（0/1）；同时接入台数；等待数据的分钟数 |

**3. 预检（只读，不做任何修改）。**

```bash
./scripts/configure.sh -c gpu-hours.env -p
```

每台 VM 输出 `OK gpus: <卡数> dcgm: <版本>`。出现 `NOT_READY` 时会写明缺什么：VM 没开机、缺 `dcgmi`、缺 `nvidia-smi` 或缺 `python3`。

**4. 一键配置。**

```bash
./scripts/configure.sh -c gpu-hours.env
```

完成上面部署顺序的 1–4 项，不重启 VM、不影响正在运行的训练，可以重跑。结束时把 `WORKSPACE_GUID`、`WORKSPACE_RESOURCE_ID`、`DCR_ID`、`DCE_ID` 写进 `gpu-hours.outputs.env`。

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 每台 VM 都在上报数据 | 继续第 5 步 |
| 1 | 某条命令失败 | 看屏幕最后一步和 `gpu-hours-logs/` 下的日志，修好后重跑 |
| 2 | 部分 VM 接入失败 | 看 `gpu-hours-logs/<时间>/onboard.<vm>.log`，修好后重跑 |
| 3 | 等待超时，有 VM 还没数据 | `./scripts/configure.sh -c gpu-hours.env -v` 只重新等待 |

**5. AML 作业：把作业 ID 传给 GPU 进程（按作业统计才需要）。** 作业在 AML 容器里直接跑 GPU 进程时不用改；启动脚本在宿主机上启动进程时，把 `AZUREML_RUN_ID` 传下去：

```bash
ssh "$HOST" "env AZUREML_RUN_ID=$AZUREML_RUN_ID torchrun ..."   # SSH 到宿主机
mpirun -x AZUREML_RUN_ID ...                                      # 跨主机分发
docker run -e AZUREML_RUN_ID ...                                  # 宿主机上起容器
```

**6. 部署报表。**

```bash
source gpu-hours.outputs.env
./scripts/deploy-workbook.sh -g "$WORKSPACE_RG" -w "$WORKSPACE_NAME"   # 打印报表的门户链接
```

**7. 给客户平台创建只读登录身份。** 平台在 Azure 上运行时，用托管身份即可：把它的 principalId 填进 `READER_OBJECT_ID`，重跑第 4 步。平台在 Azure 之外时，用应用注册：

```bash
./scripts/create-query-identity.sh -g "$WORKSPACE_RG" -w "$WORKSPACE_NAME"
./scripts/query-gpu-hours.sh -c gpu-hours.query.env -q kql/summary.kql -t P1D   # 验证登录和查询
```

`create-query-identity.sh` 只授予工作区上的 Log Analytics Reader，把租户 ID、客户端 ID、密钥和工作区 GUID 写进 `gpu-hours.query.env`。这个文件权限为 600，不进 git，密钥不会打印到屏幕。`query-gpu-hours.sh` 只依赖 `curl` 和 `jq`；退出码 4 表示登录被拒，5 表示没有查询权限。

**8. 客户平台调用查询 API。** 先用客户端凭据换令牌，再带令牌查询；查询内容是 [`kql/`](kql/) 下某个文件的全文：

```http
POST https://login.microsoftonline.com/<AZURE_TENANT_ID>/oauth2/v2.0/token
grant_type=client_credentials&client_id=<AZURE_CLIENT_ID>&client_secret=<AZURE_CLIENT_SECRET>&scope=https://api.loganalytics.io/.default

POST https://api.loganalytics.azure.com/v1/workspaces/<WORKSPACE_GUID>/query
Authorization: Bearer <access_token>
{"query": "<kql/per_job.kql 的全文>", "timespan": "<开始>/<结束>"}
```

Python 可以直接用参考客户端：`python examples/gpu_hours_client.py --credentials gpu-hours.query.env --view per_job --start <开始> --end <结束>`。

| 查询 | 每行是 |
|---|---|
| [`summary`](kql/summary.kql)、[`per_vm`](kql/per_vm.kql) | 全部 VM 合计；每台 VM |
| [`per_hour`](kql/per_hour.kql)、[`per_day`](kql/per_day.kql) | 每小时；每天（北京时间） |
| [`per_user`](kql/per_user.kql) | 每个 Linux 用户 |
| [`per_job`](kql/per_job.kql)、[`per_submitter`](kql/per_submitter.kql) | 每个 AML 作业（含提交人、状态）；每个提交人 |
| [`live`](kql/live.kql) | 每张卡上每个作业的最新一行 |

**下线与删除。** 下线一台 VM（保留 Azure Monitor Agent 和 DCGM），或删除整套监控资源（默认只预览，加 `-y` 才删除，不会删资源组）：

```bash
source gpu-hours.outputs.env
./scripts/offboard-vm.sh -g "$VM_RG" -n "$VM_NAME" -d "$DCR_ID" -e "$DCE_ID"
./scripts/remove-workspace.sh -g "$WORKSPACE_RG" -w "$WORKSPACE_NAME" -a "$AML_WORKSPACE_ID"
```

## 实现效果

**门户里的报表。** 测试订阅中的实际截图，VM 名和 Linux 账号已替换为 `gpu-vm-1`、`user-N`：

<img src="images/workbook-summary.png" width="900" alt="Azure 门户中的 Workbook：指标说明、时间范围和合计视图，分配 13.28、已观测 13.07、未知 0.22 卡时，覆盖率 98.4%">

<img src="images/workbook-per-hour-day.png" width="900" alt="Azure 门户中的 Workbook：每小时卡时柱状图和按天视图">

<img src="images/workbook-trend-user.png" width="900" alt="Azure 门户中的 Workbook：每分钟 SM Active 曲线和按 Linux 用户视图">

报表顶部可以选时间范围、VM 和占用阈值。除了图中这些，还有采样状态、显存、功耗、最近 15 分钟采样和 60 分钟内没有负载的 GPU。按作业、按提交人两个视图只在开了作业跟踪时显示。

**按 AML 作业查看消耗和提交人。** 三个 AML 作业以同一个 Linux 用户运行时，`per_job` 的实测返回（作业名、账号已替换）：

<!-- BEGIN GENERATED: jobs-table -->
| 作业 | 提交人 | 占用卡时 | 有效计算卡时 |
|---|---|---:|---:|
| `job-1` | `submitter-1` | 0.067 | 0.047 |
| `job-2` | `submitter-1` | 0.042 | 0.032 |
| `job-3` | `submitter-1` | 0.042 | 0.029 |

三个作业合计 0.150 卡时，等于这个 Linux 用户的占用卡时；两个作业共用的 3 分钟各记一半。
<!-- END GENERATED: jobs-table -->

**实测验证。** 在 1 台 `Standard_NC40ads_H100_v5`（1 张 H100 NVL，DCGM 3.3.9）上完成。每次实测的输入、过程、结果、边界，以及怎样离线复算，见 [VALIDATION_CN.md](VALIDATION_CN.md)：

<!-- BEGIN GENERATED: results -->
| 实测 | 场景 | 结果 |
|---|---|---|
| `validation-1` | 已知负载，1 个属主 | 满载 8、占用 3、半载 5 分钟，与负载安排一致；KQL 与独立重算 13 个值相同 |
| `replay-1` | 2 个 Linux 用户共用 1 张卡 | 各 0.042 占用卡时；共用的 3 分钟各记一半 |
| `configure-2` | 一条命令完成配置 | 588 秒，退出码 0；重跑 441 秒；覆盖率 91.7 %；测试资源组已删除 |
| `jobs-1` | 3 个 AML 作业，1 个 Linux 用户 | 按作业拆成 0.067、0.042、0.042 卡时并给出提交人；11 个值与重算相同 |
| `auth-1` | 平台以应用注册登录 | 8 个查询 HTTP 200；错误密钥 HTTP 401；无权限 HTTP 403 |
<!-- END GENERATED: results -->

**边界。**
- 只测过 1 张卡的 VM，客户的 8 卡 VM 和 20 台批量接入没有实测；规模集和并行接入只用替身 `az` 测过。建议先做第 3 步预检。
- 进程属主和作业 ID 每分钟读一次：任务在一分钟中途退出时，这一分钟算占用，但可能不归到任何人或作业。
- AML 提交人来自 Azure 活动日志，比 GPU 数据晚 6–9 分钟。
- 分配卡时来自代理心跳，不是账单；对账请用 Cost Management。
- 数据量：一台 8 卡 VM 约 4.7 MB/天，按所在区域 Log Analytics 单价计费。

**仓库内容。** [`scripts/`](scripts/) 配置脚本 · [`vm/`](vm/) 采集器 · [`azure/`](azure/) 数据收集规则和报表模板 · [`kql/`](kql/) 八个查询 · [`examples/`](examples/) 参考客户端 · [`evidence/`](evidence/) 实测数据 · [`images/`](images/) 配图 · [`tests/`](tests/) 和 [`tools/`](tools/) 离线校验（`python -m unittest discover -s tests`，CI 每次提交都运行）。
