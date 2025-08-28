## OpenAI OSS Model on Azure 

The **gpt-oss-120b** model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The **gpt-oss-20b** model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/30.png)

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



## gpt-oss-20b on Azure AKS Spot VM

vLLM also support an new container image vllm/vllm-openai:gptoss, which could run on AKS + KAITO + Azure Spot VM.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/29.png)

**Why use KAITO on AKS?**

• One-click GPU enablement
– Installs and maintains the NVIDIA device-plugin and runtime class automatically.
– No manual driver or privileged-pod setup.

• Spot-friendly GPU orchestration
– Adds the correct tolerations and reschedules workloads on eviction, keeping Spot A100 nodes usable with minimal downtime.

• Workspace isolation
– Each Workspace gets its own namespace, quotas, RBAC, and metrics, giving team-level separation without extra YAML.

• Built-in lifecycle automation
– Handles node provisioning, rolling upgrades, and GPU health checks; you focus on the model, not the plumbing.

• Unified observability and security
– Ships with metrics, logs, and policy hooks integrated into Azure AD and Prometheus/Grafana stacks.

Without KAITO you must: install the device-plugin, patch tolerations, manage RuntimeClass, create quotas, handle Spot evictions, and wire up monitoring yourself—KAITO does all that out of the box.

**Note:**

Reasons this approach cannot use KAITO Workspace directly:

- The Workspace CRD/controller does not support declaring Spot capacity in the manifest.
- Subscription policies block NodeClaim creation: when the Workspace attempts to auto-provision a GPU pool via NodeClaim, Azure Policy denies it (RequestDisallowedByPolicy), causing the temporary VM Scale Set (VMSS) creation to fail and the Workspace to remain stuck (never reaches Running).
- Device plugin Spot taint: KAITO’s built-in NVIDIA device-plugin DaemonSet does not include a Spot toleration by default, so it cannot schedule onto Spot nodes and those nodes will not register nvidia.com/gpu. This is addressed in the script below.The built-in KAITO DaemonSet `kaito-nvidia-device-plugin-daemonset` does not include a Spot VM toleration by default**Add the missing toleration (and a nodeSelector) so the plugin pod can be scheduled onto the Spot A100 nodes.

Total script from scrash:

```
(base) root@linuxworkvm:~# cat deploy_aks_a100_spot.sh
```

```1
#!/usr/bin/env bash
set -euo pipefail

RANDOM_ID=${RANDOM_ID:-$RANDOM}
REGION=${REGION:-southeastasia}
RG=${RG:-kaito-rg-$RANDOM_ID}
CLUSTER=${CLUSTER:-kaito-aks-$RANDOM_ID}
GPU_POOL=${GPU_POOL:-a100spot}
GPU_SKU=${GPU_SKU:-Standard_NC24ads_A100_v4}
SYS_NODE_COUNT=${SYS_NODE_COUNT:-1}
GPU_NODE_COUNT=${GPU_NODE_COUNT:-1}
MODEL=${MODEL:-openai/gpt-oss-20b}

az group create --name "$RG" --location "$REGION" -o none
az aks create --resource-group "$RG" --name "$CLUSTER" --location "$REGION" --node-count "$SYS_NODE_COUNT" --enable-ai-toolchain-operator --enable-oidc-issuer --generate-ssh-keys -o none
az aks nodepool add --resource-group "$RG" --cluster-name "$CLUSTER" --name "$GPU_POOL" --node-vm-size "$GPU_SKU" --priority Spot --eviction-policy Delete --node-count "$GPU_NODE_COUNT" -o none
az aks get-credentials --resource-group "$RG" --name "$CLUSTER" --overwrite-existing

for i in $(seq 1 60); do
  READY=$(kubectl get nodes --no-headers | awk '$2=="Ready"' | wc -l)
  TOTAL=$(kubectl get nodes --no-headers | wc -l)
  [ "$READY" -eq "$TOTAL" ] && [ "$TOTAL" -ge 2 ] && break
  sleep 10
done

kubectl -n kube-system patch ds kaito-nvidia-device-plugin-daemonset --type=merge -p "{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":{\"kubernetes.azure.com/agentpool\":\"${GPU_POOL}\"},\"tolerations\":[{\"key\":\"kubernetes.azure.com/scalesetpriority\",\"operator\":\"Equal\",\"value\":\"spot\",\"effect\":\"NoSchedule\"},{\"key\":\"nvidia.com/gpu\",\"operator\":\"Exists\",\"effect\":\"NoSchedule\"},{\"key\":\"sku\",\"operator\":\"Equal\",\"value\":\"gpu\",\"effect\":\"NoSchedule\"}]}}}}"
kubectl -n kube-system rollout status ds/kaito-nvidia-device-plugin-daemonset --timeout=5m || true

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-a100
  labels: {app: vllm-a100}
spec:
  replicas: 1
  selector: {matchLabels: {app: vllm-a100}}
  template:
    metadata: {labels: {app: vllm-a100}}
    spec:
      nodeSelector: {kubernetes.azure.com/agentpool: ${GPU_POOL}}
      tolerations:
      - {key: kubernetes.azure.com/scalesetpriority, operator: Equal, value: spot, effect: NoSchedule}
      - {key: nvidia.com/gpu, operator: Exists, effect: NoSchedule}
      containers:
      - name: vllm
        image: vllm/vllm-openai:gptoss
        args: ["--model", "${MODEL}", "--port", "5000", "--swap-space", "8", "--gpu-memory-utilization", "0.85"]
        env:
        - {name: VLLM_DISABLE_SINKS, value: "1"}
        - {name: VLLM_ATTENTION_BACKEND, value: "TRITON_ATTN_VLLM_V1"}
        ports: [{containerPort: 5000}]
        resources:
          limits: {nvidia.com/gpu: 1, cpu: "24", memory: "200Gi"}
          requests: {nvidia.com/gpu: 1, cpu: "18", memory: "180Gi"}
        startupProbe: {httpGet: {path: /health, port: 5000}, periodSeconds: 10, failureThreshold: 360}
        readinessProbe: {httpGet: {path: /health, port: 5000}, periodSeconds: 5}
        livenessProbe: {httpGet: {path: /health, port: 5000}, initialDelaySeconds: 900}
---
apiVersion: v1
kind: Service
metadata: {name: vllm-a100-svc}
spec:
  type: LoadBalancer
  selector: {app: vllm-a100}
  ports: [{port: 5000, targetPort: 5000}]
EOF

kubectl rollout status deploy/vllm-a100 --timeout=30m || true

for i in $(seq 1 120); do
  IP=$(kubectl get svc vllm-a100-svc -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [ -n "$IP" ] && break
  sleep 5
done

curl -s "http://${IP}:5000/health"
curl -s "http://${IP}:5000/v1/models" | jq -r '.'
curl -s -X POST "http://${IP}:5000/v1/chat/completions" -H "Content-Type: application/json" -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"What is Kubernetes?\"}],\"max_tokens\":80,\"temperature\":0}" | jq -r '.choices[0].message.content // .choices[0].message.reasoning_content // .choices[0].message'
```

