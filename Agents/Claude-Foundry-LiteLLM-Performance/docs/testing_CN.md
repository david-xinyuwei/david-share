# 复测与核验

[README](../README_CN.md) · [实测结果](results_CN.md) · [English](testing.md)

## 离线核验

不需要 Azure 或模型密钥；Python 标准库即可。

```powershell
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

预期旧证据核验为 50 条记录、10 个配置，生成产物一致，单元测试通过。没有 PowerShell 7 时运行器测试会显示 skipped，不算该路径已通过。负例使用内存或隔离测试副本：改 token、thinking、问题、计时，移除 trace、重复 call ID 或截断流；不修改原始证据。合成 SSE 和测试传输替身仅验证采集/分析逻辑，不作为新的模型性能证据。

## 实际调用的验收

主部署、日志采集和新运行命令统一在 README 第 1–6 步。run_matrix.ps1 保存原始响应；analyze.py --run-directory 必须同时给出 --trace-file，并按 x-litellm-call-id 核对出站模型、thinking、effort、stream、max_tokens 和缓存断点。它读取指定目录的 matrix.json、run.json、冻结采集器和 ACA_HTTP_*.json，重建 SSE、累计 usage 和完整历史；不会回退到已发布证据。日志缺失时失败，原 run.json 保持待审计状态。

trace 输入支持观察器原始 JSON/JSONL、控制台 CLAUDE_PROVIDER_TRACE 文本和 Azure CLI 的 Log 字段 JSONL；重复的完全相同日志会合并，同一 call ID 内容冲突则失败。其他运行的日志数量单独报告；不会拿它们补齐当前请求。analysis.json 和 analysis.md 是同一目录的派生输出，重新分析只更新它们；--check 不写文件。私有文件中的真实签名用于本次核验，不写入 Markdown 报告。

必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。首轮缓存状态按 usage 判断，不凭新会话 ID 判冷。

输入缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)。输出吞吐 = output_tokens/E2E；另列减去 thinking 的可见输出吞吐。nearest-rank 分位方法不插值，N=5 时 P95=max。

## 安全、支持与未验证项

真实输入、模型回答、签名及认证信息可能敏感。live-runs 与 .env 已忽略；不要上传运行目录。公开证据的签名已省略，call ID 已假名化，因此不能拿公开证据的历史重放签名；新运行必须使用自己的真实响应。

Opus 5.5 不支持 disabled。Sonnet 5.5 使用 between_tools，Haiku 5.5 使用 disabled，且这两种模式仅接受 low/medium/high。temperature、top_p、top_k 不作为本轮可调项；未验证的服务端工具或 beta 参数不加入默认配置。

公开采集器只去除了作者认证入口和资源默认值，测量循环保持与实测版本一致。它的语法、离线请求及数据测试已验证；公开包装的独立新部署未执行，没有录制公开视频，也没有客户桌面客户端验收。

部署命令的官方依据（2026-10-25 查阅）:
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)
