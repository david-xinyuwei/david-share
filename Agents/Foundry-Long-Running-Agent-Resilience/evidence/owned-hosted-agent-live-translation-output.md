# Completed long-running translation output

- Agent version: `7`
- Elapsed: `89.199` seconds
- Response SHA-256: `cfc1b7056cf1f2e8bb6fe4587405fc099d89c39b79b31fb90fc44f0be5519e09`
- Entry modes: `['fresh', 'recovered']`
- Process instances: `2`
- Terminal status: `completed`

> This is verbatim Azure Translator output captured to prove recovery and result completeness. It is not a human-edited translation or a language-quality evaluation.

| Section | English source | Chinese result |
|---:|---|---|
| 1 | A long-running agent should give each logical job a stable identity that outlives any one process. The caller stores that identity before reporting success upstream. | 一个长期运行的代理应为每个逻辑作业赋予一个稳定的身份，使其寿命超过任何一个进程。呼叫者在报告成功前会先存储该身份。 |
| 2 | Background execution and crash recovery solve different problems. Background execution survives a disconnected caller, while recovery survives the loss of the process that owns the work. | 后台执行和崩溃恢复解决了不同的问题。后台执行能在断线调用者中存活，而恢复则能承受失去拥有该工作的进程。 |
| 3 | A durable checkpoint marks completed business progress. It must be written only after the corresponding output or application state is complete and safe to replay. | 一个持久的检查点标志完成了业务进展。必须在相应输出或应用状态完成且安全可重放后才写入。 |
| 4 | Recovery starts a new process with empty memory. The handler receives the original persisted input and uses a saved response snapshot or application checkpoint to find its resume point. | 恢复启动一个新的进程，内存为空。处理器接收原始持久输入，并使用保存的响应快照或应用检查点找到其恢复点。 |
| 5 | The client must reconnect to the original response instead of creating replacement work. A timeout or temporary not-found response is not permission to duplicate the job. | 客户必须重新连接到原始响应，而不是创建替代工作。超时或临时未找到响应并不等同于重复该作业的许可。 |
| 6 | External operations require idempotency. Payments, bookings, email sends, and writes can be repeated after a crash unless the application records a stable operation key. | 外部操作需要幂等性。除非应用程序记录稳定的操作密钥，否则支付、预订、发送邮件和写入在崩溃后可能会重复。 |
| 7 | A terminal event alone is not enough evidence. Acceptance should also verify output completeness, stable work identity, checkpoint continuity, and the expected business result. | 仅凭绝症不足以证明。验收还应验证输出完整性、工作身份稳定、检查点连续性及预期业务结果。 |
| 8 | The platform preserves task metadata and leases, but the application owns domain state. Large artifacts and workflow state normally belong in application storage or a framework checkpointer. | 平台保留任务元数据和租赁，但应用拥有域状态。大型工件和工作流状态通常应存储在应用存储或框架检查点中。 |
| 9 | A recovered handler can safely skip work committed before the last checkpoint. Work performed after that boundary may run again and must therefore be replay safe. | 恢复的操作员可以在最后一个检查点之前安全跳过已完成的工作。该边界之后的工作可能会重复，因此必须是安全的重打。 |
| 10 | Operational evidence should include timestamps, process identities, status transitions, code hashes, and logs. Screenshots prove deployed objects but do not prove recovery behavior. | 操作证据应包括时间戳、进程身份、状态转换、代码哈希和日志。截图能证明已部署的对象，但不能证明恢复行为。 |
| 11 | Graceful shutdown and hard process loss are different interruption modes. Each mode needs its own trigger, expected result, observed result, and explicit PASS or NOT VERIFIED status. | 优雅关机和硬进程丢失是不同的中断模式。每种模式都需要自己的触发条件、预期结果、观察到的结果，以及显式的通过或未验证状态。 |
| 12 | Production confidence requires repeated trials, workload-specific deadlines, load tests, and side-effect reconciliation. A single successful demonstration proves capability, not reliability. | 生产置信度需要反复试验、针对工作负载的截止日期、负载测试以及副作用对账。一次成功的演示证明的是能力，而非可靠性。 |
