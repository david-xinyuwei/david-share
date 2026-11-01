# 验证说明：组件精度与资源复算

[English](VALIDATION.md) · [主文档](README_CN.md) · [数据](data/model-evidence.json)

## 验证什么

本项目的可执行工具只读取公开元数据或重放已经保存的元数据，计算张量数据负载。它不运行模型、不申请 GPU、不决定生产卡数，不输出吞吐或质量分数。

两个采集时间分别为：模型 API 元数据 `2026-11-01T12:49:24.528Z`；原厂 NVFP4 配置摘要 `2026-11-01T12:51:18.489Z`。时间使用 UTC。数据文件保留了模型 ID、固定 revision、实际读取状态和范围；来源发布者与原始模型开发者是不同维度。

## 复算与测试

环境：Node.js 20+，不需要 npm 包。Shell 可以是 PowerShell 或 Bash，工作目录是本专题目录。也可以从其他目录通过绝对路径启动脚本；数据路径相对于脚本解析，不依赖当前目录。

```bash
node tools/inspect.mjs
node --test tests/inspect.test.mjs
```

第一条成功时输出 JSON，`result_type` 为 `CALCULATED_FROM_PUBLIC_METADATA`，模型推理状态始终为 `NOT_RUN`。`tensor_payload_bytes` 是各 dtype 元素数乘以其存储字节数后求和；GB 用十进制，GiB 用二进制。它不包括 safetensors 文件头、其他文件、KV/状态缓存、运行工作区和通信缓冲。

第二条运行八项测试：模型版本覆盖及九列双语主表/本地链接一致性、U8 打包字节而非逻辑参数量、六行负载复算、Muse 401 保留、Nemotron router 排除、未知 dtype 拒绝、新 revision 不继承旧配置结论、联网失败不回退成旧数据成功。测试中的 HTTP 返回对象是单元测试桩，不是在线模型证据。

## 新数据而非旧快照

```bash
node tools/inspect.mjs --live
```

这会重新调用六个模型的公开 API。检查返回的 `capture_utc` 与 `revision`，然后比较张量负载。该模式明确清空旧配置摘要，因为它没有重新检查大体积量化配置。遇到 HTTP 错误、未知 dtype 或身份变化时退出失败；不得把旧数据改为当前结果。

不需要也不应为此工具提供模型下载凭据。Muse 原始量化配置的访问限制是单独的已知缺口，不能通过其他账号或镜像绕过。

## 需要保留的异常

Nemotron BF16 的 API `safetensors.total` 与逐 dtype 元素数之和并不一致。工具同时报告两者及 `metadata_total_matches=false`，使用逐 dtype 计数计算字节，不悄悄修改源数据。压缩 checkpoint 的 `U8` 和 scale 张量元素数也不是原始逻辑参数量。

## 模型上线验收

从[主文档的步骤](README_CN.md#先选可验证路径再启动服务)选择该模型自己的官方配方。实际执行时必须记录权重 SHA、引擎提交/镜像摘要、GPU、并行拓扑、内核选择、K/V 与其他状态精度、请求原文和结果。BF16、FP8、NVFP4 使用相同真实业务任务；未跑的组合保持 `NOT_RUN`，不得借其他模型的结果补齐。

必须覆盖质量、结构化输出、工具调用、所需模态、长上下文、目标并发、峰值显存和持续运行。结果按实际观测记录，不把正常加载当成业务成功，不把低比特存储当成原生低比特计算。

## 当前验证状态

| 验证项 | 状态与边界 |
|---|---|
| 公开模型身份与六个固定 revision | 已读取 API；未下载权重 |
| 原厂 NVFP4 配置 | Nemotron 与 Inkling 已解析；Muse 返回 401，未解析 |
| 文件诊断 | 已执行编辑器检查；不等于 Node 测试通过 |
| Node 测试与 CLI | 已执行：8 项通过、0 项失败；包含最新九列表/双语来源/链接断言及六行字节复算 |
| 页面预览 | 已检查四页、1280/390 像素宽度；主表各 25 行内容与九个版本列，图片/锚点无缺失、无页面级溢出；不代表 GitHub 线上验收 |
| 模型推理、性能与生产稳定性 | NOT_RUN |
| 独立中文与双语语义审查 | PASS：只读独立复核完成；英文未核实状态的一类歧义已修正并独立复验 |
| GitHub 发布与线上页面 | 以本专题的公开提交及检查结果为准；本地预览不替代线上验收 |

未执行的检查不能标为通过。公开来源、原理分析与可执行工具分别有自己的验收边界。

独立文本复核覆盖四份双语文档、组件矩阵与数据/图像来源摘要，并定点检查引用来源；它没有执行模型、复跑性能测试或证明尚未核实的组件精度。`AI_NATIVE_CHINESE_AUDIT=PASS`、`AI_BILINGUAL_SEMANTIC_AUDIT=PASS` 只描述本次文本审查结果。

## 重建文档预览

使用 PowerShell 7 的内置 `ConvertFrom-Markdown`，无需安装 npm 包；浏览器渲染 Mermaid 和 KaTeX 时需要访问脚本中固定版本的公共 CDN。从本专题目录执行：

```powershell
./tools/preview.ps1 -OutputDirectory "$env:TEMP/large-moe-guide-preview"
```

同一个入口生成四页并记录源文件与 HTML 的 SHA-256。表格保留全部列，窄屏通过表格内横向滚动查看，不将主表裁成精选行。官方图的来源、尺寸与 SHA-256 见 [visual-evidence.json](data/visual-evidence.json)。预览不替代 GitHub 线上页面或独立双语语义复审。

## 后续 GPU 验证

本轮先完成文档与工具。MI300X 上的 BF16 验证留到环境检查之后，不属于上述八项测试；必须另行确认目标 VM、可用显存、ROCm/引擎版本、权重访问、请求输入和资源使用边界。任何后续实测都在本专题中补充，不另建平行结论页。