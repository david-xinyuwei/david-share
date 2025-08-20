## OpenAI OSS Model on Azure 

The **gpt-oss-120b** model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The **gpt-oss-20b** model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

| **Model**    | **Layers** | **Total Params** | **Active Params Per Token** | **Total Experts** | **Active Experts Per Token** | **Context Length** |
| ------------ | ---------- | ---------------- | --------------------------- | ----------------- | ---------------------------- | ------------------ |
| gpt-oss-120b | 36         | 117B             | 5.1B                        | 128               | 4                            | 128k               |
| gpt-oss-20b  | 24         | 21B              | 3.6B                        | 32                | 4                            | 128k               |

gpt-oss-20b and gpt-oss-120b both underwent Post-Training Quantization (PTQ) after the original full-precision training was completed.

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

OAI-OSS Model Loading Methods:

| Usage                                                        | `dequantize` Parameter | Weight Format After Loading to GPU                  | VRAM Consumption | Inference Computation Method                         | Typical Scenarios                                            |
| ------------------------------------------------------------ | ---------------------- | --------------------------------------------------- | ---------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| **Storage Compression Mode** (Hugging Face default LoRA fine-tuning path) | `True`                 | **Dequantized** to BF16/FP16 full‑precision tensors | High (≈ BF16)    | **High‑precision kernel** (BF16 MatMul)              | Model fine‑tuning (LoRA/full‑parameter), needs full‑precision gradient computation, VRAM‑abundant scenarios |
| **Resident Computation Mode** (Ollama / vLLM‑gptoss dedicated kernels) | `False`                | **Retains** MXFP4 4‑bit low‑bit weights             | Low (≈ 1/4 BF16) | **Low‑bit kernel** (4‑bit MatMul/Custom CUDA Kernel) | Low‑VRAM inference deployment (local GPU, edge inference, Hopper+FA3 Sink Token) |

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

| Feature                   | MXFP4                                                        | Traditional INT4 (including GPTQ/AWQ/NF4)                   |
| ------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| **Scale Factor**          | Fixed to a power of 2, E8M0 encoding                         | Arbitrary real number (stored in FP16/FP32)                 |
| **Element Type**          | 4‑bit mini‑float E2M1 (with exponent, mantissa, supports subnormals) | 4‑bit integer (linear grid)                                 |
| **Multiplication Cost**   | Shift operation only, highly efficient                       | Floating‑point/fixed‑point multiplication, higher cost      |
| **Dynamic Range**         | Wide, small values less likely to vanish                     | Narrow, small values easily lost (especially with outliers) |
| **Outlier Resistance**    | Stronger (floating‑point properties)                         | Weaker (requires finer grouping/special algorithms)         |
| **Hardware Optimization** | **Open Compute Project** standard, kernel optimization possible by various vendors | Utilizes existing INT8/INT4 SIMD cores                      |
| **Deployment Ecosystem**  | Emerging standard, hardware support expanding                | Mature engineering, widely adopted ecosystem                |

Suppose we have 8 numbers (in practice MX is 32, but we use a small sample here for demonstration):

```
[1.0, 0.9, 1.1, 0.95, 1.05, 1.0, 0.92, 100.0]
```

#### **Traditional INT4**

- Find max value = 100
- INT4 max integer = 15 → scale ≈ 100 / 15 = 6.67
- Small number: 1.0 / 6.67 ≈ 0.15 → quantized to 0 → dequantized back to 0
- Result:

```
[0, 0, 0, 0, 0, 0, 0, 100]
```

All small values are lost.

------

#### **MXFP4**

- Max representable element value = 6.0
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

All small values retain approximate precision, only large values are slightly clipped.

| Step        | INT4 Result     | MXFP4 Result        |
| ----------- | --------------- | ------------------- |
| Scaled Val. | [0.15, ..., 15] | [0.0625, ..., 6.25] |
| Quantized   | [0, ..., 15]    | [0.0625, ..., 6.0]  |
| Dequantized | [0, ..., 100]   | [1.0, ..., 96.0]    |

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