Output of this script:

```
(base) root@linuxworkvm:~# bash deploy_aks_a100_spot.sh
Merged "kaito-aks-54403" as current context in /root/.kube/config
daemonset.apps/kaito-nvidia-device-plugin-daemonset patched
Waiting for daemon set "kaito-nvidia-device-plugin-daemonset" rollout to finish: 0 of 1 updated pods are available...
Waiting for daemon set "kaito-nvidia-device-plugin-daemonset" rollout to finish: 0 of 1 updated pods are available...
daemon set "kaito-nvidia-device-plugin-daemonset" successfully rolled out
deployment.apps/vllm-a100 created
service/vllm-a100-svc created
Waiting for deployment "vllm-a100" rollout to finish: 0 of 1 updated replicas are available...
Waiting for deployment "vllm-a100" rollout to finish: 0 of 1 updated replicas are available...
deployment "vllm-a100" successfully rolled out
{
  "object": "list",
  "data": [
    {
      "id": "openai/gpt-oss-20b",
      "object": "model",
      "created": 1755913569,
      "owned_by": "vllm",
      "root": "openai/gpt-oss-20b",
      "parent": null,
      "max_model_len": 131072,
      "permission": [
        {
          "id": "modelperm-efc884b7d31645f0a160edf38e014e4d",
          "object": "model_permission",
          "created": 1755913569,
          "allow_create_engine": false,
          "allow_sampling": true,
          "allow_logprobs": true,
          "allow_search_indices": false,
          "allow_view": true,
          "allow_fine_tuning": false,
          "organization": "*",
          "group": null,
          "is_blocking": false
        }
      ]
    }
  ]
}
The user asks: "What is Kubernetes?" They want an explanation. We should provide a concise but thorough answer. Should mention it's an open-source container orchestration platform, originally from Google, now maintained by CNCF. It automates deployment, scaling, and operations of application containers across clusters of hosts. It provides mechanisms for service discovery, load balancing, storage orchestration, automated roll

```

Full test script:

```
(base) root@linuxworkvm:~# kubectl get svc
NAME            TYPE           CLUSTER-IP     EXTERNAL-IP      PORT(S)          AGE
kubernetes      ClusterIP      10.0.0.1       <none>           443/TCP          51m
vllm-a100-svc   LoadBalancer   10.0.120.197   135.171.16.230   5000:31196/TCP   43m
(base) root@linuxworkvm:~# IP=135.171.16.230 bash ./script.sh 
```

Test inference:

```
cat script.sh
```

