# Managed Meeting Agent 功能等价矩阵

Classic实现保留在Repo根目录，固定基线为`david-xinyuwei/david-share@667357dac6ee2dc30102d572c458c77861112bea`。Managed实现位于同一个Repo的`managed-agent/`，替换模型运行时责任边界。

| 能力 | 早期实现 | Managed实现 | 验证 | 结论 |
|---|---|---|---|---|
| 事件契约 | 严格`MeetingEvent` Schema | `MeetingEvent`行为一致；Models模块额外定义可选`DeckPlan` | Model测试与有意差异Hash | 事件契约等价，Managed扩展有明确记录 |
| Session排序与幂等 | 排序、重复处理、冲突拒绝、仅使用最终转写、来源Hash | 文件SHA-256完全一致 | 模块Hash对比和Session测试 | 等价 |
| 转写与视觉输入 | Transcript TXT、ASR JSONL、Meeting JSON、视觉摘要 | Input Adapter SHA-256完全一致 | Node输入测试和浏览器E2E | 等价 |
| 结构化分析 | 使用GPT-5.4的本机AOAI Key认证客户端 | Foundry Managed Agent v6、GPT-5.4、GHCP、Entra、严格`MeetingAnalysis` JSON | Public源码部署、Agent Reference校验、两份真实差分输入、真实浏览器E2E | 运行时责任增强 |
| Skills | 模型请求中携带本机`SKILL.md` | 通过Toolbox MCP提供独立`meeting-package`与`presentation-story` Skill | v2/v6证据覆盖Meeting Skill；源码测试强制两个Skill Reference | 生命周期增强；双Skill Live验收等待新Agent Version |
| PowerPoint责任 | 本地Skill指导内容，确定性模板/Renderer生成文件 | `presentation-story`负责写作；严格`DeckPlan`、Deck/Style YAML与Template驱动确定性渲染 | Skill/Schema/Config/Renderer测试与可解析六页PPTX | Presentation Domain已在源码松耦合 |
| Streaming | 真实Responses文本Delta和完成阶段 | 真实Managed Responses SSE Delta和相同完成阶段 | 契约测试和真实浏览器Stream | 等价 |
| 思维导图 | JSON、Mermaid、SVG、PNG | 输出契约一致 | Pillow独立解析、Schema检查、桌面/移动端UI | 等价 |
| PowerPoint | 可编辑六页模板化PPTX | 相同OOXML模板字节，Managed路径使用OneDrive安全的`.zip`资源扩展名 | `python-pptx`独立解析，六页均有内容 | 等价 |
| 邮件草稿 | HTML/纯文本EML、内嵌导图、PNG/PPTX附件 | Draft模块SHA-256完全一致 | MIME解析：`X-Unsent: 1`、0收件人、2附件 | 等价 |
| Outlook交接 | 原子写入EML并启动`olk.exe` | Outlook模块SHA-256完全一致 | Node测试和no-send审计 | 等价 |
| 浏览器UI | React/Vite、loopback BFF、下载、富文本复制 | 相同用户流程，增加Managed运行时和Entra状态显示 | Vitest 18/18；契约Playwright桌面/移动端4/4；真实GPT-5.4桌面/移动端2/2 | 等价并增强透明度 |
| 产物安全 | 路径白名单和Canonical Path检查 | 相同BFF路径控制 | Node路径穿越和Symbolic Link测试 | 等价 |
| 邮件安全 | 不包含Graph、SMTP、EWS、`.Send`或Send按钮自动化 | 保持相同限制 | 静态no-send审计 | 等价 |
| 认证 | Backend进程使用AOAI API Key | Responses使用Entra Token，Toolbox使用`AgenticIdentityToken`；仅Agent Identity在Project Scope拥有`Foundry User` | 生产源码扫描、RBAC消融和真实v6调用 | 增强 |
| 显式持久文件系统 | 不依赖 | 不依赖，也不声明Preview持久化能力 | 架构与README边界 | 边界等价 |

当前Parity Manifest记录六个逐字节相等模块，以及两个带Baseline/Current Hash的有意差异：Models增加可选严格`DeckPlan`，Hosted Pipeline在渲染前处理v6兼容。Artifact与UI变化通过可执行契约验证，不冒充字节等价模块。

本矩阵证明功能契约等价，不要求两条编排路径输出完全相同的措辞，也不声称模型质量完全相同。两个实现当前都使用GPT-5.4，但运行时责任边界不同；验收依据是严格Schema、证据约束、产物、安全边界和用户流程，而不是逐字一致。