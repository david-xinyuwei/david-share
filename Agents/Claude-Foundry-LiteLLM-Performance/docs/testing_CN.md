# 复测与核验

[README](../README_CN.md) · [Results](results_CN.md) · [Other language](testing.md)

## 离线核验

不需要 Azure 或模型密钥；Python 标准库即可。

```powershell
python scripts/analyze.py --check
python scripts/render_docs.py --check
python -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

预期 50 条记录、10 个配置，全部检查通过。测试会故意改动副本中的 token、thinking、问题和计时，确认校验器拒绝；不会改原始证据。

## 实际调用的验收

部署和运行命令只有 README 一份。新运行使用新目录，正常结束仅代表调用完成；还需读取网关 CLAUDE_PROVIDER_TRACE 日志，把每个响应的 x-litellm-call-id 对上模型、thinking、effort、stream、max_tokens 与 cache_control。无对应日志时只能标记参数透传未验证。

必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。首轮缓存状态按 usage 判断，不凭新会话 ID 判冷。

输入缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)。输出吞吐 = output_tokens/E2E；另列减去 thinking 的可见输出吞吐。nearest-rank 分位方法不插值，N=5 时 P95=max。

## 安全、支持与未验证项

真实输入、模型回答、签名及认证信息可能敏感。live-runs 与 .env 已忽略；不要上传运行目录。公开证据的签名已省略，call ID 已假名化，因此不能拿公开证据的历史重放签名；新运行必须使用自己的真实响应。

Opus 5.5 不支持 disabled。Sonnet 5.5 使用 between_tools，Haiku 5.5 使用 disabled，且这两种模式仅接受 low/medium/high。temperature、top_p、top_k 不作为本轮可调项；未验证的服务端工具或 beta 参数不加入默认配置。

公开采集器只去除了作者认证入口和资源默认值，测量循环保持与实测版本一致。它的语法、离线请求及数据测试已验证；公开包装的独立新部署未执行，没有录制公开视频，也没有客户桌面客户端验收。
