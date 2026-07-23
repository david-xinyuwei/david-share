# 场景证据 Runbook

这些 Runbook 只定义可观察的验收证据，不是部署配方；Private package、endpoint、identity 与 raw payload 均不公开。

## Invocations Research

**输入形态：** 一个会展开成 18 个文档 phase 的 research topic。

**私有执行链路：** 接受 durable work → controlled crash 前生成 checkpoint → 当前连接中断 → 重连原逻辑任务 → 观察 recovery → 接收 phase 1–18 → terminal `done=completed`，并以正常 run completion 结束。

**公开 PASS 字段：** checkpoint、injected failure、connection drop、recovery marker、phase count 18、completed state 与 terminal reason。

## Responses Research

**输入形态：** 一个包含 18 个 output item 的 stored background response。

**私有执行链路：** 创建 stored background work → 持久化第一个 item → 注入故障 → 重连同一个 response → 从第一个未 checkpoint 的 item 继续 → 最终包含 index 0–17，共 18 个 item，并进入 completed。

Python reconnect 暴露了 lifecycle reset marker；.NET reconnect 在该 cursor 位置没有重放相同 marker。因此，跨 runtime 更强的不变量是 same-response output continuity 加 completed final snapshot。

## LangGraph Human Approval

**输入形态：** 在敏感动作前暂停的 tool-using graph。

**私有执行链路：** 到达 approval interrupt → 持久化 pending approval → 替换当前进程 → 提交一次 decision → graph 只恢复一次 → 观察 approval 后 confirmation 与 terminal result。

该场景证明 durable graph state 与 exactly-once decision handling，不代表真实 airline、hotel、payment 或 reservation-system transaction。

## Durable Workflow

**输入形态：** 三阶段翻译 workflow：English → French → Spanish → English。

**私有执行链路：** 生成并持久化每个 stage output → 跨 temporary host replacement 继续 → 原 response 进入 completed → 验证最终 round-trip output。

该 pattern 不使用 Research 的 failure/reconnect assertion set；它证明 durable stage state 与 terminal workflow output。

## Active-turn Steering

**输入形态：** 第一轮仍 active 时提交 materially different 的第二轮输入。

**私有执行链路：** 第二轮进入 queue → 第一轮协作结束 → queued turn 在同一 conversation 上开始 → 新输入得到相关的 completed answer。

该 pattern 证明 steering，不证明 crash recovery。第二轮如果返回常量或无关答案，场景即失败。

## Observer 裁决

Workload 已经完成后，observer 仍可能失败。Campaign 的一条路径中，final read 使用了过期 observer token；刷新 observer authentication 并只重试读取后，得到 completed snapshot。该过程没有重跑 workload，也没有把认证失败改判为 workload failure。

## Evidence 公开方式

Raw event 保留在私有边界。公开 record 包含：

- 精确 scenario contract；
- 作者证明的执行结果；
- 保留的私有 source artifact 数量；
- 由其 SHA-256 值生成的 commitment；
- 不包含私有文件名、endpoint、ID、payload text 或 credential。

Commitment 可用于后续 private-to-public drift check，但公开读者无法据此还原或独立认证私有 run。
