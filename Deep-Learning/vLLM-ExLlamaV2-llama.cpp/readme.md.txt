# **Maximizing Multi-GPU Performance for LLaMA Models: vLLM, ExLlamaV2 vs. llama.cpp**

## TL;DR

- **llama.cpp**：通用推理引擎，支持 CPU-only/单GPU、多种硬件，优势是兼容性和量化 (GGUF)，但 **不适合多GPU高并发**，无原生 TP。
- **vLLM**：多GPU、大显存环境首选，原生 **Tensor Parallelism** + 高并发 Batch Inference。
- **ExLlamaV2**：GPU-only，**必须使用 EXL2 量化权重**，原生支持 **TP**，专为显存紧张的多GPU环境优化，性能接近 vLLM。
- **实测数据**：llama.cpp CPU-only 跑 236B 模型仅 ~1 token/sec；vLLM 在 8×GPU 跑 70B LLaMA，50个 2k token 请求耗时 2分29秒 (~800 tokens/sec)。

------

## 背景与问题

### 现状

- 多GPU服务器（如 4×4090, 8×3090）上用 llama.cpp → 无法让所有 GPU 协同计算，甚至完全用 CPU 推理，造成 GPU 闲置。
- llama.cpp 的定位是 **兼容各类设备**，在 GPU 场景弱化了跨卡并行、大规模批推理的优化。

### 工程需求

- 大模型参数量 (≥65B) + 高并发请求，需要：
  1. **Tensor Parallelism**：将计算分片到多卡，协同完成矩阵运算。
  2. **Batch Inference**：多请求合并批处理，提高吞吐。
- 你的 concern：
  - ExLlamaV2 是不是 llama.cpp 的进化版？ → **不是**，两者架构独立。
  - ExLlamaV2 是否必须量化？ → **必须**使用 EXL2 格式权重。
  - 是否支持 TP？ → **支持**，原生多GPU分布计算。

### 场景

- **CPU/单 GPU /低显存** → llama.cpp + GGUF量化
- **多 GPU / 显存充足** → vLLM
- **多 GPU / 显存紧张** → ExLlamaV2 + EXL2量化

------

## 方法 — Fully Reproducible Steps

### 方案一：vLLM 多GPU部署

**安装**

```
pip install vllm
```



**示例代码**

```
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-2-7b-hf", tensor_parallel_size=4)

prompts = ["Yo, GPU 1 says hi!", "What's up from GPU 2?"]

sampling_params = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=50)

outputs = llm.generate(prompts, sampling_params)
for out in outputs:
    print(out.outputs[0].text)
```



- `tensor_parallel_size`: 设置为 GPU 数量（2/4/8）
- vLLM 会自动在多卡间分配计算，并按批次推理。

------

### 方案二：ExLlamaV2（显存紧张的GPU-only方案）

**安装**

```
# 根据官方说明安装 CUDA 依赖
pip install exllamav2
```



**示例代码**

```
from exllamav2 import ExLlamaV2, ExLlamaV2Cache, ExLlamaV2Tokenizer
from exllamav2.generator import ExLlamaV2Sampler
from exllamav2.config import ExLlamaV2Config

# 加载 EXL2 量化模型（必须）
model_dir = "path/to/exl2/model"
model = ExLlamaV2(ExLlamaV2Config(model_dir))
cache = ExLlamaV2Cache(model)
tokenizer = ExLlamaV2Tokenizer(model_dir)

ids = tokenizer.encode("Hey, what's up?")
settings = ExLlamaV2Sampler.Settings()
out_ids = ExLlamaV2Sampler.generate(model, cache, ids, settings, max_new_tokens=50)
print(tokenizer.decode(out_ids))
```



**关键点**

- 必须使用 EXL2 权重。
- 在 `config.json` 启用 TP：

```
"tensor_parallel": 2
```



------

### 方案三：llama.cpp（单卡/CPU场景）

**安装**

```
git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make
```



**运行**

```
./main -m /path/to/model.gguf -p "Hello World"
```



- 支持 GGUF Q2/Q3/Q4/Q5/Q8 量化
- 可部署在无 GPU 的 CPU-only 环境

------

## 实验与基准

| 引擎      | 模型/场景                         | GPU数 | Token类型 | 批量请求 | 耗时   | Tokens/sec     |
| --------- | --------------------------------- | ----- | --------- | -------- | ------ | -------------- |
| llama.cpp | DeepSeek 236B / CPU-only          | 0     | 推理      | 单请求   | -      | **~1**         |
| vLLM      | LLaMA 3.1 70B / 50×2k tokens 请求 | 8     | 推理      | 批处理   | 2m29s  | **~800**       |
| ExLlamaV2 | EXL2量化模型 / 2-GPU TP           | 2     | 推理      | 未说明   | 未说明 | 高（接近vLLM） |

------

## 工程化建议（Checklist）

-  多 GPU 场景启用 TP (`tensor_parallel_size` 或 `tensor_parallel`)
-  高并发场景增加 Batch Size 以提高吞吐
-  GPU显存有限：优先选择量化（GGUF/EXL2）
-  ExLlamaV2 必须 EXL2 格式，提前转换模型
-  监控 GPU 利用率（`nvidia-smi`/Prometheus）
-  单卡或 CPU-only：用 llama.cpp

------

## 部署 Runbook

### vLLM Docker多卡

```
docker run --gpus all --rm -it \
  -v /path/to/models:/models \
  vllm/vllm:latest \
  --model /models/meta-llama/Llama-2-7b-hf \
  --tensor-parallel-size 8
```



### ExLlamaV2 多卡

```
config.json
{
  "tensor_parallel": 2,
  "max_batch_size": 8
}
```



Python 脚本加载并运行。

------

## 风险与故障应对

| 问题               | 原因                    | 处理                         |
| ------------------ | ----------------------- | ---------------------------- |
| GPU利用率低        | 未开启 TP 或 batch 推理 | 启用 TP参数，调整 batch size |
| 显存溢出           | 模型过大                | 量化或减少 batch             |
| llama.cpp多GPU无效 | 架构不支持原生 TP       | 使用 vLLM 或 ExLlamaV2       |
| ExLlamaV2加载失败  | 使用了非EXL2权重        | 转换为 EXL2 量化             |

------

## 结论与下一步

1. **多GPU + 大显存 → vLLM**
2. **多GPU + 显存紧张 → ExLlamaV2 + EXL2量化**
3. **单GPU / CPU-only → llama.cpp + GGUF**
4. 建立每个引擎的 Tokens/sec & Latency 基准，持续优化 TP 和 batch size

------

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/vLLM-ExLlamaV2-llama.cpp/images/1.png)

## FAQ

**Q1: ExLlamaV2 是 llama.cpp 演进版吗？**
A: ❌ 不是，两者独立开发，架构不同。

**Q2: ExLlamaV2 支持原始FP16权重吗？**
A: ❌ 只支持 EXL2 量化格式。

**Q3: ExLlamaV2 支持 TP 吗？**
A: ✅ 原生支持 Tensor Parallelism，多卡显存分布计算。