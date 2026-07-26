# GPT-5.4 Managed Runtime 证据

本目录保存 GPT-5.4 / Agent v6 的脱敏验证摘要。

- `runtime-validation.json`：带日期的 Prompt Agent、模型部署、Toolbox、Agentic Identity、Responses 和最小权限 RBAC 契约。
- `dual-input-validation.json`：两份内容显著不同的真实 Streaming 运行，包含 Response ID Hash，以及不同的 Analysis、PNG、PPTX 和 EML Hash。
- `ui-validation.json`：Windows ARM64 Node 与 Edge 验证，以及真实 Playwright 桌面端/移动端结果。
- `large-input-recovery-validation.json`：2026-07-25 大输入故障、容量修正、SSE 详细错误透传修复及 API/浏览器恢复结果。

证据不包含 Endpoint、Tenant、Subscription、Identity GUID、原始 Token、本机绝对路径或客户数据。这是带日期的功能证据，不是生产认证，也不是模型质量 Benchmark。
