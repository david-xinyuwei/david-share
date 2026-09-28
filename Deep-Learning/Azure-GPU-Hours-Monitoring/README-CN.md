# Azure GPU 卡时统计 —— 分配卡时 vs 实际使用卡时，全 Azure 原生

> **作者**: 魏新宇 (Xinyu Wei) — Microsoft AI GBB Senior System Engineer

[English](README.md) | 中文版

[![Azure Monitor](https://img.shields.io/badge/Azure-Monitor%20%2B%20Log%20Analytics-0078D4)](https://learn.microsoft.com/azure/azure-monitor/)
[![NVIDIA DCGM](https://img.shields.io/badge/NVIDIA-DCGM%203.x%2F4.x-76B900)](https://developer.nvidia.com/dcgm)
[![GPU VM](https://img.shields.io/badge/Azure-ND%20H100%20v5%20%2F%20NC%20H100%20v5-0078D4)](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/)
[![无需自研 UI](https://img.shields.io/badge/UI-Workbook%20%7C%20%E5%8F%AF%E9%80%89%20Web%20UI-6366F1)](#5-看板)

回答每个 AI 基础设施负责人都会被问到的问题：**"我们每月付了 N 个卡时，到底有多少真正在算？谁用的？"**

本仓库是一套交付级参考实现，按 VM / GPU / 用户 / 小时 / 天 统计：

| 指标 | 定义 | 数据来源 |
|---|---|---|
| **分配卡时** | VM 运行分钟 × GPU 数 ÷ 60（账单口径） | AMA `Heartbeat` 表（每 VM 每分钟 1 条） |
| **占用卡时** | 有 GPU 进程 *或* GPU Util ≥ 阈值 的 GPU·分钟 ÷ 60 | `GpuMetrics_CL.ProcCount`、`GpuUtil` |
| **有效计算卡时** | Σ SM Active ÷ 60 —— 按 SM 活跃度加权，"占着但只算 10%" 的卡只记 0.1 | `GpuMetrics_CL.SmActive`（DCGM `PROF_SM_ACTIVE`） |
| **空闲卡时** | 分配 − 占用 —— VM 开着、GPU 没人用（纯浪费） | 计算得出 |
| **有效利用率 %** | 有效计算 ÷ 分配 | 计算得出 |
| **按人归属** | GPU 计算进程的 Linux 属主 | `nvidia-smi --query-compute-apps` + `/proc/<pid>` |

已在 Azure `NC40ads_H100_v5`（1× H100 NVL）上用三段式合成负载（满载 → 占显存空转 → 50% 占空比）端到端验证。下文 `metrics.png` 就来自那次真实运行。

<div align="center"><img src="images/architecture.png" width="960"></div>

---

## 目录

1. [为什么不直接用 Azure Monitor 指标 / 托管 Prometheus？](#1-为什么不直接用-azure-monitor-指标--托管-prometheus)
2. [架构](#2-架构)
3. [指标口径 —— 一个 GPU·分钟怎么分类](#3-指标口径--一个-gpu分钟怎么分类)
4. [三步部署](#4-三步部署)
5. [看板](#5-看板)
6. [平台对接（API 契约）](#6-平台对接api-契约)
7. [验证证据](#7-验证证据)
8. [生产化检查清单](#8-生产化检查清单)
9. [目录结构](#9-目录结构)
10. [清理](#10-清理)
11. [FAQ](#11-faq)

---

## 1. 为什么不直接用 Azure Monitor 指标 / 托管 Prometheus？

| 方案 | 结论 | 原因 |
|---|---|---|
| **VM 的 Azure 平台指标** | ✗ | Azure 看不到 Guest OS 内部，VM 没有 GPU 利用率平台指标。 |
| **Azure Monitor 托管 Prometheus + dcgm-exporter** | AKS ✓，普通 VM ✗ | 托管 Prometheus 只直接采集 AKS / Arc-enabled Kubernetes（[文档](https://learn.microsoft.com/azure/azure-monitor/metrics/prometheus-metrics-overview)）。普通 ND/NC VM 要自己跑 Prometheus agent 做 `remote_write`，多一个要运维的组件。**如果 GPU 在 AKS 节点池里，请用[官方 DCGM 集成](https://learn.microsoft.com/azure/azure-monitor/containers/prometheus-dcgm-integration)，不要用本仓库。** |
| **只用 Cost Management API** | ✗ | 能给分配卡时和费用，但不知道 GPU 是否真在算。 |
| **本仓库：DCGM → JSONL → Azure Monitor Agent → Log Analytics** | ✓ | 除了 200 行的采集脚本，其余全是 Azure 托管服务。`Heartbeat` 免费给出分配时长，DCGM 给出真实利用率，KQL 把两者 join。Workbook / Web UI / REST API 读的是同一张表。 |

设计原则：**只有一个自研组件（采集器），零自建存储，零强制自研 UI。**

---

## 2. 架构

```
GPU VM (×N)                          Azure Monitor（托管）                    消费端
┌──────────────────────────┐         ┌──────────────────────────┐          ┌────────────────────────┐
│ nvidia-dcgm (hostengine) │         │ DCE + DCR                │          │ Azure Workbook         │
│        │ dcgmi dmon 10 s │         │  Custom JSON Logs        │ ───────► │  （Portal，零代码）     │
│        ▼                 │  HTTPS  │  → Custom-GpuMetrics_CL  │          ├────────────────────────┤
│ gpumon.service (python)  │ ──────► ├──────────────────────────┤ ───────► │ Web UI + JSON API      │
│  每 GPU 每分钟均值        │  MSI    │ Log Analytics 工作区      │          │  （App Service，MSI）   │
│  + 进程属主               │         │  GpuMetrics_CL  Heartbeat│          ├────────────────────────┤
│  → /var/log/gpumon/*.json│         ├──────────────────────────┤ ───────► │ 客户自有平台            │
│        ▲ tail            │         │ 告警：空闲 ≥ 50/60 分钟   │          │  Log Analytics REST API│
│ Azure Monitor Agent      │         └──────────────────────────┘          └────────────────────────┘
└──────────────────────────┘
```

**数据链路**

1. **`nvidia-dcgm`**（host engine）暴露 profiling 计数器。读取 `DCGM_FI_PROF_SM_ACTIVE`(1002)、`GR_ENGINE_ACTIVE`(1001)、`PIPE_TENSOR_ACTIVE`(1004)、`DRAM_ACTIVE`(1005)，以及 `GPU_UTIL`、`FB_USED/TOTAL`、`POWER_USAGE`、`GPU_TEMP`。
2. **[`vm/gpu_collector.py`](vm/gpu_collector.py)** 以 10 秒间隔跑 `dcgmi dmon`，按 GPU 按分钟求平均，从 IMDS 取 VM 元数据（名称、规格、资源 ID、Tags），并记录**GPU 上每个进程的属主和进程名**，每 GPU 每分钟追加一行 JSON 到 `/var/log/gpumon/gpu_metrics_YYYYMMDD.json`，自动清理 3 天前的文件。
3. **Azure Monitor Agent** 通过 **Custom JSON Logs** DCR（[`azure/dcr.json`](azure/dcr.json)）tail 该文件，写入 `GpuMetrics_CL` 自定义表。AMA 同时每分钟发 `Heartbeat` —— 这就是分配时长的信号。
4. **KQL** 把两张表 join。Workbook、Web UI、REST API 用的是同一组查询，每个指标只有一处定义（[`azure/queries.kql`](azure/queries.kql)）。
5. **告警规则**：GPU 开机但最近 60 分钟内 ≥ 50 分钟无工作时触发。

**数据量**：每 GPU 每分钟 1 行 ≈ 600 字节 → 一台 8 卡 ND H100 v5 每天约 7 MB。Log Analytics 费用相对 GPU 账单可忽略。

---

## 3. 指标口径 —— 一个 GPU·分钟怎么分类

<div align="center"><img src="images/metrics.png" width="900"></div>

每个 GPU·分钟落在嵌套的桶里：**分配 ⊇ 占用 ⊇ 有效**。

```kusto
// 分配：VM 在运行（Heartbeat），乘以该 VM 上观察到的 GPU 数
let alloc = Heartbeat
| where Computer in ((GpuMetrics_CL | distinct Computer))
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer
| join kind=inner (GpuMetrics_CL | summarize Gpus = dcount(GpuId) by Computer) on Computer
| extend AllocGpuHours = RunMinutes * Gpus / 60.0;

// 占用 / 有效：来自 DCGM 采样
let used = GpuMetrics_CL
| summarize BusyGpuHours = countif(ProcCount > 0 or GpuUtil >= 5) / 60.0,
            EffGpuHours  = sum(SmActive) / 60.0 by Computer;

alloc | join kind=leftouter used on Computer
| extend IdleGpuHours = AllocGpuHours - BusyGpuHours,
         UtilPct = 100.0 * EffGpuHours / AllocGpuHours
```

为什么用 **SM Active** 而不是 `GPU_UTIL`：只要采样窗口内有*任何* kernel 驻留，`GPU_UTIL` 就是 100%；batch 没调好的训练任务可以 100% util 但 SM 只有 20% 活跃。`PROF_SM_ACTIVE` 是 SM 真正有活干的时间比例，在 H100 上这才是诚实的数字。两个都存了，可以对比。

**为什么"占显存但空转"这一段重要**（图中第 10–12 分钟）：一个进程占着 21 GB 显存但不算，它是*占用*（别人用不了这张卡）但*有效*为零。这个差值正是平台团队回收 GPU 需要看到的。

---

## 4. 三步部署

前置条件：Azure CLI 已登录、对目标订阅有 Contributor；运行脚本的机器有 `python3`；GPU VM 已装 NVIDIA 驱动和 `datacenter-gpu-manager`（Azure HPC 镜像和 `NvidiaGpuDriverLinux` 扩展都满足；DCGM 3.x 和 4.x 均可）。

### 第 1 步 —— Azure 侧（每个工作区一次）

```bash
cd scripts
./deploy-azure.sh -g rg-gpu-monitoring -l southeastasia -r 90
```

创建：资源组 → Log Analytics 工作区（保留 90 天）→ `GpuMetrics_CL` 表 → DCE + DCR → Workbook + 空闲告警。结束时打印 `WORKSPACE_ID`、`DCR_ID`、`DCE_ID` 供后续步骤使用。

### 第 2 步 —— 接入每台 GPU VM（可重复；不需要 SSH）

```bash
./onboard-vm.sh -g rg-gpu-vms -n nd-h100-node01 -d "$DCR_ID" -e "$DCE_ID"
```

每台 VM：开启系统托管身份 → 安装 `AzureMonitorLinuxAgent` → 关联 DCR + DCE → 通过 **Run Command** 启用 `nvidia-dcgm` 并安装 `gpumon.service`。3–5 分钟后 `GpuMetrics_CL` 出现第一批数据。

批量接入：对 `az vm list` 循环执行，或用 Azure Policy 内置策略 *"Configure Linux virtual machines to run Azure Monitor Agent"* + *"Configure Linux Machines to be associated with a Data Collection Rule"*，并把采集器打进 VM 镜像（`vm/install_collector.sh` 可直接用于镜像构建）。

### 第 3 步 ——（可选）独立 Web UI + JSON API

```bash
./deploy-webui.sh -g rg-gpu-monitoring -n gpuhours-<yourorg> -w "$WORKSPACE_ID" -l southeastasia
```

App Service（B1 Linux）+ 系统托管身份，**仅**授予工作区的 `Log Analytics Reader`；HTTPS-only、TLS 1.2+，访问码放在 `ACCESS_CODE`。如果 Azure Workbook 够用，可以跳过这一步。

---

## 5. 看板

### 5.1 Azure Workbook（零代码，Entra RBAC）

第 1 步已在工作区下部署 *"GPU 卡时统计 (DCGM + AMA)"*。参数：时间范围、VM 多选、占用阈值。面板：5 个 KPI 磁贴 → 按 VM 表 → 每小时分组柱状（分配/占用/有效）→ SM/Util/Tensor、显存、功耗趋势图（自适应粒度）→ 按用户表 → 按天表 → 当前状态 → 空闲 GPU 列表。

给同事只读权限：在资源组上分配 `Reader`（打开 Workbook）+ `Log Analytics Reader`（执行查询）。

### 5.2 Web UI（给没有 Azure 账号的人）

<div align="center"><img src="images/dashboard-webui.png" width="960"></div>

同样的指标、同样的 KQL，由 [`webui/app.py`](webui/app.py)（Flask，约 250 行）在访问码保护下提供。按小时/按天以**本地时间**切分（`TZ_HOURS`，默认 UTC+8）。响应缓存 60 秒，页面每分钟自动刷新。

---

## 6. 平台对接（API 契约）

客户平台消费数据的两种等价方式，选一种即可。

### 方式 A —— Log Analytics Query REST API（不需要额外服务）

```bash
./scripts/query.sh -w "$WORKSPACE_ID" -f ../azure/queries.kql      # 汇总查询
./scripts/query.sh -w "$WORKSPACE_ID" -q 'GpuMetrics_CL | where TimeGenerated > ago(1h) | summarize avg(SmActive) by Computer, GpuId'
```

`POST https://api.loganalytics.io/v1/workspaces/{WORKSPACE_ID}/query`，body `{"query": "...", "timespan": "P1D"}`，bearer token 的 resource 为 `https://api.loganalytics.io`。用有 `Log Analytics Reader` 的服务主体或托管身份。所有查询见 [`azure/queries.kql`](azure/queries.kql)。

### 方式 B —— Web UI 的 JSON API（已经是看板需要的形状）

```
GET /api/data?range={1h|6h|24h|7d|30d}&idle={0..100}
Authorization: Basic base64(任意用户名:ACCESS_CODE)
```

```jsonc
{
  "summary": { "Alloc": 2.717, "Busy": 0.283, "Eff": 0.157, "Idle": 2.434, "UtilPct": 5.8, "Vms": 1, "Gpus": 1 },
  "perVm":   [ { "Computer": "...", "VmSize": "Standard_NC40ads_H100_v5", "GpuName": "NVIDIA H100 NVL", "Gpus": 1,
                 "RunHours": 2.72, "Alloc": 2.72, "Busy": 0.28, "Eff": 0.16, "Idle": 2.43, "UtilPct": 5.8 } ],
  "hourly":  [ { "B": "09-28 11:00", "Alloc": 0.48, "Busy": 0.28, "Eff": 0.16, "Idle": 0.2, "UtilPct": 32.6 }, ... ],
  "daily":   [ { "B": "2026-09-28", "Alloc": 2.72, ... } ],
  "series":  [ { "T": "2026-09-28T03:34:00Z", "Gpu": "node0/GPU0", "SM": 94.1, "Util": 100, "Tensor": 91.6, "MemGB": 21.1, "PowerW": 398 }, ... ],
  "users":   [ { "User": "azureuser", "Computer": "...", "Busy": 0.27, "Eff": 0.15, "AvgSm": 56.9, "PeakMemGB": 21.1, "Processes": "python3" } ],
  "latest":  [ ... 每 GPU 最近一次采样，15 分钟窗口 ... ],
  "idleNow": [ ... 最近 60 分钟内空闲 ≥ 30 分钟的 GPU ... ],
  "meta":    { "range": "24h", "idle": 5, "grainMin": 2, "generatedAt": "2026-09-28T06:15:54Z" }
}
```

单位：所有 `*Hours`/`Alloc`/`Busy`/`Eff`/`Idle` 均为 **GPU 小时**；`SM`/`Util`/`Tensor`/`AvgSm`/`UtilPct` 为百分比；`B` 为本地时间的桶标签。

---

## 7. 验证证据

2026-09-28 在 `Standard_NC40ads_H100_v5`（Ubuntu 24.04，驱动 615.71，DCGM 3.3.9）上运行。合成负载 = 以非 root 用户（`azureuser`）跑 PyTorch bf16 8192² 矩阵乘，三个阶段：

| 阶段 | 时长 | 预期 | `GpuMetrics_CL` 实测 |
|---|---|---|---|
| 满载 | 8 分钟 | SM ≈ 100% | `SmActive` 0.94–0.97，`GpuUtil` 100，`PowerW` 398，`FbUsedMiB` 21 610，`Users` = azureuser |
| 占显存、不算 | 3 分钟 | 占用但不有效 | `ProcCount` 1，`FbUsedMiB` 21 610，`SmActive` 0.00，`PowerW` 101–115 |
| 50% 占空比 | 5 分钟 | SM ≈ 35–50% | `SmActive` 0.35，`GpuUtil` 31–63（采样效应，见 §3） |
| 空闲 | 窗口剩余 | 无 | `SmActive` 0，`ProcCount` 0，60 分钟后 `alert-gpu-idle-60min` 触发 |

截图时刻 24 小时窗口汇总：分配 2.72、占用 0.28、有效 0.16、空闲 2.43 GPU·h → **有效利用率 5.8%**。按用户表把 0.27 占用 / 0.15 有效 GPU·h 归属到 `azureuser / python3`。发布前，10 个 Workbook 查询和 7 个 API 查询全部通过 REST API 在真实工作区上执行验证。

踩过的坑，供参考：

* **镜像里装了 DCGM host engine 但没启用** —— `install_collector.sh` 里有 `systemctl enable --now nvidia-dcgm`。
* **`dcgmproftester` 拒绝运行**（"Expected Cuda version is 12, installed is 13"）—— DCGM 3.3.9 自带的压测工具落后于驱动。不影响采集，压测改用 PyTorch。
* **Workbook 时间图在 24h 下默认约 30 分钟粒度**，把 16 分钟的任务画成一条斜线。生成器强制 `max(1m, range/1440)`。
* **Workbook 图例大数字默认是 Sum**（如 "SM Active % 945"）—— 对百分比无意义，用 `chartSettings.showMetrics=false` 关掉。
* **AzureCliCredential 默认 10 秒超时**在笔记本上 7 个查询并发时不够 —— 进程内缓存 token，CLI 超时提高到 60 秒。

---

## 8. 生产化检查清单

作为可运行的 PoC 交付。在用这些数字计费或考核之前：

| # | 项目 | 本仓库状态 | 说明 |
|---|---|---|---|
| 1 | **按本地时间**切日 | ✅ Web UI（`TZ_HOURS`） | Workbook 的"按天"表是 UTC；需要的话给 `startofday()` 加 `+ 8h` |
| 2 | 分配卡时与账单**交叉校验** | ⚠️ 手动 | AMA 挂掉时 `Heartbeat` 会少算。每月用 Cost Management 用量导出或 Activity Log 的 VM 启停事件对账 |
| 3 | **保留 ≥ 90 天**；长期每日汇总 | ✅ 默认 90 天 | 加一条 [summary rule](https://learn.microsoft.com/azure/azure-monitor/logs/summary-rules)，把每 VM 每日卡时写到小表并保留 2 年 |
| 4 | **多卡（8× ND H100 v5）** | ✅ 代码就绪，未实测 | 采集器自动枚举所有 GPU，无需改动。*不*处理 MIG 实例 |
| 5 | **超越 Linux uid 的归属** | ⚠️ | 容器里看到的是容器的 uid（常为 root）。Slurm/K8s 场景用 `Computer` + 时间 join 调度器的作业表（`sacct` / pod labels） |
| 6 | **部门 / 项目维度** | ✅ 已打通 | `Tags` 列携带 VM 的 Azure 标签（来自 IMDS）——给 VM 打 `costcenter=…`、`project=…`，扩展 KQL 的 `by` 子句 |
| 7 | **批量接入** | ✅ 脚本；建议 Policy | 见第 2 步 |
| 8 | **告警通知** | ⚠️ | 告警规则没绑 Action Group。加 `--action-groups` 接 Teams/邮件/webhook |
| 9 | **消费端只读权限** | ✅ 已文档化 | 资源组上 Reader + Log Analytics Reader；或 Web UI 访问码 |
| 10 | **采集器归属** | — | `gpu_collector.py` 是你的代码，不是微软产品。在镜像流水线里把 DCGM 版本和驱动绑定 |

---

## 9. 目录结构

```
Azure-GPU-Hours-Monitoring/
├── README.md / README-CN.md
├── vm/
│   ├── gpu_collector.py        DCGM → JSONL 采集器（纯标准库，Python ≥ 3.8）
│   └── install_collector.sh    systemd 单元 + 启用 nvidia-dcgm
├── azure/
│   ├── dcr.json                ARM：Data Collection Endpoint + Rule（Custom JSON Logs → GpuMetrics_CL）
│   ├── build_workbook.py       生成下面三个文件（KQL + 标签的唯一来源）
│   ├── workbook.json           ARM：Workbook + scheduledQueryRules（空闲告警）
│   ├── workbook.parameters.json
│   ├── workbook.gallery.json   原始 Workbook JSON（Portal → 高级编辑器 → 粘贴）
│   └── queries.kql             供 REST API 消费者使用的同一组 KQL
├── webui/
│   ├── app.py                  Flask：/api/data JSON + 静态看板，托管身份访问 LAW
│   ├── static/index.html       单页看板（Chart.js）
│   └── requirements.txt
├── scripts/
│   ├── deploy-azure.sh         第 1 步
│   ├── onboard-vm.sh           第 2 步（每 VM）  ·  offboard-vm.sh 反向操作
│   ├── deploy-webui.sh         第 3 步
│   └── query.sh                Log Analytics REST API 示例
└── images/                     architecture.png, metrics.png, dashboard-*.png, make_diagrams.py
```

---

## 10. 清理

```bash
./scripts/offboard-vm.sh -g rg-gpu-vms -n nd-h100-node01     # 每 VM：采集器、AMA、关联
az group delete -n rg-gpu-monitoring --yes                    # 工作区、DCR、Workbook、告警、App Service
```

VM 保留 NVIDIA 驱动、DCGM 包和托管身份。

---

## 11. FAQ

**能用在 AKS GPU 节点池上吗？**  能，但不建议 —— Azure Monitor 托管 Prometheus 对 AKS 有[官方 DCGM 集成](https://learn.microsoft.com/azure/azure-monitor/containers/prometheus-dcgm-integration)。本仓库面向普通 ND/NC VM、CycleCloud/Slurm 集群和 VM Scale Sets。

**为什么用 JSON 文件 + AMA 而不是让采集器直接调 Logs Ingestion API？**  AMA 免费提供缓冲、重试、身份和代理，还附带 `Heartbeat`。采集器可以保持纯标准库、不持有任何凭据。

**为什么 DCGM 10 秒采样再平均到 1 分钟？**  1 分钟一行让每台 8 卡 VM 每天只有约 7 MB，并且和 `Heartbeat` 粒度一致便于 join。`PROF_*` 计数器本身已由 DCGM 在采样间隔内做了时间平均，不会丢突发。

**怎么改"占用"阈值？**  它是 Workbook 参数 / API 查询串（`idle=`）。默认 GPU util 5%。

**支持 DCGM 4.x 吗？**  支持 —— field ID 不变，`dcgmi dmon -e` 输出格式相同。

**GPU_UTIL 显示 60% 但 SM Active 只有 35%，哪个对？**  都对。`GPU_UTIL` = 窗口内有*任何* kernel 驻留的时间比例；`SM_ACTIVE` = SM 真正有活干的时间比例。要判断"这张卡值不值钱"，看 SM Active。
