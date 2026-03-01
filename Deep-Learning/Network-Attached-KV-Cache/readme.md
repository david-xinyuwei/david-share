# Scaling LLM Inference on Consumer GPUs with Network-Attached KV Cache

> **Note:** This article is an enhanced and restructured technical write-up inspired by the original Medium post  
> ["How to Give Your RTX GPU Nearly Infinite Memory for LLM Inference"](https://medium.com/data-science-collective/how-to-give-your-rtx-gpu-nearly-infinite-memory-for-llm-inference-de2c57af1e82) by Natalia Trifonova.  
> The content here is adapted for GitHub, with additional reproducible scripts, diagrams, and generalized implementation notes.


## Running on Azure

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


## 💡 Overview
Running large language models (LLMs) on RTX GPUs often hits a **KV cache memory bottleneck**.  
By **offloading KV cache to fast NVMe storage** (local or network-attached, with RDMA/GPUDirect), you can:

- Serve **2–4× more concurrent users**
- Keep latency almost unchanged
- Slash redundant computation in long-context, multi-turn workloads

This repo shows **how KV cache offload works**, and provides an example **multi-turn benchmark** to measure benefits.

---

## 📜 Why KV Cache Matters
Transformers generate tokens one-by-one. Without KV caching:

Cost per token = O(n²)   # Recompute all previous tokens

```
With KV caching:
```

First token: O(n)   # Process full context once Next tokens: O(1)   # Reuse stored keys/values

**Issue:** KV cache size grows with context length, layers, and concurrent sessions.  
Consumer GPUs (e.g. RTX 4090 24GB) quickly run out of VRAM → cache eviction → recomputation → latency spikes.

---

## 🏗 Architecture: Network-Attached KV Cache
```
       +-------------------+
         |   Client Requests |
         +---------+---------+
                   |
                   v
         +---------+---------+
         |   LLM Server (GPU)|
         +----+--------+-----+
              |        |
        KV Cache   New KV Compute
              |
              v
   +----------+-----------+
   | KV Cache Manager     |
   +----------+-----------+
              |
   RDMA / GPUDirect / TCP
              |
  +-----------+-----------+
  |  NVMe Storage Server  |
  +-----------------------+
     Shared Across GPUs
```

- Compute KV once per prefix  
- Store externally when VRAM fills  
- Retrieve instantly for repeated prefixes / multi-turn chats  
- Enables sharing KV across GPU nodes

---

## 🚀 Quick Start

### Requirements
- Python 3.9+
- [vLLM](https://github.com/vllm-project/vllm)
- One or more GPUs (tested on RTX 4090)
- NVMe storage (local or network, optional RDMA)

### Install
```bash
pip install vllm requests flask
```

### Run Benchmark

```
export MODEL_NAME=/models/llama/llama-3.1-8b-instruct
python benchmark_serving_multi_turn.py \
    --model $MODEL_NAME \
    --input-file generate_multi_turn.json \
    --num-clients 2 \
    --max-active-conversations 6 \
    --warmup-steps 1
```

------

## 📊 Sample Results (4090 ×4, network NVMe)

| Setup                  | Requests/sec | Latency TTFT | Latency TPOT |
| ---------------------- | ------------ | ------------ | ------------ |
| VRAM-only              | 1.0x         | baseline     | baseline     |
| NVMe offload (local)   | ~2.0x        | ~+1%         | ~0%          |
| NVMe offload (network) | 2.5–4.0x     | ~+2%         | ~0–3%        |

------

## 🔬 Benchmark Script

```
# benchmark_serving_multi_turn.py
import argparse
import json
import time
import random
import requests
from multiprocessing import Process, Queue

def client_process(client_id, tasks_queue, results_queue, api_url):
    while not tasks_queue.empty():
        try:
            convo = tasks_queue.get_nowait()
        except:
            break
        start = time.time()
        r = requests.post(api_url, json={"prompt": convo["prompt"], "max_tokens": convo["max_tokens"]})
        ttft = time.time() - start
        if r.ok:
            results_queue.put({"client": client_id, "ttft": ttft})
        else:
            results_queue.put({"client": client_id, "error": r.status_code})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--input-file", type=str, required=True)
    parser.add_argument("--num-clients", type=int, default=2)
    parser.add_argument("--max-active-conversations", type=int, default=6)
    parser.add_argument("--warmup-steps", type=int, default=1)
    parser.add_argument("--server-url", type=str, default="http://localhost:8000/generate")
    args = parser.parse_args()

    with open(args.input_file) as f:
        conversations = json.load(f)
    random.shuffle(conversations)

    tasks_queue = Queue()
    results_queue = Queue()

    for convo in conversations:
        tasks_queue.put(convo)

    procs = [
        Process(target=client_process, args=(i, tasks_queue, results_queue, args.server_url))
        for i in range(args.num_clients)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    results = []
    while not results_queue.empty():
        results.append(results_queue.get())

    avg_ttft = sum(r["ttft"] for r in results if "ttft" in r) / len(results)
    print(f"Average TTFT: {avg_ttft:.3f}s over {len(results)} requests")
```

------

## 🛠 Alternatives

- CPU DRAM offload — lower latency, no cross-node sharing
- Distributed NVMe pools — e.g. WEKA, Hammerspace
- GPU-Direct Storage — skip CPU for GPU↔NVMe path

------

## 📚 References

- [Original Medium Article](https://medium.com/data-science-collective/how-to-give-your-rtx-gpu-nearly-infinite-memory-for-llm-inference-de2c57af1e82)
- [vLLM Prefix Caching](https://docs.vllm.ai/en/latest/)
- [NVIDIA GPUDirect Storage](https://developer.nvidia.com/gpudirect-storage)