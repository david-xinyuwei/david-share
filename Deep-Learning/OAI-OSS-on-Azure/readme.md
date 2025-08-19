## OpenAI OSS Model on Azure 

The **gpt-oss-120b** model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The **gpt-oss-20b** model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

| **Model**    | **Layers** | **Total Params** | **Active Params Per Token** | **Total Experts** | **Active Experts Per Token** | **Context Length** |
| ------------ | ---------- | ---------------- | --------------------------- | ----------------- | ---------------------------- | ------------------ |
| gpt-oss-120b | 36         | 117B             | 5.1B                        | 128               | 4                            | 128k               |
| gpt-oss-20b  | 24         | 21B              | 3.6B                        | 32                | 4                            | 128k               |



gpt‑oss‑20b 和 gpt‑oss‑120b 都是在原始全精度训练完成之后做了后量化(Post‑Training Quantization, PTQ)。

*https://huggingface.co/openai/gpt-oss-120b/blob/main/config.json*

```
  "quantization_config": {
    "modules_to_not_convert": [
      "model.layers.*.self_attn",
      "model.layers.*.mlp.router",
      "model.embed_tokens",
      "lm_head"
    ],
    "quant_method": "mxfp4"
  },
```

https://huggingface.co/openai/gpt-oss-20b/blob/main/config.json

```
  "quantization_config": {
    "modules_to_not_convert": [
      "model.layers.*.self_attn",
      "model.layers.*.mlp.router",
      "model.embed_tokens",
      "lm_head"
    ],
    "quant_method": "mxfp4"
  },
```

OAI-OSS模型加载方式：

| 用法                                              | `dequantize` 参数 | 加载到 GPU 后权重形态                | 显存占用        | 推理计算方式                                        | 典型场景                                                    |
| ------------------------------------------------- | ----------------- | ------------------------------------ | --------------- | --------------------------------------------------- | ----------------------------------------------------------- |
| **存储压缩型**（Hugging Face 默认 LoRA 微调路径） | `True`            | **退量化**成 BF16/FP16 全精度 Tensor | 高（≈BF16）     | **高精度 kernel**（BF16 MatMul）                    | 模型微调（LoRA/全参），需全精度梯度计算，显存充足场景       |
| **常驻计算型**（Ollama / vLLM‑gptoss 专用内核）   | `False`           | **保留** MXFP4 4bit 低比特权重       | 低（≈1/4 BF16） | **低比特 kernel**（4bit MatMul/Custom CUDA Kernel） | 低显存推理部署（本地 GPU、边缘推理、Hopper+FA3 Sink Token） |

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/17.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/18.png)

In this repo, I will show ：

- 2 models performance on Azure NV A10，Azure CPU VM and NC H100 GPU VM and including TTFT, tokens/s etc.
- Model Fine-Tuning

## MXFP4(**Microscaling**)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/13.png)

| Feature                   | MXFP4                                                        | Traditional INT4 (including GPTQ/AWQ/NF4)                   |
| ------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| **Scale Factor**          | Fixed to a power of two, E8M0 encoding                       | Arbitrary real number (stored as FP16/FP32)                 |
| **Element Type**          | 4-bit mini-float E2M1 (with exponent, mantissa, supports subnormals) | 4-bit integer (linear grid)                                 |
| **Multiplication Cost**   | Shift operation only, highly efficient                       | Floating-point/fixed-point multiplication, higher cost      |
| **Dynamic Range**         | Wide, small values less likely to vanish                     | Narrow, small values easily lost (especially with outliers) |
| **Outlier Resistance**    | Stronger (due to floating-point properties)                  | Weaker (requires finer grouping/special algorithms)         |
| **Hardware Optimization** | **Open Compute Project** standard, vendors can optimize kernels | Leverages existing INT8/INT4 SIMD cores                     |
| **Deployment Ecosystem**  | Emerging standard, growing hardware support                  | Mature engineering, broad ecosystem                         |

Assume we have 8 numbers (in practice MX uses 32, but here we use a small sample for demonstration):

```
[1.0, 0.9, 1.1, 0.95, 1.05, 1.0, 0.92, 100.0]
```



#### **Traditional INT4**

- Find max = 100
- Max INT4 integer = 15 → scale ≈ 100 / 15 = 6.67
- Small numbers: 1.0 / 6.67 ≈ 0.15 → quantized to 0 → dequantized back to 0
- Result:

```
[0, 0, 0, 0, 0, 0, 0, 100]
```



Small values are completely lost.

