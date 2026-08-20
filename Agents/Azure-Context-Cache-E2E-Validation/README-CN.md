# Azure Context Cache 客户评估

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/azure-context-cache-e2e-validation-ci.yml)
[![CPython 3.11 AMD64](https://img.shields.io/badge/CPython-3.11%20AMD64-3776AB)](https://www.python.org/)
[![PowerShell 7+](https://img.shields.io/badge/PowerShell-7%2B-5391FE)](https://learn.microsoft.com/powershell/)
[![Upstream pin](https://img.shields.io/badge/AzureContextCache-7d1029a5-247A45)](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)

[英文版](README.md) | [源码](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Azure-Context-Cache-E2E-Validation) | [官方上游](https://github.com/Azure/AzureContextCache)

本仓库用于评估 Azure OpenAI 的显式上下文缓存能力，面向需要重复使用系统指令、工具定义、示例或参考资料的应用。

**已经证明：** 在获准使用 Private Preview 的订阅中，固定版本的官方 Quickstart 可以成功部署。已绑定缓存的 Azure OpenAI deployment 成功调用 Azure 数据面，并返回非零 `cached_tokens`。
**尚未证明：** 该方案已经生产就绪，或能够保证延迟和成本收益。现有数据也无法判断命中来自 Context Cache，还是模型默认的 prompt caching。

## 先看结论

| 客户要回答的问题 | 当前答案 |
|---|---|
| 是否值得评估？ | 如果应用会重复发送较长且稳定的前缀，并需要明确控制缓存生命周期、资源所有权和访问权限，值得评估 |
| 实测看到了什么？ | 6 次官方 Demo 调用全部完成；首次调用后，`5/5` 次请求命中，每次报告 `2304` 个 cached tokens |
| 哪些收益还不能承诺？ | 不能把本次结果解释为生产 SLA、确定的成本节省，或 Context Cache 相比默认 prompt caching 的增量命中率 |
| 下一步做什么？ | 先确认订阅已获 Preview 准入，再检查权限、配额和区域支持；条件满足后，按本仓库脚本在客户环境中运行官方 E2E，并用真实 prompt 验证命中率 |

## 适用场景

| 评估结论 | 工作负载模式 | 建议 |
|---|---|---|
| **建议评估** | 长系统/开发者指令、稳定工具目录、少样本示例或共享政策 | 把可复用内容放在前部，把变化的任务数据放在末尾 |
| **建议评估** | 客户支持、代码/合规审查、文档密集型助手和受控智能体工作流 | 规则、工具或参考资料会跨请求重复使用时进入评估 |
| **满足条件后评估** | 早期对话历史保持稳定、后续内容仅追加的多轮对话 | 验证早期前缀能否保持字节完全一致 |
| **暂不优先** | 短提示词，或请求前部频繁变化 | 可复用前缀有限，通常不应优先投入 |
| **暂不优先** | 一次性请求，或每次请求开头都是高度个性化内容 | 缓存命中率通常较低 |
| **满足条件后评估** | 需要承诺精确成本节省或吞吐提升的业务场景 | 使用客户数据单独做基准测试，并按当前价格建模 |

## 实测结果

![官方 demo 六次调用的输入处理复用占比与延迟变化](images/verified-observation.svg)

| 信号 | 计算口径 | 实测结果 | 客户应如何理解 |
|---|---:|---:|---|
| 缓存命中 | 首次调用后的 5 次请求 | `5/5` 次命中 | deployment 与 container 的绑定确实为重复前缀提供了缓存 |
| 输入处理复用 | 预热后 `11,520 / 13,037` 个输入 token | 总输入的 `88.4%` 被报告为 cached；单次为 `85.9%–90.7%` | 大部分重复输入处理转为 cache read；这不等于账单降低 88.4% |
| 延迟变化 | 首次调用 `5820 ms`；预热后均值 `3642.4 ms` | 本次运行降低 `2177.6 ms`（`37.4%`） | 只说明值得继续验证；单次运行无法反映性能分布，也不构成 SLA |
| 输入 token 成本 | 5 次预热后调用每次 `2304` cached tokens | 合计读取 `11,520` 个 cached token | 需要结合客户命中率和当前模型、区域定价计算；本仓库不声称具体金额 |
| 输出行为 | `6/6` 次 Responses API 调用 | 全部返回正常模型输出和 usage telemetry | Prompt caching 复用输入处理，不改变应用预期的响应契约 |

本次 E2E 使用已获 Private Preview 准入的 Azure 订阅，并将官方 Quickstart 固定到 commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a`。后续两次不完整运行均被拒绝，没有折算成通过。

> **证据边界：** 这是单次运行的能力观测，不代表生产就绪，也不保证可用性、成本、吞吐或延迟。通用 Azure OpenAI prompt caching 指南会因模型家族和 API 接口而不同；本仓库验证的是 Private Preview 的 `Microsoft.Storage/contextCaches` 和 `contextCacheContainerId` 路径。

## 客户问题与业务价值

这类应用会在每次请求中重复发送同一段稳定前缀。没有缓存时，服务需要反复执行 tokenization 和 prefill。

Azure Context Cache 允许客户在自己的订阅和区域中部署具名缓存容器，再将其绑定到 Azure OpenAI deployment。第一次匹配请求会写入前缀处理结果；后续请求可以在设定的生命周期内复用。应用仍然发送完整前缀，缓存查询由 deployment 自动完成。

因此，它提供的是**跨请求的 prompt 处理复用**，不是文档存储，也不是语义检索。

| 收益维度 | 官方资料给出的机制 | 客户可以怎么验证 |
|---|---|---|
| 请求延迟 | 命中的前缀跳过重新 tokenization 和 prefill | 在客户自己的提示词组合和并发条件下测量延迟分布 |
| 输入 token 成本 | 缓存读取按折扣后的输入 token 价格计费 | 结合 `cached_tokens`、实际命中率和当前 Azure 定价计算 |
| 容量效率 | 省下的 prefill 算力可以在同等容量下支撑更多并发 | 在目标负载下执行受控吞吐测试 |
| 跨请求复用 | 具名缓存容器可以在配置的生命周期内跨调用复用符合条件的前缀处理结果 | 通过已绑定 deployment 重复发送字节一致的前缀，并监控 `cached_tokens` |
| 治理 | 具名缓存资源部署在客户订阅、区域和 RBAC 边界内，并配置 TTL | 核对目标区域是否受支持，以及访问控制、生命周期和数据要求 |

> [固定版本的官方 Quickstart](https://github.com/Azure/AzureContextCache/tree/7d1029a5e8b59b1805e70992c85ffe6798d2f47a) 将这些列为产品价值。本仓库只证明缓存已在一个获准环境中实际生效，不对上述收益做量化承诺。

## 收益到底是什么

### 省的是什么

应用仍会在每次请求中发送完整前缀。Context Cache 节省的是服务端对这段前缀的**重复处理**，并不会减少客户端发送的数据量。

固定版本的官方资料说明，服务会保存稳定前缀经过 tokenization 和 pre-attention（预先完成注意力计算）后的中间表示。后续请求只要以相同内容开头，就可以复用这份结果。因此，可能改善的是延迟、输入 token 成本和容量效率。

收益取决于两个条件：前缀足够长，而且足够稳定。可复用前缀很短，或前部字节频繁变化时，即使启用缓存，收益也会很有限。

### 已经有默认 prompt caching，为什么还要它

Azure OpenAI 对支持的模型**默认启用** [prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)。因此，客户自然会问：既然已有默认缓存，为什么还要部署 Context Cache？

固定版本的官方资料给出的核心区别是：默认缓存由服务隐式管理，是否命中不由客户控制；Context Cache 则由客户显式配置。客户创建具名容器，将其绑定到 deployment，并控制缓存生命周期。

| 维度 | 默认 prompt caching（隐式） | Azure Context Cache（显式） |
|---|---|---|
| 性质 | 尽力而为，机会性命中 | 契约式：由客户部署并绑定的具名资源 |
| 生效门槛 | 至少 1,024 token，且前 1,024 token 必须完全一致 | 同样的前缀匹配约定，通过已绑定的容器表达 |
| 生命周期控制 | 由服务管理，按请求选择保留策略 | 客户在自己拥有的资源上设置容器 `timeToLive` |
| 驻留与隔离 | 由服务管理；prompt 缓存不跨 Azure 订阅共享 | 缓存账户与容器位于客户的订阅、区域和 RBAC 边界内 |
| 治理能力 | 不是可检查的资源 | 一个可审计、可改绑、可轮换、可解绑的 ARM 资源 |
| 客户端改造 | 无需 | 无需；只在 deployment 上设置 `properties.contextCacheContainerId` |

这张表说明的是**生命周期和控制权**，不是命中率。对于持续重复出现的前缀，默认缓存可能已经足够。

当客户需要自己拥有、检查和治理缓存资源，并明确控制复用窗口、数据驻留和生命周期时，Context Cache 才体现出差异。

公开文档给出的默认缓存保留时间可以作为参照：

- 内存态缓存通常在空闲 5 到 10 分钟后清除，最晚在最后一次使用后一小时内释放。
- 对于支持的模型，扩展保留最长可到 24 小时。

Context Cache 的容器生命周期可以按天设置，而且由客户显式声明，无需根据服务行为猜测。

### 容器生命周期最长能设多久

这里需要区分三个事实：

| 陈述 | 状态 | 依据 |
|---|---|---|
| 固定版本 Quickstart 交付的容器生命周期是 `7` 天 | **已验证** | `timeToLive` 声明在模板的 `variables` 块中，且实际部署出的容器回读到同一个值 |
| 这个值本来就是让客户改的 | **已验证** | 官方自定义指引把客户直接指向同一个 variables 块修改 TTL，模板既没有 allowed-value 列表也没有最大值约束 |
| 某个具体天数是资源提供程序接受的上限 | **未验证** | 固定版本仓库、ARM 模板和 Bicep 模块都没有公布上限，本次验证也没有做这方面的测试 |

因此，`7` 天只是**默认值，不是上限**。如果客户需要更长的保留时间，应向 Microsoft 产品团队确认支持范围，或通过一次显式部署测试验证。不能把 `7` 天写成产品限制。

### 客户可以自己算的收益模型

本仓库不直接给出金额，因为结果取决于模型、区域、部署类型和流量形态。客户可以用下面的公式估算：

```text
每次命中省下的全价输入 token = cached_tokens
每月省下的输入 token       = cached_tokens × 命中率 × 月请求数
每月输入 token 成本        = 未命中输入 token × 输入单价
                           + 缓存读取 token   × 折扣后输入单价
```

以本次观测为例，每次预热后调用报告 `2304` 个 cached tokens。假设某个工作负载每月对同一前缀发起 `100,000` 次请求，并保持相同命中率，那么每月约有 2.3 亿（`230` million）个输入 token 从全价处理转为折扣缓存读取。

金额还需要根据目标模型、区域和部署类型的当前公开价格计算。Standard 与 Provisioned 的缓存读取折扣不同，因此不能使用统一换算系数。

| 变量 | 对收益的影响 | 验证方法 |
|---|---|---|
| 稳定前缀长度 | 低于生效门槛就没有任何可复用内容，而官方指引把更大的节省与更长的稳定前缀直接关联 | 对真实的系统提示词、工具目录、护栏规则和固定参考资料做 tokenize |
| 前缀字节稳定性 | 前部只要有一个字符变化就会 miss | 在真实生产流量样本上 diff 拼装后的前缀，包括序列化方式和字段顺序 |
| 请求间隔与缓存生命周期的关系 | 决定下一次匹配请求到达时，前缀是否仍在缓存中 | 按相同前缀分组统计请求间隔，而不是只看全局请求速率 |

把这三个变量组合起来，就得到实际的决策矩阵：

| 流量形态 | 默认 prompt cache 的表现 | Context Cache 额外带来什么 |
|---|---|---|
| 匹配前缀持续到达，间隔在秒级到几分钟 | 大概率已由默认缓存命中 | 资源归属、数据驻留、显式 TTL 和可审计资源 |
| 匹配前缀之间存在几十分钟到数小时的间隔 | 内存态保留会在空闲后被释放 | 一个由客户设定而非推测的复用窗口 |
| 匹配前缀按天、按周或按计划批次复用 | 超出扩展保留的上限 | 增量收益最强的场景：以天为单位的容器生命周期 |

应优先用客户真实流量验证后两类场景。如果前缀始终达不到生效门槛，问题在提示词布局，而不在缓存配置。下文的**工作负载适配**给出了对应建议。

## 客户业务架构

![Azure Context Cache 客户应用业务架构](images/customer-architecture.svg)

1. 客户应用把可复用的指令、工具、示例和共享资料放入稳定前缀。
2. 每次变化的用户任务和案例数据追加为动态后缀。
3. 应用继续调用 Azure OpenAI Responses API；已关联的部署会在 Context Cache 容器中查找匹配前缀。
4. 应用通过 `cached_tokens`、延迟和请求结果验证真实业务流量是否适配。

Context Cache 容器是客户订阅中的 Azure 资源。锁定的 Private Preview Quickstart 配置缓存账户、模型专属容器、TTL 和 `contextCacheContainerId` 绑定。

## 客户评估路径

### 前提条件

- Windows 上的 PowerShell 7（`pwsh`）、Git、Azure CLI，以及 AMD64 Windows 上的 64 位 CPython 3.11
- 已获得 Azure Context Cache Private Preview 权限的 Azure 订阅
- `OpenAI.ContextCacheAllowed` 已达到 `Registered`
- 已通过租户允许的用户认证流登录独立 `AZURE_CONFIG_DIR`
- 具备部署资源和分配 `Cognitive Services OpenAI User` 的权限
- 在受支持的区域具备可用模型配额

正式运行会创建计费 Azure 资源并发送模型请求。请使用全新的资源组和唯一名称前缀。检查生成的证据后，再单独决定是否清理资源。

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

先使用 `-WhatIf`。它只执行有超时上限的 Azure 只读前置检查，不克隆源码、不部署资源，也不发送模型请求。

正式运行要求使用全新的资源组。运行器会在源码树之外创建私有证据目录，但不会自动清理 Azure 资源。网络受限时，可以用 `-ExistingUpstreamDirectory` 指向固定 commit 的本地检出副本。来源控制详见[方法与证据链](docs/METHOD-CN.md)。

### 本地验证

```powershell
python -m unittest discover -s tests -v
python scripts\demo_code_validator.py
python scripts\audit_public_content.py
python scripts\validate_repo.py
```

这些检查不需要访问 Azure。还可以用现有的固定 commit 检出副本核对上游源码锁：

```powershell
python scripts\verify_upstream.py `
  --upstream-dir "PATH-TO-AzureContextCache" `
  --lock .\UPSTREAM_LOCK.json `
  --output "EMPTY-PRIVATE-OUTPUT-DIRECTORY"
```

## 数据从哪里来，缓存实际存在哪里

### 已验证路径的资源拓扑

这里的 `Microsoft.Storage` **不是**普通 Azure Storage account（存储账户）或 Blob container（Blob 容器）。固定版本的 Private Preview 会创建专用的 `Microsoft.Storage/contextCaches` 资源及其模型专属子容器。应用不会把 prompt 预先上传到 Blob Storage，也不会直接调用缓存资源。

| 对象 | 已验证路径中的位置 | 精确契约 | 存放或执行的内容 |
|---|---|---|---|
| 请求前的稳定来源 | 官方 Quickstart 的私有本地副本 | `demo/system_prompt.md` | 约 2.4K token 的代码审查指令；每次调用保持字节完全一致 |
| 请求前的变化来源 | 同一个 Quickstart 私有副本 | `demo/diffs/*.diff` | 每次调用在稳定 system prompt 之后追加一个不同的 PR diff |
| Azure OpenAI 账户 | 已开通的私有订阅、新建验证资源组、`centralus` | `Microsoft.CognitiveServices/accounts/<name-prefix>-aoai` | 承载 Azure OpenAI endpoint |
| Azure OpenAI 部署 | Azure OpenAI 账户的子资源 | `deployments/context-cache-deployment`，模型 `gpt-5.4`，版本 `2026-03-05-contextcache` | 接收 Responses API 请求，并配置 `properties.contextCacheContainerId` |
| Context Cache 账户 | 同一订阅、资源组和区域 | `Microsoft.Storage/contextCaches/<name-prefix>-cache`，`accountKind = Regional` | 客户通过 Azure RBAC 管理的缓存命名空间 |
| Context Cache 容器 | Context Cache 账户的子资源 | `contextCacheContainers/default-container`，provider `OpenAI`，模型 `gpt-5.4`，`timeToLive = 7` 天 | 由服务托管的存储单元，存放可复用的前缀处理结果 |

可检查的 ARM resource ID（资源 ID）为：

```text
/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/contextCaches/<name-prefix>-cache/contextCacheContainers/default-container
```

按 README 示例使用 `-NamePrefix ccvalidate` 时，缓存资源是 `ccvalidate-cache/default-container`，与它绑定的 Azure OpenAI 部署是 `ccvalidate-aoai/context-cache-deployment`。公共 Repo 有意隐去实际验证订阅、资源组和名称前缀；本次运行已确认资源位于私有订阅中一个新建的 `centralus` 资源组。

官方资料把缓存内容描述为稳定前缀经过 tokenization 和 pre-attention 后的表示。它不是客户可寻址的文件、Blob URL 或 Blob object。上面的 resource ID 是公开的 control-plane（控制面）边界；服务内部的物理存储布局不属于本次验证的范围。

### 端到端数据流

| 步骤 | 所在位置 | 实际发生的动作 | 可观察结果 |
|---:|---|---|---|
| 1 | 本地 Quickstart 私有副本 | Python 读取 `system_prompt.md` 和一个 `.diff` 文件 | 客户端不做任何预上传，因此此时 Azure 中不存在该前缀的缓存内容 |
| 2 | 客户应用 → Azure OpenAI | 把稳定 system prompt 放在请求前部，把变化的 diff 放在末尾，组成一次 Responses API 请求 | 普通的 `POST /openai/v1/responses` 调用 |
| 3 | 已绑定缓存的 Azure OpenAI 部署 | `contextCacheContainerId` 让 deployment 透明查询 `default-container` | 应用始终只调用 Azure OpenAI，不需要单独的缓存 SDK 调用 |
| 4 | 第一次请求：cache miss | Azure OpenAI 完整处理请求，服务把可复用的稳定前缀处理结果写入已绑定容器 | 第 1 次调用返回 `cached_tokens = 0` |
| 5 | 后续请求：cache hit | 字节完全一致的前缀直接复用；末尾不同的 PR diff 仍按本次请求处理 | 第 2–6 次调用均返回 `cached_tokens = 2304` |
| 6 | Azure OpenAI → 客户应用 | 正常返回模型结果和 usage telemetry（用量遥测） | `usage.input_tokens_details.cached_tokens`、输出 token、延迟和状态 |

固定样例同时使用两个不同的保留设置：Context Cache 容器配置 `timeToLive = 7` 天，而每个 gpt-5.4 请求设置 `prompt_cache_retention = "24h"`。两者都来自官方样例，但不是同一个设置。本仓库验证了它们的配置值，不从这两个值推断服务内部的存储分层。

### 应用如何调用

下面保留了固定官方 Demo 的核心调用路径。请求中不需要出现 cache account 或 container，因为 Azure OpenAI deployment 已经预先与它们绑定。

```python
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential

endpoint = "https://YOUR-AOAI-ACCOUNT.openai.azure.com"
deployment = "context-cache-deployment"
stable_prefix = Path("demo/system_prompt.md").read_text(encoding="utf-8")
diff_name = "01-sql-injection.diff"
dynamic_suffix = Path(f"demo/diffs/{diff_name}").read_text(encoding="utf-8")

token = DefaultAzureCredential(
  exclude_interactive_browser_credential=False
).get_token("https://cognitiveservices.azure.com/.default").token

payload = {
  "model": deployment,
  "input": [
    {
      "type": "message",
      "role": "system",
      "content": [{"type": "input_text", "text": stable_prefix}],
    },
    {
      "type": "message",
      "role": "user",
      "content": [{
        "type": "input_text",
        "text": f"Review this PR diff:\n\nFile: {diff_name}\n\n{dynamic_suffix}",
      }],
    },
  ],
  "max_output_tokens": 200,
  "prompt_cache_retention": "24h",
}

response = httpx.post(
  f"{endpoint}/openai/v1/responses?api-version=preview",
  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
  json=payload,
  timeout=240,
)
response.raise_for_status()
result = response.json()
print(result.get("output_text") or result.get("output"))
print(result["usage"]["input_tokens_details"]["cached_tokens"])
```

生产应用沿用同一个原则：把长期复用的指令、工具、政策、示例或参考资料放在前部，把当前用户输入或案例数据追加到末尾，并持续监控每次响应中的 `cached_tokens`。

### 在客户环境中找到这些资源

使用运行器接收的同一个资源组和 `-NamePrefix`。以下命令可以找到逻辑缓存资源并证明 deployment 绑定，不会输出任何秘密：

```powershell
$subscriptionId = "YOUR-SUBSCRIPTION-ID"
$resourceGroup = "YOUR-RESOURCE-GROUP"
$namePrefix = "YOUR-NAME-PREFIX"

az resource list --subscription $subscriptionId --resource-group $resourceGroup `
  --query "[?contains(type, 'contextCaches') || type=='Microsoft.CognitiveServices/accounts/deployments'].{name:name,type:type,location:location}" `
  -o table

$containerId = az resource show --subscription $subscriptionId `
  --resource-group $resourceGroup `
  --resource-type "Microsoft.Storage/contextCaches/contextCacheContainers" `
  --name "${namePrefix}-cache/default-container" `
  --api-version "2026-01-01-preview" --query id -o tsv

az resource show --subscription $subscriptionId `
  --resource-group $resourceGroup `
  --resource-type "Microsoft.CognitiveServices/accounts/deployments" `
  --name "${namePrefix}-aoai/context-cache-deployment" `
  --api-version "2026-03-15-preview" `
  --query "{deployment:name,model:properties.model,contextCacheContainerId:properties.contextCacheContainerId}" `
  -o json

Write-Output "Expected container: $containerId"
```

返回的 `properties.contextCacheContainerId` 必须与 `$containerId` 完全相同。在 Azure Portal 中，同一批资源位于验证资源组内，分别属于 Azure OpenAI 账户和 `Microsoft.Storage/contextCaches` 资源类型；这里没有可供浏览的普通 Blob container。

## 是否必须使用 RAG

**不需要。** Azure Context Cache 和 RAG 解决的是两个不同问题：

| 能力 | 首要问题 | 存储内容 | 应用如何使用 |
|---|---|---|---|
| 基于 Azure AI Search 的 RAG | “这次问题需要哪些客户知识？” | Search index 或 knowledge source 中的原始文档、chunks、metadata 和 embeddings | 应用或 Agent 针对每个问题显式检索排名靠前的结果，再把它们加入 prompt |
| Azure Context Cache | “已经提供过的哪些 prompt 前缀不必从头处理？” | 具名 Context Cache 容器中由服务管理的、经过 tokenization 和 pre-attention 处理后的稳定前缀表示 | 应用发送正常模型请求；已绑定的 deployment 自动匹配并复用前缀 |

Context Cache 不能替代文档摄取、chunking、embedding、vector/hybrid search、relevance ranking、引用、内容新鲜度或文档级授权。它不是 vector database，也不会检索语义相似内容。

### 如何与客户 RAG 应用组合

```mermaid
flowchart LR
  Docs[企业文档] --> Ingest[切分 + 富化 + 向量化]
  Ingest --> Index[Azure AI Search index<br/>chunks + metadata + vectors]
  Query[本次用户问题] --> Retrieve[向量 / 关键词 / Hybrid retrieval]
  Index --> Retrieve
  Retrieve --> Dynamic[动态后缀<br/>top-N chunks + 本次问题]
  Stable[稳定前缀<br/>system 指令 + tool schemas<br/>guardrails + 输出契约] --> Prompt[组装 Prompt]
  Dynamic --> Prompt
  Prompt --> AOAI[已绑定缓存的 Azure OpenAI deployment]
  AOAI <--> Cache[Context Cache container<br/>已处理的稳定前缀]
  AOAI --> Answer[有依据的回答 + 引用来源<br/>cached_tokens telemetry]
```

高价值的 RAG 组合方式是：

1. 企业内容仍存放在权威数据源和 RAG index 中，并沿用原有治理方式。
2. 针对本次用户问题检索相关 chunks；这些结果通常每次都不同。
3. 把稳定的应用指令、tool schemas、安全政策、输出格式和真正固定的参考内容放在模型请求的**最前部**。
4. 把检索得到的 top-N chunks 和本次用户问题追加到**末尾**。
5. 把完整请求发送给已绑定缓存的 Azure OpenAI deployment，并监控 `cached_tokens`。

| RAG prompt 组成 | 缓存预期 | 原因 |
|---|---|---|
| System/developer 指令、工具定义、guardrails、响应 schema | **强候选** | 内容较长，并在大量请求中保持一致 |
| 每次请求都附带的固定产品手册或政策 | **字节一致且未超过 TTL 时可作为候选** | 相同的大段参考前缀会重复出现 |
| Vector/hybrid search 针对本次问题返回的 top-N chunks | **通常是动态内容** | 不同问题会返回不同 chunks 或排序 |
| 用户问题、对话尾部、当前案例数据 | **动态后缀** | 每次请求都会变化 |

因此，当 RAG 应用在每次检索调用外围都包含很长的稳定编排前缀时，Context Cache 会让业务价值更明显；但这不代表所有 RAG 检索结果都可以自动复用。只要 chunk 内容、顺序、security trimming（安全裁剪）结果或前部个性化内容发生变化，就可能无法命中相同前缀。

> **验证状态：** 当前发布的实跑 E2E 验证的是官方非 RAG Code Reviewer workload。上面的 RAG 组合是依据 Microsoft RAG 指南和官方 Context Cache 前缀契约形成的架构模式；本仓库尚未使用客户 Search index 对其进行 benchmark。

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
| 缓存契约 | 模型专属 Context Cache 容器、7 天 TTL，以及显式 `contextCacheContainerId` 绑定 |
| 请求模式 | 1 次预热请求，随后并行发送 5 次请求 |

本表描述的是经过脱敏的验证环境，不代表区域支持或生产容量建议。

### 测试步骤

1. **验证官方源码。** `scripts/verify_upstream.py` 解析固定 Git 对象，核对全部 25 个执行输入的 SHA-256，并且只把这些已验证字节写出到公共源码树之外。
2. **执行 Azure 只读前置检查。** `scripts/run_official_e2e.ps1 -WhatIf` 检查当前订阅、在线 ARM 读取、必要资源提供程序、受控 Preview 功能、运行时架构和目标区域前提条件；此步骤不部署资源，也不发送模型请求。
3. **部署官方 Quickstart。** 实跑运行器安装具有精确 hash 的 Windows AMD64 CPython 3.11 依赖，然后在私有运行目录中调用字节完全一致的官方 `scripts/quickstart.ps1 -SkipPython`。
4. **验证数据面。** 官方 Demo 先发送 1 次预热请求，再使用相同的稳定前缀并行发送 5 次 Responses API 请求。
5. **独立验证结果。** `scripts/parse_demo_output.py` 解析全部 6 条调用记录；缺行、传输错误、零阈值、零延迟或预热后命中不足都会失败。`scripts/validate_arm_summary.py` 独立核对部署成功状态、模型身份、缓存容器 ID、提供程序、TTL 和部署绑定。
6. **执行离线回归门。** 在发布 commit 上运行单元测试、真实性检查、公共内容审计、Repo gate、依赖检查、PowerShell 语法检查、CI 矩阵和 CodeQL。

### 测试脚本

| 脚本或测试集 | 在测试中的职责 | 失败即拒绝条件 |
|---|---|---|
| [`scripts/run_official_e2e.ps1`](scripts/run_official_e2e.ps1) | Azure 前置检查、已验证源码落盘、官方 Quickstart 执行、日志捕获和证据编排 | 配置目录复用、运行时不符、资源组已存在、Azure 超时/报错、官方进程非零退出或证据验证失败时立即停止 |
| [`scripts/verify_upstream.py`](scripts/verify_upstream.py) | 核对固定 Repo、commit 和 25 个 Git blob 的 SHA-256 | blob 缺失、不匹配或输出目录非空时拒绝执行 |
| [`scripts/parse_demo_output.py`](scripts/parse_demo_output.py) | 解析调用级延迟和 token 字段并计算缓存判定 | 传输错误、调用缺失/格式错误、零阈值/延迟或预热后命中不足时拒绝结果 |
| [`scripts/validate_arm_summary.py`](scripts/validate_arm_summary.py) | 交叉核对 ARM 部署状态以及 AOAI 与缓存的绑定 | 部署失败、字段缺失、模型/提供程序/TTL 错误或资源 ID 不一致时拒绝结果 |
| [`scripts/demo_code_validator.py`](scripts/demo_code_validator.py) | 确认验证器使用真实官方路径，而不是硬编码或 mock 结果 | 模拟产品行为或源码/运行时契约漂移时失败 |
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

被拒绝的运行保留在证据里，不删除，也不折算成通过。传输错误发生在调用完成之前，因此不产生缓存分数。

## 证据边界与验证方法

### 本次验证没有归因的部分

本次实测证明了两件事：绑定 `properties.contextCacheContainerId` 的 deployment 可以处理重复前缀；真实 Azure 数据面会返回非零 `cached_tokens`。

但现有数据**不能证明 Context Cache 相比默认 prompt caching 增加了多少命中**。原因是官方 demo 同时满足两个条件：

- 每次请求都设置了 `prompt_cache_retention`。
- 所用模型本身支持默认 prompt caching，与是否绑定 Context Cache 无关。

因此，两种缓存机制在本次验证中同时存在，无法拆分各自贡献。

准确的结论是：**显式缓存路径可用，资源归客户所有，命中结果可观测。** 现有证据不支持“Context Cache 比默认缓存带来更高命中率”。

要区分两者，需要受控对照实验。私有环境中的第一阶段实验发现，原始调用顺序会污染结果：

| 本环境中的观测 | 实测到的内容 |
|---|---|
| 同一账户中新建的第二个 deployment 未绑定容器，也从未调用过，但第一次请求就返回非零 `cached_tokens` | 3.759 秒前，绑定组刚用完全相同的前缀完成冷启动 |
| 随后每轮交替调用中，两个 deployment 的命中表现完全一致 | 绑定组始终先调用，在未绑定组测量前已经预热共享前缀 |

本次观测能支持的最窄结论是：**在这个环境中，同一 Azure OpenAI 账户下的两个 deployment 复用了前缀缓存状态。** 这只是单一环境的实测现象，不代表文档承诺的产品行为，也不能据此判断服务内部机制。

这带来两个直接影响：

1. 如果每轮都先调用绑定组，未绑定组会在测量前被预热。这样的实验无法判断未绑定组自身的缓存状态，因此前几个阶段不能用于计算增量命中率。
2. **不能假设同一账户下的不同 deployment 天然构成缓存隔离边界。** 如果业务需要隔离，必须单独验证，不能只根据部署拓扑推断。

修正后的实验会在决定结论的间隔档位先调用未绑定组，确保它在绑定组预热共享前缀之前完成首次测量：

| 要素 | 设计 |
|---|---|
| 对照组 | 同一账户、同一区域下，一个设置了 `contextCacheContainerId` 的部署与一个未设置的部署，模型与版本完全相同 |
| 提示词 | 两组使用完全字节一致的同一稳定前缀，以及同一组变化后缀 |
| 间隔档位 | 至少三档请求间隔：位于内存态窗口内、超出内存态但仍在扩展保留内、以及超出扩展保留 |
| 调用顺序 | 在决定结论的那一档间隔上先调用未绑定组，使其自身缓存状态在绑定组预热共享前缀之前被观测 |
| 指标 | 每组、每个间隔档位的命中率与 `cached_tokens`，重复足够次数以区分真实差异与运行间波动 |
| 报告方式 | 按组、按档位公布结果，包括两组无法区分的档位 |

在修正后的实验跨过扩展保留边界并完成之前，能够确认的差异仍只有生命周期、数据驻留和治理能力。增量命中率和成本节省均未得到证明。

方法由三层相互独立的证据组成：

| 层 | 权威来源 | 证据 |
|---|---|---|
| 源码身份 | Azure 官方 Git 仓库 | 固定 commit 和经过验证的执行输入 |
| Azure control plane（控制面） | Azure Resource Manager | 资源提供程序和功能前置检查，以及部署、AOAI 模型、缓存容器 ID、提供程序和 TTL 绑定 |
| Azure data plane（数据面） | 官方 Responses API 示例 | 六条调用记录、cached tokens 和失败即拒绝阈值 |

详见 [方法与证据链](docs/METHOD-CN.md)、[公共证据边界](evidence/README.md)、[脱敏运行摘要](evidence/verified-run-summary.json) 和 [验证历史](evidence/validation-history.json)。公共证据不包含云资源标识和私有原始日志。

## 安全与运维

- 禁止把凭据、Azure CLI 缓存、终结点、资源 ID 或实跑原始日志写入本仓库。扫描器同时拒绝符号链接、重解析点、不支持的公共文件格式，以及常见 token、SAS 和连接字符串形式。
- 每个项目使用独立 `AZURE_CONFIG_DIR`；运行器拒绝隐式共享配置，也拒绝把工作目录放入公共源码树。
- 本地验证通过 Azure CLI 使用用户身份认证。长期运行的服务应选择合适的托管身份或服务主体。
- 运行器要求使用全新资源组，并故意不自动清理。执行任何删除前，应先检查上游 `scripts/cleanup.ps1`、生成的 `run-contract.json`、私有 `manifest.json` 和目标资源组。
- 删除是独立的显式操作。如果使用已有 Azure OpenAI 账户，在确认其所有权之前不得运行清理脚本。

安全问题和运维说明见 [SECURITY.md](SECURITY.md)。

## 产品与证据限制

- 这是 Private Preview 验证工具，不是可用性或生产就绪保证。
- 上游 API 版本、模型版本、区域、配额和准入流程都可能变化。
- 单次运行无法证明延迟分布、并发保证或成本节省。
- 缓存命中可能随运行变化。默认验证门要求 5 次预热后调用至少命中 3 次，且阈值不能为零；只有明确修改验收契约后才应调整。
- 当前验证工具面向上游 Windows PowerShell Quickstart。
- 实跑依赖锁明确限定为已实测的 Windows AMD64 CPython 3.11 运行环境。
- 固定 commit 未提供 license file。该子树不签入任何上游源码；运行器会从已验证 Git blob 创建临时私有执行副本。

## 参考资料

- [Azure/AzureContextCache](https://github.com/Azure/AzureContextCache)
- [固定的上游 commit](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a)
- [Azure OpenAI prompt caching](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/prompt-caching)
- [OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Microsoft RAG 架构指南](https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide)
- [Azure AI Search 的 RAG 说明](https://learn.microsoft.com/azure/search/retrieval-augmented-generation-overview)
- [Azure CLI configuration isolation](https://learn.microsoft.com/cli/azure/azure-cli-configuration)
- [ATTRIBUTION.md](ATTRIBUTION.md)

维护者：魏新宇