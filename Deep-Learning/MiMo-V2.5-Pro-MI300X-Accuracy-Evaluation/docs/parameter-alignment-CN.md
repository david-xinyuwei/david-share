# H200参考方法与AMD MI300X参数对齐

本文逐项映射H200参考启动方法与本次准确率快照使用的MI300X Runtime。“对齐”表示参数和值一致；“拓扑适配”和“后端替换”表示公开披露的差异，不会被静默视为等价。

## 摘要

- H200参考拓扑：TP16 / DP2 / EP16 / PP1，启用DP Attention和FA3。
- MI300X实测拓扑：两套独立服务，每套TP8 / DP1 / EP1 / PP1，使用AITER。
- FP8、page size、context length、请求上限、EAGLE控制项、parser、模型加载、metrics和histogram bucket均对齐。
- 两套MI300X服务互相独立，因此不设置跨节点参数。
- 准确率的采样与评分由evaluator定义，不因服务拓扑适配而改变。

## 启动参数矩阵

| # | H200参考设置 | MI300X实测设置 | 状态 | 原因 |
|---:|---|---|---|---|
| 1 | `python3 -m sglang.launch_server` | `python3 -u -m sglang.launch_server` | 等价 | `-u`只影响日志缓冲。 |
| 2 | 参考模型路径 | 本地MiMo-V2.5-Pro路径 | 环境适配 | 路径与部署环境相关，不公开内部位置。 |
| 3 | `--trust-remote-code` | 相同 | 对齐 | — |
| 4 | `--pp-size 1` | `--pp-size 1` | 对齐 | — |
| 5 | `--dp-size 2` | `--dp-size 1` | 拓扑适配 | 每台MI300X节点独立运行一套服务。 |
| 6 | `--ep-size 16` | `--ep-size 1` | 拓扑适配 | 本次稳定MI300X实测路径使用EP1。 |
| 7 | `--tp-size 16` | `--tp-size 8` | 拓扑适配 | 每套服务使用本机全部8张MI300X。 |
| 8 | `--moe-dense-tp-size 1` | 相同 | 对齐 | — |
| 9 | `--enable-dp-attention` | 未设置 | 不适用 | DP1不启用DP Attention。 |
| 10 | `--dist-init-addr ...` | 未设置 | 不适用 | 独立单节点服务不组成跨节点group。 |
| 11 | `--node-rank ...` | 未设置 | 不适用 | — |
| 12 | `--nnodes ...` | 未设置 | 不适用 | — |
| 13 | `--page-size 1` | 相同 | 对齐 | — |
| 14 | `--attention-backend fa3` | `--attention-backend aiter` | 后端替换 | FA3面向NVIDIA Hopper；MI300X使用AMD AITER。 |
| 15 | `--quantization fp8` | 相同 | 对齐 | — |
| 16 | `--mem-fraction-static 0.8` | 相同 | 对齐 | — |
| 17 | `--max-running-requests 128` | 相同 | 对齐 | — |
| 18 | `--context-length 1048576` | 相同 | 对齐 | — |
| 19 | `--tokenizer-worker-num 64` | 相同 | 对齐 | — |
| 20 | `--speculative-algorithm EAGLE` | 相同 | 对齐 | — |
| 21 | `--speculative-num-steps 3` | 相同 | 对齐 | — |
| 22 | `--speculative-eagle-topk 1` | 相同 | 对齐 | — |
| 23 | `--speculative-num-draft-tokens 4` | 相同 | 对齐 | — |
| 24 | `--enable-multi-layer-eagle` | 相同 | 对齐 | — |
| 25 | `--host 0.0.0.0` | 节点本地加速网络地址 | 网络适配 | 不公开内部地址。 |
| 26 | 参考端口 | 部署本地端口 | 网络适配 | 端口不改变采样与评分。 |
| 27 | `--reasoning-parser qwen3` | 相同 | 对齐 | — |
| 28 | `--tool-call-parser mimo` | 相同 | 对齐 | — |
| 29 | `--watchdog-timeout 3600` | 相同 | 对齐 | — |
| 30 | 多线程模型加载，64线程 | 相同 | 对齐 | — |
| 31 | `--log-level-http warning` | 相同 | 对齐 | — |
| 32 | `--enable-cache-report` | 相同 | 对齐 | 仅影响观测。 |
| 33 | `--collect-tokens-histogram` | 相同 | 对齐 | 仅影响观测。 |
| 34 | `--enable-metrics` | 相同 | 对齐 | 仅影响观测。 |
| 35 | TTFT bucket：`0.1 ... 7200` | 相同24项数列 | 对齐 | 仅影响观测。 |
| 36 | E2E latency bucket：`0.1 ... 7200` | 相同24项数列 | 对齐 | 仅影响观测。 |
| 37 | `--decode-log-interval 1` | 相同 | 对齐 | 仅影响观测。 |
| 38 | `--enable-metrics-for-all-schedulers` | 相同 | 对齐 | 仅影响观测。 |
| 39 | `SGLANG_ENABLE_SPEC_V2=1` | 相同 | 对齐 | 已在实测Runtime中验证。 |

## AMD Runtime控制项

| 控制项 | 值 | 用途 |
|---|---|---|
| `SGLANG_USE_AITER` | `1` | 启用AMD AITER kernel路径。 |
| `SGLANG_MOE_PADDING` | `1` | 启用本次实测的AMD MoE padding路径。 |
| `SGLANG_ROCM_FUSED_DECODE_MLA` | `1` | 启用ROCm fused decode MLA。 |
| `SGLANG_SET_CPU_AFFINITY` | `1` | 稳定进程放置。 |
| `HSA_NO_SCRATCH_RECLAIM` | `1` | 固定本次Runtime的HSA scratch行为。 |
| `SGLANG_SPEC_NAN_DETECTION` | `1` | speculative decoding出现NaN时失败关闭。 |
| `SGLANG_SPEC_OOB_DETECTION` | `1` | 检测speculative decoding越界。 |
| `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE` | `1` | 启用已验证的block-scale B-preshuffle路径。 |
| 模拟接受率变量 | 未设置 | 准确率测试使用EAGLE自然接受率。 |

## 可比性边界

该映射对齐模型、量化、采样合同、speculative decoding控制项、context length和评分路径，但不会把TP8/DP1/EP1/AITER解释为与TP16/DP2/EP16/FA3在性能或通信行为上等价。在双方都没有完整、匹配的原始输出前，准确率差异只能作为方向性观察。
