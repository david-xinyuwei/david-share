# 基于 Azure 的 Qwen3-ASR 训练与推理验证

[![Azure GPU](https://img.shields.io/badge/Azure-H100%20NVL-0078D4)](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/)
[![Qwen3-ASR](https://img.shields.io/badge/Model-Qwen3--ASR-7B68EE)](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
[![vLLM](https://img.shields.io/badge/Serving-vLLM-16A34A)](https://docs.vllm.ai/en/latest/models/supported_models/)
[![ASR](https://img.shields.io/badge/Workload-ASR%20Engineering-4B8BBE)](https://huggingface.co/tasks/automatic-speech-recognition)

> **Author**: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

[English](README.md) | 中文版

这是一份面向自研 ASR 团队的 field guide 和 validation harness。目标场景是：客户用 Qwen/Gemma 这类 backbone，训练侧基于 Hugging Face 生态，推理侧评估 vLLM、SGLang、TensorRT-LLM 等高性能 serving engine。

它不声称某个公开模型能直接解决客户生产问题。它回答的是：如何验证 exact model route、训练瓶颈、推理延迟、长音频行为和 Azure GPU 适配。

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
| **vLLM 并发 serving** | **并发 8：P50=88ms，79 rps，32/32 成功** | `results/concurrent_benchmark_v2.json` |
| **数据吞吐 profiling** | **200 条样本：audio decode=0.196s，GPU transfer=0.31s** | `results/dataloader_profile.json` |
| **LoRA 可行性** | **rank=16 时仅 0.78% 参数可训练（6.1M/788M），但 LoRA CER 尚未测** | `results/lora_param_info.json` |
| **模型结构拆分** | **Encoder=186M(23.8%)，Decoder=596M(76.2%)** | `results/encoder_decoder_split.json` |
| **成本 proxy** | **H100 serial 推理估算约 $0.24/audio-hour；需补价格来源/区域后再对外精确引用** | `results/cost_proxy.json` |
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
| Qwen/Gemma backbone | Qwen3-ASR 0.6B/1.7B H100 推理和长音频证据 | 客户 exact checkpoint；如果用 Gemma，需要确认 Gemma 3n 或自研 Gemma audio route |
| HF training stack | Qwen3-ASR 官方 fine-tuning 已跑通；fp32 稳定，bf16 产生 NaN | 客户 training command、Accelerate/DeepSpeed/FSDP config、失败日志 |
| vLLM/SGLang/TensorRT-LLM serving | vLLM clean env serving、CUDA Graph A/B、并发 8 benchmark 已跑；SGLang/TRT-LLM 边界已查 | 客户 exact checkpoint 上的 serving config 和 SLA |
| 数据存储/传输/吞吐 | 有 profiling 方法和脚本基础 | 数据规模、存储位置、音频时长、codec、train/eval manifest |
| 训练稳定性和速度 | 单卡 fp32 SFT 稳定跑通；训练诊断清单已写 | multi-GPU/resume 仍需客户 config 和日志 |
| 量化训练稳定性 | 已实测 bf16 NaN；fp32 稳定 | QLoRA/FP8 before-after CER 仍需补测 |
| 推理延迟和成本 | H100 batch throughput、CUDA Graph A/B、vLLM 并发 8、成本 proxy | 当前 baseline cost、SLA、region/SKU pricing |
| 准确率提升 | FLEURS 200 条 baseline + full-param SFT before/after | 客户或更大公开 eval dataset 上的 LoRA / encoder-only before-after |

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
- vLLM serving、CUDA Graph A/B 和并发 8 已验证；并发 16 尚未测。
- LoRA 参数可行性已验证（0.78% 可训练参数），但 LoRA 微调后的 CER 尚未跑。
- Encoder/decoder 参数拆分已完成，但 encoder-only 微调效果尚未实测。
- Gemma 3n 官方支持 audio/ASR，但本 repo 尚未跑 Gemma 的 FLEURS CER 或 H100 serving benchmark。
- SGLang 和 TensorRT-LLM 对 Qwen3-ASR 不是已验证推荐：SGLang 未见 Qwen3-ASR registry，TensorRT-LLM ASR 路径主要是 Whisper。
- 成本数字是 proxy，正式对外报价必须补 Azure 区域、SKU、价格来源和日期。
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
