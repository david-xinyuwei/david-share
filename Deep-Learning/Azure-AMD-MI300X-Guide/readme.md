# Azure AMD MI300X Guide

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

This guide provides comprehensive guidance and resources for deploying, benchmarking, and fine-tuning cutting-edge open-source foundation models on Azure ND MI300X (Standard_ND96isr_MI300X_v5) GPU Virtual Machines powered by AMD Instinct MI300X accelerators.

**Models covered:**
- DeepSeek R1 671B (SGLang)
- Qwen3-235B-A22B (vLLM)
- Qwen 2.5 72B Instruct (vLLM)
- Qwen 2.5 VL 7B (vLLM)
- Llama 4 (vLLM)

---


## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [Standard_ND96isr_MI300X_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nd-mi300x-v5-series) |
| **GPU** | AMD MI300X 192GB |
| **Frameworks** | vLLM, SGLang, LoRA/PEFT |


## Table of Contents

- [Part 1: Azure ND MI300X GPU VM Environment Setup](#part-1-azure-nd-mi300x-gpu-vm-environment-setup)
- [Part 2: DeepSeek R1 671B on MI300X](#part-2-deepseek-r1-671b-on-mi300x)
  - [Deploy with SGLang](#deploy-deepseek-r1-671b-with-sglang)
  - [Custom Benchmark Script](#custom-benchmark-script-for-deepseek-r1)
  - [Benchmark Results (3 Scenarios)](#benchmark-results-for-deepseek-r1)
  - [EvalScope Stress Testing (Default Dataset)](#evalscope-stress-testing-deepseek-r1-with-default-dataset)
  - [EvalScope Stress Testing (Custom C3 Dataset)](#evalscope-stress-testing-deepseek-r1-with-custom-c3-dataset)
- [Part 3: Qwen3-235B-A22B on MI300X](#part-3-qwen3-235b-a22b-on-mi300x)
  - [Deploy with vLLM](#deploy-qwen3-235b-a22b-with-vllm)
  - [Reasoning / Thinking Mode Test](#reasoning--thinking-mode-test)
  - [EvalScope Stress Testing](#evalscope-stress-testing-qwen3-235b-a22b)
- [Part 4: Qwen 2.5 72B on MI300X](#part-4-qwen-25-72b-on-mi300x)
  - [Deploy with vLLM](#deploy-qwen-25-72b-with-vllm)
  - [Custom Benchmark Script](#custom-benchmark-script-for-qwen-25-72b)
  - [Benchmark Results](#benchmark-results-for-qwen-25-72b)
  - [EvalScope Stress Testing (Default Dataset)](#evalscope-stress-testing-qwen-25-72b-with-default-dataset)
  - [EvalScope Stress Testing (Custom C3 Dataset)](#evalscope-stress-testing-qwen-25-72b-with-custom-c3-dataset)
- [Part 5: Qwen 2.5 VL 7B on MI300X (Step-by-Step)](#part-5-qwen-25-vl-7b-on-mi300x-step-by-step)
- [Part 6: Additional Models and Resources](#part-6-additional-models-and-resources)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Part 1: Azure ND MI300X GPU VM Environment Setup

### Create VM

Quickly create a Spot VM using password-based authentication:

```
az vm create --name <VMNAME> --resource-group <RESOURCE_GROUP_NAME> --location <REGION>  --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 256 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password <YOUR_PASSWORD> 
```

Example CLI command:

```
xinyu [ ~ ]$ az vm create --name mi300x-xinyu --resource-group amdrg --location westus --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 512 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password azureadmin@123  
```

VM Deployment Output:

```
Argument '--max-price' is in preview and under development. Reference and support levels: https://aka.ms/CLI_refstatus
Consider upgrading security for your workloads using Azure Trusted Launch VMs. To know more about Trusted Launch, please visit https://aka.ms/TrustedLaunch.
{
  "fqdns": "",
  "id": "/subscriptions/***/resourceGroups/amdrg/providers/Microsoft.Compute/virtualMachines/mi300x-xinyu",
  "location": "westus",
  "macAddress": "60-45-BD-01-4B-AF",
  "powerState": "VM running",
  "privateIpAddress": "10.0.0.4",
  "publicIpAddress": "<your-vm-public-ip>",
  "resourceGroup": "amdrg",
  "zones": ""
}
```

After the system is successfully deployed, open port 22 on the VM's NSG. Then SSH into the VM and perform the following environment configuration steps.

### NVMe Temporary Disk Setup

For testing, use the local NVMe temporary disk as the docker runtime environment. Note that after VM restart, data stored on the temporary disk will be lost. This approach is suitable for fast, low-cost testing scenarios. For production scenarios, a persistent file system should be used.

<!-- Image not found: images/1.png -->

```
mkdir -p /mnt/resource_nvme/
sudo mdadm --create /dev/md128 -f --run --level 0 --raid-devices 8 $(ls /dev/nvme*n1)  
sudo mkfs.xfs -f /dev/md128 
sudo mount /dev/md128 /mnt/resource_nvme 
sudo chmod 1777 /mnt/resource_nvme  
```

Create a mount directory for RAID0 and set up HuggingFace cache:

```
mkdir -p /mnt/resource_nvme/hf_cache 
export HF_HOME=/mnt/resource_nvme/hf_cache 
```

### Docker Configuration

Configure Docker to use the NVMe disk:

```
mkdir -p /mnt/resource_nvme/docker 
sudo tee /etc/docker/daemon.json > /dev/null <<EOF 
{ 
    "data-root": "/mnt/resource_nvme/docker" 
} 
EOF 
sudo chmod 0644 /etc/docker/daemon.json 
sudo systemctl restart docker 
```

### GPU and ROCm Verification

```
rocm-smi
```

Expected output (excerpt):

```
Device  Node  IDs      Temp  Power  ...  VRAM%  GPU%
0       2     0x74b5   41°C  139W   ...   0%     0%
...
```

If `rocm-smi` reports "command not found", ROCm is not properly installed — complete ROCm 6.3 installation and reboot.

### Docker Installation (If Not Already Installed)

```
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
> /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io \
                   docker-buildx-plugin docker-compose-plugin
```

Start and enable Docker:

```
systemctl enable --now docker
```

Verify:

```
docker info | grep 'Server Version'
```

Example:

```
Server Version: 28.1.1
```

---

## Part 2: DeepSeek R1 671B on MI300X

### Deploy DeepSeek R1 671B with SGLang

Pull the Docker image:

```bash
docker pull rocm/sgl-dev:upstream_20250312_v1
```

When launching DeepSeek 671B, it will take approximately 5 minutes.

```bash
docker run \
  --device=/dev/kfd \
  --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --cap-add=SYS_PTRACE \
  --group-add video \
  --privileged \
  --shm-size 128g \
  --ipc=host \
  -p 30000:30000 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e GPU_FORCE_BLIT_COPY_SIZE=64 \
  -e DEBUG_HIP_BLOCK_SYN=1024 \
  rocm/sgl-dev:upstream_20250312_v1 \
  python3 -m sglang.launch_server --model deepseek-ai/DeepSeek-R1 --tp 8 --trust-remote-code --chunked-prefill-size 131072  --host 0.0.0.0 
```

Once you see output similar to the following, it indicates the container has successfully started and is ready to accept requests:

```
[2025-04-01 03:42:11 DP7 TP7] Prefill batch. #new-seq: 1, #new-token: 7, #cached-token: 0, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 03:42:15] INFO:     127.0.0.1:37762 - "POST /generate HTTP/1.1" 200 OK
[2025-04-01 03:42:15] The server is fired up and ready to roll!
[2025-04-01 04:00:11] INFO:     172.17.0.1:55994 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

Verify local accessibility:

```
curl http://localhost:30000/get_model_info 
{"model_path":"deepseek-ai/DeepSeek-R1","tokenizer_path":"deepseek-ai/DeepSeek-R1","is_generation":true} 
curl http://localhost:30000/generate -H "Content-Type: application/json" -d '{ "text": "Once upon a time,", "sampling_params": { "max_new_tokens": 16, "temperature": 0.6 } }'
```

Then open port 30000 on Azure NSG for remote access testing.

### Custom Benchmark Script for DeepSeek R1

```python
# cat deepseek_benchmark_chat_vshow.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek‑R1 benchmark  (TTFT & total tok/s)
随机打印 3 组 {prompt, completion} 便于人工核查
"""

import argparse, asyncio, aiohttp, json, random, statistics, sys, time
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer

SCENARIOS = {
    "focused":   ((256, 512),  ( 50, 150)),
    "analysis":  ((512, 1024), (150, 500)),
    "reasoning": ((256, 512),  (1024, 1024)),
}

DEFAULT_URL, DEFAULT_CONCURRENCY = "http://localhost:30000/v1/chat/completions", 300
TOKENIZER = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1", trust_remote_code=True)

def load_buckets(p: Path):
    dat = json.loads(p.read_text())
    bk  = defaultdict(list)
    for rec in dat:
        dlg = "\n".join(rec["dialogue"])
        chs = "\n".join(f"{chr(65+i)}. {c}" for i, c in enumerate(rec["choices"]))
        prompt = ( "你是一位助理，需要阅读一段对话并回答随后的选择题。"
                   "只输出最终答案对应的文字，不要输出多余内容。\n\n"
                   f"{dlg}\n\n问题：{rec['question']}\n\n选项：{chs}\n\n答案：" )
        ptok = len(TOKENIZER.encode(prompt, add_special_tokens=False))
        for name,(pr,_ ) in SCENARIOS.items():
            if pr[0] <= ptok <= pr[1]:
                bk[name].append(prompt); break
    return bk

class Metrics:
    def __init__(self):
        self.ttft=[]; self.tok=0; self.lock=asyncio.Lock()
        self.samples=[]  # reservoir
    async def add(self, ttft, ctok, prompt, reply):
        async with self.lock:
            self.ttft.append(ttft); self.tok+=ctok
            # reservoir size 3
            k=len(self.samples)
            if k<3:
                self.samples.append((prompt, reply))
            else:
                idx=random.randint(0,k)
                if idx<3:
                    self.samples[idx]=(prompt, reply)

async def call(sess, url, prompt, comp_max, m:Metrics):
    payload={"model":"deepseek-r1","stream":True,
             "messages":[{"role":"user","content":prompt}],
             "max_tokens":comp_max,"temperature":0.7,"top_p":0.9}
    st=time.perf_counter(); first=None; ct=0; reply=[]
    async with sess.post(url,json=payload,timeout=900) as r:
        async for b in r.content:
            if not b.startswith(b"data:"): continue
            d=b[5:].strip()
            if d==b"[DONE]":
                if first: await m.add((first-st)*1000, ct, prompt, "".join(reply))
                return
            try:
                j=json.loads(d)
                delta=j["choices"][0]["delta"]
                if delta.get("content"):
                    tok=delta["content"]
                    if first is None: first=time.perf_counter()
                    ct+=1; reply.append(tok)
                if j["choices"][0].get("finish_reason") is not None:
                    if first: await m.add((first-st)*1000, ct, prompt, "".join(reply))
                    return
            except json.JSONDecodeError:
                continue

async def main(a):
    buckets=load_buckets(Path(a.data_file))
    if a.scenario=="reasoning" and not buckets["reasoning"]:
        buckets["reasoning"]=buckets["focused"][:]            # 复用 prompt

    pool=buckets[a.scenario]
    if not pool: print("No prompt"); return
    prompts=random.choices(pool,k=a.concurrency)
    comp_max=SCENARIOS[a.scenario][1][1]

    m=Metrics(); conn=aiohttp.TCPConnector(limit=a.concurrency)
    t0=time.perf_counter()
    async with aiohttp.ClientSession(connector=conn,
            headers={"Content-Type":"application/json"}) as sess:
        await asyncio.gather(*(call(sess,a.url,p,comp_max,m) for p in prompts))
    wall=time.perf_counter()-t0; n=len(m.ttft)
    if n==0: print("All failed"); return
    pct=lambda lst,p:statistics.quantiles(lst,n=100)[p-1]
    print("\n==== DeepSeek‑R1 Benchmark ====")
    print(f"Scenario        : {a.scenario}")
    print(f"Completed req   : {n}")
    print(f"TTFT ms         : avg={sum(m.ttft)/n:.1f} | "
          f"p50={pct(m.ttft,50):.1f} | p90={pct(m.ttft,90):.1f} | p99={pct(m.ttft,99):.1f}")
    print(f"Total tokens/s  : {m.tok/wall:.1f}")
    # 打印随机采样的 3 组结果
    print("\n--- Random 3 samples ---")
    for i,(p,r) in enumerate(m.samples,1):
        print(f"\n[SAMPLE {i}] Prompt excerpt:\n{p[:120]}...")
        print(f"Reply excerpt  :\n{r[:400]}...\n")
    print("================================\n")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--data_file",default="external_dialogue_comprehension.json")
    ap.add_argument("--scenario",choices=SCENARIOS,required=True)
    ap.add_argument("--concurrency",type=int,default=DEFAULT_CONCURRENCY)
    ap.add_argument("--url",default=DEFAULT_URL)
    asyncio.run(main(ap.parse_args()))
```

### Benchmark Results for DeepSeek R1

**Scenario 1: Focused (Input 256-512 tokens, Output 50-150 tokens, 300 concurrent)**

```
python3 deepseek_benchmark_chat_vshow.py \
        --scenario focused \
        --concurrency 300 \
        --data_file external_dialogue_comprehension.json \
        --url http://172.167.140.16:30000/v1/chat/completions

==== DeepSeek‑R1 Benchmark ====
Scenario        : focused
Completed req   : 300
TTFT ms         : avg=2031.1 | p50=2030.8 | p90=2038.1 | p99=2042.3
Total tokens/s  : 2771.4
```

<details>
<summary>Sample outputs (click to expand)</summary>

```
[SAMPLE 1] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：今天我们非常荣幸地请到了中国体操队的总指导黄玉斌。黄指导曾经是优秀的体操运动员，现在又是一位"金牌教练"。您在结束了运动员生涯之后，就走上...
Reply excerpt  :
好的，我现在需要仔细看一下这段对话，然后回答问题。问题是问在当教练之前，男的曾经做过什么，选项是四个不同的职业。

首先，对话一开始，女的介绍黄指导是中国体操队的总教练，提到他以前是优秀的体操运动员，现在是金牌教练。然后她问黄指导在结束运动员生涯后成为教练是不是人生的转折。男的回应说，退役后努力学习文化知识和训练方法，这些帮助了他的教学。所以这里明显提到他之前是运动员，之后转成教练。所以答案应该是C选项运动员。
```

</details>

**Scenario 2: Analysis (Input 512-1024 tokens, Output 150-500 tokens, 300 concurrent)**

```
==== DeepSeek‑R1 Benchmark ====
Scenario        : analysis
Completed req   : 300
TTFT ms         : avg=1055.4 | p50=1106.2 | p90=1116.6 | p99=1120.6
Total tokens/s  : 2351.2
```

**Scenario 3: Reasoning (Input 256-512 tokens, Output 1024 tokens, 300 concurrent)**

```
==== DeepSeek‑R1 Benchmark ====
Scenario        : reasoning
Completed req   : 300
TTFT ms         : avg=1075.9 | p50=1119.9 | p90=1129.6 | p99=1132.3
Total tokens/s  : 1652.3
```

### EvalScope Stress Testing DeepSeek R1 with Default Dataset

Install the evalscope stress-testing tool:

```
pip install -U "evalscope[perf,dataset]" \
    @ git+https://github.com/modelscope/evalscope.git@main
pip install gradio
```

This tool supports specifying concurrency, total requests, input/output tokens, and test datasets:

- To maximize total throughput: increase concurrency while reducing input tokens per request, focus on overall tokens/s.
- To test single-request performance: decrease concurrency and increase input tokens, focus on TTFT and per-request tokens/s.

The following test uses a relatively extreme scenario with an input of 10,000 tokens:

```
evalscope perf --url http://<your-vm>.cloudapp.azure.com:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --parallel 1 --number 20 --api openai --min-prompt-length 10000 --dataset "longalpaca" --max-tokens 2048 --min-tokens 2048 --stream 
```

Test results for several scenarios with different concurrency levels and request counts:

**Single concurrency:**

<!-- Image not found: images/2.jpg -->

**5 Concurrent Requests:**

<!-- Image not found: images/3.jpg -->

**10 Concurrent Requests:**

<!-- Image not found: images/4.jpg -->

**Note**: The `--enable-torch-compile` parameter is currently not supported in the AMD MI300X environment. The `--enable-dp-attention` parameter is supported but doesn't improve performance under low concurrency. Its effectiveness under high concurrency requires further observation.

#### EvalScope with longalpaca Dataset

```
evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca"  --min-prompt-length 256 --min-tokens 50 --max-tokens 150

evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 400 --dataset "longalpaca" --min-prompt-length 512 --min-tokens 150 --max-tokens 500

evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 400 --dataset "longalpaca" --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024
```

**Result: longalpaca, 300 concurrent, 2000 requests, input 256+, output 50-150**

```
Benchmarking summary:
+-----------------------------------+-------------------------------------------------------+
| Key                               | Value                                                 |
+===================================+=======================================================+
| Time taken for tests (s)          | 1908.7585                                             |
+-----------------------------------+-------------------------------------------------------+
| Number of concurrency             | 300                                                   |
+-----------------------------------+-------------------------------------------------------+
| Total requests                    | 2000                                                  |
+-----------------------------------+-------------------------------------------------------+
| Succeed requests                  | 2000                                                  |
+-----------------------------------+-------------------------------------------------------+
| Failed requests                   | 0                                                     |
+-----------------------------------+-------------------------------------------------------+
| Output token throughput (tok/s)   | 157.1702                                              |
+-----------------------------------+-------------------------------------------------------+
| Total token throughput (tok/s)    | 8428.545                                              |
+-----------------------------------+-------------------------------------------------------+
| Average time to first token (s)   | 192.1444                                              |
+-----------------------------------+-------------------------------------------------------+
| Average input tokens per request  | 7894.0285                                             |
+-----------------------------------+-------------------------------------------------------+
| Average output tokens per request | 150.0                                                 |
+-----------------------------------+-------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 125.2711 | 0.0611  |  0.1415  |  239.5102   |     6220     |      150      |          0.435           |         22.6209         |
|    25%     | 147.5032 | 0.0666  |  0.2565  |  240.2333   |     6661     |      150      |          0.5193          |         26.9221         |
|    50%     | 185.1756 | 0.0709  |  0.4476  |  240.7587   |     7195     |      150      |          0.623           |         29.8891         |
|    66%     | 208.934  | 0.0726  |  0.5645  |  241.9315   |     7583     |      150      |          0.6243          |         31.8673         |
|    75%     | 221.5459 | 0.0737  |  0.6394  |  288.8619   |     7854     |      150      |          0.6244          |         33.3623         |
|    80%     | 229.0159 | 0.0744  |  0.6823  |  321.1012   |     8040     |      150      |          0.6255          |         34.6574         |
|    90%     | 298.5819 | 0.0787  |  0.7653  |  344.8243   |    12765     |      150      |          0.6263          |         48.7416         |
|    95%     | 346.7225 | 0.0828  |  0.8836  |  434.1349   |    14279     |      150      |          1.2317          |         57.478          |
|    98%     | 380.0461 | 0.1565  |  1.158   |  474.2577   |    15300     |      150      |          1.2319          |         64.6744         |
|    99%     | 392.8557 | 0.8745  |  1.2514  |  490.0534   |    15812     |      150      |          1.232           |         66.9624         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

**Result: longalpaca, 300 concurrent, 400 requests, input 512+, output 150-500**

```
Benchmarking summary:
+-----------------------------------+-------------------------------------------------------+
| Key                               | Value                                                 |
+===================================+=======================================================+
| Time taken for tests (s)          | 396.5486                                              |
+-----------------------------------+-------------------------------------------------------+
| Number of concurrency             | 300                                                   |
+-----------------------------------+-------------------------------------------------------+
| Total requests                    | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Succeed requests                  | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Failed requests                   | 0                                                     |
+-----------------------------------+-------------------------------------------------------+
| Output token throughput (tok/s)   | 504.1274                                              |
+-----------------------------------+-------------------------------------------------------+
| Total token throughput (tok/s)    | 7704.4835                                             |
+-----------------------------------+-------------------------------------------------------+
| Average time to first token (s)   | 145.5601                                              |
+-----------------------------------+-------------------------------------------------------+
| Average input tokens per request  | 7138.2275                                             |
+-----------------------------------+-------------------------------------------------------+
| Average output tokens per request | 499.7775                                              |
+-----------------------------------+-------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 33.4355  | 0.0603  |  0.0831  |   142.122   |     6180     |      500      |          1.7833          |         24.8043         |
|    25%     | 77.9315  | 0.0622  |  0.1128  |  142.1716   |     6615     |      500      |          1.7837          |         27.1727         |
|    50%     | 167.9003 | 0.0656  |  0.1618  |  254.3657   |     7090     |      500      |          1.9657          |         30.6316         |
|    66%     | 191.4027 | 0.0672  |  0.1941  |  280.3073   |     7445     |      500      |          3.5165          |         44.7478         |
|    75%     | 204.3268 | 0.0699  |  0.2123  |  280.3209   |     7642     |      500      |          3.5169          |         50.4143         |
|    80%     | 211.4103 | 0.0718  |  0.2236  |  280.3322   |     7776     |      500      |          3.5177          |         52.0564         |
|    90%     | 225.9042 | 0.0734  |  0.2481  |  280.3818   |     8025     |      500      |          3.5181          |         57.0637         |
|    95%     | 241.6131 | 0.0745  |  0.2617  |  280.3932   |     8249     |      500      |          3.5183          |         58.5389         |
|    98%     | 283.4446 | 0.0763  |  0.2732  |  396.4733   |     8749     |      500      |          3.5184          |         61.139          |
|    99%     | 285.9595 | 0.0812  |  0.2758  |  396.4834   |     9038     |      500      |          3.5186          |         64.8766         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

**Result: longalpaca, 300 concurrent, 400 requests, input 256+, output 1024**

```
Benchmarking summary:
+-----------------------------------+-------------------------------------------------------+
| Key                               | Value                                                 |
+===================================+=======================================================+
| Time taken for tests (s)          | 510.2013                                              |
+-----------------------------------+-------------------------------------------------------+
| Number of concurrency             | 300                                                   |
+-----------------------------------+-------------------------------------------------------+
| Total requests                    | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Succeed requests                  | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Failed requests                   | 0                                                     |
+-----------------------------------+-------------------------------------------------------+
| Output token throughput (tok/s)   | 802.8203                                              |
+-----------------------------------+-------------------------------------------------------+
| Total token throughput (tok/s)    | 6399.2207                                             |
+-----------------------------------+-------------------------------------------------------+
| Average time to first token (s)   | 177.9161                                              |
+-----------------------------------+-------------------------------------------------------+
| Average input tokens per request  | 7138.2275                                             |
+-----------------------------------+-------------------------------------------------------+
| Average output tokens per request | 1024.0                                                |
+-----------------------------------+-------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 37.6685  | 0.0636  |  0.0753  |  175.6955   |     6180     |     1024      |          2.9991          |         20.3847         |
|    25%     | 81.5646  | 0.0651  |  0.0895  |  175.7176   |     6615     |     1024      |          2.9999          |         22.7964         |
|    50%     | 207.0302 | 0.0667  |  0.1139  |  334.4339   |     7090     |     1024      |          3.0619          |         25.472          |
|    66%     | 230.9126 | 0.0678  |  0.1293  |  341.3319   |     7445     |     1024      |          3.0623          |         32.6671         |
|    75%     | 244.6862 | 0.0686  |  0.1375  |  341.3469   |     7642     |     1024      |          5.8275          |         43.3419         |
|    80%     | 251.8305 |  0.069  |  0.1439  |  341.4147   |     7776     |     1024      |          5.8278          |         44.8389         |
|    90%     | 266.3631 | 0.0701  |  0.155   |  341.4345   |     8025     |     1024      |          5.8283          |         48.1986         |
|    95%     | 348.8776 | 0.0712  |  0.1592  |  510.2014   |     8249     |     1024      |          5.8285          |         50.6913         |
|    98%     | 356.9199 | 0.0728  |  0.1634  |  510.2079   |     8749     |     1024      |          5.8287          |         52.4331         |
|    99%     | 359.9374 | 0.0746  |  0.2555  |  510.2104   |     9038     |     1024      |          5.8288          |         55.3024         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

### EvalScope Stress Testing DeepSeek R1 with Custom C3 Dataset

Prepare C3-dialog dataset in JSONL format:

```python
python - <<'PY'
from datasets import load_dataset
import json, pathlib, tqdm, sys

# Load C3‑dialog subset
ds = load_dataset("c3", "dialog")
out = pathlib.Path("c3_evalscope.jsonl").open("w", encoding="utf-8")

def parse(item):
    """
    Yield tuples: (dialogue, question, choices, answer)
    Works for both the old and the new C3 schema.
    """
    if "documents" in item:               # New schema
        dlg = "\n".join(item["documents"])
        qs  = item["questions"]
        for q, ch, ans in zip(qs["question"], qs["choice"], qs["answer"]):
            yield dlg, q, ch, ans
    else:                                 # Old schema
        dlg = "\n".join(item.get("dialogue", item["context"]))
        ch  = item.get("choices", item["options"])
        ans = ch[item.get("label", 0)]
        yield dlg, item["question"], ch, ans

for split in ("train", "validation", "test"):
    for item in tqdm.tqdm(ds[split], desc=split):
        for dlg, q, ch, ans in parse(item):
            prompt = (
                f"以下是一段中文对话，请从给定选项中选出正确答案。\n\n{dlg}\n\n"
                f"问题：{q}\n选项：{' / '.join(ch)}\n请直接输出正确选项文本，不要解释。"
            )
            json.dump({"prompt": prompt, "answer": ans}, out, ensure_ascii=False)
            out.write("\n")

out.close()
print("✅ Lines written:", sum(1 for _ in open("c3_evalscope.jsonl")))
PY
```

```
train: 100%|█████████████████████████████████████████████████████████| 4885/4885 [00:00<00:00, 13936.95it/s]
validation: 100%|████████████████████████████████████████████████████| 1628/1628 [00:00<00:00, 14640.62it/s]
test: 100%|██████████████████████████████████████████████████████████| 1627/1627 [00:00<00:00, 14258.74it/s]
✅ Lines written: 9571
```

Stress test commands using the custom dataset:

```bash
# Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

# Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

# MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

# MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

# Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

# Reasoning-S3-high 512→1024
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in [**results1.txt**](PoC-Handbook-for-Azure-AMD-MI300X/results1.txt).

---

## Part 3: Qwen3-235B-A22B on MI300X

Qwen3-235B-A22B is the flagship MoE model in the Qwen3 family:

- 235B total parameters / 22B activated parameters (Top-2 gating)
- Native context length of 32,768 tokens, extendable to 131,072 with YaRN
- Supports "thinking mode / non-thinking mode"
  - When thinking mode is enabled, the model outputs the `<think> … </think>` block before the final answer

| Dimension             | vLLM                                                | SGLang                       |
| --------------------- | --------------------------------------------------- | ---------------------------- |
| OpenAI-compatible API | Yes (`/v1/chat/completions`)                        | Yes (`/v1/chat/completions`) |
| Reasoning parser      | `--enable-reasoning --reasoning-parser deepseek_r1` | `--reasoning-parser qwen3`   |

### Deploy Qwen3-235B-A22B with vLLM

```bash
docker run -d --name qwen3_A \
  --device=/dev/kfd --device=/dev/dri --privileged \
  --security-opt seccomp=unconfined --cap-add SYS_PTRACE \
  -p 8000:8000 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e VLLM_USE_TRITON_FLASH_ATTN=0 \
  -e VLLM_USE_V1=0 \
  rocm/vllm-dev:nightly_main_20250423 \
  vllm serve Qwen/Qwen3-235B-A22B \
    --dtype float16 \
    --tensor-parallel-size 8 \
    --swap-space 16 \
    --max-model-len 8192 \
    --max-num-batched-tokens 65536 \
    --gpu-memory-utilization 0.95 \
    --num-scheduler-steps 10 \
    --disable-log-requests
```

### Reasoning / Thinking Mode Test

Test with `curl` using a complex math/probability/number-theory problem with thinking mode enabled:

```bash
curl -s -w '\nTIME_NAMELOOKUP:%{time_namelookup}\nTIME_CONNECT:%{time_connect}\nTIME_STARTTRANSFER:%{time_starttransfer}\nTIME_TOTAL:%{time_total}\n' \
  http://172.167.140.16:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Qwen/Qwen3-235B-A22B",
        "enable_thinking": true,
        "messages": [
          {
            "role": "system",
            "content": "You are a bilingual (Chinese + English) mathematical reasoning assistant. Explain every step and finish with a bilingual conclusion."
          },
          {
            "role": "user",
            "content": "【复杂概率 + 数论综合题 / Advanced Mixed‑Probability & Number‑Theory Problem】\\n\\n袋子 A 内有 4 个红球、4 个蓝球与 2 个绿球 (total 10)。袋子 B 内有 6 个红球、3 个蓝球与 1 个绿球 (total 10)。\\nStep 1：先从袋子 A 随机取出 2 个球并放入袋子 B；\\nStep 2：再从现在的袋子 B (此时共 12 球) 随机取出 3 个球，不放回。\\n\\nQ1 求 Step 2 抽到"恰好 2 个蓝球且 1 个红球"的概率。\\nQ2 若把 Step 2 的 3 个球颜色按 (R=2, B=1) 记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数 —— 问该数能否被 3 整除？请说明理由，并给出一般判别法。\\n\\n要求：① 全程中英双语逐步推理；② 用组合数或条件概率公式写出每一步；③ 最后分别用中英文各 1 句话总结。"
          }
        ],
        "max_tokens": 8192,
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "stream": false
      }'
```

The model produces correct results with extended reasoning. The answer is correct: Q1 probability = 1/6, Q2 not divisible by 3 (digit sum = 4).

Performance timing from curl:

```
TIME_STARTTRANSFER: 150.380720
TIME_TOTAL: 150.380917
```

Server-side metrics during inference:

```
Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 43.2 tokens/s, Running: 1 reqs
```

<details>
<summary>Full response JSON (click to expand)</summary>

The response includes detailed `reasoning_content` showing step-by-step mathematical derivation, and the final `content` with bilingual answers:

- Q1: Probability = 1/6 (computed via law of total probability across 6 transfer cases)
- Q2: Sum of digits (1+1+2=4) is not divisible by 3, so the number cannot be divisible by 3
- General rule: A number is divisible by 3 iff the sum of its digits is divisible by 3

Usage: prompt_tokens=339, completion_tokens=6675, total_tokens=7014

</details>

### EvalScope Stress Testing Qwen3-235B-A22B

Stress testing with EvalScope's random dataset:

```bash
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions \
  --model Qwen/Qwen3-235B-A22B --api openai --stream \
  --parallel 256 --number 1024 \
  --dataset random \
  --tokenizer-path Qwen/Qwen3-235B-A22B \
  --min-prompt-length 64 --max-prompt-length 64 \
  --min-tokens 64 --max-tokens 128
```

Results:

```
Benchmarking summary:
+-----------------------------------+-----------------------------------------------------------+
| Key                               | Value                                                     |
+===================================+===========================================================+
| Time taken for tests (s)          | 36.7434                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Number of concurrency             | 256                                                       |
+-----------------------------------+-----------------------------------------------------------+
| Total requests                    | 1024                                                      |
+-----------------------------------+-----------------------------------------------------------+
| Succeed requests                  | 1024                                                      |
+-----------------------------------+-----------------------------------------------------------+
| Failed requests                   | 0                                                         |
+-----------------------------------+-----------------------------------------------------------+
| Output token throughput (tok/s)   | 3554.4601                                                 |
+-----------------------------------+-----------------------------------------------------------+
| Total token throughput (tok/s)    | 5428.2653                                                 |
+-----------------------------------+-----------------------------------------------------------+
| Request throughput (req/s)        | 27.8689                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Average latency (s)               | 9.1115                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average time to first token (s)   | 1.4027                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average time per output token (s) | 0.0604                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average input tokens per request  | 67.2363                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Average output tokens per request | 127.542                                                   |
+-----------------------------------+-----------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     |  0.8964  |  0.045  |  0.0554  |   8.6328    |      64      |      128      |          13.211          |         19.9599         |
|    25%     |  1.0316  |  0.05   |  0.0572  |   8.9201    |      65      |      128      |         13.2985          |         20.9292         |
|    50%     |  1.4154  | 0.0521  |  0.0604  |   9.1129    |      66      |      128      |         14.0408          |         21.3371         |
|    66%     |  1.6397  | 0.0532  |  0.0624  |   9.1501    |      67      |      128      |         14.1096          |         21.7367         |
|    75%     |  1.7551  | 0.0541  |  0.0637  |   9.2661    |      68      |      128      |         14.1733          |         22.2206         |
|    80%     |  1.8324  | 0.0551  |  0.0643  |   9.6476    |      69      |      128      |         14.7727          |         22.359          |
|    90%     |  1.9268  | 0.0685  |  0.0657  |   9.6874    |      72      |      128      |         14.8223          |         22.6624         |
|    95%     |  1.9417  | 0.0798  |  0.0677  |   9.7063    |      77      |      128      |         14.8601          |         23.0177         |
|    98%     |  2.0382  | 0.1591  |  0.0692  |   9.7183    |      83      |      128      |         14.8913          |         23.7145         |
|    99%     |  2.0397  | 0.2097  |  0.0695  |   9.7246    |      87      |      128      |         14.8994          |          24.73          |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

---

## Part 4: Qwen 2.5 72B on MI300X

### Deploy Qwen 2.5 72B with vLLM

#### Option A: Using pre-built ROCm vLLM image

```bash
docker run -d --name qwen72b_8x --device=/dev/kfd --device=/dev/dri --privileged \
  --security-opt seccomp=unconfined --cap-add SYS_PTRACE \
  -p 8000:8000 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e VLLM_USE_TRITON_FLASH_ATTN=0 \
  -e VLLM_USE_V1=0 \
  rocm/vllm-dev:nightly_main_20250423 \
  vllm serve Qwen/Qwen2.5-72B-Instruct \
    --dtype float16 \
    --tensor-parallel-size 8 \
    --swap-space 16 \
    --max-model-len 8192 \
    --max-num-batched-tokens 65536 \
    --gpu-memory-utilization 0.95 \
    --num-scheduler-steps 10 \
    --disable-log-requests
```

#### Option B: Build custom vLLM image with V1 engine

Dockerfile:

```dockerfile
FROM rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410

# 1. Dependencies
RUN python -m pip install --upgrade pip && \
    python -m pip uninstall -y vllm && \
    python -m pip install numpy wheel ninja cmake packaging pyyaml==6.0.1

# 2. Install vLLM main from source (ROCm)
RUN export FORCE_ROCM=1 ROCM_HOME=/opt/rocm && \
    python -m pip install --no-build-isolation \
        "vllm @ git+https://github.com/vllm-project/vllm.git@main"
```

```bash
docker build -t vllm:rocm6.3.1_v1 .
```

Build output:

```
[+] Building 823.5s (7/7) FINISHED
 => CACHED [1/3] FROM docker.io/rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410
 => [2/3] RUN python -m pip install --upgrade pip ...                              2.9s
 => [3/3] RUN export FORCE_ROCM=1 ROCM_HOME=/opt/rocm ...                       815.9s
 => exporting to image                                                             4.6s
 => => naming to docker.io/library/vllm:rocm6.3.1_v1
```

Launch with V1 engine:

```bash
export VLLM_USE_V1=1

docker rm -f qwen72b_v1 2>/dev/null

docker run -d --name qwen72b_v1 --device=/dev/kfd --device=/dev/dri --privileged \
  --security-opt seccomp=unconfined --cap-add SYS_PTRACE \
  -p 8080:8080 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e VLLM_USE_V1=1 \
  -e FLASH_ATTENTION_FORCE_TRITON=1 \
  vllm:rocm6.3.1_v1 \
  bash -lc "python -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen2.5-72B-Instruct \
      --dtype bfloat16 \
      --tensor-parallel-size 8 \
      --gpu-memory-utilization 0.7 \
      --port 8080 --host 0.0.0.0 \
      --trust-remote-code"
```

Verify V1 engine is active:

```bash
docker logs -f qwen72b_v1 | grep "V1 LLM engine"
# Initializing a V1 LLM engine (flash‑attn‑rocm)
```

### Custom Benchmark Script for Qwen 2.5 72B

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen‑2.5‑72B‑Instruct benchmark (专用数据集版本)
数据文件: external_dialogue_comprehension_Qwen2.5-72B-Instruct.json
"""

import argparse, asyncio, aiohttp, json, random, statistics, time
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
SCENARIOS = {
    "focused":   ((256, 512),  ( 50, 150)),
    "analysis":  ((512, 1024), (150, 500)),
    "reasoning": ((256, 512),  (1024, 1024)),
}
DEFAULT_URL, DEFAULT_CONCURRENCY = "http://localhost:8080/v1/chat/completions", 300
TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

# -------- load buckets (dict structure) --------
def load_buckets(path: Path):
    obj = json.loads(path.read_text())
    buckets = defaultdict(list)
    for meta in obj.values():                           # key = "0","1",...
        prompt = "".join(seg["prompt"] for seg in meta["origin_prompt"])
        ptok   = len(TOKENIZER.encode(prompt, add_special_tokens=False))
        for name, (rng, _) in SCENARIOS.items():
            if rng[0] <= ptok <= rng[1]:
                buckets[name].append(prompt)
                break
    return buckets

# -------- metrics --------
class Metrics:
    def __init__(self):
        self.ttft, self.tok, self.samples, self.fail = [], 0, [], 0
    async def ok(self, ttft, ctok, pr, rep):
        self.ttft.append(ttft); self.tok += ctok
        if len(self.samples) < 3:
            self.samples.append((pr, rep))
        else:
            i = random.randint(0, len(self.ttft))
            if i < 3: self.samples[i] = (pr, rep)

# -------- single request --------
async def call_one(sess, url, prompt, cmax, m: Metrics):
    payload = {
        "model": MODEL_ID,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": cmax,
        "temperature": 0.0
    }
    st = time.perf_counter(); first=None; ct=0; rep=[]
    try:
        async with sess.post(url, json=payload, timeout=900) as resp:
            async for line in resp.content:
                if not line.startswith(b"data:"): continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    if first:
                        await m.ok((first-st)*1000, ct, prompt, "".join(rep))
                    return
                try:
                    j = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if "choices" not in j:
                    continue
                ch = j["choices"][0]
                delta = ch.get("delta", {})
                if delta.get("content"):
                    if first is None: first = time.perf_counter()
                    ct += 1; rep.append(delta["content"])
                if ch.get("finish_reason"):
                    if first:
                        await m.ok((first-st)*1000, ct, prompt, "".join(rep))
                    return
    except Exception:
        m.fail += 1

# -------- main --------
async def main(a):
    buckets = load_buckets(Path(a.data_file))
    if a.scenario == "reasoning" and not buckets["reasoning"]:
        buckets["reasoning"] = buckets["focused"][:]

    pool = buckets[a.scenario]
    assert pool, "No prompt in this bucket"
    prompts = random.choices(pool, k=a.concurrency)
    cmax = SCENARIOS[a.scenario][1][1]

    m = Metrics()
    connector = aiohttp.TCPConnector(limit=a.concurrency)
    t0 = time.perf_counter()
    async with aiohttp.ClientSession(connector=connector) as s:
        await asyncio.gather(*(call_one(s, a.url, p, cmax, m) for p in prompts))
    wall = time.perf_counter() - t0
    n = len(m.ttft)
    if n == 0:
        print("all requests failed"); return

    pct = lambda arr, p: (statistics.quantiles(arr, n=100)[p-1]
                          if len(arr) >= 2 else float("nan"))
    print("\n===== Qwen 72B =====")
    print(f"Scenario : {a.scenario} | Completed : {n} | Failed : {m.fail}")
    print(f"TTFT ms  : avg={sum(m.ttft)/n:.1f} | "
          f"p50={pct(m.ttft,50):.1f} | p90={pct(m.ttft,90):.1f} | "
          f"p99={pct(m.ttft,99):.1f}")
    print(f"Tok/s    : {m.tok / wall:.1f}")
    print("--- Samples ---")
    for i, (pr, rep) in enumerate(m.samples, 1):
        print(f"[{i}] {pr[:80]} ... -> {rep[:120]} ...")

# -------- CLI --------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_file",
        default="external_dialogue_comprehension_Qwen2.5-72B-Instruct.json")
    ap.add_argument("--scenario", choices=SCENARIOS, required=True)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--url", default=DEFAULT_URL)
    asyncio.run(main(ap.parse_args()))
```

### Benchmark Results for Qwen 2.5 72B

Run the benchmark:

```bash
python3 qwen_benchmark_8080.py --scenario focused   --concurrency 300
python3 qwen_benchmark_8080.py --scenario analysis  --concurrency 300
python3 qwen_benchmark_8080.py --scenario reasoning --concurrency 300
```

**Focused scenario results (multiple runs):**

| Run | Concurrency | Completed | TTFT avg (ms) | TTFT p50 (ms) | Tok/s  |
|-----|-------------|-----------|---------------|---------------|--------|
| 1   | 300         | 300       | 11102.9       | 9924.8        | 134.5  |
| 2   | 300         | 300       | 9841.3        | 9659.1        | 166.4  |
| 3   | 300         | 300       | 8048.3        | 6514.9        | 168.9  |
| 4   | 100         | 100       | 4126.4        | 3904.1        | 141.7  |
| 5   | 100         | 100       | 6237.1        | 6128.0        | 100.8  |
| 6   | 50          | 50        | 5175.7        | 5127.1        | 63.9   |
| 7   | 5           | 5         | 2161.0        | 2161.0        | 16.9   |
| 8   | 1           | 1         | 2086.7        | -             | 2.8    |

**Analysis scenario results (multiple runs):**

| Run | Concurrency | Completed | TTFT avg (ms) | TTFT p50 (ms) | Tok/s  |
|-----|-------------|-----------|---------------|---------------|--------|
| 1   | 300         | 300       | 15427.6       | 15263.0       | 92.2   |
| 2   | 300         | 300       | 9942.5        | 8526.9        | 130.1  |
| 3   | 300         | 300       | 10097.7       | 7943.7        | 136.4  |
| 4   | 100         | 100       | 5740.0        | 5220.6        | 104.5  |
| 5   | 100         | 100       | 3722.3        | 3228.6        | 155.8  |
| 6   | 50          | 50        | 3896.4        | 3581.1        | 78.6   |
| 7   | 10          | 10        | 2531.9        | 2531.8        | 25.6   |

**Reasoning scenario results (multiple runs):**

| Run | Concurrency | Completed | TTFT avg (ms) | TTFT p50 (ms) | Tok/s  |
|-----|-------------|-----------|---------------|---------------|--------|
| 1   | 300         | 300       | 5768.2        | 4531.0        | 253.7  |
| 2   | 300         | 300       | 8075.8        | 6537.7        | 168.7  |
| 3   | 300         | 300       | 5981.3        | 5004.6        | 198.1  |

### EvalScope Stress Testing Qwen 2.5 72B with Default Dataset

```bash
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca" --min-prompt-length 256 --min-tokens 50 --max-tokens 150
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca" --min-prompt-length 512 --min-tokens 150 --max-tokens 500
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset longalpaca --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024
```

**Result: longalpaca, 300 concurrent, 2000 requests, input 256+, output 50-150**

```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 1810.7969                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Number of concurrency             | 300                                                            |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 165.2129                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 9190.5007                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 128.1664                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 8171.4815                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 149.5835                                                       |
+-----------------------------------+----------------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 50.0377  | 0.0829  |  0.3512  |  200.6691   |     6429     |      150      |          0.3611          |         17.9766         |
|    25%     | 74.7061  | 0.0847  |  0.5382  |  209.3805   |     6885     |      150      |          0.4958          |         29.1994         |
|    50%     | 123.0922 | 0.0871  |  0.8697  |   220.316   |     7435     |      150      |          0.6808          |         34.1403         |
|    66%     | 152.6436 | 0.0888  |  1.0786  |   228.496   |     7838     |      150      |          0.6983          |         36.5236         |
|    75%     | 170.2323 | 0.0907  |  1.2006  |   302.52    |     8121     |      150      |          0.7164          |         38.1459         |
|    80%     | 181.5637 | 0.1029  |  1.258   |  302.6109   |     8346     |      150      |          0.7295          |         39.3196         |
|    90%     |  223.22  | 0.5089  |  1.4175  |  415.0705   |    13155     |      150      |          0.7475          |         44.2413         |
|    95%     | 234.9383 |  2.125  |  1.6208  |  448.3035   |    14847     |      150      |          0.7476          |         54.0722         |
|    98%     | 265.0679 |  2.21   |  1.8875  |   530.326   |    15954     |      150      |          0.7478          |         64.6721         |
|    99%     | 301.6214 | 3.0639  |  1.9901  |  530.6473   |    16321     |      150      |          0.7478          |         67.3814         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

**Result: longalpaca, 300 concurrent, 1000 requests, input 512+, output 150-500**

```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 1575.5161                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 1000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 1000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 258.3611                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 4937.1365                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 96.5871                                                        |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 7371.486                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 407.052                                                        |
+-----------------------------------+----------------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 52.4965  | 0.0783  |   0.42   |  250.2315   |     6397     |      299      |          0.6767          |         11.6492         |
|    25%     | 78.0104  | 0.0859  |  0.7675  |  361.4854   |     6810     |      349      |          0.7509          |         13.5258         |
|    50%     | 87.7938  | 0.0905  |  0.9939  |  478.3213   |     7318     |      407      |          0.8811          |         16.3032         |
|    66%     | 93.5391  | 0.5942  |  1.0807  |  549.0423   |     7646     |      475      |          0.9031          |         18.908          |
|    75%     | 100.222  | 2.0894  |  1.118   |  556.7161   |     7868     |      500      |          0.9787          |         21.5699         |
|    80%     | 108.6323 | 2.1255  |  1.1366  |  587.2937   |     7995     |      500      |          1.0402          |         23.3121         |
|    90%     | 154.3641 |  2.195  |  1.1954  |  655.2437   |     8311     |      500      |          1.4314          |         30.8714         |
|    95%     | 184.9905 | 3.3221  |  1.2291  |   700.129   |     8586     |      500      |          2.0466          |         41.3329         |
|    98%     | 268.8557 | 3.8601  |  1.348   |  747.0711   |     9180     |      500      |          2.7861          |         51.4136         |
|    99%     | 295.0391 | 4.1128  |  1.4306  |   838.265   |     9631     |      500      |          3.3498          |         56.2532         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

**Result: longalpaca, 300 concurrent, 2000 requests, input 256+, output 1024**

```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 2191.3567                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 934.5808                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 8392.5007                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 128.5064                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 8171.4815                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 1024.0                                                         |
+-----------------------------------+----------------------------------------------------------------+
```

<details>
<summary>Percentile results (click to expand)</summary>

```
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 41.3834  | 0.0871  |  0.1108  |  218.1732   |     6429     |     1024      |          2.2751          |         18.3404         |
|    25%     | 65.6466  | 0.0909  |  0.1343  |   221.82    |     6885     |     1024      |          2.5992          |         25.8683         |
|    50%     | 103.9827 | 0.0956  |  0.1726  |  280.8245   |     7435     |     1024      |          3.6464          |         33.5236         |
|    66%     | 132.7753 | 0.0984  |  0.1946  |  344.4832   |     7838     |     1024      |          4.6139          |         37.0172         |
|    75%     | 170.3912 | 0.1015  |  0.2084  |  393.9659   |     8121     |     1024      |          4.6164          |         38.6355         |
|    80%     | 206.7594 | 0.1038  |  0.2216  |  394.0702   |     8346     |     1024      |          4.6545          |         39.6021         |
|    90%     | 244.5239 |  0.117  |  0.261   |  450.0822   |    13155     |     1024      |          4.6935          |         41.9353         |
|    95%     | 300.2397 | 0.1237  |  0.3054  |  564.1507   |    14847     |     1024      |          4.6949          |         44.1926         |
|    98%     | 403.7368 | 0.1278  |  0.3406  |  738.5439   |    15954     |     1024      |          4.6959          |         46.9588         |
|    99%     | 431.8423 | 0.2345  |  0.3603  |  738.5612   |    16321     |     1024      |          4.6963          |         50.2519         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```

</details>

### EvalScope Stress Testing Qwen 2.5 72B with Custom C3 Dataset

```bash
# Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

# Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

# MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

# MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

# Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

# Reasoning-S3-high 512→1024
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in [**results2.txt**](PoC-Handbook-for-Azure-AMD-MI300X/results2.txt).

---

## Part 5: Qwen 2.5 VL 7B on MI300X (Step-by-Step)

This section provides a complete step-by-step guide for deploying and testing Qwen2.5-VL-7B-Instruct on AMD MI300X using vLLM with ROCm.

Reference: https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/models/qwen2_5_vl.py

### 1. Pull vLLM ROCm Image

```bash
docker pull rocm/vllm-dev:main
```

Image size is ~6 GB. Verify:

```bash
docker images | grep vllm-dev
# rocm/vllm-dev   main   9a9582e6...   6.2GB
```

### 2. Create Host Shared Directory

```bash
mkdir -p $HOME/dockerx/{models,data}
```

### 3. Run Container

```bash
docker run -it --network host \
  --device=/dev/kfd --device=/dev/dri \
  --ipc=host --shm-size 16G --group-add video \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v $HOME/dockerx:/dockerx \
  rocm/vllm-dev:main
```

If you see `docker: unknown server OS:`, you're likely running docker inside a container — `exit` back to the host first.

### 4. Verify vLLM and Model Plugin

```python
python - <<'PY'
import vllm, importlib.util
print("vLLM:", vllm.__version__)
print("Qwen2.5-VL module:",
      bool(importlib.util.find_spec("vllm.model_executor.models.qwen2_5_vl")))
PY
```

Expected:

```
vLLM: 0.7.4.dev388...
Qwen2.5-VL module: True
```

If the module is False:

```bash
pip install --no-cache-dir --upgrade 'vllm[rocm]' flash-attn-rocm xformers
```

### 5. Download Qwen2.5-VL-7B-Instruct Weights

```bash
export HUGGING_FACE_HUB_TOKEN=hf_xxx          # Replace with your token
cd /dockerx/models
huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct \
    --local-dir Qwen2_5-VL-7B
```

Download is ~20 GB; the directory will contain 5 `model-0000*-of-00005.safetensors` files.

### 6. Text-Only Latency Benchmark

```bash
python /app/vllm/benchmarks/benchmark_latency.py \
  --model /dockerx/models/Qwen2_5-VL-7B \
  --input-len 1024 --output-len 1024 \
  --batch-size 1 --num-iters 5 --num-iters-warmup 2 \
  --dtype float16 --max_model_len 4096
```

Results:

```
Avg latency: 6.52 seconds
p50 6.52 | p90 6.53 | p99 6.53
```

Server-side metrics during profiling:

```
Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s
```

Note: This benchmark uses only 1 GPU (single-card inference, TP=1, world_size=1). The 191 GiB total GPU memory corresponds to a single MI300X card. For multi-GPU testing:

```bash
export HIP_VISIBLE_DEVICES=0,1,2,3
python ... --tensor-parallel-size 4
```

### 7. Multimodal Inference Demo

Prepare image:

```bash
apt-get update
apt-get install -y wget
mkdir -p /dockerx/data
wget -O /dockerx/data/test.jpg \
  https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
```

Create script `/dockerx/data/qwen_vl_demo.py`:

```python
from vllm import LLM, SamplingParams
from transformers import Qwen2_5_VLProcessor
from PIL import Image

MODEL = "/dockerx/models/Qwen2_5-VL-7B"
IMG   = "/dockerx/data/test.jpg"

llm  = LLM(model=MODEL, dtype="float16")
proc = Qwen2_5_VLProcessor.from_pretrained(MODEL, trust_remote_code=True)

batch = proc(text="请描述这张图片。", images=Image.open(IMG), return_tensors="pt")

out = llm.generate(
    input_ids       = batch["input_ids"],
    sampling_params = SamplingParams(max_tokens=64, temperature=0.2),
    pixel_values    = batch["pixel_values"],
    image_grid_thw  = batch["image_grid_thw"]
)
print(out[0].outputs[0].text)
```

Run:

```bash
python /dockerx/data/qwen_vl_demo.py
```

Expected output: A Chinese description of the image content.

If `RuntimeError: ... backend not supported`:

```bash
pip install --force-reinstall flash-attn-rocm==2.5.6 xformers
```

Or temporarily:

```bash
export VLLM_ATTEN_BACKEND=torch
```

### 8. Exit and Reuse

```bash
exit   # Exit container
```

To reuse: repeat step 3 with the same image and mount directory — the model is already at `/dockerx/models`.

---

## Part 6: Additional Models and Resources

### Megatron-LM for Qwen2-VL Training

If using Megatron-LM framework to train Qwen2-VL on AMD GPUs, simply replace the kernel load function from NVIDIA's version:

- NVIDIA: https://github.com/NVIDIA/Megatron-LM/blob/4429e8ebe21fb011529d7401c370841ce530785a/megatron/legacy/fused_kernels/__init__.py#L17
- AMD: https://github.com/ROCm/Megatron-LM/blob/rocm_dev/megatron/legacy/fused_kernels/__init__.py#L18

### Llama 4 on AMD

Reference: https://rocm.blogs.amd.com/artificial-intelligence/llama4-day-0-support/README.html#how-to-run-llama4-on-line-inference-mode-with-vllm-on-amd-instinct-gpus

Make sure to pull the latest recommended image (currently `rocm/vllm-dev:llama4-20250407`).

Enabling V1 can also improve performance: `VLLM_USE_V1=1`

### vLLM Setup on NVads V710 v5-series

Reference: https://github.com/dasilvajm/V710-VLLM-inference

### AMD Fine-Tuning

Reference: https://github.com/ROCm/gpuaidev/blob/main/docs/notebooks/fine_tune/fine_tuning_lora_qwen2vl.ipynb

### AMD Performance Test Reports

Reference: https://github.com/ROCm/MAD/tree/develop/benchmark

### Qwen3 Docker Image Support

The `rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410` image supports Qwen3 with a relatively new vLLM version.

---

## Troubleshooting

| Error | Fix |
| ----- | --- |
| Cannot connect to the Docker daemon | `systemctl enable --now docker` (run on host) |
| docker: unknown server OS | You ran `docker` inside a container → `exit` back to host |
| ModuleNotFoundError: qwen2_5_vl | `pip install -U 'vllm[rocm]' flash-attn-rocm` |
| 401/404 download failure | Set `HUGGING_FACE_HUB_TOKEN`, check model name spelling |
| backend not supported (flash-attn) | Reinstall flash-attn-rocm; or `export VLLM_ATTEN_BACKEND=torch` |
| GPU OOM | Lower `--batch-size` / reduce `gpu_memory_utilization` |
| `rocm-smi` command not found | Complete ROCm 6.3 installation and reboot |

---

## References

- [Running DeepSeek R1 on a single NDv5 MI300X VM](https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726)
- [AMD ROCm Llama 4 Day-0 Support](https://rocm.blogs.amd.com/artificial-intelligence/llama4-day-0-support/README.html)
- [AMD MAD Benchmarks](https://github.com/ROCm/MAD/tree/develop/benchmark)
- [V710 VLLM Inference](https://github.com/dasilvajm/V710-VLLM-inference)
- [AMD LoRA Fine-Tuning Qwen2-VL](https://github.com/ROCm/gpuaidev/blob/main/docs/notebooks/fine_tune/fine_tuning_lora_qwen2vl.ipynb)
- [AMD Megatron-LM ROCm Fork](https://github.com/ROCm/Megatron-LM/blob/rocm_dev/)



## Reproducing the Results

### Prerequisites

- Python 3.10+
- CUDA-compatible GPU (recommended)

### Setup

```bash
git clone <this-repo-url>
cd <repo-name>
```