------

#### **MXFP4**

- Maximum element representable = 6.0
- X = 2^(floor(log2(100 / 6.0))) ≈ 16
- After dividing by X:

```
[0.0625, ..., 6.25]
```



- Quantization:

```
P_i ≈ [0.0625, ..., 6.0 (saturated)]
```



- Dequantization:

```
[1.0, 1.0, ..., 96.0]
```



Small values retain approximate precision, while large value is only slightly clipped.

| 特性               | MXFP4                                         | 传统 INT4（包括 GPTQ/AWQ/NF4） |
| ------------------ | --------------------------------------------- | ------------------------------ |
| **缩放因子 Scale** | 固定为 2 的幂，E8M0 编码                      | 任意实数（FP16/FP32 存）       |
| **元素类型**       | 4 位小浮点 E2M1（有指数、尾数、支持次正规）   | 4 位整数（线性格子）           |
| **乘法成本**       | 移位即可，高效                                | 浮点/定点乘法，成本高          |
| **动态范围**       | 宽，小值不易消失                              | 窄，小值易丢失（尤其有离群值） |
| **抗离群值能力**   | 更强（浮点属性）                              | 较弱（需分组更细/特殊算法）    |
| **硬件优化**       | **Open Compute Project** 标准，各厂可优化内核 | 利用已有 INT8/INT4 SIMD 核     |
| **落地生态**       | 新兴标准，支持硬件在扩展                      | 工程化成熟，生态广             |

假设我们有 8 个数（实际 MX 是 32，为了演示用小样本）：

```
[1.0, 0.9, 1.1, 0.95, 1.05, 1.0, 0.92, 100.0]
```



#### **传统 INT4**

- 找最大值 = 100
- INT4 最大整数 = 15 → scale ≈ 100 / 15 = 6.67
- 小数：1.0 / 6.67 ≈ 0.15 → 量化成 0 → 反量化回 0
- 结果：

```
[0, 0, 0, 0, 0, 0, 0, 100]
```

小值全没了。

------

#### **MXFP4**

- 元素最大可以表示 6.0
- X = 2^(floor(log2(100 / 6.0))) ≈ 16
- 除以 X 后：

```
[0.0625, ..., 6.25]
```



- 量化：

```
P_i ≈ [0.0625, ..., 6.0(饱和)]
```

- 反量化：

```
[1.0, 1.0, ..., 96.0]
```

小值全部保留大致精度，只有大值轻微截断。

| 步骤     | INT4 结果     | MXFP4 结果        |
| -------- | ------------- | ----------------- |
| 缩放后值 | [0.15,...,15] | [0.0625,...,6.25] |
| 量化后值 | [0,...,15]    | [0.0625,...,6.0]  |
| 反量化   | [0,...,100]   | [1.0,...,96.0]    |

```
[ INT4 (无符号示例) ]                 [ E2M1 (FP4) ]

┌───┬───┬───┬───┐                   ┌───┬───┬───┬───┐
│b3 │b2 │b1 │b0 │  ← 4 bits         │ S │ E1│ E0│ M0│  ← 4 bits
└───┴───┴───┴───┘                   └───┴───┴───┴───┘
b3..b0 → 整数值 (0~15)               S: 符号位 (0=正, 1=负)
                                     E1E0: 2-bit 指数（Exponent）
                                     M0: 1-bit 尾数（Mantissa）
```



## **Sink Token Mechanism and Performance Impact**

In GPT‑OSS, the sink token mechanism primarily improves **inference throughput and latency** in long‑context scenarios, while maintaining accuracy by preventing context loss — it does not inherently increase reasoning accuracy.

### **What is a Sink Token?**

In GPT‑OSS’s inference path (especially with `vLLM`), a **sink token** is a special token inserted at the very beginning of the input sequence.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/14.png)

It serves two key purposes:

1. **Global Context Anchor** – The sink token is attended to by **all tokens** in the sequence, acting as a compressed, high‑dimensional summary of the entire prompt/context.
2. **Long‑Context Efficiency** – While most tokens only attend to a *local sliding window* (recent N tokens), they can still query the sink token to retrieve global information without re‑processing the entire history.

> Think of it as a “pinned global memory cell” in the KV cache — it never slides out, even when using long‑context attention mechanisms.

------

### **Required Attention Mechanism**

To be effective, a sink token requires a **hybrid attention mask**:

- **Sink token → Global attention**: attends to all tokens (prefix global attention)
- **Other tokens → Local + sink attention**: attend to the sink token and their own sliding‑window neighbors