```
#!/usr/bin/env bash
set -euo pipefail

NS="${NS:-default}"
APP_LABEL="${APP_LABEL:-app=gpt-oss-20b-vllm}"
DEPLOY="${DEPLOY:-gptoss-vllm-a100}"
SVC="${SVC:-gptoss-vllm-a100-pub}"
PORT="${PORT:-5000}"
MODEL="${MODEL:-openai/gpt-oss-20b}"
QUESTION="${QUESTION:-Explain the future of human}"

if ! command -v kubectl >/dev/null 2>&1; then echo "kubectl not found"; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then echo "curl not found"; exit 1; fi
if ! command -v jq >/dev/null 2>&1; then echo "jq not found"; exit 1; fi

if [ $# -ge 1 ]; then
  EXTERNAL_IP="$1"
else
  EXTERNAL_IP="${IP:-}"
fi
if [ -z "${EXTERNAL_IP:-}" ]; then
  EXTERNAL_IP="$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
fi
if [ -z "${EXTERNAL_IP:-}" ]; then
  echo "Unable to get Service external IP. Pass IP as arg or ensure $NS/$SVC has an EXTERNAL-IP"
  exit 1
fi

echo "===== 0) Basics ====="
date
echo "Namespace: ${NS}"
echo "App label: ${APP_LABEL}"
echo "Deployment: ${DEPLOY}"
echo "Service: ${SVC}"
echo "Port: ${PORT}"
echo "Model: ${MODEL}"
echo "Endpoint: http://${EXTERNAL_IP}:${PORT}"
echo

echo "===== 1) Kaito components and CRDs ====="
kubectl get crd | grep -i kaito || true
kubectl -n kube-system get deploy | grep -i kaito || true
kubectl -n kube-system get pods | egrep -i "kaito|device-plugin" || true
echo

echo "===== 2) Kaito Workspaces (if installed) ====="
kubectl get workspace -A || true
echo

echo "===== 3) GPU nodes and device plugins ====="
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPUS:.status.allocatable.nvidia\.com/gpu,AGENTPOOL:.metadata.labels.kubernetes\.azure\.com/agentpool --no-headers || true
kubectl -n kube-system get ds | grep -i device-plugin || true
kubectl -n kube-system get pods -o wide | grep -i device-plugin || true
echo

echo "===== 4) Inference workload and Service ====="
kubectl -n "${NS}" get deploy "${DEPLOY}" -o wide || true
kubectl -n "${NS}" get pods -l "${APP_LABEL}" -o wide || true
kubectl -n "${NS}" get svc "${SVC}" -o wide || true
echo

echo "===== 5) Run nvidia-smi in inference Pod ====="
POD="$(kubectl -n "${NS}" get pod -l "${APP_LABEL}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [ -n "${POD:-}" ]; then
  kubectl -n "${NS}" exec "${POD}" -- nvidia-smi || true
else
  echo "No Pod found for label ${APP_LABEL}"
fi
echo

echo "===== 6) Health check ====="
HTTP_CODE="$(curl -sS -o /dev/null -w "%{http_code}" "http://${EXTERNAL_IP}:${PORT}/health" || true)"
echo "GET /health -> HTTP ${HTTP_CODE}"
echo

echo "===== 7) List models and run a test question ====="
curl -sS "http://${EXTERNAL_IP}:${PORT}/v1/models" | jq -r '.' || true
echo
REQ="$(jq -n --arg m "$MODEL" --arg q "$QUESTION" '{model:$m,messages:[{role:"user",content:$q}],max_tokens:1000,temperature:1}')"
RESP_JSON="$(curl -sS -X POST "http://${EXTERNAL_IP}:${PORT}/v1/chat/completions" -H "Content-Type: application/json" -d "$REQ" || true)"
THOUGHT="$(echo "$RESP_JSON" | jq -r '.choices[0].message.reasoning_content // ""')"
ANSWER="$(echo "$RESP_JSON" | jq -r '.choices[0].message.content // ""')"
echo "Thought process:"
echo "$THOUGHT"
echo
echo "Final answer:"
echo "$ANSWER"
if [ -z "$THOUGHT" ] && [ -z "$ANSWER" ]; then
  echo
  echo "Raw response:"
  echo "$RESP_JSON"
fi
echo

echo "===== 8) Summary ====="
READY_CNT="$(kubectl -n "${NS}" get pods -l "${APP_LABEL}" -o jsonpath='{range .items[*]}{.status.containerStatuses[0].ready}{"\n"}{end}' 2>/dev/null | grep -c true || true)"
echo "Ready inference Pods: ${READY_CNT}"
echo "Health /health HTTP code: ${HTTP_CODE}"
echo "Endpoint: http://${EXTERNAL_IP}:${PORT}"
echo "Test question: ${QUESTION}"
echo "Done"
```

Run script:

```
#kubectl get svc
#IP=135.171.16.230 bash script.sh
```



***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/oHPu2-ly9Y8)



For Normal Azure GPU VM and sub，it is more easier, please refer to:

*https://techcommunity.microsoft.com/blog/machinelearningblog/deploying-openai%E2%80%99s-first-open-source-model-on-azure-aks-with-kaito/4444234*

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

## gpt-oss-20b Supervised Fine-Tuning - Bad Case

Overall SFT of gpt-oss is as：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/28.png)

In this part of demo, I will show as folllowing flow to do SFT on gpt-oss.

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

 **Although** the GGUF quantized to MXFP4-MoE can run, extensive testing has shown that the quantization process has significantly weakened the  effect of SFT. Therefore, in the following subsection, I will try other  quantization methods.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/24.png)

## gpt-oss-20b Supervised Fine-Tuning - Good Case

In this part, I quantize model to different data type to chech the SFT effect.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/28.png)

```
cat ./quantize_all.sh
```

```
#!/usr/bin/env bash
set -euo pipefail

LLAMA_BIN_DIR="${LLAMA_BIN_DIR:-/root/llama.cpp/build/bin}"
LLAMA_QUANT="${LLAMA_QUANT:-$LLAMA_BIN_DIR/llama-quantize}"
SRC_FP16="${SRC_FP16:-/root/merged_fp16.gguf}"
OUTDIR="${OUTDIR:-./quant_models}"
RQ_FLAG=""
if [ "${ALLOW_REQUANTIZE:-0}" = "1" ]; then RQ_FLAG="--allow-requantize"; fi

mkdir -p "$OUTDIR"

"$LLAMA_QUANT" $RQ_FLAG "$SRC_FP16" "$OUTDIR/merged_fp16_Q4_K_M.gguf" Q4_K_M
"$LLAMA_QUANT" $RQ_FLAG "$SRC_FP16" "$OUTDIR/merged_fp16_Q5_K_M.gguf" Q5_K_M
"$LLAMA_QUANT" $RQ_FLAG "$SRC_FP16" "$OUTDIR/merged_fp16_Q6_K.gguf"   Q6_K
"$LLAMA_QUANT" $RQ_FLAG "$SRC_FP16" "$OUTDIR/merged_fp16_Q8_0.gguf"   Q8_0

"$LLAMA_QUANT" --help > /tmp/llq_help.txt || true
MX_TYPE=""
for T in MXFP4_MoE MXFP4; do
  if grep -qiE "\b${T}\b" /tmp/llq_help.txt; then
    MX_TYPE="$T"
    break
  fi
done
if [ -n "$MX_TYPE" ]; then
  "$LLAMA_QUANT" $RQ_FLAG "$SRC_FP16" "$OUTDIR/merged_mxfp4.gguf" "$MX_TYPE"
else
  echo "[INFO] MXFP4/MoE quant type not found in this llama-quantize build; skip MXFP4 output."
fi

ls -lh "$OUTDIR" || true
```