In GPT-OSS's inference logic, a sink token has been introduced. The sink token requires FlashAttention-3 for efficient execution  (FlashAttention-2 does not have the corresponding kernel), but FA3 is  better supported on Hopper. 

Therefore, if you are using an A10, you can use the Ollama method or transformers. Ollama is the simplest. The Ollama version  model uses MXFP4 quantization by default.

BWT， vLLM also support an new container image vllm/vllm-openai:gptoss, you could refer to it:

*https://techcommunity.microsoft.com/blog/machinelearningblog/deploying-openai%E2%80%99s-first-open-source-model-on-azure-aks-with-kaito/4444234*

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



## gpt-oss-120b inference on Azure H100 GPU VM

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

## gpt-oss-20b Supervised Fine-Tuning 

Overall SFT of gpt-oss is as：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/17.png)

In this part of demo, I will show as folllowing flow to do SFT on gpt-oss:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/18.png)

**Note：**

The method shown in the figure works fine and can be executed, but when  the model weight file is quantized from FP16 GGUF to MXFP4-MoE GGUF**(No way quantize back to MXFP4 )**,  there will be a significant loss of accuracy. According to the Unslotsh  documentation, a similar point is made. Therefore, after the model has  been fine-tuned, one can consider loading the base model with MXFP4 and  the adapter with FP16, which ensures accuracy while saving GPU memory.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/25.png)

Install required package

```
pip install --upgrade transformers accelerate optimum

```

Add openai/gpt-oss-20b and do dequantize:

```
import torch
from transformers import AutoModelForCausalLM, Mxfp4Config

quantization_config = Mxfp4Config(dequantize=True)

model = AutoModelForCausalLM.from_pretrained(
    "openai/gpt-oss-20b",
    attn_implementation="eager",
    torch_dtype=torch.bfloat16,
    quantization_config=quantization_config,
    use_cache=False,
    device_map=None
).to("cuda:0")
```

```
messages = [
    {"role": "user", "content": "¿Cuál es el capital de Australia?"},
]

input_ids = tokenizer.apply_chat_template(
    messages,
    add_generation_prompt=True,
    return_tensors="pt",
).to(model.device)

output_ids = model.generate(input_ids, max_new_tokens=512)
response = tokenizer.batch_decode(output_ids)[0]
print(response)
```

Set SFT mode using LoRA:

```
from peft import LoraConfig, get_peft_model

peft_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules="all-linear",
    target_parameters=[
        "7.mlp.experts.gate_up_proj",
        "7.mlp.experts.down_proj",
        "15.mlp.experts.gate_up_proj",
        "15.mlp.experts.down_proj",
        "23.mlp.experts.gate_up_proj",
        "23.mlp.experts.down_proj",
    ],
)
peft_model = get_peft_model(model, peft_config)
peft_model.print_trainable_parameters()
```

Set SFT training parameters:

```
from trl import SFTConfig

training_args = SFTConfig(
    learning_rate=2e-4,
    gradient_checkpointing=True,
    num_train_epochs=1,
    logging_steps=1,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    max_length=2048,
    warmup_ratio=0.03,
    lr_scheduler_type="cosine_with_min_lr",
    lr_scheduler_kwargs={"min_lr_rate": 0.1},
    output_dir="gpt-oss-20b-multilingual-reasoner",
    report_to="trackio",
    push_to_hub=True,
)
```

```
from trl import SFTTrainer

trainer = SFTTrainer(
    model=peft_model,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)
trainer.train()
```

SFT result:

