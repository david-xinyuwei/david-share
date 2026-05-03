# Azure CycleCloud 深度解析 — 架构、Slurm 集成与 AI 训练适用性分析

> **客户**: Insilico Medicine（英矽智能，AI 药物发现）
> **场景**: 9× ND H200 v5 (72 GPU), DeepSpeed 分布式训练
> **最后更新**: 2026-03-11
> **作者**: 魏新宇 (Senior System Engineer, Microsoft)

---

## 目录

1. [什么是 Azure CycleCloud](#1-什么是-azure-cyclecloud)
2. [CycleCloud 架构](#2-cyclecloud-架构)
3. [Slurm 集成深度解析](#3-slurm-集成深度解析)
4. [CycleCloud Workspace for Slurm (CCWS)](#4-cyclecloud-workspace-for-slurm-ccws)
5. [Slurm vs Kubernetes — 不在同一层面](#5-slurm-vs-kubernetes--不在同一层面)
6. [作业执行模型 — 进程 vs 容器](#6-作业执行模型--进程-vs-容器)
7. [GPU 分区与支持的 VM SKU](#7-gpu-分区与支持的-vm-sku)
8. [CycleCloud 做 AI 训练 — 能行吗?](#8-cyclecloud-做-ai-训练--能行吗)
9. [CycleCloud vs 裸 GPU VM vs AML — 对比](#9-cyclecloud-vs-裸-gpu-vm-vs-aml--对比)
10. [容器镜像兼容性](#10-容器镜像兼容性)
11. [CycleCloud + DeepSpeed GitHub 生态](#11-cyclecloud--deepspeed-github-生态)
12. [信息来源](#12-信息来源)

---

## 1. 什么是 Azure CycleCloud

Azure CycleCloud 是 Azure 上的 **HPC 集群编排和管理应用**。它 **不是 PaaS 服务** — 而是安装在你订阅中的一台 Linux VM 上，通过 Azure API 管理计算集群。

| 能力 | 说明 |
|------|------|
| 集群生命周期管理 | 一键创建、扩缩容、监控、终止 HPC 集群 |
| 调度器支持 | Slurm、PBS Pro、Grid Engine、HTCondor、LSF |
| 自动扩缩容 | 根据作业队列从 0 扩到 N，空闲时缩回 0 |
| InfiniBand/RDMA | 原生支持 IB 互联的 VM Placement Group |
| 容器支持 | 预装 PMIx v4 + Pyxis + Enroot（CCWS 中） |
| 混合云突发 | 扩展本地 Slurm 集群到 Azure |
| IaC 模板 | 声明式集群定义，可重复部署 |
| Web UI + CLI + REST API | 完整管理界面 |

**关键点**: CycleCloud 是**带调度器集成的 VM 编排器** — 它创建/销毁 Azure VM。实际计算发生在标准 Azure VM（ND/NC/HB 系列等）上。

### CycleCloud 对 AI 训练实际只做 3 件事

剥离 HPC/Slurm 的复杂性，对纯 AI 训练客户来说，CycleCloud 的价值就是：

| # | 做什么 | 替代了什么 |
|:-:|--------|----------|
| 1 | **按需创建/销毁 GPU VM** | 你手动 `az vmss create` / `deallocate` |
| 2 | **Slurm 作业队列** | 你手动写 hostfile 和 `ssh` 登录节点 |
| 3 | **InfiniBand Placement** | 你手动配置 VMSS Placement Group |

其他一切（DeepSpeed、NCCL、训练代码、模型 checkpoint）— **与裸 VM 完全一样**。

**一句话**: CycleCloud = 一个高级的 VM 开关 + Slurm 调度器。它不会让训练更快或更好。

---

## 2. CycleCloud 架构

### 2.1 组件概览

![CycleCloud AI 训练架构图](images/cyclecloud-architecture.png)

> 微软官方架构图: [CycleCloud Deployment](https://learn.microsoft.com/en-us/azure/cyclecloud/images/architecture-deployment.png) | [Core Concepts](https://learn.microsoft.com/en-us/azure/cyclecloud/images/concept-architecture-diagram.png)

```
CycleCloud Server（1 台 CPU VM，常驻）
├── REST API / Web UI / CLI
├── 调用 Azure RM API，通过 VMSS 创建/销毁 VM
│
├── Slurm Scheduler（1 台 CPU VM，常驻）
│   ├── slurmctld（调度引擎）
│   ├── azslurm CLI（Azure-Slurm 桥梁）
│   └── munge（认证）
│
├── Login Node（可选，1 台 CPU VM，常驻）
│
├── 计算节点（按需扩缩）
│   ├── ND H200 × 9（72 GPU）— 示例
│   ├── slurmd + Pyxis + Enroot
│   ├── NCCL + InfiniBand 400Gb/s
│   └── 共享存储自动挂载
│
└── 共享存储（ANF / Managed Lustre / NFS）
```

### 2.2 常驻 vs 按需组件

| 组件 | VM 类型 | 常驻 |
|------|---------|:----:|
| CycleCloud Server | D4ads_v5 (4 vCPU, 16GB) | 是 |
| Slurm Scheduler | D4as_v4 (4 vCPU, 16GB) | 是 |
| Login Node（可选） | F4s_v2 (4 vCPU, 8GB) | 是 |
| Bastion | Standard | 是 |
| 共享存储 (NFS/ANF) | — | 是 |
| **GPU 计算节点** | **ND H200** | **否 — 按需** |

### 2.3 Marketplace 两种产品

| | Azure CycleCloud | CycleCloud Workspace for Slurm |
|---|---|---|
| 类型 | Virtual Machine | Azure Application |
| 部署内容 | 仅 1 台 CycleCloud Server VM | 完整环境（Server + Scheduler + 登录节点 + VNet + 存储 + Bastion） |
| 之后 | 手动创建集群、配 Slurm、网络、存储 | 开箱即用 — 直接提交作业 |
| 工作量 | 几天完成配置 | 几分钟（不到 3 分钟部署） |
| 调度器灵活性 | Slurm/PBS/LSF/GridEngine | 仅 Slurm |
| 容器支持 | 手动配置 | 预装 PMIx + Pyxis + Enroot |

**类比**: Azure CycleCloud = **毛坯房**（你自己装修一切）。CycleCloud Workspace for Slurm = **精装修**（拎包入住直接开工）。

---

## 3. Slurm 集成深度解析

### 3.1 Slurm Scheduler 头节点 — 集群的"大脑"

头节点自己不跑训练 — 它只做调度和分发。

| 职责 | 具体做什么 |
|------|-----------|
| 接收作业 | 用户 `sbatch train.sh` 提交到这里 |
| 排队调度 | 按优先级、公平策略排队 |
| 资源分配 | 决定哪个作业分到哪些 GPU 节点 |
| 节点管理 | 跟踪每台计算节点状态（idle/busy/down） |
| 记账 | 记录每个用户/项目的 GPU 时 |

核心进程: `slurmctld`（调度器）+ `slurmdbd`（记账，可选）+ `munge`（认证）

### 3.2 Slurm 头节点 vs K8s Master

| | Slurm 头节点 | K8s Master |
|---|---|---|
| 核心进程 | slurmctld | kube-apiserver + kube-scheduler + etcd |
| 调度什么 | Job（计算作业） | Pod（容器） |
| CLI | `sbatch` / `squeue` / `scancel` | `kubectl apply` / `kubectl get` |
| 管网络 | 否（IB 是基础设施层） | 是（CNI、Service、Ingress） |
| 管存储 | 否（NFS/Lustre 预配好） | 是（PV/PVC/StorageClass） |

Slurm 头节点 ≈ K8s Master 的**作业调度子集**。K8s 管的事情多得多。

### 3.3 azslurm 桥梁 — CycleCloud 怎么跟 Azure 对接

```
用户: sbatch train.sh
  → slurmctld: "需要 9 台 GPU 节点，当前 0 台" → 触发 ResumeProgram
    → azslurm resume: 读 Slurm 队列，计算需要多少 VM
      → CycleCloud Server: 调用 Azure RM API
        → Azure VMSS: 在同一 Placement Group 创建 9 台 ND H200
          → 9 台 VM 启动 → cluster-init → slurmd 注册 → 加入集群
```

Slurm 不知道 Azure 的存在。`azslurm` 是**翻译官**。

### 3.4 一个 Partition = 一个 NodeArray = 一个 VMSS

同一分区的所有节点在同一个 VMSS + Placement Group → InfiniBand 互联有保证。

### 3.5 节点生命周期（8 步）

![节点生命周期](images/node-lifecycle.png)

1. 用户 `sbatch` 提交作业，请求 9 台 GPU 节点
2. Slurm 排队 — 节点不够
3. azslurm 检测到 pending 作业 → 调 CycleCloud API → 创建 9 台 VMSS 实例
4. VM 启动 → cluster-init 安装 slurmd + Pyxis/Enroot + 挂载存储 + 配置 IB
5. 节点注册: `down` → `idle` → `alloc`
6. `srun` 执行训练（可选在 Enroot 容器中）— NCCL over IB
7. 训练完成 → 输出写入共享存储 → 节点变 `idle`
8. azslurm 检测空闲超时 → CycleCloud 删除 VM → **空闲零开销**

### 3.6 Slurm 自动注入 DeepSpeed 环境变量

| 变量 | 裸 VM（手动） | CycleCloud + Slurm |
|------|-------------|---------------------|
| MASTER_ADDR | 手动设置 | 自动从 `SLURM_NODELIST` 获取 |
| WORLD_SIZE | 手动计算: 9×8=72 | `SLURM_NTASKS` = 72 |
| RANK | DeepSpeed launcher | `SLURM_PROCID` 自动注入 |
| LOCAL_RANK | DeepSpeed launcher | `SLURM_LOCALID` 自动注入 |
| NODE_RANK | 手动设置 | `SLURM_NODEID` 自动注入 |
| hostfile | 手动编写 | 不需要 — `srun` 自动处理 |

---

## 4. CycleCloud Workspace for Slurm (CCWS)

### 4.1 配置 Tab（Marketplace GUI）

| Tab | 配置内容 |
|-----|---------|
| Basics | 订阅、Region、资源组、CycleCloud VM 规格、管理员用户 |
| File-system | NFS/ANF/Lustre 共享存储 |
| Networking | VNet、Subnet、Bastion |
| Slurm Settings | Slurm 版本、作业记账 |
| Scheduler | 头节点 VM 规格（CPU） |
| Login Node | 登录节点 VM 规格/数量 |
| **Partitions** | HTC / HPC / GPU 分区定义 |
| Other Settings | Branch 名、SSH 端口 |

### 4.2 默认三个分区

| 分区 | VM 类型 | 用途 | AI 训练需要？ |
|------|---------|------|:------------:|
| HTC | F2s_v2 (2 vCPU, 无 GPU) | 高吞吐小任务 | **不需要 — 设 Max=0** |
| HPC | HB120rs_v3 (120 vCPU, 无 GPU) | CPU 密集 MPI/CFD | **不需要 — 设 Max=0** |
| **GPU** | ND96asr_v4 (8×A100) | GPU 分布式训练 | **需要 — 只用这个** |

纯 AI 训练: 只保留 GPU 分区。

**为什么默认 3 个分区？** 因为 CCWS 是**通用 HPC 模板** — 假设你可能同时跑三种负载:

```
传统 HPC 用户的集群:
├── HTC → 跑上万个独立 GROMACS 小任务
├── HPC → 跑 128 节点 OpenFOAM MPI 仿真
└── GPU → 跑 AI 模型训练

纯 AI 训练集群（Insilico）:
├── HTC → 删掉或 Max=0
├── HPC → 删掉或 Max=0
└── GPU → 只需要这个（改为 ND H200，Max=9）
```

这也是 CycleCloud 对纯 AI 用户**过度工程化**的另一个体现 — AML 没有这些 HPC 包袱。

### 4.3 自动部署的资源（不到 3 分钟）

VNet、Bastion、Storage Account、NFS、Key Vault、监控、CycleCloud Server + Slurm 集群 — 全部自动化。

---

## 5. Slurm vs Kubernetes — 不在同一层面

| 维度 | Slurm | Kubernetes |
|------|-------|-----------|
| 设计目的 | HPC 作业调度器 | 容器编排平台 |
| 核心抽象 | Job — "跑一个计算任务" | Pod — "运行一个服务/进程" |
| 调度粒度 | 节点级 | 容器级 |
| 通信模型 | 紧耦合 — MPI/NCCL 原生 | 松耦合 — API/网络 |
| 网络 | InfiniBand/RDMA 原生 | TCP/IP 为主，IB 需额外配置 |
| 用户画像 | HPC 研究员 (`sbatch`) | 云原生工程师 (`kubectl`) |

交集: 两者都能调度 GPU 作业。但 Slurm **原生支持 IB/RDMA** — 千卡以上优势明显。

---

## 6. 作业执行模型 — 进程 vs 容器

### 6.1 CycleCloud 默认 = 裸进程（不是容器）

**两种执行模式一张图说清:**

```
CycleCloud + Slurm 作业执行模式
│
├── 默认: 裸进程（直接跑在宿主机 OS 上）
│     sbatch → srun python train.py
│                    ↓
│           宿主机 OS (Ubuntu)
│              ├── python (PID 12345)  ← 直接在宿主机跑
│              ├── GPU: /dev/nvidia* 直接访问
│              └── 网络: InfiniBand 宿主机直通
│     优点: 零开销
│     缺点: CUDA/PyTorch 需预装在每台 VM
│
└── 可选: Enroot 容器（轻量级，不是 Docker！）
      sbatch → srun --container-image=nvcr.io#nvidia/pytorch:24.01
                    ↓
           宿主机 OS (Ubuntu)
              └── Enroot 容器（无 daemon，用户态）
                    ├── python + CUDA + PyTorch 在容器内
                    ├── GPU: 直通（和裸进程一样）
                    └── 网络: 直通（和裸进程一样）
      优点: 环境一致性好（NGC 镜像自带全套）
      缺点: 接近零开销（不是你想象的 Docker 开销）
```

**与 K8s/Docker 的关键区别**: Enroot 不是 Docker。无 daemon、无网络虚拟化、无 cgroup 开销。GPU 和 InfiniBand 始终是宿主机直通。

| | 裸进程（默认） | Enroot 容器（可选） |
|---|---|---|
| 方式 | `srun python train.py` | `srun --container-image=nvcr.io#nvidia/pytorch:24.01 ...` |
| 隔离 | 无 — 直接跑在宿主机 OS | 仅文件系统隔离 |
| GPU 访问 | 直接 `/dev/nvidia*` | 直通（passthrough） |
| 网络 | 宿主机 IB 直通 | 宿主机 IB 直通 |
| 性能开销 | 零 | 接近零 |

### 6.2 与 K8s/AML/SageMaker 对比

| 平台 | 运行方式 | 网络 |
|------|---------|------|
| CycleCloud 默认 | 裸进程 | 宿主机 IB 直通 |
| CycleCloud + Pyxis | Enroot（无 daemon） | 宿主机 IB 直通 |
| AML / SageMaker | Docker | 虚拟网络（有开销） |
| AKS | containerd | CNI 虚拟网络 |

CycleCloud 优势: GPU 和 IB **始终是宿主机直通** — 无虚拟化层。

---

## 7. GPU 分区与支持的 VM SKU

CycleCloud **不限制** VM SKU。任何 Azure GPU VM 都能用。但多节点训练**必须 ND 系列**（有 InfiniBand）。

### ND 系列（多节点，InfiniBand）

| VM SKU | GPU | 显存/卡 | GPU/台 | IB |
|--------|-----|---------|:------:|:--:|
| ND96isr_H200_v5 | H200 | 141GB HBM3e | 8 | 400Gb/s |
| ND96isr_H100_v5 | H100 | 80GB HBM3 | 8 | 400Gb/s |
| ND96amsr_A100_v4 | A100 | 80GB HBM2e | 8 | 200Gb/s |
| ND96asr_v4 | A100 | 40GB HBM2e | 8 | 200Gb/s |
| ND96isr_MI300X_v5 | MI300X | 192GB HBM3 | 8 | 400Gb/s |

### NC 系列（单节点，无 InfiniBand）

| VM SKU | GPU | GPU/台 | IB |
|--------|-----|:------:|:--:|
| NC40ads_H100_v5 | H100 NVL | 1-2 | 无 |
| NC96ads_A100_v4 | A100 | 1-4 | 无 |
| NCasT4_v3 | T4 | 1-4 | 无 |

多节点训练: 每张 ND GPU 都有独立的 400 Gb/s InfiniBand 连接（每台 VM 聚合 3.2 Tb/s），支持大规模 NCCL all-reduce。NC 无 IB → 仅 25Gbps 以太网 — 多节点训练基本不可用。

---

## 8. CycleCloud 做 AI 训练 — 能行吗?

### 8.1 能 — 业界事实

几乎所有大规模 LLM 预训练都跑在 Slurm 集群上（Meta LLaMA 3: 16K H100，DeepSeek V3: 2K H800 等）。Azure CycleCloud + Slurm 技术上完全可行。

### 8.2 CycleCloud + Slurm + DeepSpeed 作业脚本示例

```bash
#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --nodes=9
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-node=8
#SBATCH --exclusive

CONTAINER="myacr.azurecr.io#ai/training:latest"

srun --mpi=pmix \
     --container-image=${CONTAINER} \
     --container-mounts=/shared:/shared \
     deepspeed --num_gpus=8 \
         train.py --deepspeed ds_config.json
```

训练代码（DeepSpeed + NCCL）无论用 CycleCloud、裸 VM 还是 AML，**完全一样**。

### 8.3 启动 9 节点训练 — 逐步对比

**裸 VM 方式（7 步）:**

```bash
# Step 1: 手动创建 9 台 VM
az vmss create --name gpu-cluster --instance-count 9 --vm-sku Standard_ND96isr_H200_v5 ...
# Step 2: 等所有 VM 启动（5-10 分钟）
# Step 3: 获取每台 VM 的 IP
az vmss list-instances ...
# Step 4: 手动写 hostfile
echo "10.0.0.4 slots=8" > hostfile && echo "10.0.0.5 slots=8" >> hostfile ...
# Step 5: 验证 NFS 挂载和 IB
ssh gpu-1 "ls /shared/data && ibstatus"
# Step 6: 从第一台节点发起训练
ssh gpu-1 "deepspeed --hostfile hostfile --num_gpus=8 --num_nodes=9 train.py"
# Step 7: 记得训练完关机！
az vmss deallocate --name gpu-cluster ...
```

**CycleCloud 方式（1 步）:**

```bash
sbatch train.sh
# 就这样。VM 自动创建、hostfile 自动生成、训练跑完、VM 自动删除。
```

### 8.4 CycleCloud vs 裸 VM 的区别

| 维度 | 裸 GPU VM | CycleCloud + Slurm |
|------|----------|---------------------|
| 拉起 9 台 H200 | 手动 | `sbatch` → 自动创建 |
| 训练完关机 | 手动（忘关有风险） | 自动缩到 0 |
| IB Placement Group | 手动配 VMSS | 自动 |
| MASTER_ADDR / hostfile | 手动写 | Slurm 自动注入 |
| 共享存储挂载 | 每台 VM 手动 mount | 模板自动 mount |
| 节点健康检查 | 无 | 内置 GPU/IB 检查 |
| 多人排队 | 无 | Slurm 公平调度 |
| 学习成本 | 零 | 要学 Slurm |

### 8.5 CycleCloud 没有的能力

| 缺失 | AML 有？ |
|------|:-------:|
| 实验追踪 | 有（MLflow） |
| MLOps 流水线 | 有 |
| 模型版本管理 | 有（Registry） |
| AML 计算目标 | 无法将 CycleCloud 挂到 AML |

---

## 9. CycleCloud vs 裸 GPU VM vs AML — 对比

![平台对比](images/platform-comparison.png)

| 维度 | 裸 GPU VM | CycleCloud + Slurm | Azure Machine Learning |
|------|----------|---------------------|----------------------|
| **部署复杂度** | 低（直接建 VM） | 中（需配 Slurm + CycleCloud） | 低（托管服务） |
| **自动扩缩容** | 手动 VMSS | 自动（基于 Slurm 队列） | 自动（基于作业） |
| **GPU 空闲成本风险** | 高（手动关机） | 低（自动缩到 0） | 低（托管计算） |
| **InfiniBand / RDMA** | 手动配 Placement Group | 原生（partition = VMSS + PG） | 原生 |
| **容器支持** | Docker / Podman | Enroot + Pyxis（零开销） | Docker |
| **作业调度** | 无（手动 hostfile） | Slurm（公平调度、优先级、多用户） | AML 作业队列 |
| **实验追踪** | 无 | 无（可单独加 MLflow） | MLflow 内置 |
| **MLOps 流水线** | 无 | 无 | 有（AML Pipelines） |
| **多用户隔离** | 无 | Slurm 账户 + 分区 | Workspace RBAC |
| **学习成本** | 零 | 要学 Slurm | 要学 AML SDK |
| **团队适配** | 任何 Linux 管理员 | HPC / Slurm 用户 | 数据科学家 / ML 工程师 |
| **最适合** | 快速 PoC，1-2 节点 | 多用户、大规模、HPC 团队 | 以 MLOps 为核心的团队 |

**选型建议：**

- **裸 VM**: 快速实验、单用户、1-2 节点、不需要调度器
- **CycleCloud + Slurm**: 多用户团队、4+ 节点、有 HPC 背景、需兼容 Slurm 生态
- **AML**: ML 团队需要托管 MLOps、实验追踪、模型注册表、类 SageMaker 体验

---

## 10. 容器镜像兼容性

### 10.1 CycleCloud 完全支持容器镜像

常见问题：*"我们已经有 Docker 镜像了 —— CycleCloud 能用吗？"*

**可以。** CycleCloud 使用 **Enroot**（通过 Pyxis Slurm 插件）作为容器运行时。Enroot **完全兼容 Docker/OCI 镜像格式** —— 你现有的 Docker 镜像无需任何修改即可使用。

### 10.2 支持的镜像来源

| 镜像来源 | 语法 | 示例 |
|---------|------|------|
| Docker Hub | `docker.io#org/image:tag` | `docker.io#pytorch/pytorch:2.1.0` |
| NVIDIA NGC | `nvcr.io#nvidia/pytorch:tag` | `nvcr.io#nvidia/pytorch:24.01-py3` |
| Azure Container Registry | `myacr.azurecr.io#repo/image:tag` | `myacr.azurecr.io#ai/training:latest` |
| 本地 squashfs 镜像 | `/path/to/image.sqsh` | `/shared/images/train.sqsh` |

### 10.3 为什么用 Enroot 而不是 Docker？

| | Docker | Enroot |
|---|---|---|
| 需要 Daemon | 是（dockerd） | **不需要** — 无 daemon，用户态 |
| 需要 Root | 是（或 rootless 模式） | **不需要** — 普通用户运行 |
| 网络虚拟化 | 是（bridge/overlay） | **不需要** — 宿主机网络直通 |
| GPU 访问 | 通过 `--gpus` 标志 | **直接** — 宿主机 `/dev/nvidia*` 直通 |
| InfiniBand 访问 | 需要 `--privileged` 或设备挂载 | **直接** — 宿主机 IB 直通 |
| MPI / NCCL 性能 | 网络栈有轻微开销 | **零开销** — 与裸进程完全一样 |
| 镜像兼容性 | Docker/OCI 原生 | **Docker/OCI 兼容**（转换为 squashfs） |

**核心洞察**: Enroot 专为 HPC/AI 设计 —— 去掉了 Docker 为微服务添加的一切（daemon、网络虚拟化、cgroup 隔离），只保留文件系统隔离。结果：容器的便利性 + 裸机的性能。

### 10.4 在 CycleCloud Slurm 作业中使用容器镜像

```bash
#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --nodes=9
#SBATCH --gpus-per-node=8

# 从 ACR（或任何 Docker 兼容 registry）拉取
srun --container-image=myacr.azurecr.io#ai/training:latest \
     --container-mounts=/shared/data:/data,/shared/checkpoints:/checkpoints \
     python train.py --deepspeed ds_config.json
```

**从 Docker 平台迁移（SageMaker、AML 等）**: 同一个镜像、同一个 Dockerfile — 只需修改 `srun --container-image=` 引用。无需重新打包。

---

## 11. CycleCloud + DeepSpeed GitHub 生态

微软提供官方 GitHub 仓库，用于在 CycleCloud 上运行大规模 AI 训练：

| 仓库 | Stars | 说明 |
|------|:-----:|------|
| [Azure/cyclecloud-slurm](https://github.com/Azure/cyclecloud-slurm) | ~80 | CycleCloud + Slurm 核心集成（模板、azslurm CLI、自动扩缩器） |
| [Azure/cyclecloud-pyxis](https://github.com/Azure/cyclecloud-pyxis) | — | 在 CycleCloud 集群上安装 Pyxis + Enroot（容器支持） |
| [Azure/ai-infrastructure-on-azure](https://github.com/Azure/ai-infrastructure-on-azure) | ~25 | 大规模 AI 训练示例（GPT-3-175B、MegatronLM、LLM Foundry） |
| [Azure/cyclecloud-llm](https://github.com/Azure/cyclecloud-llm) | — | CycleCloud + Slurm LLM 训练配置（OPT-175B 等） |

### 关键软件版本（截至 2026-03）

| 组件 | 版本 |
|------|------|
| cyclecloud-slurm | 4.0.6 |
| Slurm | 25.05.5 |
| PMIx | 4.2.9 |
| CycleCloud | 8.8+ |

### 支持的框架

| 框架 | 支持 | 说明 |
|------|:----:|------|
| PyTorch DDP | ✅ | 原生多卡分布式训练 |
| DeepSpeed | ✅ | ZeRO、梯度累积、流水线并行 |
| Megatron-LM | ✅ | 张量并行、流水线并行 |
| Horovod | ✅ | 基于 NCCL All-Reduce |

---

## 12. 信息来源

| 来源 | URL |
|------|-----|
| Azure CycleCloud 文档 | https://learn.microsoft.com/en-us/azure/cyclecloud/ |
| CycleCloud Workspace for Slurm | Azure Marketplace — 搜索 "CycleCloud Workspace for Slurm" |
| ND H200 v5 VM 规格 | https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nd-h200-v5-series |
| ND H100 v5 VM 规格 | https://learn.microsoft.com/en-us/azure/virtual-machines/nd-h100-v5-series |
| cyclecloud-slurm GitHub | https://github.com/Azure/cyclecloud-slurm |
| cyclecloud-pyxis GitHub | https://github.com/Azure/cyclecloud-pyxis |
| ai-infrastructure-on-azure GitHub | https://github.com/Azure/ai-infrastructure-on-azure |
| Slurm 文档 | https://slurm.schedmd.com/ |
| NVIDIA Enroot | https://github.com/NVIDIA/enroot |
| NVIDIA Pyxis | https://github.com/NVIDIA/pyxis |