This asymmetric attention layout requires:

- Flexible attention masking
- Pinning selected KV cache entries
- Single‑pass execution for global + local tokens

------

### **Why FlashAttention‑3 (FA3) is Needed**

- FA3 advantages:
  - Native support for *prefix + local hybrid attention masks*
  - Can process sink token’s global access **and** other tokens’ local attention **in the same kernel call**
  - Hopper‑optimized (H100, L40S) → high throughput, low latency
- FA2 limitations:
  - No native hybrid attention support
  - Would either:
    1. Fallback to full O(N²) global attention (slow), or
    2. Require multiple kernel launches (extra latency)

**Conclusion:**

- On **Hopper GPUs** (H100, L40S): vLLM + FA3 = optimal sink token performance
- On **Ampere GPUs** (A10, A100): FA3 kernels may be incomplete/unsupported → slower or fail
- Ollama bypasses this by **not** running true sink token logic (fixed attention pattern + MXFP4 quantization)

------

### **Performance Implications**

| GPU Architecture        | Inference Runtime | Sink Token Support   | Attention Kernel  | Long‑Context Perf.    |
| ----------------------- | ----------------- | -------------------- | ----------------- | --------------------- |
| **H100 / Hopper**       | vLLM + FA3        | ✅ Full, efficient    | Hybrid FA3 kernel | **Best**              |
| **A100 / A10 (Ampere)** | vLLM + FA3        | ⚠ Partial / unstable | FA3 (limited)     | May error or degrade  |
| **A100 / A10**          | Ollama (MXFP4)    | ❌ Not executed       | llama.cpp style   | Stable, no sink boost |
| **Any**                 | HF+BF16 (no FA3)  | ⚠ Possible via hacks | Default attention | High VRAM/latency     |

------

### **Key Takeaways**

- Sink token improves **TTFT** and **throughput** for very long contexts (≥32k tokens) by turning expensive re‑scans into cheap “global memory lookups”.

- FA3 is not just an optimization — it is practically a requirement for efficient sink token in vLLM.

- If running on Ampere (A10/A100)

  :

  - Use Ollama (MXFP4) if you don’t need sink token long‑context speedups.
  - Or disable sink token in vLLM to avoid FA3 issues.

- If on Hopper (H100/L40S):

  - Always leverage vLLM + FA3 with sink token for maximum performance.

------

If you want, I can also generate a **matching color diagram** showing:

1. Sink token workflow
2. FA3 hybrid mask
3. H100 vs A10 kernel path differences

## **gpt-oss-20b** on Azure NV A10 GPU VM

In GPT-OSS's inference logic, a sink token has been introduced. The sink token requires FlashAttention-3 for efficient execution  (FlashAttention-2 does not have the corresponding kernel), but FA3 is  better supported on Hopper, while there are issues on Ampere. 

Therefore, if you are using an A10, you can use the Ollama method or transformers. Ollama is the simplest. The Ollama version  model uses MXFP4 quantization by default.

If  you don't do quantization and directly use HF transformers with BF16  inference, the A10's memory is insufficient.



In this part of test, I only use one A10 GPU on ollama. Before load model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/1.png)

### **Ollama**

```
ollama run gpt-oss:20b
```

After I load the 20B model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/2.png)

**During inference:**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/3.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/SuMhR0UZyOM)

The approximate performance during inference with Ollama is:

```
 TTFT < 1s
 Throughput: 45~55 tokens/s
```

Script during test：

```
import requests, time, json

MODEL = "gpt-oss:20b"
PROMPT = "Give me a 2000-word introduction to Ollama."

url = "http://localhost:11434/api/generate"
payload = {"model": MODEL, "prompt": PROMPT, "stream": True}

t0 = time.time()
first_token_time = None
token_count = 0

with requests.post(url, json=payload, stream=True, timeout=600) as resp:
    for line in resp.iter_lines():
        if not line:
            continue
        data = json.loads(line)
        if data.get("done"):
            break
        chunk = data.get("response", "")
        if not chunk:
            continue
        if first_token_time is None:
            first_token_time = time.time()
        token_count += len(chunk.split())   # 简化统计token，可用tiktoken更精确

t1 = time.time()
ttft = first_token_time - t0
throughput = token_count/(t1-first_token_time) if first_token_time else 0
print(f"TTFT: {ttft:.3f}s, Tokens: {token_count}, Throughput: {throughput:.2f} tokens/s")
```



## **gpt-oss-20b** on Azure CPU VM