```
[63/63 17:08, Epoch 1/1]
Step	Training Loss
1	1.975800
2	2.060100
3	1.815100
4	1.823500
5	1.598900
6	1.563900
7	1.401600
8	1.405500
9	1.209600
10	1.318000
11	1.309800
12	1.231300
13	1.161000
14	1.144500
15	1.229000
16	1.154300
17	1.228000
18	1.130400
19	1.092700
20	1.117900
21	1.052200
22	1.053300
23	1.040400
24	1.031400
25	1.094900
26	1.093800
27	0.891500
28	1.032500
29	1.032100
30	1.030200
31	1.038400
32	1.061200
33	1.014500
34	1.113900
35	1.082300
36	0.942400
37	1.042100
38	0.962500
39	1.014300
40	0.996600
41	0.977500
42	0.877100
43	0.919200
44	1.090500
45	1.044600
46	1.109000
47	0.987300
48	0.866800
49	1.061900
50	0.998900
51	0.936400
52	1.004800
53	1.067200
54	0.992500
55	1.029600
56	1.087800
57	1.117300
58	1.021500
59	1.017900
60	0.990300
61	0.935400
62	0.993400
63	1.092800

```

```
trainer.save_model(training_args.output_dir)
trainer.push_to_hub(dataset_name="HuggingFaceH4/Multilingual-Thinking")
```

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# 1. HF分词器
tokenizer = AutoTokenizer.from_pretrained("openai/gpt-oss-20b")

# 2. 加载基础模型（单卡 cuda:0）
base_model = AutoModelForCausalLM.from_pretrained(
    "openai/gpt-oss-20b",
    attn_implementation="eager",
    torch_dtype="auto",
    use_cache=True
).to("cuda:0")

# 3. 本地 LoRA 路径
peft_model_id = "./gpt-oss-20b-multilingual-reasoner"  # ← 这里改成你本地LoRA目录

# 4. 加载 LoRA adapter 并合并
model = PeftModel.from_pretrained(base_model, peft_model_id)
model = model.merge_and_unload()

# 5. 保存合并后模型
output_dir = "merged_bf16_model"
model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)

print(f"✅ 模型合并完成并保存到 {output_dir}")
```



```
MXFP4 quantization requires triton >= 3.4.0 and kernels installed, we will default to dequantizing the model to bf16
Loading checkpoint shards: 100%
 3/3 [02:56<00:00, 53.50s/it]
