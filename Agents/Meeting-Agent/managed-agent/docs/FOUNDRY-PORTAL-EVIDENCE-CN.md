# Foundry Portal 实证

**中文** | [English](FOUNDRY-PORTAL-EVIDENCE.md) | [Managed 实现](MANAGED-IMPLEMENTATION-CN.md) | [产品首页](../../README-CN.md)

本页解释 Microsoft Foundry Portal 如何呈现一套独立的 West US 2 Private Preview Managed Meeting Agent 验证环境。截图拍摄于 2026-07-28，进入 Repo 前已脱敏：Project、Agent、Endpoint、Subscription、Tenant、Account 和浏览器 Profile 标识均被移除。

这些截图补充产品首页中的本机浏览器工作区，证明云端 Agent、Toolbox、版本化 Skill 与内置 Hand/Sandbox 路径在 Foundry 中真实可见并能够执行。它们不代表生产 SLA，也不能替代版本化 API Export 对精确配置的权威记录。

## 1. Agent 资源与 Managed Harness

Agents 列表在不暴露资源名称的前提下，显示了三个产品事实：Agent 处于 **Running** 状态，类型为 **prompt**，Harness 为 **GitHub Copilot**。

<div align="center">
<img src="../images/foundry-portal/agent-list.png" width="960" alt="脱敏 Foundry Agent 列表：Running Prompt Agent 与 GitHub Copilot Harness">
</div>

Playground 显示选中的模型与 Agent Instructions。Toolbox Endpoint 和资源名称已主动遮罩。此处证明 Portal Authoring Surface（编写界面）真实存在；Immutable Version（不可变版本）的精确字段仍以实时 Agent API Export 为准。

<div align="center">
<img src="../images/foundry-portal/agent-playground.png" width="800" alt="脱敏 Foundry Playground：模型与 Agent Instructions">
</div>

## 2. Toolbox 是受治理的 MCP Surface

Toolbox 页面显示 Web Search 和会议输出 Skill。Toolbox 是版本化 Foundry 资源，通过 MCP Endpoint 向 Agent 暴露 Tool 与 Skill Resource；Toolbox 不是 Hand Sandbox。

<div align="center">
<img src="../images/foundry-portal/toolbox-skills.png" width="500" alt="脱敏 Foundry Toolbox：Web Search 与会议输出 Skill">
</div>

该截图是 Portal Observation（界面观测），不是完整 Inventory Contract（清单契约）。精确成员必须按 Toolbox Version，通过 API 或 MCP `resources/list` 验证。当前 Repo 把三个会议输出职责拆开：

| Skill | 职责 | Renderer 边界 |
|---|---|---|
| `meeting-package` | Summary、Topic、Decision、Action 和 Open Question | 不负责思维导图或 Slide 渲染 |
| `mind-map-story` | 证据约束的 Semantic Tree（语义树） | 不选择坐标、颜色或文件格式 |
| `presentation-story` | 严格六段 `DeckPlan` | 不生成 PPTX Shape 或文件 |

## 3. Portal 中的版本化 Skill 源码

Portal 可以显示某个 Toolbox Version 实际解析到的 Immutable `SKILL.md`。

### 会议分析

<div align="center">
<img src="../images/foundry-portal/skill-meeting-package-version-drift.png" width="800" alt="Foundry Portal 中较早版本的 meeting-package Skill">
</div>

这张图还有一项重要价值：它暴露了 Version Drift（版本漂移）。截图中的旧云端 Skill 描述仍提到 concise mind map，而最新 Repo Source 已把 Semantic Tree 职责移交给 `mind-map-story`。因此，不能拿一张 Portal 截图直接证明云端与源码完全一致。正确验收方式是 Reconcile 并重新发布 Toolbox，再通过版本化 API 校验 Skill 正文或 Hash。

### 思维导图语义

<div align="center">
<img src="../images/foundry-portal/skill-mind-map-story.png" width="800" alt="Foundry Portal 中的 mind-map-story Skill">
</div>

`mind-map-story` 负责证据选择、层级、分支边界和简洁节点文案。本机确定性 Renderer 负责 Mermaid 语法、SVG/PNG、几何、换行和颜色。

### 六页故事线

<div align="center">
<img src="../images/foundry-portal/skill-presentation-story.png" width="800" alt="Foundry Portal 中的 presentation-story Skill">
</div>

`presentation-story` 生成严格六段 `DeckPlan`；本机 Renderer 与内置模板继续负责可编辑 PPTX。

## 4. 内置 Hand/Sandbox 实测

Managed Agent Definition 不包含客户手工配置的 Sandbox Tool、CPU、Memory、Image 或 Runtime 字段。选择 Managed GHCP Harness 后，运行时会获得内置 Hand 执行 Tool；当模型调用 Bash、Shell、Code Execution 或文件操作时，平台才按需启动 Sandbox Compute。

下面这次 Portal 运行要求 Agent 检查文件系统和计算容量。该 Session 返回 19 GB Root Filesystem、2 个可见 CPU Core 与 4 GB Memory。

<div align="center">
<img src="../images/foundry-portal/hand-sandbox-capacity.png" width="960" alt="Foundry Portal Hand Sandbox 文件系统、CPU 与内存实测">
</div>

另一条 Fail-Closed Probe（失败即停止探针）交叉验证了 Linux x86_64、2 个可见 Processor、约 4.07 GiB 总内存、Debian 12、Python 3.13.14，以及 `/workspace` 工作目录。详见[脱敏 Runtime Observation](../evidence/managed-live-westus2/sandbox-runtime-observation.json)。

这些数字只是单次 Session Observation，不是不可变 Sandbox Profile、Agent Version 保证、Quota 或 SLA。当前 Portal 与 Agent Definition 没有暴露版本化 Sandbox Profile、Image Digest、Runtime Package Inventory、cgroup Limit 或 Sandbox Session Lifecycle。若工作负载要求确定的 CPU/Memory 规格或客户自定义 Python/.NET Image，应选择 Hosted Agent 或直接管理 ACA Sandbox。

## 截图证明什么，不能证明什么

| 声明 | 状态 | 证据边界 |
|---|---|---|
| Prompt Agent 运行在 Managed GitHub Copilot Harness | 已证明 | Agents 列表与实时 Agent API |
| Toolbox 暴露版本化 Tool 与 Skill | 已证明 | Toolbox 页面与 API/MCP 验证 |
| Meeting、Mind Map、Presentation 职责已拆分 | 当前源码已证明；Portal Version 仍需 Reconcile | Skill 页面与 Repo 契约 |
| 内置 Hand 执行了文件系统和容量命令 | 对该次 Session 已证明 | Portal 输出与独立 Fail-Closed Probe |
| 以后每个 Sandbox 都是 2 CPU / 4 GB | **未证明** | 平台未暴露版本化 Sandbox Runtime Contract |
| Hand Sandbox 是客户在 Toolbox 中配置的 Tool | **错误** | 实时 Agent Definition 只有 Toolbox MCP Connection |

这里也暴露了当前产品缺口：Portal 能证明 Hand 执行发生过，却没有提供客户可审计的 Runtime Profile，包括 CPU、Memory、OS Image、语言版本、Lifecycle、Persistence 和 Drift。任何生产就绪讨论都必须保留这项限制。