quantized models:

```
(base) root@h100vm:~/gpt-oss# ls -al quant_models/
total 75345216
drwxr-xr-x  2 root root        4096 Aug 20 13:15 .
drwxr-xr-x 10 root root        4096 Aug 21 06:08 ..
-rw-r--r--  1 root root 15805136320 Aug 20 13:15 merged_fp16_Q4_K_M.gguf
-rw-r--r--  1 root root 16893062080 Aug 20 13:15 merged_fp16_Q5_K_M.gguf
-rw-r--r--  1 root root 22193344960 Aug 20 13:14 merged_fp16_Q6_K.gguf
-rw-r--r--  1 root root 22261912000 Aug 20 13:13 merged_fp16_Q8_0.gguf
```

Check SFT performance:

```
(base) root@h100vm:~/gpt-oss#cat run_strict_eval_32.py
```

```
#!/usr/bin/env python3
import os
import sys
import json
import csv
import time
import glob
import signal
import socket
import shutil
import subprocess
from pathlib import Path

def ensure_packages():
    pkgs = ["requests", "langdetect"]
    for p in pkgs:
        try:
            __import__(p)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        __import__("pycld3")
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pycld3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

ensure_packages()
import requests
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 42
try:
    from pycld3 import NNetLanguageIdentifier
    _cld3_identifier = NNetLanguageIdentifier(min_num_bytes=0, max_num_bytes=1000)
    CLD3_OK = True
except Exception:
    _cld3_identifier = None
    CLD3_OK = False

def find_llama_server():
    env_path = os.environ.get("LLAMA_SERVER", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    bin_dir = os.environ.get("LLAMA_BIN_DIR", "").strip()
    candidates = []
    if bin_dir:
        candidates.append(str(Path(bin_dir) / "llama-server"))
    home = str(Path.home())
    candidates += [
        "/root/llama.cpp/build/bin/llama-server",
        f"{home}/llama.cpp/build/bin/llama-server",
        "/usr/local/bin/llama-server",
        "/usr/bin/llama-server",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return ""

def pick_free_port(start_port):
    p = start_port
    while p < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                p += 1
    raise RuntimeError("no free port found")

def wait_server_ready_simple(port, timeout):
    url = f"http://127.0.0.1:{port}/completion"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.post(url, json={"prompt": "ping", "n_predict": 1}, timeout=2)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False

def start_server(llama_server, model_path, port, gpu_layers, log_path):
    cmd = [
        llama_server,
        "-m", model_path,
        "--gpu-layers", str(gpu_layers),
        "--port", str(port),
        "--chat-template", "",
        "--reasoning-format", "none",
    ]
    extra = os.environ.get("LLAMA_SERVER_EXTRA", "").strip()
    if extra:
        cmd.extend(extra.split())
    lf = open(log_path, "w")
    proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
    return proc, lf

def stop_server(proc):
    if proc.poll() is None:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

def normalize_lang_name(name):
    s = (name or "").strip().lower()
    if s in ["zh", "zh-cn", "zh_tw", "zh-tw", "chinese", "中文", "汉语", "國語", "普通话", "cn"]:
        return "Chinese"
    if s in ["en", "english", "英文", "us", "gb"]:
        return "English"
    if s in ["es", "spanish", "español", "西班牙语"]:
        return "Spanish"
    if s in ["fr", "french", "français", "法语"]:
        return "French"
    if s in ["de", "german", "deutsch", "德语"]:
        return "German"
    if s:
        return s.title()
    return "unknown"

def code_to_name(code):
    c = (code or "").lower()
    if c.startswith("zh"):
        return "Chinese"
    if c.startswith("en"):
        return "English"
    if c.startswith("es"):
        return "Spanish"
    if c.startswith("fr"):
        return "French"
    if c.startswith("de"):
        return "German"
    return "unknown"

def detect_lang_cld3(text):
    if not CLD3_OK or not text or not text.strip():
        return "unknown"
    try:
        res = _cld3_identifier.FindLanguage(text)
        return code_to_name(res.language)
    except Exception:
        return "unknown"

def detect_lang_ld(text):
    t = (text or "").strip()
    if not t:
        return "unknown"
    try:
        return code_to_name(detect(t))
    except Exception:
        return "unknown"

def cjk_ratio(text):
    if not text:
        return 0.0
    total = 0
    cjk = 0
    for ch in text:
        total += 1
        if "\u4e00" <= ch <= "\u9fff":
            cjk += 1
    return (cjk / total) if total else 0.0

def heuristic_match(text, target_lang):
    tgt = normalize_lang_name(target_lang)
    t = (text or "").strip().lower()
    if not t:
        return False
    if tgt == "Chinese":
        return cjk_ratio(t) >= 0.3
    if tgt == "Spanish":
        sw = [" el ", " la ", " de ", " que ", " y ", " en ", " los ", " las ", " para ", " como ", " porque ", " del "]
        return sum(1 for w in sw if w in f" {t} ") >= 2
    if tgt == "French":
        sw = [" le ", " la ", " les ", " de ", " des ", " et ", " en ", " pour ", " que ", " est ", " aux ", " du "]
        return sum(1 for w in sw if w in f" {t} ") >= 2
    if tgt == "German":
        sw = [" und ", " der ", " die ", " das ", " ist ", " ein ", " eine ", " von ", " zu ", " mit ", " dem ", " den "]
        return sum(1 for w in sw if w in f" {t} ") >= 2
    if tgt == "English":
        sw = [" the ", " and ", " is ", " are ", " of ", " to ", " in ", " for ", " that ", " with ", " on "]
        return sum(1 for w in sw if w in f" {t} ") >= 2
    return False

def adherence_ok(analysis_text, target_lang, strict=True):
    tgt = normalize_lang_name(target_lang)
    det1 = detect_lang_cld3(analysis_text)
    det2 = detect_lang_ld(analysis_text)
    if strict:
        if det1 == tgt and det1 != "unknown":
            return 1, f"{det1}|{det2}"
        if det2 == tgt and det2 != "unknown" and heuristic_match(analysis_text, tgt):
            return 1, f"{det1}|{det2}"
        return 0, f"{det1}|{det2}"
    else:
        if (det1 == tgt and det1 != "unknown") or (det2 == tgt and det2 != "unknown"):
            return 1, f"{det1}|{det2}"
        if heuristic_match(analysis_text, tgt):
            return 1, f"{det1}|{det2}"
        return 0, f"{det1}|{det2}"

def build_analysis_prompt(rlang, question):
    sys_part = (
        f"<|start|>system<|message|>reasoning language: {rlang}\n"
        f"You MUST first output your reasoning inside:\n"
        f"<|start|>assistant<|channel|>analysis<|message|> ... <|end|>\n"
        f"Then output your final answer inside:\n"
        f"<|start|>assistant<|channel|>final<|message|> ... <|end|>\n"
        f"<|end|>"
    )
    user_part = f" <|start|>user<|message|>{question}<|end|> "
    start_analysis = "<|start|>assistant<|channel|>analysis<|message|>"
    return sys_part + user_part + start_analysis

def call_completion(port, prompt, n_predict, temperature, top_p, top_k, seed, timeout_s):
    url = f"http://127.0.0.1:{port}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "stop": ["<|end|>"]
    }
    if seed is not None:
        payload["seed"] = seed
    try:
        r = requests.post(url, json=payload, timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            return data.get("content", "")
        return ""
    except Exception:
        return ""

def extract_analysis(text):
    if not text:
        return ""
    parts = text.split("<|end|>")
    return parts[0].strip() if parts else text.strip()

def evaluate_model(model_path, tag, port, gpu_layers, run_dir, eval_items, n_predict, temp, top_p, top_k, seed, wait_timeout, per_req_timeout, strict_lang, verbose):
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"server_{tag}.log"
    llama_server = find_llama_server()
    if not llama_server:
        print("[ERROR] llama-server not found. Set LLAMA_SERVER or LLAMA_BIN_DIR.")
        return None
    proc, lf = start_server(llama_server, model_path, port, gpu_layers, str(log_path))
    time.sleep(5)
    ok_ready = wait_server_ready_simple(port, wait_timeout)
    if not ok_ready:
        try:
            lf.flush()
        except Exception:
            pass
        print(f"[ERROR] Server not ready for {tag}. Tail log:")
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-200:]
                for line in lines:
                    sys.stdout.write(line)
        except Exception:
            pass
        stop_server(proc)
        try:
            lf.close()
        except Exception:
            pass
        return None
    rows = []
    mname = Path(model_path).name
    csv_path = run_dir / f"{tag}.csv"
    total = len(eval_items)
    for idx, item in enumerate(eval_items, 1):
        rlang = item.get("reasoning_language", "")
        question = item.get("question", "")
        prompt = build_analysis_prompt(rlang, question)
        content_full = call_completion(port, prompt, n_predict, temp, top_p, top_k, seed, per_req_timeout)
        analysis = extract_analysis(content_full)
        ok, detected = adherence_ok(analysis, rlang, strict=strict_lang)
        row = {
            "model_name": mname,
            "quant_type": tag,
            "reasoning_language": rlang,
            "question": question,
            "analysis_text": analysis,
            "analysis_lang_detected": detected,
            "analysis_adherence": ok
        }
        rows.append(row)
        if verbose:
            print(f"[{tag}] {idx}/{total} Rlang={rlang} Detected={detected} OK={ok}")
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    stop_server(proc)
    try:
        lf.close()
    except Exception:
        pass
    return str(csv_path)

def aggregate_dir(outdir):
    files = sorted(glob.glob(str(Path(outdir) / "*.csv")))
    files = [f for f in files if not f.endswith("summary_overview.csv")]
    if not files:
        print("[ERROR] No CSV files to aggregate.")
        return None
    summary = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            rows = []
        if not rows:
            continue
        model_name = rows[0].get("model_name", "")
        quant_type = rows[0].get("quant_type", "")
        by_lang = {}
        for r in rows:
            rl = r.get("reasoning_language", "")
            by_lang.setdefault(rl, {"ok": 0, "tot": 0})
            try:
                by_lang[rl]["ok"] += int(r.get("analysis_adherence", "0"))
            except Exception:
                pass
            by_lang[rl]["tot"] += 1
        for lang, v in by_lang.items():
            pct = 100.0 * v["ok"] / max(1, v["tot"])
            summary.append({
                "model_name": model_name,
                "quant_type": quant_type,
                "reasoning_language": lang,
                "adherence_ok": v["ok"],
                "adherence_total": v["tot"],
                "adherence_pct": f"{pct:.1f}"
            })
    if not summary:
        print("[ERROR] Empty summary.")
        return None
    out_csv = Path(outdir) / "summary_overview.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    totals = {}
    for r in summary:
        key = (r["model_name"], r["quant_type"])
        totals.setdefault(key, {"ok": 0, "tot": 0})
        totals[key]["ok"] += int(r["adherence_ok"])
        totals[key]["tot"] += int(r["adherence_total"])
    ranking = []
    for k, v in totals.items():
        pct = 100.0 * v["ok"] / max(1, v["tot"])
        ranking.append((pct, v["ok"], v["tot"], k[0], k[1]))
    ranking.sort(reverse=True, key=lambda x: x[0])
    print("\n=== Per-language breakdown ===")
    grouped = {}
    for r in summary:
        key = (r["model_name"], r["quant_type"])
        grouped.setdefault(key, []).append(r)
    for k, items in grouped.items():
        print(f"{k[0]} | {k[1]}")
        for it in sorted(items, key=lambda x: x["reasoning_language"]):
            print(f"  {it['reasoning_language']}: {it['adherence_pct']}% ({it['adherence_ok']}/{it['adherence_total']})")
        total_ok = sum(int(x["adherence_ok"]) for x in items)
        total_tot = sum(int(x["adherence_total"]) for x in items)
        total_pct = 100.0 * total_ok / max(1, total_tot)
        print(f"  TOTAL: {total_pct:.1f}% ({total_ok}/{total_tot})\n")
    print("=== Overall Ranking (by TOTAL adherence %) ===")
    for pct, ok, tot, model_name, quant_type in ranking:
        print(f"{model_name} | {quant_type}: {pct:.1f}% ({ok}/{tot})")
    return str(out_csv)

def default_eval_32():
    zh = [
        "中国最长的河流是什么？",
        "太阳系中最大的行星是什么？",
    ]
    en = [
        "What is the capital of Australia?",
        "Who wrote 'Pride and Prejudice'?",
    ]
    es = [
        "¿Cuál es la capital de Japón?",
        "¿Cuál es el océano más grande del mundo?",
    ]
    fr = [
        "Quelle est la capitale de l'Allemagne ?",
        "Quel est l'océan le plus profond ?",
    ]
    de = [
        "Was ist die Hauptstadt von Kanada?",
        "Welcher Fluss ist der längste der Welt?",
    ]
    langs = ["Chinese", "Spanish", "French", "German"]
    items = []
    for q in zh + en + es + fr + de:
        for rl in langs:
            items.append({"reasoning_language": rl, "question": q})
    return items[:32]

def load_eval_set_exact(path_hint):
    if path_hint and Path(path_hint).is_file():
        with open(path_hint, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[:32], path_hint
    here = Path(__file__).resolve().parent
    candidates = [
        here / "eval_set.json",
        here / "quant_eval_suite_strict" / "eval_set.json",
        Path.cwd() / "eval_set.json",
    ]
    for c in candidates:
        if c.is_file():
            with open(c, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data[:32], str(c)
    data = default_eval_32()
    tmp_path = Path.cwd() / "eval_set_autogen_32.json"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data, str(tmp_path)

def main():
    models = [
        ("/root/merged_fp16.gguf", "FP16"),
        ("/root/merged_mxfp4.gguf", "MXFP4_MoE"),
        ("./quant_models/merged_fp16_Q4_K_M.gguf", "Q4_K_M"),
        ("./quant_models/merged_fp16_Q5_K_M.gguf", "Q5_K_M"),
        ("./quant_models/merged_fp16_Q6_K.gguf", "Q6_K"),
        ("./quant_models/merged_fp16_Q8_0.gguf", "Q8_0"),
    ]
    env_models = os.environ.get("MODELS", "").strip()
    if env_models:
        parsed = []
        for part in env_models.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                p, t = part.split(":", 1)
                parsed.append((p.strip(), t.strip()))
            else:
                parsed.append((part, Path(part).stem))
        if parsed:
            models = parsed

    outdir = os.environ.get("OUTDIR", "eval_results_strict")
    gpu_layers = int(os.environ.get("GPU_LAYERS", "25"))
    base_port = int(os.environ.get("BASE_PORT", "8081"))
    mxfp4_port_env = int(os.environ.get("MXFP4_PORT", "8080"))
    n_predict = int(os.environ.get("N_PREDICT", "480"))
    wait_timeout = int(os.environ.get("WAIT_TIMEOUT", "300"))
    per_req_timeout = int(os.environ.get("REQ_TIMEOUT", "180"))
    temperature = float(os.environ.get("TEMPERATURE", "0.8"))
    top_p = float(os.environ.get("TOP_P", "1.0"))
    top_k = int(os.environ.get("TOP_K", "0"))
    seed_env = os.environ.get("SEED", "").strip()
    seed = int(seed_env) if seed_env else None
    verbose = os.environ.get("VERBOSE", "1") != "0"
    clean = os.environ.get("CLEAN", "1") == "1"
    strict_lang = os.environ.get("STRICT_LANG", "1") == "1"
    eval_hint = os.environ.get("EVAL_SET_JSON", "").strip()

    eval_items, eval_path_used = load_eval_set_exact(eval_hint)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path(outdir) / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for f in Path(outdir).glob("*.csv"):
            try:
                f.unlink()
            except Exception:
                pass

    print(f"[INFO] Using eval set: {eval_path_used} ({len(eval_items)} items)")
    print(f"[INFO] Output run dir: {run_dir}")

    produced = []
    used_ports = set()
    for path, tag in models:
        if not Path(path).is_file():
            print(f"[WARN] Skip {tag}: file not found: {path}")
            continue
        if tag == "MXFP4_MoE":
            port = mxfp4_port_env
            if port in used_ports:
                port = pick_free_port(mxfp4_port_env)
        else:
            port = pick_free_port(base_port)
        used_ports.add(port)
        print(f"[RUN] {tag}: starting llama-server on port {port} (gpu-layers={gpu_layers})")
        csv_path = evaluate_model(path, tag, port, gpu_layers, run_dir, eval_items, n_predict, temperature, top_p, top_k, seed, wait_timeout, per_req_timeout, strict_lang, verbose)
        if csv_path:
            produced.append(csv_path)
            print(f"[DONE] {tag}: results -> {csv_path}")
        else:
            print(f"[FAIL] {tag}: no results")

    if not produced:
        print("[ERROR] No CSV produced. Abort aggregation.")
        return

    summary_path = aggregate_dir(run_dir)
    if summary_path:
        latest_link = Path(outdir) / "latest"
        try:
            if latest_link.is_symlink() or latest_link.exists():
                if latest_link.is_dir():
                    shutil.rmtree(latest_link, ignore_errors=True)
                else:
                    latest_link.unlink()
            os.symlink(run_dir.name, latest_link, target_is_directory=True)
        except Exception:
            pass
        print(f"[INFO] Summary CSV: {summary_path}")
        print(f"[INFO] Logs: {run_dir}/logs")
        print(f"[INFO] Latest symlink: {Path(outdir) / 'latest'}")

if __name__ == "__main__":
    main()
```