The gpt-oss-20b model, with the help of Ollama, can also run on an Azure CPU VM. It requires more than 14 GB of memory and an 8-core CPU, as in the VM configuration shown below:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/15.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/aAYb_v7wsEs)

The approximate performance during inference with Ollama is:

```
 Throughput: < 10 tokens/s
```



## gpt-oss-20b on Azure H100 GPU VM

On the NC H100, with the help of vLLM, we are able to achieve excellent inference performance with the OSS-20B model.

**vLLM**

Before I load the model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/4.png)

**Load model:**

```
vllm serve openai/gpt-oss-20b
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/6.png)

(oss-20b-tgi) root@h100vm:~# cat stress_test.py 

```
#!/usr/bin/env python3
# stress_test.py
"""
Asynchronously stress-test a local vLLM OpenAI-compatible endpoint.

Prerequisites:
  pip install "httpx[http2]" tqdm orjson

Author: 2025-08-06
"""

import argparse, asyncio, time, statistics, os
import orjson, httpx
from tqdm.asyncio import tqdm_asyncio as tqdm   # tqdm ≥ 4.66

ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"
HEADERS  = {"Content-Type": "application/json"}
SYSTEM   = "You are a helpful assistant."


def build_payload(prompt: str, max_tokens: int = 128, temp: float = 0.0):
    return {
        "model": "openai/gpt-oss-20b",      # 任意字符串也行，只要跟 serve 时一致
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
        "stream": False                    # 如需压 TTFT 可设 True，但统计更复杂
    }


async def worker(
    client: httpx.AsyncClient,
    payload: dict,
    latencies: list,
    ttfts: list,
    tokens: list,
):
    """Send a single request and record metrics."""
    t0 = time.perf_counter()
    resp = await client.post(ENDPOINT, headers=HEADERS, content=orjson.dumps(payload))
    t1 = time.perf_counter()

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    out = resp.json()
    # usage 字段遵循 OpenAI 规范
    usage  = out.get("usage", {})
    c_tok  = usage.get("completion_tokens", 0)
    ttft   = out.get("ttft", 0)            # vLLM 0.10 起返回，若无自行估算
    if not ttft:
        # 估算：总时长*(prompt_tokens/全部tokens)   粗略近似
        p_tok = usage.get("prompt_tokens", 1)
        ttft  = (p_tok / (p_tok + c_tok + 1e-6)) * (t1 - t0)

    latencies.append(t1 - t0)
    ttfts.append(ttft)
    tokens.append(c_tok)


async def run(concurrency: int, total_requests: int, payload: dict):
    latencies, ttfts, tokens = [], [], []
    limits = httpx.Limits(max_connections=concurrency)
    timeout = httpx.Timeout(60.0)          # 适当加大

    async with httpx.AsyncClient(limits=limits, timeout=timeout, http2=True) as client:
        sem = asyncio.Semaphore(concurrency)

        async def _task(_):
            async with sem:
                await worker(client, payload, latencies, ttfts, tokens)

        await tqdm.gather(*[_task(i) for i in range(total_requests)])

    return latencies, ttfts, tokens


