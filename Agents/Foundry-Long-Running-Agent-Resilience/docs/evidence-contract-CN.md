# 证据契约

## Public object model

每个提交到 Repo 的 scenario 都是作者证明的脱敏 record，包含九个必填字段：

| 字段 | 用途 |
|---|---|
| `id` | 稳定的公开 scenario 标识。 |
| `runtime` | `python` 或 `dotnet`。 |
| `protocol` | `responses` 或 `invocations`。 |
| `pattern` | Research、graph HITL、durable workflow 或 steering。 |
| `status` | 必须为 `passed`；失败过程保留在私有原始证据中，并作为经验总结。 |
| `source_kind` | 必须为 `author-attested-sanitized-run`。 |
| `provenance` | Author-attestation type、campaign date、private source count 与 private-source commitment。 |
| `assertions` | 与 pattern 对应的可观察不变量。 |
| `scope` | 必须限定为文档定义的 main scenario。 |

## 明确排除的字段

契约拒绝 credential、endpoint、subscription/tenant identifier、resource ID、private repo link、用户身份、session ID、response ID、invocation ID、VM 名称和 hostname。

Event summarizer 采用 allowlist，不依赖 denylist。它只保留 event type、phase、output index、status、total 和 sequence number 等协议字段，其他字段全部丢弃。

Summary 会保留有序 phase/index observation 与 sequence diagnostics。`monotonic` 只表示 nondecreasing order，不表示无 gap；必须分别检查 `gap_count`、`duplicate_count` 与 `strictly_increasing`。

## 完整性

`evidence/manifest.json` 为每个脱敏 run 和生成后的 matrix 保存相对路径、字节数与 SHA-256。`lra-evidence manifest` 遇到文件缺失、字节变化、digest 变化、重复路径、意外文件或路径逃逸时会直接失败。

每个 scenario 的 `private_source_commitment_sha256` 由保留的私有 artifact SHA-256 值生成。作者重新核验这些 artifact 时，它可以发现 private-source drift；它不会暴露 source file，也不会形成公开 execution chain of custody。

## 声明边界

Matrix 只证明八个文档定义的主场景。它不表示所有可选分支、所有模型、所有区域或所有生产拓扑都经过测试。

## Repo 表面分类

[scenario-manifest.json](../scenario-manifest.json) 区分四种含义：

- `dynamic-runtime`：输出由用户提供的 JSONL 实时计算，必须随 stream 改变。
- `architecture-explainer`：静态文档只解释方法，不是执行结果。
- `sanitized-runtime-attestation`：带 private-source commitment 的作者证明 campaign 结果。
- `test-fixture`：只放在 `tests/fixtures/` 的 synthetic parser input，绝不计入 campaign evidence。