Run script:

```
(gpt-oss) root@h100vm:~/gpt-oss# GPU_LAYERS=25 ./run_strict_eval_32.py
```

Result:

```
=== Per-language breakdown ===
merged_fp16.gguf | FP16
  Chinese: 37.5% (3/8)
  French: 37.5% (3/8)
  German: 50.0% (4/8)
  Spanish: 37.5% (3/8)
  TOTAL: 40.6% (13/32)

merged_mxfp4.gguf | MXFP4_MoE
  Chinese: 12.5% (1/8)
  French: 25.0% (2/8)
  German: 0.0% (0/8)
  Spanish: 25.0% (2/8)
  TOTAL: 15.6% (5/32)

merged_fp16_Q4_K_M.gguf | Q4_K_M
  Chinese: 37.5% (3/8)
  French: 12.5% (1/8)
  German: 12.5% (1/8)
  Spanish: 50.0% (4/8)
  TOTAL: 28.1% (9/32)

merged_fp16_Q5_K_M.gguf | Q5_K_M
  Chinese: 37.5% (3/8)
  French: 50.0% (4/8)
  German: 37.5% (3/8)
  Spanish: 50.0% (4/8)
  TOTAL: 43.8% (14/32)

merged_fp16_Q6_K.gguf | Q6_K
  Chinese: 50.0% (4/8)
  French: 37.5% (3/8)
  German: 37.5% (3/8)
  Spanish: 37.5% (3/8)
  TOTAL: 40.6% (13/32)

merged_fp16_Q8_0.gguf | Q8_0
  Chinese: 50.0% (4/8)
  French: 37.5% (3/8)
  German: 37.5% (3/8)
  Spanish: 62.5% (5/8)
  TOTAL: 46.9% (15/32)

=== Overall Ranking (by TOTAL adherence %) ===
merged_fp16_Q8_0.gguf | Q8_0: 46.9% (15/32)
merged_fp16_Q5_K_M.gguf | Q5_K_M: 43.8% (14/32)
merged_fp16.gguf | FP16: 40.6% (13/32)
merged_fp16_Q6_K.gguf | Q6_K: 40.6% (13/32)
merged_fp16_Q4_K_M.gguf | Q4_K_M: 28.1% (9/32)
merged_mxfp4.gguf | MXFP4_MoE: 15.6% (5/32)
```