def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--concurrency", "-c", type=int, default=64,
                    help="number of concurrent requests")
    ap.add_argument("--requests", "-n", type=int, default=1024,
                    help="total requests to send")
    ap.add_argument("--prompt", type=str, default="Explain quantum mechanics in one sentence.",
                    help="user prompt")
    ap.add_argument("--max-tokens", type=int, default=128)
    args = ap.parse_args()

    payload = build_payload(args.prompt, max_tokens=args.max_tokens)

    print(f"Start stress test: {args.requests} requests  | "
          f"concurrency={args.concurrency} | max_tokens={args.max_tokens}")

    st = time.perf_counter()
    lat, ttft, toks = asyncio.run(run(args.concurrency, args.requests, payload))
    et = time.perf_counter()
    total_time = et - st

    # ── Stats ────────────────────────────────────────────────────────────────
    def pct(lst, p): return statistics.quantiles(lst, n=100)[p-1]

    print("\nRESULTS")
    print(f"Total wall-clock time : {total_time:8.2f}  s")
    print(f"Requests / second     : {args.requests / total_time:8.1f}  req/s")
    print(f"Tokens  / second      : {sum(toks) / total_time:8.1f}  tok/s")

    for name, arr in [("Latency (s)", lat), ("TTFT (s)", ttft)]:
        print(f"{name:<15} p50={statistics.median(arr):.3f} "
              f"p90={pct(arr,90):.3f}  p99={pct(arr,99):.3f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
(oss-20b-tgi) root@h100vm:~# 
(oss-20b-tgi) root@h100vm:~# 
(oss-20b-tgi) root@h100vm:~# 
(oss-20b-tgi) root@h100vm:~# 
(oss-20b-tgi) root@h100vm:~# cat stress_test.py 
#!/usr/bin/env python3
# stress_test.py
"""
Asynchronously stress-test a local vLLM OpenAI-compatible endpoint.

Prerequisites:
  pip install "httpx[http2]" tqdm orjson

Author: 2025-08-06
"""

import argparse, asyncio, time, statistics, os
import orjson, httpx
from tqdm.asyncio import tqdm_asyncio as tqdm   # tqdm ≥ 4.66

ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"
HEADERS  = {"Content-Type": "application/json"}
SYSTEM   = "You are a helpful assistant."


def build_payload(prompt: str, max_tokens: int = 128, temp: float = 0.0):
    return {
        "model": "openai/gpt-oss-20b",      # 任意字符串也行，只要跟 serve 时一致
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
        "stream": False                    # 如需压 TTFT 可设 True，但统计更复杂
    }


async def worker(
    client: httpx.AsyncClient,
    payload: dict,
    latencies: list,
    ttfts: list,
    tokens: list,
):
    """Send a single request and record metrics."""
    t0 = time.perf_counter()
    resp = await client.post(ENDPOINT, headers=HEADERS, content=orjson.dumps(payload))
    t1 = time.perf_counter()

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    out = resp.json()
    # usage 字段遵循 OpenAI 规范
    usage  = out.get("usage", {})
    c_tok  = usage.get("completion_tokens", 0)
    ttft   = out.get("ttft", 0)            # vLLM 0.10 起返回，若无自行估算
    if not ttft:
        # 估算：总时长*(prompt_tokens/全部tokens)   粗略近似
        p_tok = usage.get("prompt_tokens", 1)
        ttft  = (p_tok / (p_tok + c_tok + 1e-6)) * (t1 - t0)

    latencies.append(t1 - t0)
    ttfts.append(ttft)
    tokens.append(c_tok)


async def run(concurrency: int, total_requests: int, payload: dict):
    latencies, ttfts, tokens = [], [], []
    limits = httpx.Limits(max_connections=concurrency)
    timeout = httpx.Timeout(60.0)          # 适当加大

    async with httpx.AsyncClient(limits=limits, timeout=timeout, http2=True) as client:
        sem = asyncio.Semaphore(concurrency)

        async def _task(_):
            async with sem:
                await worker(client, payload, latencies, ttfts, tokens)

        await tqdm.gather(*[_task(i) for i in range(total_requests)])

    return latencies, ttfts, tokens


def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--concurrency", "-c", type=int, default=64,
                    help="number of concurrent requests")
    ap.add_argument("--requests", "-n", type=int, default=1024,
                    help="total requests to send")
    ap.add_argument("--prompt", type=str, default="Explain quantum mechanics in one sentence.",
                    help="user prompt")
    ap.add_argument("--max-tokens", type=int, default=128)
    args = ap.parse_args()

    payload = build_payload(args.prompt, max_tokens=args.max_tokens)

    print(f"Start stress test: {args.requests} requests  | "
          f"concurrency={args.concurrency} | max_tokens={args.max_tokens}")

    st = time.perf_counter()
    lat, ttft, toks = asyncio.run(run(args.concurrency, args.requests, payload))
    et = time.perf_counter()
    total_time = et - st

    # ── Stats ────────────────────────────────────────────────────────────────
    def pct(lst, p): return statistics.quantiles(lst, n=100)[p-1]

    print("\nRESULTS")
    print(f"Total wall-clock time : {total_time:8.2f}  s")
    print(f"Requests / second     : {args.requests / total_time:8.1f}  req/s")
    print(f"Tokens  / second      : {sum(toks) / total_time:8.1f}  tok/s")

    for name, arr in [("Latency (s)", lat), ("TTFT (s)", ttft)]:
        print(f"{name:<15} p50={statistics.median(arr):.3f} "
              f"p90={pct(arr,90):.3f}  p99={pct(arr,99):.3f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
```

During the test:

```
x (oss-20b-tgi) root@h100vm:~# python stress_test.py --concurrency 256 --requests 2000     --prompt "Explain quantum mechanics in one paragraph."   --max-tokens 256
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/7.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/kYDJDIWX9xw)



