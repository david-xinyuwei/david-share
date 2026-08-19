# Azure Context Cache 客户评估

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![CPython 3.11 AMD64](https://img.shields.io/badge/CPython-3.11%20AMD64-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[英文版](README.md) | [源码](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [官方上游](https://github.com/Azure/AzureContextCache)

评估 Azure OpenAI 应用的显式上下文缓存：适用于反复发送相同长指令、工具定义、示例或参考资料的业务请求。

## 客户问题与业务价值

企业 AI 应用通常会在每次请求中重复发送大段稳定上下文，只有用户任务或当前案例数据发生变化。Azure Context Cache 将 Azure OpenAI 部署与具名缓存容器关联，使前缀匹配的后续请求能够复用已经处理过的稳定内容。

| 业务价值杠杆 | 为什么重要 | 客户应如何验证 |
|---|---|---|
| 请求延迟 | 缓存命中可以避免重复处理稳定前缀 | 使用客户自己的提示词组合与并发测试延迟分布 |
| 输入 token 经济性 | 缓存读取可以使用折扣后的输入 token 价格 | 结合 `cached_tokens`、实际命中率和当前 Azure 定价计算 |
| 容量效率 | 复用重复前缀计算可以释放模型计算能力 | 在目标负载下执行受控吞吐测试 |
| 治理 | 具名缓存资源部署在客户订阅、区域和 RBAC 边界内，并配置 TTL | 核对目标区域、访问控制、生命周期和数据要求 |

> [固定版本的官方 Quickstart](https://github.com/Azure/AzureContextCache/tree/7d1029a5e8b59b1805e70992c85ffe6798d2f47a) 将延迟、成本和吞吐列为产品价值杠杆。本仓库只证明在一个已获准环境中实际使用了缓存，不量化客户的成本节省或生产性能。

## 工作负载适配

| 决策 | 工作负载模式 | 评估建议 |
|---|---|---|
| **GO** | 长系统/开发者指令、稳定工具目录、少样本示例或共享政策 | 把可复用内容放在前部，把变化的任务数据放在末尾 |
| **GO** | 客户支持、代码/合规审查、文档密集型助手和受控智能体工作流 | 规则、工具或参考资料会跨请求重复使用时进入评估 |
| **CONDITIONAL** | 早期对话历史保持稳定、后续内容仅追加的多轮对话 | 验证早期前缀能否保持字节完全一致 |
| **LOW PRIORITY** | 短提示词，或请求前部频繁变化 | 可复用前缀有限，通常不应优先投入 |
| **LOW PRIORITY** | 一次性请求，或每次请求开头都是高度个性化内容 | 缓存复用概率较低 |
| **CONDITIONAL** | 需要承诺精确成本节省或吞吐提升的业务场景 | 另做客户数据基准测试和当前定价模型 |

## 客户业务架构

![Azure Context Cache 客户应用业务架构](images/customer-architecture.svg)

1. 客户应用把可复用的指令、工具、示例和共享资料放入稳定前缀。
2. 每次变化的用户任务和案例数据追加为动态后缀。
3. 应用继续调用 Azure OpenAI Responses API；已关联的部署会在 Context Cache 容器中查找匹配前缀。
4. 应用通过 `cached_tokens`、延迟和请求结果验证真实业务流量是否适配。

Context Cache 容器是客户订阅中的 Azure 资源。锁定的 Private Preview Quickstart 配置缓存账户、模型专属容器、TTL 和 `contextCacheContainerId` 绑定。

## 本仓库实际证明了什么

已在获得 Private Preview 准入的 Azure 订阅中，对锁定至 commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` 的官方 Quickstart 完成端到端验证。

| 验证信号 | 实际结果 | 证据含义 |
|---|---:|---|
| 真实 Responses API 调用 | `6/6` 完成 | 官方部署链路和数据面调用成功完成 |
| 预热后缓存调用 | `5/5` 命中 | 已关联的 Context Cache 为预热后调用提供缓存 |
| 缓存输入 token | 每次均为 `2304` | 观测到一致的非零缓存信号 |
| 证据处理 | 后续 2 次不完整运行被拒绝 | 传输错误没有被转换为通过结果 |

**建议下一步：** 完成 Preview 准入、权限、配额和区域可用性确认后，在客户自有 Azure 环境中使用具有代表性的提示词运行同一套验证。

> **证据边界：** 这是一次运行的能力观测，不代表生产就绪、可用性、成本节省、吞吐或延迟保证。

本仓库评估的是基于 `Microsoft.Storage/contextCaches` 和 `contextCacheContainerId` 的固定 Private Preview 资源路径。通用 Azure OpenAI prompt caching 指南可能因模型家族和 API 接口形态不同而采用其他机制；目标模型与当前能力边界应另行对照最新官方文档确认。

## 测试信息、步骤与证据

### 测试信息

| 项目 | 已验证值 |
|---|---|
| 观测日期 | `2026-08-18` |
| 执行面 | `LOCAL_WINDOWS` |
| Azure 区域 | `centralus` |
| 官方源码 | commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` 对应的 `Azure/AzureContextCache` |
| 运行时 | CPython `3.11.9 AMD64`；通过 PowerShell 7 编排，并使用 Azure CLI 用户身份认证 |
| 部署 | `gpt-5.4`，模型版本 `2026-03-05-contextcache`，Responses API `preview` |
| 缓存合同 | 模型专属 Context Cache 容器、7 天 TTL，以及显式 `contextCacheContainerId` 绑定 |
| 请求模式 | 1 次预热请求，随后并行发送 5 次请求 |

本表描述的是经过脱敏的验证环境，不代表区域支持或生产容量建议。

### 测试步骤

1. **验证官方源码。** `scripts/verify_upstream.py` 解析固定 Git 对象，核对全部 25 个执行输入的 SHA-256，并且只在公共源码树之外物化这些已验证字节。
2. **执行 Azure 只读前置检查。** `scripts/run_official_e2e.ps1 -WhatIf` 检查当前订阅、实时 ARM 读取、必要资源提供程序、受控 Preview 功能、运行时架构和目标区域前提条件；此步骤不部署资源，也不发送模型请求。
3. **部署官方 Quickstart。** 实时运行器安装具有精确 hash 的 Windows AMD64 CPython 3.11 依赖，然后在私有运行目录中调用字节完全一致的官方 `scripts/quickstart.ps1 -SkipPython`。
4. **验证数据面。** 官方 Demo 先发送 1 次预热请求，再使用相同的稳定前缀并行发送 5 次 Responses API 请求。
5. **独立验证结果。** `scripts/parse_demo_output.py` 解析全部 6 条调用记录；缺行、传输错误、零阈值、零延迟或预热后命中不足都会失败。`scripts/validate_arm_summary.py` 独立核对部署成功状态、模型身份、缓存容器 ID、提供程序、TTL 和部署绑定。
6. **执行离线回归门。** 在发布 commit 上运行单元测试、真实性检查、公共内容审计、Repo gate、依赖检查、PowerShell 语法检查、CI 矩阵和 CodeQL。

### 测试脚本

| 脚本或测试集 | 在测试中的职责 | 失败即拒绝条件 |
|---|---|---|
| [`scripts/run_official_e2e.ps1`](scripts/run_official_e2e.ps1) | Azure 前置检查、已验证源码物化、官方 Quickstart 执行、日志捕获和证据编排 | 配置目录复用、运行时不符、资源组已存在、Azure 超时/报错、官方进程非零退出或证据验证失败时立即停止 |
| [`scripts/verify_upstream.py`](scripts/verify_upstream.py) | 核对固定 Repo、commit 和 25 个 Git blob 的 SHA-256 | blob 缺失、不匹配或输出目录非空时拒绝执行 |
| [`scripts/parse_demo_output.py`](scripts/parse_demo_output.py) | 解析调用级延迟和 token 字段并计算缓存判定 | 传输错误、调用缺失/格式错误、零阈值/延迟或预热后命中不足时拒绝结果 |
| [`scripts/validate_arm_summary.py`](scripts/validate_arm_summary.py) | 交叉核对 ARM 部署状态以及 AOAI 与缓存的绑定 | 部署失败、字段缺失、模型/提供程序/TTL 错误或资源 ID 不一致时拒绝结果 |
| [`scripts/demo_code_validator.py`](scripts/demo_code_validator.py) | 确认验证器使用真实官方路径，而不是硬编码或 mock 结果 | 模拟产品行为或源码/运行时合同漂移时失败 |
| [`scripts/audit_public_content.py`](scripts/audit_public_content.py) | 扫描秘密、具体云标识、不安全链接、重解析点和不支持的公开格式 | 发现任何 Public boundary（公开边界）问题时发布门失败 |
| [`scripts/validate_repo.py`](scripts/validate_repo.py) 和 [`tests/`](tests/) | 重新计算证据算术/hash，并测试解析器、ARM、源码锁、编排和 Public boundary 分支 | 任一不变量或回归测试失败均返回非零退出码 |

### 脱敏测试日志

下面是根据 [`evidence/verified-run-summary.json`](evidence/verified-run-summary.json) 渲染的可读摘录。它**不是**私有原始 stdout/stderr；云资源标识、endpoint、身份和部署记录均未公开。

```text
[run] observed_at=2026-08-18 upstream_commit=7d1029a5e8b59b1805e70992c85ffe6798d2f47a
[environment] execution_plane=LOCAL_WINDOWS region=centralus python="3.11.9 AMD64"
[deployment] model=gpt-5.4 model_version=2026-03-05-contextcache api_version=preview cache_ttl_days=7
[call 1] latency_ms=5820 input_tokens=2607 cached_tokens=0    output_tokens=200
[call 2] latency_ms=3791 input_tokens=2571 cached_tokens=2304 output_tokens=126
[call 3] latency_ms=3751 input_tokens=2681 cached_tokens=2304 output_tokens=200
[call 4] latency_ms=3671 input_tokens=2675 cached_tokens=2304 output_tokens=200
[call 5] latency_ms=3215 input_tokens=2570 cached_tokens=2304 output_tokens=133
[call 6] latency_ms=3784 input_tokens=2540 cached_tokens=2304 output_tokens=200
[summary] successful_calls=6 warm_hits=5/5 warm_cached_tokens=2304 verdict=PASS
```

这些延迟值仅用于审计追溯。一次运行无法建立延迟分布，也不能支撑生产性能声明。

### 测试结果

已入库的 [`validation-history.json`](evidence/validation-history.json) 同时保留完整运行和被拒绝的运行：

| 日期 | 执行路径 | 完成调用数 | 传输错误数 | 缓存结果 | 判定 |
|---|---|---:|---:|---:|---|
| `2026-08-18` | `official-baseline` | 6 | 0 | 5/5 次预热后命中 | **PASS** |
| `2026-08-19` | `public-wrapper-reference` | 6 | 0 | 4/5 次预热后命中 | **PASS** |
| `2026-08-19` | `hardened-wrapper-probe-1` | 3 | 3 | 不计分 | **REJECTED — INCOMPLETE** |
| `2026-08-19` | `hardened-wrapper-probe-2` | 2 | 4 | 不计分 | **REJECTED — INCOMPLETE** |

| 发布 commit 质量门 | 结果 | 证据 |
|---|---:|---|
| 确定性单元测试 | `38/38` 通过 | `python -m unittest discover -s tests -v` |
| 真实性、公开边界与 Repo gate | `3/3` 通过 | `demo_code_validator.py`、`audit_public_content.py`、`validate_repo.py` |
| Windows/Ubuntu × Python 3.11/3.13 CI 矩阵 | `4/4` 个 job 通过 | [GitHub Actions run 32270323872](https://github.com/david-xinyuwei/david-share/actions/runs/32270323872) |
| CodeQL 分析器 | `7/7` 个 job 通过 | [CodeQL run 32270323901](https://github.com/david-xinyuwei/david-share/actions/runs/32270323901) |

实时结果和离线质量门回答的是不同问题：实时运行证明有边界的 Azure 产品路径；离线测试证明证据解析器、源码锁、编排控制和公开发布合同仍按预期工作。

## 客户评估路径

### 前提条件

- Windows 上的 PowerShell 7（`pwsh`）、Git、Azure CLI，以及 AMD64 Windows 上的 64 位 CPython 3.11
- 已获得 Azure Context Cache Private Preview 权限的 Azure 订阅
- `OpenAI.ContextCacheAllowed` 已达到 `Registered`
- 已通过租户允许的用户认证流登录独立 `AZURE_CONFIG_DIR`
- 具备部署资源和分配 `Cognitive Services OpenAI User` 的权限
- 目标区域具备可用模型配额

实时运行会创建计费 Azure 资源并发送模型请求。请使用唯一的资源组和名称前缀；检查生成的证据后，再单独决定是否清理。

### 运行官方 E2E

```powershell
$env:AZURE_CONFIG_DIR = "$HOME\.azure-context-cache-validation"
$subscriptionId = "YOUR-SUBSCRIPTION-ID"

az account set --subscription $subscriptionId
az account show --query '{name:name,id:id,tenantId:tenantId,user:user.name}' -o json

pwsh -NoProfile -File .\scripts\run_official_e2e.ps1 `
  -SubscriptionId $subscriptionId `
  -ResourceGroup "rg-context-cache-validation" `
  -Location "centralus" `
  -NamePrefix "ccvalidate" `
  -Runs 6
```

建议先加 `-WhatIf`：它只执行有超时上限的 Azure 只读前置检查，不克隆、不部署、也不发送请求。实时运行必须使用全新的唯一资源组；运行器会在源码树之外创建唯一的私有证据目录，并且不会自动清理 Azure 资源。网络受限时，可用 `-ExistingUpstreamDirectory` 指向固定 commit 的检出副本；来源控制细节见 [方法与证据链](docs/METHOD-CN.md)。

### 本地验证

```powershell
python -m unittest discover -s tests -v
python scripts\demo_code_validator.py
python scripts\audit_public_content.py
python scripts\validate_repo.py
```

这些离线验证门不需要 Azure。也可以针对位于固定 commit 的已有检出副本核对官方上游版本锁定：

```powershell
python scripts\verify_upstream.py `
  --upstream-dir "PATH-TO-AzureContextCache" `
  --lock .\UPSTREAM_LOCK.json `
  --output "EMPTY-PRIVATE-OUTPUT-DIRECTORY"
```

## 证据边界与验证方法

方法由三层相互独立的证据组成：

| 层 | 权威来源 | 证据 |
|---|---|---|
| 源码身份 | Azure 官方 Git 仓库 | 固定 commit 和经过验证的执行输入 |
| Azure control plane（控制面） | Azure Resource Manager | 资源提供程序和功能前置检查，以及部署、AOAI 模型、缓存容器 ID、提供程序和 TTL 绑定 |
| Azure data plane（数据面） | 官方 Responses API 示例 | 六条调用记录、cached tokens 和失败即拒绝阈值 |

详见 [方法与证据链](docs/METHOD-CN.md)、[公共证据边界](evidence/README.md)、[脱敏运行摘要](evidence/verified-run-summary.json) 和 [验证历史](evidence/validation-history.json)。公共证据不包含云资源标识和私有原始日志。

## 安全与运维

- 禁止把凭据、Azure CLI 缓存、终结点、资源 ID 或实时运行原始日志写入本仓库。扫描器同时拒绝符号链接、重解析点、不支持的公共文件格式，以及常见 token、SAS 和连接字符串形式。
- 每个项目使用独立 `AZURE_CONFIG_DIR`；运行器拒绝隐式共享配置，也拒绝把工作目录放入公共源码树。
- 本地验证通过 Azure CLI 使用用户身份认证。长期运行的服务应选择合适的托管身份或服务主体。
- 运行器要求使用全新资源组，并故意不自动清理。执行任何删除前，应先检查上游 `scripts/cleanup.ps1`、生成的 `run-contract.json`、私有 `manifest.json` 和目标资源组。
- 删除是独立的显式操作。如果使用已有 Azure OpenAI 账户，在确认其所有权之前不得运行清理脚本。

安全问题和运维说明见 [SECURITY.md](SECURITY.md)。

## 产品与证据限制

- 这是 Private Preview 验证工具，不是可用性或生产就绪保证。
- 上游 API 版本、模型版本、区域、配额和准入流程都可能变化。
- 单次运行无法证明延迟分布、并发保证或成本节省。
- 缓存命中可能随运行变化。默认验证门要求 5 次预热后调用至少命中 3 次，且阈值不能为零；只有明确修改验收合同后才应调整。
- 当前验证工具面向上游 Windows PowerShell Quickstart。
- 实时依赖锁明确限定为已实测的 Windows AMD64 CPython 3.11 运行环境。
- 固定 commit 未提供 license file。该子树不签入任何上游源码；运行器会从已验证 Git blob 创建临时私有执行副本。

## 参考资料

- [Azure/AzureContextCache](https://github.com/Azure/AzureContextCache)
- [固定的上游 commit](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
- [Azure OpenAI prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)
- [Azure CLI configuration isolation](https://learn.microsoft.com/cli/azure/azure-cli-configuration)
- [ATTRIBUTION.md](ATTRIBUTION.md)

维护者：魏新宇