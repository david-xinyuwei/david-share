# 失败模式与证据裁决

| 失败模式 | 容易得出的错误结论 | 正确处理 |
|---|---|---|
| Agent version 为 active | “长任务场景已经通过。” | 必须跑完 checkpoint、failure、recovery 和 terminal completion。 |
| Stream 文件达到 byte cap | “任务只执行到最后捕获的 phase。” | 按截断文件处理；查询 durable state 或重新保存完整 stream。 |
| 最终读取时 observer token 过期 | “Workload 因 403 失败。” | 分开 observer authentication 与 workload state；刷新 token 后执行只读终态查询。 |
| 某个 runtime 没在 cursor 位置重放另一个 SDK 的 reset event | “没有发生 recovery。” | 检查同一任务引用、output index 连续性、reconnect cursor 和 terminal completion。 |
| Approval 被解释两次 | “Approve 变成了 deny。” | 明确 approval decision 由 hosting adapter 还是 graph 负责，只执行一次契约。 |
| 忘记 background mode | “Stored response durability 不工作。” | 确认请求确实选择了协议所需的 background/stored lifecycle。 |
| Durable task/storage preview onboarding 缺失 | “必须开启某个无关 resource provider feature。” | 区分 service-side allowlisting 与客户可配置的 control-plane registration。Agent version active 不代表该路径已启用。 |
| Inline shell quoting 破坏请求 | “服务拒绝了 API payload。” | 使用 structured client 或 file-backed request，并保存原始 HTTP response。 |

## 裁决规则

可观察的 workload continuity 优先于某个 SDK 的 event 名。只有 raw event order、durable state、final snapshot 或 deterministic validator 能支撑 finding 时，才接受该结论。

Observer authentication 必须与 workload state 分开裁决。如果 workload 已发出 terminal evidence，而后续只读 final query 因 observer auth 失败，应刷新 observer authentication 并只重试读取；不要重跑 workload，也不要把 authentication failure 静默改判成 workload failure。