/root/anaconda3/envs/gpt-oss/lib/python3.12/site-packages/peft/tuners/lora/layer.py:159: UserWarning: Unsupported layer type '<class 'transformers.models.gpt_oss.modeling_gpt_oss.GptOssExperts'>' encountered, proceed at your own risk.
  warnings.warn(
✅ 模型合并完成并保存到 merged_bf16_model
```



```
from transformers import AutoModelForCausalLM, Mxfp4Config

input_dir = "./merged_bf16_model"   # 全精度模型
output_dir = "./merged_mxfp4_model" # 4bit MXFP4 模型

# MXFP4 量化配置
quant_config = Mxfp4Config(dequantize=False)

# 加载全精度模型
model = AutoModelForCausalLM.from_pretrained(input_dir)

# 保存时量化为 MXFP4（保留在显存中为4bit）
model.save_pretrained(output_dir, quantization_config=quant_config)

print(f"✅ MXFP4 模型已保存到 {output_dir}")
```



```
Loading checkpoint shards: 100%
 9/9 [07:02<00:00, 42.84s/it]
✅ MXFP4 模型已保存到 ./merged_mxfp4_model
```

Check quantized model：

```
(base) root@h100vm:~# ls -al merged_mxfp4_model
total 81698556
drwxr-xr-x  2 root root       4096 Aug 19 06:23 .
drwx------ 84 root root       4096 Aug 19 06:16 ..
-rw-r--r--  1 root root       1617 Aug 19 06:16 config.json
-rw-r--r--  1 root root        172 Aug 19 06:16 generation_config.json
-rw-r--r--  1 root root 4547208368 Aug 19 06:16 model-00001-of-00025.safetensors
-rw-r--r--  1 root root 4461395728 Aug 19 06:16 model-00002-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00003-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00004-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00005-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00006-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00007-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00008-of-00025.safetensors
-rw-r--r--  1 root root 3292749840 Aug 19 06:16 model-00009-of-00025.safetensors
-rw-r--r--  1 root root 3292749800 Aug 19 06:16 model-00010-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:16 model-00011-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:16 model-00012-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:17 model-00013-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:17 model-00014-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:18 model-00015-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:18 model-00016-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:19 model-00017-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:19 model-00018-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:20 model-00019-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:20 model-00020-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:21 model-00021-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:22 model-00022-of-00025.safetensors
-rw-r--r--  1 root root 3292749856 Aug 19 06:22 model-00023-of-00025.safetensors
-rw-r--r--  1 root root 3186190904 Aug 19 06:23 model-00024-of-00025.safetensors
-rw-r--r--  1 root root 2316533888 Aug 19 06:23 model-00025-of-00025.safetensors
-rw-r--r--  1 root root      33635 Aug 19 06:23 model.safetensors.index.json
```

Compile  llama.cpp tool：

```
sudo apt install -y git cmake build-essential
pip install sentencepiece
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip install -r llama.cpp/requirements.txt
mkdir build && cd build
cmake .. -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=90
make -j$(nproc)
```

Compile result：

```
[ 98%] Built target llama-tts
[ 99%] Linking CXX executable ../bin/test-chat
[ 99%] Built target test-chat
[ 99%] Linking CXX executable ../bin/test-backend-ops
[ 99%] Built target test-backend-ops
[100%] Linking CXX executable ../../bin/llama-server
[100%] Built target llama-server
(gpt-oss) root@h100vm:~/llama.cpp/build# 
```

convert  HF to  llama.cpp FP16 BIN  file:

```
(gpt-oss) root@h100vm:~# python3 ~/llama.cpp/convert_hf_to_gguf.py     ./merged_bf16_model     --outfile merged_fp16.gguf --outtype f16
```

```
{#- Generation prompt #}
{%- if add_generation_prompt -%}
<|start|>assistant
{%- endif -%}
INFO:gguf.gguf_writer:Writing the following files:
INFO:gguf.gguf_writer:merged_fp16.gguf: n_tensors = 459, total_size = 41.8G
Writing: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████| 41.8G/41.8G [07:36<00:00, 91.7Mbyte/s]
INFO:hf-to-gguf:Model successfully exported to merged_fp16.gguf
```

Check merged_fp16.gguf：

```
(gpt-oss) root@h100vm:~# ls -al merged_fp16.gguf 
-rw-r--r-- 1 root root 41860888000 Aug 19 07:38 merged_fp16.gguf
(gpt-oss) root@h100vm:~# 
```

Use llama-quantize tool to quantize model from fp16.gguf  to MXFP4-MoE:

```
(gpt-oss) root@h100vm:~/llama.cpp/build# ./bin/llama-quantize --help
usage: ./bin/llama-quantize [--help] [--allow-requantize] [--leave-output-tensor] [--pure] [--imatrix] [--include-weights]
       [--exclude-weights] [--output-tensor-type] [--token-embedding-type] [--tensor-type] [--prune-layers] [--keep-split] [--override-kv]
       model-f32.gguf [model-quant.gguf] type [nthreads]

  --allow-requantize: Allows requantizing tensors that have already been quantized. Warning: This can severely reduce quality compared to quantizing from 16bit or 32bit
  --leave-output-tensor: Will leave output.weight un(re)quantized. Increases model size but may also increase quality, especially when requantizing
  --pure: Disable k-quant mixtures and quantize all tensors to the same type
  --imatrix file_name: use data in file_name as importance matrix for quant optimizations
  --include-weights tensor_name: use importance matrix for this/these tensor(s)
  --exclude-weights tensor_name: use importance matrix for this/these tensor(s)
  --output-tensor-type ggml_type: use this ggml_type for the output.weight tensor
  --token-embedding-type ggml_type: use this ggml_type for the token embeddings tensor
  --tensor-type TENSOR=TYPE: quantize this tensor to this ggml_type. example: --tensor-type attn_q=q8_0
      Advanced option to selectively quantize tensors. May be specified multiple times.
  --prune-layers L0,L1,L2...comma-separated list of layer numbers to prune from the model
      Advanced option to remove all tensors from the given layers
  --keep-split: will generate quantized model in the same shards as input
  --override-kv KEY=TYPE:VALUE
      Advanced option to override model metadata by key in the quantized model. May be specified multiple times.
Note: --include-weights and --exclude-weights cannot be used together

Allowed quantization types:
   2  or  Q4_0    :  4.34G, +0.4685 ppl @ Llama-3-8B
   3  or  Q4_1    :  4.78G, +0.4511 ppl @ Llama-3-8B
  38  or  MXFP4_MOE :  MXFP4 MoE
   8  or  Q5_0    :  5.21G, +0.1316 ppl @ Llama-3-8B
   9  or  Q5_1    :  5.65G, +0.1062 ppl @ Llama-3-8B
  19  or  IQ2_XXS :  2.06 bpw quantization
  20  or  IQ2_XS  :  2.31 bpw quantization
  28  or  IQ2_S   :  2.5  bpw quantization
  29  or  IQ2_M   :  2.7  bpw quantization
  24  or  IQ1_S   :  1.56 bpw quantization
  31  or  IQ1_M   :  1.75 bpw quantization
  36  or  TQ1_0   :  1.69 bpw ternarization
  37  or  TQ2_0   :  2.06 bpw ternarization
  10  or  Q2_K    :  2.96G, +3.5199 ppl @ Llama-3-8B
  21  or  Q2_K_S  :  2.96G, +3.1836 ppl @ Llama-3-8B
  23  or  IQ3_XXS :  3.06 bpw quantization
  26  or  IQ3_S   :  3.44 bpw quantization
  27  or  IQ3_M   :  3.66 bpw quantization mix
  12  or  Q3_K    : alias for Q3_K_M
  22  or  IQ3_XS  :  3.3 bpw quantization
  11  or  Q3_K_S  :  3.41G, +1.6321 ppl @ Llama-3-8B
  12  or  Q3_K_M  :  3.74G, +0.6569 ppl @ Llama-3-8B
  13  or  Q3_K_L  :  4.03G, +0.5562 ppl @ Llama-3-8B
  25  or  IQ4_NL  :  4.50 bpw non-linear quantization
  30  or  IQ4_XS  :  4.25 bpw non-linear quantization
  15  or  Q4_K    : alias for Q4_K_M
  14  or  Q4_K_S  :  4.37G, +0.2689 ppl @ Llama-3-8B
  15  or  Q4_K_M  :  4.58G, +0.1754 ppl @ Llama-3-8B
  17  or  Q5_K    : alias for Q5_K_M
  16  or  Q5_K_S  :  5.21G, +0.1049 ppl @ Llama-3-8B
  17  or  Q5_K_M  :  5.33G, +0.0569 ppl @ Llama-3-8B
  18  or  Q6_K    :  6.14G, +0.0217 ppl @ Llama-3-8B
   7  or  Q8_0    :  7.96G, +0.0026 ppl @ Llama-3-8B
   1  or  F16     : 14.00G, +0.0020 ppl @ Mistral-7B
  32  or  BF16    : 14.00G, -0.0050 ppl @ Mistral-7B
   0  or  F32     : 26.00G              @ 7B
          COPY    : only copy tensors, no quantizing
(gpt-oss) root@h100vm:~/llama.cpp/build# 
```



```
(gpt-oss) root@h100vm:~# ~/llama.cpp/build/bin/llama-quantize     merged_fp16.gguf     merged_mxfp4.gguf     MXFP4_MOE
```



```
llama_model_quantize_impl: model size  = 39909.25 MB
llama_model_quantize_impl: quant size  = 11536.18 MB

main: quantize time = 43510.50 ms
main:    total time = 43510.50 ms
```



```
(gpt-oss) root@h100vm:~# ls -al merged_mxfp4.gguf 
-rw-r--r-- 1 root root 12109566400 Aug 19 07:51 merged_mxfp4.gguf
(gpt-oss) root@h100vm:~# ls -al merged_fp16.gguf
-rw-r--r-- 1 root root 41860888000 Aug 19 07:38 merged_fp16.gguf
(gpt-oss) root@h100vm:~# 
```

Use llama.cpp to run the MXFP4-MoE gguf file:

```
(gpt-oss) root@h100vm:~/llama.cpp/build# ./bin/llama-cli -m /root/merged_mxfp4.gguf  --gpu-layers 25  -p "Hello"
```

```
> the result add form 1 to 100
<|channel|>analysis<|message|>The user wants the sum of the numbers from 1 to 100. I should calculate this using the formula for the sum of an arithmetic series: n(n+1)/2. For 1 to 100, n = 100, so the sum is 100*101/2 = 5050. The user might be confused by the result, so I should confirm what they expect and explain the formula.<|end|><|start|>assistant<|channel|>final<|message|>Sure! Let's calculate the sum of all integers from 1 to 100:

### Formula for the Sum of an Arithmetic Series
For a series of consecutive numbers from 1 to \( n \), the sum is given by:
\[
\text{Sum} = \frac{n(n+1)}{2}
\]

### Applying the Formula to 1 to 100
Here, \( n = 100 \). Plugging it into the formula:
\[
\text{Sum} = \frac{100 \times 101}{2} = \frac{10{,}100}{2} = 5{,}050
\]

### Verification
You can verify by adding the numbers in pairs:
- 1 + 100 = 101
- 2 + 99 = 101
- ...
- 50 + 51 = 101

There are 50 pairs, each summing to 101:
\[
50 \times 101 = 5{,}050
\]

### Result
The sum of all integers from 1 to 100 is **5,050**.

---

If you were expecting a different result or need help with another range, let me know!

```

**Check the SFT effect:**

Start the server (be sure to disable the chat template):

```
pip install requests langdetect
```

Start server:

```
/root/llama.cpp/build/bin/llama-server \
    -m /root/merged_mxfp4.gguf \
    --gpu-layers 25 \
    --port 8080 \
    --chat-template "" \
    --reasoning-format none
```

Run python as client:

```
# 保存为 batch_test_analysis_force.py
# llama.cpp server 批量测试 reasoning language × question
# 强制标签 + 降级捕获，保证 analysis_text 不为空

import requests
import csv
import re
from langdetect import detect

# llama.cpp server 配置
SERVER_URL = "http://localhost:8080/completion"

# 推理语言与测试问题
reasoning_langs = ["German", "Spanish", "French", "Chinese"]
questions = [
    "¿Cuál es el capital de Australia?",       # 西班牙语
    "What is the capital of Australia?",       # 英语
    "Quelle est la capitale de l'Australie ?", # 法语
    "澳大利亚的首都是什么？",                     # 中文
]

# CSV 输出文件
csv_file = "reasoning_language_test.csv"

# llama.cpp server 启动（一次加载模型）：
# ./bin/llama-server -m ./merged_mxfp4moe.gguf --gpu-layers 25 --port 8080 --chat-template "" --reasoning-format none

def run_prompt(prompt):
    payload = {
        "prompt": prompt,
        "n_predict": 512,
        "temperature": 0.8,
        "stop": []
    }
    try:
        r = requests.post(SERVER_URL, json=payload)
        if r.status_code == 200:
            return r.json().get("content", "")
        else:
            print(f"[错误] 服务器返回 HTTP {r.status_code}")
            return ""
    except Exception as e:
        print(f"[错误] 请求失败: {e}")
        return ""

def extract_analysis_final(text):
    # 1. 尝试用标签匹配 analysis / final
    analysis_match = re.search(r"<\|start\|>assistant<\|channel\|>analysis<\|message\|>(.*?)<\|end\|>", text, re.S)
    final_match = re.search(r"<\|start\|>assistant<\|channel\|>final<\|message\|>(.*)", text, re.S)

    analysis_text = analysis_match.group(1).strip() if analysis_match else ""
    final_text = final_match.group(1).strip() if final_match else ""

    # 2. 如果 analysis 标签不存在，降级捕获：取 final 标签/关键字前的第一段内容
    if not analysis_text:
        # 去掉可能的 final 部分
        temp_text = text
        if "<|start|>assistant<|channel|>final" in temp_text:
            temp_text = temp_text.split("<|start|>assistant<|channel|>final")[0]
        # 去掉 prompt 部分
        temp_text = re.sub(r"^.*<\|start\|>assistant<\|channel\|>analysis<\|message\|>", "", temp_text, flags=re.S)
        # 按段落分割
        parts = re.split(r"\n\s*\n", temp_text.strip(), 1)
        if parts and parts[0]:
            analysis_text = parts[0].strip()

    return analysis_text, final_text

def detect_lang_safe(text):
    try:
        return detect(text) if text else ""
    except:
        return "unknown"

rows = []
for rlang in reasoning_langs:
    for q in questions:
        # 构造带强制规则的 Prompt
        prompt = (
            f"<|start|>system<|message|>"
            f"reasoning language: {rlang}\n"
            "You MUST first output your reasoning inside:\n"
            "<|start|>assistant<|channel|>analysis<|message|> ... <|end|>\n"
            "Then output your final answer inside:\n"
            "<|start|>assistant<|channel|>final<|message|> ... <|end|>\n"
            "<|end|> "
            f"<|start|>user<|message|>{q}<|end|> "
            f"<|start|>assistant<|channel|>analysis<|message|>"
        )

        output_text = run_prompt(prompt)
        analysis_text, final_text = extract_analysis_final(output_text)
        analysis_lang = detect_lang_safe(analysis_text)
        final_lang = detect_lang_safe(final_text)

        rows.append({
            "reasoning_language": rlang,
            "question": q,
            "analysis_text": analysis_text,
            "analysis_lang_detected": analysis_lang,
            "final_text": final_text,
            "final_lang_detected": final_lang
        })

        print(f"[完成] {rlang} | {q} => Analysis({analysis_lang}), Final({final_lang})")

# 保存到 CSV
with open(csv_file, "w", newline='', encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "reasoning_language", "question",
        "analysis_text", "analysis_lang_detected",
        "final_text", "final_lang_detected"
    ])
    writer.writeheader()
    writer.writerows(rows)

print(f"[完成] 测试结果已保存到 {csv_file}")
```

Result:

```
Chinese,Quelle est la capitale de l'Australie ?,"The user is asking about the capital of Australia.  
Key points to consider:",en,The capital of Australia is **Canberra**.,en
Chinese,澳大利亚的首都是什么？,好的，用户问的是澳大利亚的首都。我先想一下我知道的。澳大利亚的首都是堪培拉（Canberra），是个小城市，位于澳大利亚东南部，靠近悉尼和墨尔本。堪培拉是澳大利亚联邦的政治中心，也是许多联邦政府机构所在地。用户可能只是想确认这个事实。为了确保答案准确无误，我再确认一下：堪培拉是澳大利亚的首都，而不是悉尼或墨尔本，它们只是大城市。堪培拉成立于1908年，作为澳大利亚首都而设。用户没有提到其他信息，所以只需回答这个问题即可。<|end|>,zh-cn,堪培拉（Canberra）是澳大利亚的首都。,no
```



![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/24.png)



**Refer to**: *https://openai.com/index/introducing-gpt-oss/*  
