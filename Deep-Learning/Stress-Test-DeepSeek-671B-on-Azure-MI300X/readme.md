## PoC Handbook for Azure AMD MI300X

This repository aims to help you quickly deploy and validate performance of open-source flagship models on Azure NDMI300X.

Currently included models: 

- DeepSeek R1 671B
- Qwen2.5 72B

### Azure ND MI300X GPU VM Environment Setup

Quickly create a Spot VM, using Spot VM and password-based authentication:

```
az vm create --name <VMNAME> --resource-group <RESOURCE_GROUP_NAME> --location <REGION>  --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 256 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password <YOUR_PASSWORD> 

```

Taking the CLI command I used for creating VM as an example:

```
xinyu [ ~ ]$ az vm create --name mi300x-xinyu --resource-group amdrg --location westus --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 512 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password azureadmin@123  


```
VM Deployment Steps:

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
  "publicIpAddress": "13.64.8.207",
  "resourceGroup": "amdrg",
  "zones": ""
}
```

After the system is successfully deployed, open port 22 on the VM's NSG.

Then SSH into the VM and perform the following environment configuration steps.

For testing, use the local NVME temporary disk as the docker runtime environment. Note that after VM restart, data stored on the temporary disk will be lost. This approach is suitable for fast, low-cost testing scenarios. However, for production scenarios, a persistent file system should be used.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/1.png)

```
mkdir -p /mnt/resource_nvme/
sudo mdadm --create /dev/md128 -f --run --level 0 --raid-devices 8 $(ls /dev/nvme*n1)  
sudo mkfs.xfs -f /dev/md128 
sudo mount /dev/md128 /mnt/resource_nvme 
sudo chmod 1777 /mnt/resource_nvme  
```

First, create a mount directory for RAID0:

```
mkdir –p /mnt/resource_nvme/hf_cache 
export HF_HOME=/mnt/resource_nvme/hf_cache 
```

Configure RAID0 and designate it for Docker usage.

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

### Launch DeepSeek R1 671B using SGLang

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

Once you see output similar to the following, it indicates that the container has successfully started and is ready to accept external requests:

```
[2025-04-01 03:42:11 DP7 TP7] Prefill batch. #new-seq: 1, #new-token: 7, #cached-token: 0, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 03:42:15] INFO:     127.0.0.1:37762 - "POST /generate HTTP/1.1" 200 OK
[2025-04-01 03:42:15] The server is fired up and ready to roll!
[2025-04-01 04:00:11] INFO:     172.17.0.1:55994 - "POST /v1/chat/completions HTTP/1.1" 200 OK
[2025-04-01 04:00:11 DP0 TP0] Prefill batch. #new-seq: 1, #new-token: 5, #cached-token: 1, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 04:00:43] INFO:     172.17.0.1:41068 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

Ensure local accessibility to the DeepSeek 671B container:

```
curl http://localhost:30000/get_model_info 
{"model_path":"deepseek-ai/DeepSeek-R1","tokenizer_path":"deepseek-ai/DeepSeek-R1","is_generation":true} 
curl http://localhost:30000/generate -H "Content-Type: application/json" -d '{ "text": "Once upon a time,", "sampling_params": { "max_new_tokens": 16, "temperature": 0.6 } }'
```

Next, open port 30000 on Azure NSG for remote access testing.

### Stress test DeepSeek R1 671B using SGLang with EvalScope's default dataset.

Log into the Linux stress-testing client and execute the following CLI commands to install the evalscope stress-testing tool:

```
pip install -U "evalscope[perf,dataset]" \
    @ git+https://github.com/modelscope/evalscope.git@main
pip install gradio
```

Then use evalscope to perform stress testing. This tool supports specifying concurrency, total requests, input and output tokens, and test datasets.

- If you want to maximize total throughput, increase concurrency while reducing the number of input tokens per request. For example, use 100 concurrent requests with 100 input tokens each, focusing on the overall tokens/s metric.
- If you want to test single-request performance, decrease concurrency and increase the number of input tokens per request, paying attention to the Time-to-First-Token (TTFT) and tokens/s metrics of individual requests.

In the test, I used a relatively extreme scenario with an input of 10,000 tokens.

```
evalscope perf --url http://mi300x-xinyu.westus.cloudapp.azure.com:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --parallel 1 --number 20 --api openai --min-prompt-length 10000 --dataset "longalpaca" --max-tokens 2048 --min-tokens 2048 --stream 
```

Next, I will list test results for several scenarios with different concurrency levels and request counts.

Single concurrency:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/2.jpg)

5 Concurrent Requests:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/3.jpg)

10 Concurrent Requests:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/4.jpg)

**Note**: Additional performance parameters

```
--enable-torch-compile
```

This parameter is currently not supported in the AMD MI300X environment.

```
--enable-dp-attention
```

This parameter is supported in the AMD environment. However, it doesn't improve performance under low concurrency scenarios. Its effectiveness under high concurrency scenarios requires further observation.



#### Stress test DeepSeek R1 671B using SGLang with EvalScope's customized dataset.

In many cases, EvalScope's default dataset might not meet our specific requirements. In this section, I will demonstrate the steps to conduct stress testing on DeepSeek R1 671B using the customized C3 dataset.

Prepare C³-dialog dataset → JSONL format:

```
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

Perform stress testing on DeepSeek R1 671B using a customized dataset.

```
DeepSeek-R1（30000 端口） 1️⃣ Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

2️⃣ Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

3️⃣ MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

4️⃣ MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

5️⃣ Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

6️⃣ Reasoning-S3-high 512→1024 172.167.140.16
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in **result.txt**.



### Launch Qwen 2.5 72B using vLLM

Start container：

```
docker run -d --name qwen72b_8x --device=/dev/kfd --device=/dev/dri --privileged --security-opt seccomp=unconfined --cap-add SYS_PTRACE -p 8080:8080 -v /mnt/resource_nvme:/mnt/resource_nvme -e HF_HOME=/mnt/resource_nvme/hf_cache -e HSA_NO_SCRATCH_RECLAIM=1 rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410 python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-72B-Instruct --dtype bfloat16 --tensor-parallel-size 8 --max-num-batched-tokens 60000 --tokenizer-pool-size 8 --tokenizer-pool-type ray --swap-space 4 --gpu-memory-utilization 0.9 --port 8080 --host 0.0.0.0 --trust-remote-code
```



**Stress test Qwen 2.5 72B  using SGLang with EvalScope's customized dataset.**

```
Qwen-2.5-72B（8080 端口） 7️⃣ Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

8️⃣ Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

9️⃣ MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

🔟 MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

1️⃣1️⃣ Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

1️⃣2️⃣ Reasoning-S3-high 512→1024
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in **result.txt**.



**Refer to:**

*https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726*
