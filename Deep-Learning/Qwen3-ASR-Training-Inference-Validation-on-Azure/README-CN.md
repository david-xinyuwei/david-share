# 基于 Azure 的 Qwen3-ASR 训练与推理验证

> **Author**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

[English](README.md) | 中文版

[![Azure GPU](https://img.shields.io/badge/Azure-H100%20NVL-0078D4)](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/)
[![Qwen3-ASR](https://img.shields.io/badge/Model-Qwen3--ASR-7B68EE)](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
[![vLLM](https://img.shields.io/badge/Serving-vLLM-16A34A)](https://docs.vllm.ai/en/latest/models/supported_models/)
[![ASR](https://img.shields.io/badge/Workload-ASR%20Engineering-4B8BBE)](https://huggingface.co/tasks/automatic-speech-recognition)

面向自研 ASR 团队的 field guide 和 validation harness：Qwen/Gemma backbone + Hugging Face 训练 + vLLM/SGLang/TensorRT-LLM 高性能 serving。

## 在 Azure 上运行

这个 repo 不是一次性的 ASR demo，而是一条 **validation-first 的工程验证链路**：把客户自研 Qwen/Gemma 风格 ASR 路线，从 backbone 选择一路推到 serving、微调和生产验收决策。整个路径按顺序分成五步：

1. **Backbone smoke 和公开 CER** — 先证明 Qwen3-ASR 能加载、能转录、有 FLEURS baseline，再碰客户音频
2. **长音频和数据路径验证** — 优化训练前，先检查 chunking 风险、audio decode、dataloader wait、GPU transfer
3. **微调策略** — 用 before/after CER 对比 full-param SFT、LoRA、encoder-only、QLoRA 和精度稳定性
4. **Serving framework 选型** — 用原始 endpoint evidence 验证 vLLM transcription、CUDA Graph 和并发
5. **替代 backbone 和生产 gate** — 写清 Gemma 3n 前置条件、SGLang/TRT-LLM 边界和客户数据验收标准

本 public repo 里已完成的实验都使用公开音频样例或公开 FLEURS 数据。客户音频、私有 endpoint 和订阅信息不需要进入 public artifact。

![架构总览](images/solution_architecture.png)

---

## 核心成果

### 推荐路线

| 决策项 | 推荐 | 为什么重要 |
|---|---|---|
| **Backbone** | 纯 ASR 先用 Qwen3-ASR；Gemma 3n 作为 multimodal 候选路线保留 | Qwen3-ASR 已有 public CER 和 serving evidence；Gemma 3n 在本 repo 还需要 clean-env smoke 和 CER |
| **微调** | 第一轮先做 decoder LoRA；小数据不要直接 full-param SFT | LoRA 只改 0.78% 参数，在公开 FLEURS 检查中优于小样本 full-param run |
| **精度** | 先建立 FP32 稳定基线，再谈 mixed precision 或量化训练 | 本次 H100 实验中 bf16 SFT 从第一步开始出现 NaN gradients |
| **Serving** | Qwen3-ASR transcription serving 第一阶段用 vLLM | clean env 跑通，CUDA Graph 给出最强延迟结果 |
| **长音频** | 不要把完整会议录音当作一个请求直接丢给模型 | 180s synthetic long audio 输出坍缩；需要 VAD/chunk/overlap/stitching |

### 关键结论（验证条件）

以下结论来自 Azure H100 上的公开样例和公开 FLEURS 数据验证。

| 条件 | 值 |
|---|---|
| GPU | 1× Azure H100-class GPU，visible memory 95 GB |
| 模型 | `Qwen/Qwen3-ASR-0.6B`, `Qwen/Qwen3-ASR-1.7B`, `google/gemma-3n-E2B-it` route check |
| 公开 eval | FLEURS `cmn_hans_cn` test split；Qwen CER 使用 200 条样本 |
| Serving | Qwen3-ASR 的 vLLM transcription endpoint + transformers baseline |
| 公平性 | 同一批公开音频/eval split、同一 metric script；repo 不包含客户音频或私有 endpoint |

| 结论 | 实测结果 | 行动建议 |
|---|---|---|
| Qwen3-ASR public CER baseline 可用于 harness 验证 | 200 条 FLEURS 中文：0.6B=**7.74%**，1.7B=**7.09%** | 用作 public regression baseline，不当作客户域质量 |
| 小数据 full-param SFT 泛化风险高 | CER 从 **7.74%** 退化到 **21.53%** | 小数据不要从 full-param SFT 起步 |
| LoRA 是本次最稳的第一轮微调路线 | LoRA rank=16 在 80 条检查中达到 **5.48% CER** | 优先 LoRA，再考虑更大范围参数更新 |
| vLLM + CUDA Graph 是当前最强 serving 路线 | 短音频 benchmark P50 **69ms**，transformers 是 **522ms** | 质量验证通过后，用 vLLM 做第一阶段 serving PoC |
| 长音频必须 pipeline 化 | 180s synthetic long audio 只输出 16 个字符 | 生产前必须做 VAD/chunk/overlap/stitching |

### 推荐生产配置

| 参数 | 推荐值 | 原因 |
|---|---|---|
| ASR model route | 第一阶段云端 PoC 用 Qwen3-ASR 1.7B | 本 repo 中 public CER baseline 更好，且有 dedicated transcription route |
| 微调方式 | 先做 LoRA rank=16；如果需要声学域适配，再试 encoder+LoRA | 比 full-param SFT 风险小，小数据表现更好 |
| 精度 | FP32 稳定基线；mixed precision 必须先过 grad_norm 和 CER 检查 | 避免 NaN 或 checkpoint 被悄悄破坏 |
| Serving engine | vLLM Qwen3-ASR transcription endpoint | clean env 路线已验证，并有延迟/并发数据 |
| 音频输入 | VAD + chunk + overlap + stitching | 避免长音频坍缩，延迟和成本更可控 |
| 验收数据 | 客户脱敏音频 + 人工 transcript + hotwords | FLEURS 只证明 harness，客户域数据决定生产质量 |

---

## 1. 我们实际跑了什么

下表是当前 public evidence。所有结果都来自公开 Qwen 样例和 Azure H100 测试，不包含客户音频、私有 endpoint、VM 名称/IP 或订阅信息。

| 方向 | Evidence | Raw data |
|---|---|---|
| Qwen3-ASR 0.6B 推理 | Azure H100 NVL 95GB 上跑通官方中英文公开样例 | `results/h100/h100_0.6b_full_benchmark.json` |
| Qwen3-ASR 1.7B 推理 | 同一批公开样例跑通 | `results/h100/h100_1.7b_full_benchmark.json` |
| H100 batch throughput | batch size 1/4/8/16 扫描 | `results/h100/h100_model_comparison.json` |
| 长音频行为 | 30s、60s、180s synthetic long-audio 测试 | `results/h100/h100_long_audio_test.json` |
| **FLEURS CER baseline** | **200 条中文测试样本：0.6B=7.74%，1.7B=7.09%** | `results/fleurs_cer_qwen3_asr_0.6b.json`, `results/fleurs_cer_qwen3_asr_1.7b.json` |
| **官方 SFT 微调** | **官方 `qwen3_asr_sft.py` 跑通；本次发现 bf16 会产生 NaN，fp32 可稳定训练** | `results/sft_v3_log_summary.json` |
| **微调准确率影响** | **100 条全参数 SFT 后 FLEURS CER 从 7.74% 变为 21.53%，说明小数据全参微调泛化风险很高** | `results/fleurs_cer_finetuned_fp32.json` |
| **vLLM serving** | **clean conda env 下 Qwen3-ASR-1.7B transcription endpoint 跑通；旧失败文件保留为 dirty-env 教训** | `results/vllm_serving_result.json` |
| **CUDA Graph A/B** | **Transformers P50=522ms；vLLM+CUDA Graph P50=69ms；20 条 FLEURS 未观察到 CER 退化** | `results/cuda_graph_ab.json`, `results/accuracy_verification.json` |
| **vLLM 并发 serving** | **并发 16：P50=154ms，P95=388ms，119 rps，64/64 成功** | `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json` |
| **数据吞吐 profiling** | **200 条样本：audio decode=0.196s，GPU transfer=0.31s** | `results/dataloader_profile.json` |
| **LoRA SFT** | **rank=16 只训练 0.78% 参数，80 条 FLEURS 检查 CER=5.48%** | `results/lora_param_info.json`, `results/lora_sft_result.json` |
| **Encoder-only SFT** | **Encoder=186M(23.8%)；只训 encoder 后 80 条 FLEURS 检查 CER=6.26%** | `results/encoder_decoder_split.json`, `results/encoder_only_sft_result.json` |
| **LR stability smoke** | **fp32 下 2e-5/1e-5/5e-6/2e-6 四档小样本训练均无 NaN** | `results/lr_stability_smoke.json` |
| **4-bit NF4 推理准确率** | **同一批 80 条 FLEURS：4-bit NF4 CER=5.99%，bf16 baseline=5.28%** | `results/qwen3_asr_0.6b_4bit_cer_comparison.json` |
| **QLoRA SFT** | **4-bit NF4 + LoRA rank=16 训练完成，80 条 CER=5.69%** | `results/qlora_sft_result.json` |
| **FP8 支持检查** | **PyTorch 有 float8 dtype，但当前环境没有 TransformerEngine/torchao；没有现成 FP8 SFT recipe** | `results/fp8_support_check.json` |
| **Checkpoint resume** | **官方 SFT checkpoint/resume smoke 已在 20 条样本上跑通** | `results/checkpoint_resume_smoke.json` |
| **4-bit 量化 smoke** | **BitsAndBytes 4-bit load + transcribe smoke 可跑 Qwen3-ASR-0.6B** | `results/qlora_4bit_load_smoke.json` |
| **Gemma 3n 路线状态** | **Gemma 3n E2B-it 权重已下载，官方 HF API 路线已对齐；最终 clean-env smoke JSON 在 SSH 超时前未收集到，因此不报告 CER** | `results/gemma3n_h100_route_status.json`, `docs/gemma-3n-audio-feasibility.md` |
| **成本 proxy** | **Korea Central H100 Linux PayGo 价格来自 Azure Retail Prices API；serial proxy 约 $0.626/audio-hour** | `results/cost_proxy.json` |
| Harness regression | WER/CER、endpoint benchmark、py_compile 全通过 | `results/harness_test_results.json` |

### H100 模型对比

| Metric | Qwen3-ASR-0.6B | Qwen3-ASR-1.7B | 解读 |
|---|---:|---:|---|
| Model load | 5.8s | 4.9s | 权重已缓存后加载都很快 |
| Single request latency | 0.826s | **0.185s** | 这个短中文样例上 1.7B 更快 |
| Batch 4 throughput | 19.38 req/s | 19.21 req/s | 小 batch 接近 |
| Batch 8 throughput | **35.05 req/s** | 28.93 req/s | 0.6B 更高 |
| Batch 16 throughput | **55.13 req/s** | 51.74 req/s | 单张 H100 上都超过 50 short req/s |
| 10-round P50 | 0.172s | 0.174s | 稳态延迟稳定 |
| 10-round P95 | 0.215s | **0.174s** | 1.7B tail latency 更稳 |
| 官方中文样例 CER | 0.0% | 0.0% | 只是 smoke quality，不代表客户数据 |
| 英文公开样例 latency | 1.195s | **0.954s** | 1.7B 更快 |

**边界：** 这里的 CER=0% 只说明官方短样例和预期文本完全一致，不是客户业务准确率。

### 长音频发现

| Audio | Duration | Transcribe time | RTF | Output chars | 发现 |
|---|---:|---:|---:|---:|---|
| 重复中文样例 | 30s | 1.769s | 0.0590 | 98 | 短/中音频正常 |
| 重复中文样例 | 60s | 2.044s | 0.0341 | 196 | 短/中音频正常 |
| 重复中文样例 | 180s | 82.726s | 0.4596 | 16 | **失败：输出坍缩** |
| 官方英文样例 | 15.1s | 1.202s | 0.0799 | 188 | 正常 |

这条结果对会议转录客户最重要：**长会议音频不能整段一把梭。** 生产 pipeline 必须做 VAD、chunking、overlap、stitching、可选 forced alignment 和 diarization。

---

## 2. 客户诉求与当前证据

| 客户诉求 | 现在能展示什么 | 还需要客户给什么 |
|---|---|---|
| Qwen/Gemma backbone | Qwen3-ASR 0.6B/1.7B H100 推理和长音频证据；Gemma 3n E2B-it 官方 HF 路线和环境前置条件已记录 | 客户 exact checkpoint；如果选择 Gemma 做 ASR backbone，需要在 clean env 下补 audio smoke 和 CER |
| HF training stack | Qwen3-ASR 官方 fine-tuning 已跑通；fp32 稳定，bf16 产生 NaN | 客户 training command、Accelerate/DeepSpeed/FSDP config、失败日志 |
| vLLM/SGLang/TensorRT-LLM serving | vLLM clean env serving、CUDA Graph A/B、并发 16 benchmark 已跑；SGLang/TRT-LLM 边界已查 | 客户 exact checkpoint 上的 serving config 和 SLA |
| 数据存储/传输/吞吐 | 有 profiling 方法和脚本基础 | 数据规模、存储位置、音频时长、codec、train/eval manifest |
| 训练稳定性和速度 | 单卡 fp32 SFT 稳定跑通；训练诊断清单已写 | multi-GPU/resume 仍需客户 config 和日志 |
| 量化训练稳定性 | 已实测 bf16 NaN；fp32 稳定；LoRA SFT 已跑 | QLoRA/FP8 before-after CER 仍需补测 |
| 推理延迟和成本 | H100 batch throughput、CUDA Graph A/B、vLLM 并发 16、成本 proxy | 当前 baseline cost、SLA、region/SKU pricing |
| 准确率提升 | FLEURS baseline + full-param / LoRA / encoder-only before-after | 客户或更大公开 eval dataset 上的复验 |

### 作战目标覆盖表

下表对应客户会议准备时的 17 个验证目标。✅ 表示 repo 里已有 raw evidence；⚠️ 表示路线和边界已写清，但还需要客户拓扑、clean env 复测或客户数据。

| # | 验证目标 | Repo 状态 | Evidence |
|---:|---|---|---|
| 1 | Qwen 推理延迟 | ✅ 已完成 | `results/h100/h100_model_comparison.json` |
| 2 | 吞吐-延迟平衡 | ✅ 已完成 | `results/h100/h100_model_comparison.json`, `results/concurrent_benchmark_v2.json` |
| 3 | 长音频退化 | ✅ 已完成 | `results/h100/h100_long_audio_test.json` |
| 4 | vLLM serving | ✅ 已完成 | `results/vllm_serving_result.json` |
| 5 | SGLang / TensorRT-LLM 边界 | ✅ 已完成 | `docs/sglang-trtllm-asr-boundary.md` |
| 6 | Qwen3-ASR 官方 SFT | ✅ 已完成 | `results/sft_v3_log_summary.json` |
| 7 | dataloader/audio decode profiling | ✅ 已完成 | `results/dataloader_profile.json` |
| 8 | 训练稳定性和 resume | ⚠️ 部分完成 | `results/checkpoint_resume_smoke.json`；multi-GPU 需要目标拓扑 |
| 9 | 量化训练稳定性 | ✅ bf16/4-bit/QLoRA 已覆盖 | `results/qwen3_asr_0.6b_4bit_cer_comparison.json`, `results/qlora_sft_result.json`, `results/fp8_support_check.json` |
| 10 | 公开 CER baseline | ✅ 已完成 | `results/fleurs_cer_qwen3_asr_0.6b.json`, `results/fleurs_cer_qwen3_asr_1.7b.json` |
| 11 | Gemma backbone route | ⚠️ 路线已准备，不声明 CER | `results/gemma3n_h100_route_status.json`, `docs/gemma-3n-audio-feasibility.md` |
| 12 | 成本 proxy | ✅ 已完成 | `results/cost_proxy.json` |
| 13 | CUDA Graph / compile 可行性 | ✅ 已完成 | `results/cuda_graph_ab.json`, `results/accuracy_verification.json` |
| 14 | 并发 serving | ✅ 已完成 | `results/concurrent_benchmark_v2.json` |
| 15 | LoRA vs 全参数 | ✅ 已完成 | `results/lora_sft_result.json`, `results/fleurs_cer_finetuned_fp32.json` |
| 16 | Encoder-only vs 全模型 | ✅ 已完成 | `results/encoder_only_sft_result.json`, `results/encoder_decoder_split.json` |
| 17 | LR/数据量/精度最佳实践 | ⚠️ 部分完成 | `results/lr_stability_smoke.json`；数据量梯度和 mixed-precision recipe 仍待补 |

---

## 3. Qwen3-ASR 微调路径

Qwen3-ASR 和 Phi-4-mm 这类 audio-capable LLM 在大方向上类似：audio waveform 经过 audio encoder/front-end 变成 audio embeddings，再由 decoder 生成文本。但训练时不要照搬 Phi-4-mm，应该优先用 **Qwen3-ASR 官方 fine-tuning path**。

官方路径：https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning

官方说明：该脚本使用 JSONL audio-text pairs 微调 Qwen3-ASR，并支持 `torchrun` 多 GPU 训练。

### 训练数据格式

每行一条 audio-transcript 样本：

```jsonl
{"audio":"/data/wavs/utt0001.wav","text":"language Chinese<asr_text>这是训练文本。"}
{"audio":"/data/wavs/utt0002.wav","text":"language English<asr_text>This is a test sentence."}
```

已知语言时建议加 language prefix：

```text
language Chinese<asr_text>...
language English<asr_text>...
language None<asr_text>...
```

### 单卡微调

```bash
python qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file ./train.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 32 \
  --grad_acc 4 \
  --lr 2e-5 \
  --epochs 1 \
  --save_steps 200 \
  --save_total_limit 5
```

### 关键发现：BF16 会产生 NaN gradients

**H100 NVL 95GB 上的实测发现**：官方 SFT 脚本默认 `bf16=True` 路径从第一个日志步开始就出现 `grad_norm=nan`。降低学习率并改成 FP32 后，训练可以正常完成，没有 NaN。

| 精度 | grad_norm | Loss | 训练后模型输出 |
|---|---|---|---|
| BF16（默认） | **step 1 开始就是 nan** | 209 → 无意义 | `'!'`（模型被破坏） |
| FP32（patch 后） | **11-49**（正常） | 0.54 → 0.17 | 合法中文转录 |

修复方式：把 SFT 脚本里的训练参数改成 FP32：

```python
# qwen3_asr_sft.py 中修改：
bf16=False,
fp16=False,
# 模型加载时：
dtype=torch.float32
```

这不是小问题。任何人要 fine-tune Qwen3-ASR，都应该先做 FP32 stability baseline，再考虑 mixed precision。

### 微调策略推荐

| 策略 | 训练参数量 | H100 实测结果 | 解读 |
|---|---:|---|---|
| Full-param SFT (fp32) | 788M (100%) | 数值稳定，但 100 条样本微调后 200 条 held-out CER 从 7.74% 退化到 21.53% | 小数据风险太高；只适合更大、更干净的数据集 |
| Decoder LoRA (rank=16) | 6.1M (0.78%) | 80 条 FLEURS 检查 CER=5.48% | 小数据第一轮最值得跑 |
| Encoder-only | 186M (23.8%) | 同一批 80 条检查 CER=6.26% | 可用于声学域适配，但本次弱于 LoRA |
| Encoder + LoRA decoder | 186M + 6.1M | 尚未运行 | 拿到客户数据后值得作为下一阶段 |

### 多卡微调

```bash
export CUDA_VISIBLE_DEVICES=0,1
torchrun --nproc_per_node=2 qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file ./train.jsonl \
  --eval_file ./eval.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 1 \
  --grad_acc 4 \
  --lr 5e-6 \
  --warmup_ratio 0.1 \
  --epochs 3 \
  --save_strategy epoch
```

### 训练优化清单

| 层级 | 优化项 | 指标 |
|---|---|---|
| 数据质量 | transcript normalization、language prefix、坏音频过滤 | WER/CER、hard samples |
| 数据吞吐 | `num_workers`、`pin_memory`、`persistent_workers`、`prefetch_factor`、local cache | samples/sec、audio-hours/sec、dataloader wait |
| GPU 效率 | Qwen3-ASR SFT 先用 FP32 稳定基线，再验证 mixed precision；调 batch size 和 grad accumulation | step time、GPU utilization、HBM、`grad_norm` |
| 稳定性 | save/resume、checkpoint interval、NCCL logs、loss spike monitoring | resume success、failure interval |
| 量化 | 先做 FP32 稳定基线；QLoRA/FP8 必须同数据同 eval 做 before/after CER | loss curve、WER/CER delta、memory |

### 准确率验证

正确的 before/after 闭环：

```text
same eval audio + same ground truth
    -> base Qwen3-ASR transcript
    -> fine-tuned checkpoint transcript
    -> WER/CER/hotword comparison
```

FLEURS 这种公开数据集可以证明训练 harness；领域真实结论仍然需要客户脱敏音频和人工 transcript。

---

## 4. 微调后的推理优化

先用 transformers backend 确认质量，再切 vLLM 做 serving 优化。

### CUDA Graph A/B Benchmark（H100 NVL，Qwen3-ASR-1.7B）

| 模式 | P50 latency | CER（20 条样本） | 与 baseline 文本一致性 |
|---|---:|---:|---|
| Transformers direct | 522ms | 6.65% | baseline |
| vLLM CUDA Graph ON（默认） | **69ms** | **5.90%** | 18/20 完全一致 |
| vLLM `--enforce-eager`（CUDA Graph OFF） | 369ms | — | 17/20 完全一致 |

核心结论：

- CUDA Graph 在这个短音频测试里把 latency 从 369ms 降到 69ms，约 **5x**。
- vLLM 的组合优化（CUDA Graph + PagedAttention + scheduling）相对 raw transformers 约 **7x**。
- 20 条 FLEURS 检查里没有观察到 CER 退化（5.90% vs 6.65%）。这只是实测检查，不是通用保证。

### 推理加速后必须复查准确率

| 技术 | 速度收益 | 对准确率的预期 | 备注 |
|---|---|---|---|
| CUDA Graph | 本次约 5x decode | 理论上不改变模型质量 | replay 同一 kernel sequence，但 ASR endpoint 仍要复查输出 |
| Flash Attention | attention 约 2-4x | 数值精度范围内等价 | 仍需抽样核对转录 |
| PagedAttention | 提升 KV cache 管理效率 | 理论上不改变质量 | 更偏 serving 内存管理 |
| Continuous Batching | 提高吞吐 | 理论上不改变质量 | 要防 request mixing / 调度 bug |
| FP8 / INT8 quantization | 约 1.5-2x | ⚠️ 必须实测 CER | 不能只看 latency |
| INT4 quantization (GPTQ/AWQ) | 显存收益大 | ⚠️ 必须实测 CER | 可能有 0.5-2% 级别退化 |

注意：Qwen3-ASR 的 audio encoder 在训练时对数值精度敏感（bf16 会 NaN）。任何 FP8/INT4 推理或训练优化，都必须用 CER 做 before/after 验收。

### Transformers Backend

适合 correctness 和 debugging：

```python
from qwen_asr import Qwen3ASRModel
import torch

model = Qwen3ASRModel.from_pretrained(
    "qwen3-asr-finetuning-out/checkpoint-200",
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_inference_batch_size=32,
    max_new_tokens=512,
)

result = model.transcribe(audio="sample.wav", language="Chinese")
print(result[0].text)
```

### vLLM Backend

vLLM 明确把 Qwen3-ASR 列在 transcription model 里：

| vLLM route | Architecture | Example |
|---|---|---|
| Transcription | `Qwen3ASRForConditionalGeneration` | `Qwen/Qwen3-ASR-1.7B` |
| Realtime transcription | `Qwen3ASRRealtimeGeneration` | `Qwen/Qwen3-ASR-0.6B` |

Qwen 官方命令：

```bash
pip install -U qwen-asr[vllm]
qwen-asr-serve Qwen/Qwen3-ASR-1.7B \
  --gpu-memory-utilization 0.8 \
  --host 0.0.0.0 \
  --port 8000
```

注意：要用 clean environment。我们在已有 H100 系统环境中遇到 `qwen-asr` 与 vLLM API 不匹配（`vllm.inputs.data` missing），server 没启动。这是一个真实 deployment lesson：**Qwen/vLLM/Transformers 版本要整体 pin 住，并先验证 endpoint，再承诺 vLLM production throughput。**

### SGLang 和 TensorRT-LLM 边界

| Engine | 当前支持结论 |
|---|---|
| vLLM | 官方文档明确支持 Qwen3-ASR transcription / realtime transcription |
| SGLang | 是高性能 LLM/multimodal serving framework，但本次未查到明确 Qwen3-ASR transcription endpoint 支持 |
| TensorRT-LLM | 对 decoder-heavy LLM path 有价值，但完整 audio frontend + ASR pipeline 要逐模型验证 |

不要在没有实际跑通前说 SGLang 或 TensorRT-LLM 支持客户 ASR 模型。

---

## 5. 复现当前证据

### Local Harness

```bash
python3 scripts/run_harness_tests.py
python3 scripts/eval_asr_metrics.py --reference ref.txt --hypothesis hyp.txt --output results/asr_metrics.json
python3 scripts/benchmark_endpoint.py --url http://127.0.0.1:8000/v1/audio/transcriptions --audio sample.wav
```

### Qwen3-ASR Smoke Test

```bash
python3 scripts/qwen3_asr_transformers_smoke.py \
  --model Qwen/Qwen3-ASR-0.6B \
  --audio https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_zh.wav \
  --language Chinese \
  --output results/qwen3_asr_smoke.json
```

### H100 Benchmark Results

Raw files:

```text
results/h100/h100_0.6b_full_benchmark.json
results/h100/h100_1.7b_full_benchmark.json
results/h100/h100_model_comparison.json
results/h100/h100_long_audio_test.json
results/h100/h100_vllm_serving_benchmark.json
```

---

## 6. 现场要问客户什么

1. 你们训练的 exact Qwen/Gemma checkpoint 是什么？
2. 架构是 dedicated ASR、audio LLM、Gemma audio，还是 custom audio encoder + LLM？
3. 当前训练命令是什么？用 Accelerate、Transformers Trainer、TRL、DeepSpeed、FSDP，还是自研？
4. 数据存储在哪里？object store、disk、NFS、local cache、feature cache？
5. 训练失败点是什么？data loader、OOM、NCCL、checkpoint、quantized training，还是 eval WER？
6. 生产推理路径是什么？vLLM、SGLang、TensorRT-LLM、TensorRT，还是 custom endpoint？
7. 当前 RTF、P50/P95、throughput、GPU utilization、每小时音频成本是多少？
8. 是否能提供 30-60 分钟脱敏音频、人工 transcript 和 hotword list？

---

## 7. 当前限制

- Qwen3-ASR 官方 SFT 已跑通，但目前只验证了 100 条 FLEURS 子集；客户域结论仍需客户脱敏音频和人工 transcript。
- bf16 SFT 在本次 H100 实验中产生 NaN；fp32 稳定。是否可用 mixed precision 需要额外 recipe 验证。
- vLLM serving、CUDA Graph A/B 和并发 16 已验证；更高并发需按客户音频时长和 SLA 复测。
- LoRA rank=16 已做 SFT 并跑了 80 条 FLEURS CER；客户域 LoRA 结论仍需客户数据复验。
- Encoder-only SFT 已跑，并做了 80 条 FLEURS CER；是否适合客户口音/噪声/设备域仍需客户数据复验。
- Gemma 3n 官方支持 audio/ASR。本次已下载 E2B-it 权重并对齐官方 HF API 路线，但 SSH 超时前没有收集到最终 clean-env smoke JSON，因此本 repo 不能声明 Gemma FLEURS CER。
- 4-bit NF4 推理和 QLoRA SFT 已有 FLEURS CER；FP8 微调仍需要 TransformerEngine/torchao 这类 recipe 验证。
- checkpoint/resume smoke 已在单张 H100 上跑通；multi-GPU torchrun 仍需要多 GPU 或客户拓扑。
- fp32 LR smoke 覆盖 2e-5/1e-5/5e-6/2e-6 且无 NaN；数据量梯度和 mixed precision recipe 仍需后续验证。
- SGLang 和 TensorRT-LLM 对 Qwen3-ASR 不是已验证推荐：SGLang 未见 Qwen3-ASR registry，TensorRT-LLM ASR 路径主要是 Whisper。
- 成本数字是 proxy，已补 Azure Retail Prices API 来源；正式报价仍需按客户 region/SKU/折扣/利用率计算。
- 公开样例不能代表客户的会议音频、设备麦克风、口音、噪音、diarization 或 hotwords。

---

## References

| Topic | Source |
|---|---|
| Qwen3-ASR model card | https://huggingface.co/Qwen/Qwen3-ASR-1.7B |
| Qwen3-ASR GitHub | https://github.com/QwenLM/Qwen3-ASR |
| Qwen3-ASR official fine-tuning | https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning |
| vLLM supported models | https://docs.vllm.ai/en/latest/models/supported_models/ |
| SGLang docs | https://docs.sglang.io/ |
| TensorRT-LLM multimodal support | https://nvidia.github.io/TensorRT-LLM/features/multi-modality.html |
| Hugging Face Accelerate | https://huggingface.co/docs/accelerate/index |
| Hugging Face Transformers | https://huggingface.co/docs/transformers/index |
| Hugging Face TRL | https://huggingface.co/docs/trl/index |
| FLEURS dataset | https://huggingface.co/datasets/google/fleurs |
| Gemma 3n E2B-it model card | https://huggingface.co/google/gemma-3n-E2B-it |
| Gemma3n Transformers docs | https://huggingface.co/docs/transformers/main/en/model_doc/gemma3n |