```
(oss-20b-tgi) root@h100vm:~# python stress_test.py --concurrency 256 --requests 2000     --prompt "Explain quantum mechanics in one paragraph."   --max-tokens 256
```

```
Start stress test: 2000 requests  | concurrency=256 | max_tokens=256
100%|████████████████████████████████████████████████████████████████████████████████████████████████████████| 2000/2000 [01:06<00:00, 29.92it/s]

RESULTS
Total wall-clock time :    66.89  s
Requests / second     :     29.9  req/s
Tokens  / second      :   7645.2  tok/s
Latency (s)     p50=8.835 p90=11.235  p99=14.755
TTFT (s)        p50=2.271 p90=2.874  p99=3.775

Done.
```



## gpt-oss-120b on Azure H100 GPU VM

Load model via vLLM

```
(gpt-oss) root@h100vm:~# vllm serve openai/gpt-oss-120b
```

After model is loaded:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/8.png)

Use stress_test.py, only change  "model": "openai/gpt-oss-20b", to "model": "openai/gpt-oss-120b".

```
(gpt-oss) root@h100vm:~# python stress_test-120b.py --concurrency 256 --requests 2000     --prompt "Explain quantum mechanics in one paragraph."   --max-tokens 128
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/9.png)

Result:

```
RESULTS
Total wall-clock time :    60.73  s
Requests / second     :     32.9  req/s
Tokens  / second      :   4215.6  tok/s
Latency (s)     p50=8.254 p90=10.479  p99=11.782
TTFT (s)        p50=3.363 p90=4.269  p99=4.800

Done.
```

Real Inference case:

```
(gpt-oss) root@h100vm:~# python run_local_llm.py "Please write me a Python program that can run directly in the terminal. This program should be a Tetris game with a colorful interface, and allow the player to control the direction of the blocks, game screen should has a clear border, run without any error."
```

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/MQeVIcaIp1Y)

**Code**

```
cat run_local_llm.py
```

Detailed:

```
#!/usr/bin/env python3
"""
简易命令行调用本地 vLLM (OpenAI 兼容) 的脚本
用法:
    python run_llm.py "你的 prompt ..."
可选:
    -m/--model      指定模型名称          (默认: 自动探测)
    -u/--url        指定服务地址          (默认: http://127.0.0.1:8000)
    -v/--verbose    显示完整 JSON 响应
"""

import argparse
import sys
import requests
from openai import OpenAI
from openai.types.chat import ChatCompletion

def list_models(base_url: str):
    """调用 /v1/models 获取当前加载的模型列表"""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/models", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []

def main() -> None:
    parser = argparse.ArgumentParser(description="Run prompt on local vLLM server")
    parser.add_argument("prompt", nargs="+", help="提示词")
    parser.add_argument("-m", "--model", help="模型名称 (默认: 自动探测)")
    parser.add_argument("-u", "--url", default="http://127.0.0.1:8000",
                        help="服务器地址(不带 /v1)，默认 http://127.0.0.1:8000")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="打印完整 JSON")

    args = parser.parse_args()
    base_url = args.url.rstrip("/") + "/v1"

    # 如果用户没指定模型，就到 /v1/models 去探测
    model_name = args.model
    if model_name is None:
        models = list_models(base_url)
        if not models:
            print("❌ 无法从 /v1/models 获取模型列表，请检查 vLLM 是否在运行。", file=sys.stderr)
            sys.exit(1)
        if len(models) > 1:
            print("⚠️  服务器上有多个模型，请用 -m 指定；当前可用：", ", ".join(models), file=sys.stderr)
            sys.exit(1)
        model_name = models[0]

    prompt_text = " ".join(args.prompt)

    client = OpenAI(base_url=base_url, api_key="EMPTY")

    try:
        resp: ChatCompletion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.7
        )
    except Exception as e:
        print("❌ 调用失败:", e, file=sys.stderr)
        sys.exit(1)

    # 输出
    if args.verbose:
        print("=== 完整 JSON ===")
        print(resp.model_dump_json(indent=2, ensure_ascii=False))
        print("\n=== 模型回答 ===")

    print(resp.choices[0].message.content.strip())

if __name__ == "__main__":
    main()
```



## gpt-oss-120b on Azure AI foundry

OpenAI-oss-120b has been released on Azure AI Foundry and can be deployed in a very convenient one-click manner.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/10.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/11.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/12.png)



**Refer to**: *https://openai.com/index/introducing-gpt-oss/*  
