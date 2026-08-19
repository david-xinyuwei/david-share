# Azure Context Cache 端到端验证

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![CPython 3.11 AMD64](https://img.shields.io/badge/CPython-3.11%20AMD64-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[English](README.md) | [Source](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [官方 upstream](https://github.com/Azure/AzureContextCache)

已完成 Azure Context Cache Private Preview 官方 Quickstart 的端到端验证：`6/6` 次真实 Responses API 调用均完成，`5/5` 次预热后调用均报告 `2304` 个 cached tokens。

## 已验证结果

已在获得 Private Preview 准入的 Azure 订阅中，对锁定至 commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a` 的官方 Quickstart 完成端到端验证。验证采用失败即拒绝策略，不完整证据不会计入通过结果。

| 验证信号 | 实际结果 | 能够证明什么 |
|---|---:|---|
| 真实 Responses API 调用 | `6/6` 完成 | 官方部署链路和数据面调用成功完成 |
| 预热后缓存调用 | `5/5` 命中 | 已关联的 Context Cache 为预热后调用提供缓存 |
| 缓存输入 token | 每次均为 `2304` | 观测到一致的非零缓存信号 |
| 证据处理 | 后续 2 次不完整运行被拒绝 | 传输错误没有被转换为通过结果 |

**建议下一步：** 完成 Preview 准入、权限、配额和区域可用性确认后，在客户自有 Azure 环境中运行同一套验证。

> **结论边界：** 这是一次运行的能力观测，不代表生产就绪、可用性、成本节省或延迟保证。后续两次不完整运行均按失败即拒绝策略判定为未通过，未计入缓存结果。

## 快速开始

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

建议先加 `-WhatIf`：它只执行有超时上限的 Azure 只读前置检查，不克隆、不部署、也不发送请求。实时运行必须使用全新的唯一资源组；运行器会在源码树之外创建唯一的私有运行目录和全新虚拟环境，并输出精确证据路径。网络受限时，可用 `-ExistingUpstreamDirectory` 提供位于固定 commit 的检出副本作为 Git 对象源；未提交的工作树字节会被忽略，运行器仍只导出并执行 25 个通过 SHA-256 校验的 Git blob。默认使用全新的官方克隆。

### 本地验证

```powershell
python -m unittest discover -s tests -v
python scripts\demo_code_validator.py
python scripts\audit_public_content.py
python scripts\validate_repo.py
```

这些离线验证门不需要 Azure。也可以针对位于固定 commit 的已有检出副本核对官方上游锁：

```powershell
python scripts\verify_upstream.py `
  --upstream-dir "PATH-TO-AzureContextCache" `
  --lock .\UPSTREAM_LOCK.json `
  --output "EMPTY-PRIVATE-OUTPUT-DIRECTORY"
```

## 验证范围

1. 目标 Azure 订阅已启用，所需资源提供程序和 `OpenAI.ContextCacheAllowed` 功能均已注册。
2. 官方源码与固定 commit、origin 及全部 25 个执行输入的 SHA-256 一致。
3. 与官方字节完全一致的 Quickstart 部署了 Context Cache 账户、容器、已关联的 Azure OpenAI 部署和数据面角色。
4. 运行器独立核对部署状态、模型版本、容器绑定、提供程序和 TTL。
5. 六条 Responses API 调用记录均被采集并独立复算；缺行、错误、零阈值和缓存证据不足都会立即失败。

运行器不负责登录、不注册 Preview 功能、不回退到 API key、不编造缓存结果，也不自动删除 Azure 资源。

## 架构

![官方执行路径](images/architecture.svg)

Azure 负责 Private Preview 资源；官方上游负责部署和示例行为；本仓库负责源码核验、受约束的编排、证据采集和独立验算。

## 证据与审计追溯

方法由三层相互独立的证据组成：

| 层 | 权威来源 | 证据 |
|---|---|---|
| 源码身份 | Azure 官方 Git 仓库 | 固定 commit、origin 和 Git blob 内容的 SHA-256 校验值；忽略外部工作树字节 |
| Azure control plane（控制面） | Azure Resource Manager | 资源提供程序和功能前置检查，以及部署、AOAI 模型、缓存容器 ID、提供程序和 TTL 绑定 |
| Azure data plane（数据面） | 官方 Responses API 示例 | 六条调用记录、cached tokens 和失败即拒绝阈值 |

详见 [方法与证据链](docs/METHOD-CN.md)、[公共证据边界](evidence/README.md)、[脱敏运行摘要](evidence/verified-run-summary.json) 和 [验证历史](evidence/validation-history.json)。公共证据不包含云资源标识和私有原始日志。

## 本次运行明细

![脱敏后的验证观测](images/verified-observation.svg)

第 1 次调用的 `cached_tokens = 0`；第 2 至第 6 次调用均返回 `2304` 个 cached tokens。重新计算得到后五次调用的平均延迟为 `3642.4 ms`，第 1 次调用为 `5820 ms`；在这一个环境中的观测比值为 `1.597848x`。

这些延迟只描述当次运行。更具持续证据价值的能力信号是已验证的部署绑定和非零 `cached_tokens`。没有单独的受控基准测试和当前有效价格来源时，不应外推该比值或推导成本收益。

两次完整运行通过。后续两次运行分别出现 3 个和 4 个传输错误，因此被拒绝。被拒绝的运行保留在验证历史中，不会被计为缓存结果。

## 验证设计与边界

| 范围 | 真实发生的行为 | 边界 |
|---|---|---|
| `scripts/run_official_e2e.ps1` | 读取 Azure 实时状态，调用已验证的官方 Quickstart，创建真实 Azure 资源并发送真实 Responses API 请求 | 需要 Preview 准入及已认证、相互隔离的 Azure CLI 配置目录 |
| `scripts/verify_upstream.py` | 核对 commit、origin 和全部 25 个执行输入，再将精确的 Git blob 字节写入私有运行目录 | 外部工作树不会被执行 |
| `scripts/parse_demo_output.py` | 重新计算调用数、缓存命中、cached tokens 和延迟字段 | 错误、缺行、零阈值、零延迟或预热后命中不足均立即失败 |
| `scripts/validate_arm_summary.py` | 跨三个 ARM 资源核对部署成功状态和模型/缓存绑定 | 缺字段、失败状态或绑定不一致均立即失败 |
| `tests/fixtures/` | 确定性覆盖成功与失败分支 | 合成测试数据不会进入实时运行路径 |

## 仓库结构

| 路径 | 用途 |
|---|---|
| `UPSTREAM_LOCK.json` | 固定官方 commit 和全部 25 个执行输入的 Git blob 内容 SHA-256 校验值 |
| `requirements-live-win-py311.lock` | 固定 Windows AMD64 CPython 3.11 wheel 版本及产物 SHA-256 |
| `scripts/run_official_e2e.ps1` | 围绕未修改官方 Quickstart 的实时编排 |
| `scripts/verify_upstream.py` | 跨平台源码身份校验器 |
| `scripts/parse_demo_output.py` | 独立运行记录解析器和缓存验证门 |
| `scripts/validate_arm_summary.py` | 独立 ARM 部署和资源绑定验证门 |
| `scripts/demo_code_validator.py` | 实时路径的静态真实性检查 |
| `scripts/audit_public_content.py` | 按实际值识别的公共边界扫描器 |
| `scripts/validate_repo.py` | 确定性仓库质量门 |
| `tests/` | 解析器、来源追溯、运行器、扫描器和验证器测试 |
| `evidence/` | 脱敏观测和证据清单 |
| `images/` | 架构图和实测观测图 |

## 安全与清理

- 禁止把凭据、Azure CLI 缓存、终结点、资源 ID 或实时运行原始日志写入本仓库。扫描器同时拒绝符号链接、重解析点、不支持的公共文件格式，以及常见 token、SAS 和连接字符串形式。
- 每个项目使用独立 `AZURE_CONFIG_DIR`；运行器拒绝隐式共享配置，也拒绝把工作目录放入公共源码树。
- 本地验证使用 Azure CLI user authentication。长期运行的服务应选择合适的 managed identity 或 service principal。
- 运行器要求使用全新资源组，并故意不自动清理。执行任何删除前，应先检查上游 `scripts/cleanup.ps1`、生成的 `run-contract.json`、私有 `manifest.json` 和目标资源组。
- 删除是独立的显式操作。如果使用已有 Azure OpenAI account，在确认其所有权之前不得运行 cleanup。

安全问题和运维说明见 [SECURITY.md](SECURITY.md)。

## 当前限制

- 这是 Private Preview 验证工具，不是可用性或生产就绪保证。
- 上游 API 版本、模型版本、区域、配额和准入流程都可能变化。
- 单次运行无法证明延迟分布、并发保证或成本节省。
- 缓存命中可能随运行变化。默认验证门要求 5 次预热后调用至少命中 3 次，且阈值不能为零；只有明确修改验收合同后才应调整。
- 当前验证工具面向上游 Windows PowerShell Quickstart。
- 实时依赖锁明确限定为已实测的 Windows AMD64 CPython 3.11 运行环境。
- 固定 commit 未提供 license file。公共子目录不签入上游源码；运行器会从已验证 Git blob 创建临时私有执行副本。

## 参考资料

- [Azure/AzureContextCache](https://github.com/Azure/AzureContextCache)
- [固定的 upstream commit](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
- [Azure OpenAI prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)
- [Azure CLI configuration isolation](https://learn.microsoft.com/cli/azure/azure-cli-configuration)
- [ATTRIBUTION.md](ATTRIBUTION.md)

维护者：魏新宇