**Explaination of the evaluation result:** 

1. Why some quantized models score higher than FP16 on your metric

- Your metric is language adherence, not answer accuracy. It rewards “writing the analysis in the requested language,” not “being correct.”
- Quantization changes the logit distribution. With the same sampling settings, quantized models often behave more conservative/template-like. They tend to produce high-frequency function words and stock phrases in the target language, which align well with stopword-based heuristics and language detectors.
- Less code-mixing. FP16 is more fluent and more likely to mix English terms or named entities in the analysis; detectors then label the segment as English/unknown. Quantized models often output shorter, single-language sentences, which boosts adherence.
- Detector/heuristic bias. Short or entity-heavy text hurts detectors; stock phrases help them. This inherently benefits models that produce template-like outputs (often the quantized ones).
- Even with the same seed, decoding paths differ across models because logits differ; that can shift detection outcomes.

1. Why MXFP4-MoE is so low

- MoE is highly sensitive to quantization. Aggressive formats like MXFP4 without MoE-specific handling can degrade expert routing/gating, leading to unstable style and poor adherence to language instructions.
- Inference stack support varies. Some builds can load MoE+MXFP4 but don’t fully exercise expert routing or handle caches/layout properly, effectively degrading the model into something that outputs short/English/empty analysis segments.
- Protocol mismatch with your analysis extraction. If the model doesn’t reliably emit the analysis block and the <|end|> marker, your extraction returns empty/short segments → scored as 0.
- Resource/param mismatch. High GPU offload, longer n_predict, and higher temperature can further destabilize an already fragile MoE-quantized model.





