## OpenAI OSS Model on Azure 

Refer to:

*https://openai.com/index/introducing-gpt-oss/*  

The **gpt-oss-120b** model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The **gpt-oss-20b** model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

In this repo, I will show 2 models performance on Azure NC A10/H100 GPU VM, including TTFT, tokens/s etc.

## **gpt-oss-20b** on Azure NC A10 GPU VM

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



## gpt-oss-20b Azure H100 GPU VM

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

