# 架构取舍（Trade-offs）

每个架构决策都有代价。这份文档把"hosted agent + toolbox"形态的取舍明示出来，让你决定哪些代价能接受、哪些不能。

参考来源：

- Hosted Agents concept: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- Toolbox how-to: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox
- Foundry pricing: https://azure.microsoft.com/pricing/details/foundry-agent-service/

## 三个力

Agent 系统和任何分布式系统一样，要平衡三种力：

- **Governance**：对 auth / audit / approval / version / policy 的中心化控制。
- **Latency**：caller 请求到第一个有用 token 的墙钟时间。
- **Flexibility**：新 tool / 新 agent / 新 framework 接入的便利度。

通常只能同时优化两个。这套架构选了 **Governance + Flexibility**，代价是 **Latency**。

| 架构 | Governance | Latency | Flexibility |
| --- | :---: | :---: | :---: |
| App 直接调 model | 低 | 最佳 | 低 |
| App + in-process tools（仅 function calling） | 低 | 好 | 中 |
| App + 私有 MCP server | 中 | 好 | 中 |
| **Hosted Agent + Toolbox MCP（本 repo）** | **高** | **可接受** | **高** |
| Hosted Agent + 裸 MCP server（无 toolbox） | 中 | 好 | 高 |

如果你的场景在加粗行左边，你在为不需要的 governance 付费。如果在右边，你在为不需要的 flexibility 付费。

## 取舍 1：Latency vs Governance

每一层都加一跳：

| 跳 | 成本 | 原因 |
| --- | --- | --- |
| Caller → Hosted Agent endpoint | TLS + ingress 路由 | 提供稳定 endpoint 和 per-agent identity 的必要代价。 |
| Hosted Agent container | 冷启动可见（首次 idle 后请求） | Per-session sandbox 按需启动；warm 路径跳过。 |
| Hosted Agent → Foundry model | Model inference（占主导） | 与直接调 model 一样，无额外开销。 |
| Hosted Agent → Toolbox MCP | 一次 MCP round-trip（`tools/list` 缓存，`tools/call` per use） | 受管 tool execution 的必要代价。 |
| Hosted Agent → Responses API web search | 一次 HTTP round-trip + Bing grounding | 公开网页 grounding + 引用的必要代价。 |

任何非 trivial 生成场景下，model call 占总延迟主导。Toolbox 跳加常数；冷启动是唯一可观测的 trade-off。缓解：

- 每个活跃会话保留一个 warm session（Hosted Agents 15 分钟 idle timeout，再回收）。
- 稳态用 consumer endpoint（缓存 `default_version`），canary 测试用 version endpoint。
- 跳过 `prompts/list`：MCP client 设 `load_prompts=False`（Toolbox docs troubleshooting）。
- 用 streaming `tools/call`（文档明确说 non-streaming 不支持，会返回 500）。

## 取舍 2：Governance vs Flexibility

高 governance 倾向"全部经过 catalog + 审批"；高 flexibility 倾向"agent 自由选 tool"。Toolbox 用 per-tool `require_approval` 解决（Toolbox docs Step 4）：

- `require_approval = "never"`：agent 自由调；适合只读 tool 和 code interpreter。
- `require_approval = "always"`：agent 必须把待执行的 action 呈给用户、等确认；适合写操作、资金流动、不可逆变更。

MCP endpoint **不会** 因为 `require_approval` 阻塞 `tools/call` —— enforcement 是 agent runtime 的责任。Toolbox 在 `tools/list` 里把 `_meta.tool_configuration.require_approval` 暴露出来；agent 读它，构建 approval map，gate 调用。这把取舍放到合适的地方：tool owner 决定 gate，agent runtime 一致地强制。

## 取舍 3：Flexibility vs 运维成本

加一个 hosted agent 和一个 toolbox 引入运维面：

| 面 | 增加什么 |
| --- | --- |
| Foundry project | 资源图节点、RBAC scope、区域放置。 |
| Toolbox versions | 生命周期（创建、测试、promote、deprecate）。 |
| Hosted Agent versions | Container image 生命周期、ACR 存储、idle session 计费。 |
| Connections | 每个外部服务一个 Foundry connection 带 credential。 |

Pricing（preview）：Managed hosting runtime 按 active session 的 CPU/memory 计费；session idle 15 分钟回收（Hosted Agents docs, Pricing）。和"自建 ACA service + 独立 tool registry + 独立 identity wiring"对比 —— 一旦 agent 或 tool 数量上来，运维成本天平倾向 managed。

## 取舍 4：Preview 稳定性 vs 现代能力

Hosted Agents 和 Toolbox 都在 public preview。取舍：

| 你接受 | 你得到 |
| --- | --- |
| Preview SLA 限制、可能的 breaking change、区域可用性 gap | Agent + tool model 的第一方受管表面、官方 sample、持续演进的 feature set |

本 repo 编码进的缓解：

- 所有 preview header 显式（`Foundry-Features: Toolboxes=V1Preview`）。
- 双 web-search 路径（Toolbox MCP listing + direct Responses API runtime）吸收最显眼的 preview gap。
- Region 矩阵和 tool-by-region 可用性从 toolbox 文档链出；生产 rollout 应固定到全部所需 tool type 都支持的 region。

## 取舍 5：Managed Identity vs 本地开发速度

Hosted agent 用部署时创建的 Microsoft Entra ID 跑。本地通常用 `AzureCliCredential` 让多 tenant 机器选对 subscription。同一份代码走 `DefaultAzureCredential` 在两种环境都能跑：

| 环境 | Credential | 原因 |
| --- | --- | --- |
| 本地（多 tenant 机器） | `AzureCliCredential`（`AZURE_AUTH_MODE=cli`） | 避免 `DefaultAzureCredential` 选错 tenant。 |
| Hosted Agent | 默认链 → agent 的 Entra ID | RBAC 由 `azd deploy` 预接；无需处理密钥。 |

启动时强制 credential 让本地错误显式；hosted runtime 默认让生产无密钥。

## 决策速查

| 现象 | 可能错的选择 | 正确调整 |
| --- | --- | --- |
| 冷启动延迟不可接受 | 把 hosted agent 当纯请求-响应用 | 每会话保留 warm session；用户 idle 时预热 |
| 跨团队 tool 名冲突 | 一个 toolbox 装所有 | 按业务域多 toolbox；每个团队 own 自己的 |
| Tool 频繁 breaking change | 太激进 promote `default_version` | Stage with version endpoint → canary → promote |
| Auth 复杂度蔓延到 agent 代码 | 为"简单"绕过 toolbox 直调 | 把 auth 放到 toolbox 后面的 Foundry connection |
| Approval 弹窗困扰用户 | 读写 tool 混着没设 `require_approval` | 每个写 tool 设 `require_approval=always`；让 agent 弹确认 |

## 底线

你付一个常数跳和一个小管理面。你买到：

- 稳定、带身份的 agent endpoint，跨计算迁移依然在线。
- 版本化、中心化的 tool catalog，带显式 approval gate。
- 自由切换 agent framework、增加 tool 而不需要重新部署 client。

如果这三点你都不需要，你就不需要这套架构。