Run individual model:

```
(gpt-oss) root@h100vm:~/gpt-oss# cat check_reasoning_cn.sh
```

```
#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-./quant_models/merged_fp16_Q5_K_M.gguf}"
GPU_LAYERS="${GPU_LAYERS:-25}"
PORT="${PORT:-8098}"
QUESTION="${QUESTION:-What is the national symbol of Canada?}"
TEMPERATURE="${TEMPERATURE:-0.2}"
N_PREDICT="${N_PREDICT:-256}"
WAIT_TIMEOUT=300
LOG_FILE="check_cn.log"
PID_FILE=".llama_check_cn.pid"

find_llama_server() {
  if [[ -n "${LLAMA_SERVER:-}" && -x "${LLAMA_SERVER}" ]]; then echo "${LLAMA_SERVER}" && return; fi
  if [[ -n "${LLAMA_BIN_DIR:-}" && -x "${LLAMA_BIN_DIR}/llama-server" ]]; then echo "${LLAMA_BIN_DIR}/llama-server" && return; fi
  for p in \
    "/root/llama.cpp/build/bin/llama-server" \
    "${HOME}/llama.cpp/build/bin/llama-server" \
    "/usr/local/bin/llama-server" \
    "/usr/bin/llama-server"; do
    [[ -x "$p" ]] && { echo "$p"; return; }
  done
}

probe_ready() {
  local port="$1"
  curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1 && return 0
  curl -fsS -X POST "http://127.0.0.1:${port}/completion" \
    -H 'Content-Type: application/json' \
    -d '{"prompt":"ping","n_predict":1}' >/dev/null 2>&1 && return 0
  return 1
}

wait_server() {
  local port="$1" timeout_s="$2" t0=$(date +%s)
  while true; do
    if probe_ready "$port"; then return 0; fi
    sleep 2
    (( $(date +%s) - t0 > timeout_s )) && return 1
  done
}

detect_lang_py() {
python3 - "$1" <<'PY'
import sys
from langdetect import detect
try:
    from pycld3 import NNetLanguageIdentifier
    cld3 = NNetLanguageIdentifier(min_num_bytes=0, max_num_bytes=1000)
except Exception:
    cld3=None

txt=sys.argv[1].strip()
def code2(lang):
    l=lang.lower()
    if l.startswith("zh"): return "Chinese"
    if l.startswith("en"): return "English"
    if l.startswith("es"): return "Spanish"
    if l.startswith("fr"): return "French"
    if l.startswith("de"): return "German"
    return lang

ld=cld="unknown"
if txt:
    try: ld=code2(detect(txt))
    except: pass
    if cld3:
        try: cld=code2(cld3.FindLanguage(txt).language)
        except: pass
print(f"langdetect={ld}, cld3={cld}")
PY
}

# 1. 启动 server
srv=$(find_llama_server)
[[ -n "$srv" ]] || { echo "[ERROR] llama-server not found"; exit 1; }
echo "[INFO] 启动: $MODEL_PATH (port=$PORT)"
nohup "$srv" -m "$MODEL_PATH" --gpu-layers "$GPU_LAYERS" --port "$PORT" \
  --chat-template "" --reasoning-format none >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 5
wait_server "$PORT" "$WAIT_TIMEOUT" || { echo "[ERROR] 启动失败"; tail -n 20 "$LOG_FILE"; kill $(cat "$PID_FILE"); exit; }

# 2. 构造 prompt（analysis only）
PROMPT="<|start|>system<|message|>reasoning language: Chinese
You MUST first output your reasoning inside:
<|start|>assistant<|channel|>analysis<|message|> ... <|end|>
Then output your final answer inside:
<|start|>assistant<|channel|>final<|message|> ... <|end|>
<|end|> <|start|>user<|message|>${QUESTION}<|end|> <|start|>assistant<|channel|>analysis<|message|>"

echo "[INFO] 发送问题: $QUESTION"
resp=$(curl -s -X POST "http://127.0.0.1:${PORT}/completion" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg p "$PROMPT" --argjson t "$TEMPERATURE" \
        --argjson n "$N_PREDICT" \
        '{prompt:$p, temperature:$t, n_predict:$n, stop:["<|end|>"], stream:false}')")

analysis=$(echo "$resp" | jq -r '.content // empty')
echo
echo "[Analysis 段输出]"
echo "$analysis"
echo
lang_info=$(detect_lang_py "$analysis")
echo "[语言检测] $lang_info"

[[ "$lang_info" == *"Chinese"* ]] && echo "✅ 符合 REASONING_LANGUAGE: Chinese" || echo "❌ 不符合 REASONING_LANGUAGE: Chinese"

# 3. 停止 server
kill $(cat "$PID_FILE") >/dev/null 2>&1 || true
rm -f "$PID_FILE"
```

```
(gpt-oss) root@h100vm:~/gpt-oss# MODEL_PATH=./quant_models/merged_fp16_Q5_K_M.gguf GPU_LAYERS=25 ./check_reasoning_cn.sh
```

```
(gpt-oss) root@h100vm:~/gpt-oss# MODEL_PATH=./quant_models/merged_fp16_Q5_K_M.gguf GPU_LAYERS=25 ./check_reasoning_cn.sh
[INFO] 启动: ./quant_models/merged_fp16_Q5_K_M.gguf (port=8098)
[INFO] 发送问题: What is the national symbol of Canada?

[Analysis 段输出]
先思考一下加拿大的国家象征。加拿大的国旗是红白相间的，中央有一片红色的枫叶。枫叶在加拿大的文化和历史中具有重要意义，象征着国家的自然环境和人民的团结。枫叶是加拿大的国旗、国徽和国歌中的主要元素。它也被广泛用于加拿大的官方文件、纪念品和标志中。加拿大的国旗和国徽上都以枫叶为主要图案，象征着加拿大的身份和价值观。加拿大的国旗和国徽也被视为国家的象征，代表着加拿大的历史、文化和人民的团结。

[语言检测] langdetect=Chinese, cld3=unknown
✅ 符合 REASONING_LANGUAGE: Chinese
```

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/iHVoLaIIihs)



**Refer to**: 

*https://openai.com/index/introducing-gpt-oss/*  

*https://techcommunity.microsoft.com/blog/machinelearningblog/deploying-openai%E2%80%99s-first-open-source-model-on-azure-aks-with-kaito/4444234*
