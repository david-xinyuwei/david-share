# Azure AMD GPU VM相关测试



## Deepseek 671B on Azure

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X



### AMD性能测试报告

https://github.com/ROCm/MAD/tree/develop/benchmark



###  Qianwen 2.5 VL

https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/models/qwen2_5_vl.py

###### 0. 登录并切 root

```
Last login: Tue Apr 15 03:34:54 2025 from 202.171.178.15
azureuser@gbb-ea-vm-uksouth-mi300x-a-01:~$ sudo -i
root@gbb-ea-vm-uksouth-mi300x-a-01:~#
```



1. ###### GPU 与 ROCm 验证

```
rocm-smi
```



期望输出（节选）

```
Device  Node  IDs      Temp  Power  ...  VRAM%  GPU%
0       2     0x74b5   41°C  139W   ...   0%     0%
...
```



若 `rocm-smi` 报 “command not found”，说明 ROCm 未正确安装 → 需先完成 ROCm 6.3 安装并重启。

2. Docker 安装与守护进程验证

2‑A. 一键安装（如已安装可跳过）

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



2‑B. 启动并设自启

```
systemctl enable --now docker
```



验收

```
docker info | grep 'Server Version'
```



示例

```
Server Version: 28.1.1
```



❌ 错误输出

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```



纠正 → 执行 `systemctl enable --now docker` 并确认 `systemd` 为 PID 1

```
ps -p 1 -o comm   # 若不是 systemd 说明仍在容器里；exit 回宿主机
```



###### 3. 创建宿主机共享目录

```
mkdir -p $HOME/dockerx/{models,data}
```



4. 拉取 vLLM ROCm 镜像

```
docker pull rocm/vllm-dev:main
```



镜像体积 ~6 GB，完成后

```
docker images | grep vllm-dev
```



示例

```
rocm/vllm-dev   main   9a9582e6...   6.2GB
```

###### 5. 运行容器（推荐命令）

```
docker run -it --network host \
  --device=/dev/kfd --device=/dev/dri \
  --ipc=host --shm-size 16G --group-add video \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v $HOME/dockerx:/dockerx \
  rocm/vllm-dev:main
```



若出现 ❌ `docker: unknown server OS:` 多半是在 **容器内部** 再次运行 docker；先 `exit` 回宿主机再执行上面命令。

进入后提示符示例

```
root@gbb-ea-vm-uksouth-mi300x-a-01:/app#
```



6. 容器内验证 vLLM 版本 & 模型插件

```
python - <<'PY'
import vllm, importlib.util
print("vLLM:", vllm.__version__)
print("Qwen2.5-VL 模块:",
      bool(importlib.util.find_spec("vllm.model_executor.models.qwen2_5_vl")))
PY
```



期望

```
vLLM: 0.7.4.dev388...
Qwen2.5-VL 模块: True
```



❌ 若模块 False：

```
pip install --no-cache-dir --upgrade 'vllm[rocm]' flash-attn-rocm xformers
```



7. 下载 Qwen2.5‑VL‑7B‑Instruct 权重

```
export HUGGING_FACE_HUB_TOKEN=hf_xxx          # ← 换成你的 token
cd /dockerx/models
huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct \
    --local-dir Qwen2_5-VL-7B
```



下载约 20 GB；目录完成后包含 5 个 `model-0000*-of-00005.safetensors`。

❌ 常见错误
401 / 404 → token 不对或模型名写成 `Qwen2_5-VL-7B`；正确拼写 `Qwen/Qwen2.5-VL-7B-Instruct`

8. 纯文本延迟基准

```
root@gbb-ea-vm-uksouth-mi300x-a-01:/dockerx/models# python /app/vllm/benchmarks/benchmark_latency.py \
  --model /dockerx/models/Qwen2_5-VL-7B \
  --input-len 1024 --output-len 1024 \
  --batch-size 1 --num-iters 5 --num-iters-warmup 2 \
  --dtype float16 --max_model_len 4096
```



典型输出片段

```
Warmup iterations:   0%|                                                                                                                                                                    | 0/2 [00:00<?, ?it/s]INFO 04-28 11:18:39 [metrics.py:481] Avg prompt throughput: 204.6 tokens/s, Avg generation throughput: 120.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Warmup iterations:  50%|██████████████████████████████████████████████████████████████████████████████                                                                              | 1/2 [00:07<00:07,  7.69s/it]INFO 04-28 11:18:44 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
Warmup iterations: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2/2 [00:14<00:00,  7.11s/it]
Profiling iterations:   0%|                                                                                                                                                                 | 0/5 [00:00<?, ?it/s]INFO 04-28 11:18:49 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
INFO 04-28 11:18:54 [metrics.py:481] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 158.1 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Profiling iterations:  20%|██████████████████████████████▌                                                                                                                          | 1/5 [00:06<00:26,  6.52s/it]INFO 04-28 11:18:59 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Profiling iterations:  40%|█████████████████████████████████████████████████████████████▏                                                                                           | 2/5 [00:13<00:19,  6.52s/it]INFO 04-28 11:19:04 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.8 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Profiling iterations:  60%|███████████████████████████████████████████████████████████████████████████████████████████▊                                                             | 3/5 [00:19<00:13,  6.52s/it]INFO 04-28 11:19:09 [metrics.py:481] Avg prompt throughput: 204.7 tokens/s, Avg generation throughput: 156.7 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
INFO 04-28 11:19:14 [metrics.py:481] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 157.7 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Profiling iterations:  80%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████▍                              | 4/5 [00:26<00:06,  6.52s/it]INFO 04-28 11:19:19 [metrics.py:481] Avg prompt throughput: 204.7 tokens/s, Avg generation throughput: 156.9 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
Profiling iterations: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5/5 [00:32<00:00,  6.52s/it]
Avg latency: 6.522189523799898 seconds
10% percentile latency: 6.517169274200024 seconds
25% percentile latency: 6.51796872199975 seconds
50% percentile latency: 6.518479874999684 seconds
75% percentile latency: 6.528756830999555 seconds
90% percentile latency: 6.528966261599999 seconds
99% percentile latency: 6.529091919960265 secondsxxxxxxxxxx Warmup iterations:   0%|                                                                                                                                                                    | 0/2 [00:00<?, ?it/s]INFO 04-28 11:18:39 [metrics.py:481] Avg prompt throughput: 204.6 tokens/s, Avg generation throughput: 120.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Warmup iterations:  50%|██████████████████████████████████████████████████████████████████████████████                                                                              | 1/2 [00:07<00:07,  7.69s/it]INFO 04-28 11:18:44 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.Warmup iterations: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2/2 [00:14<00:00,  7.11s/it]Profiling iterations:   0%|                                                                                                                                                                 | 0/5 [00:00<?, ?it/s]INFO 04-28 11:18:49 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.INFO 04-28 11:18:54 [metrics.py:481] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 158.1 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Profiling iterations:  20%|██████████████████████████████▌                                                                                                                          | 1/5 [00:06<00:26,  6.52s/it]INFO 04-28 11:18:59 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.6 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Profiling iterations:  40%|█████████████████████████████████████████████████████████████▏                                                                                           | 2/5 [00:13<00:19,  6.52s/it]INFO 04-28 11:19:04 [metrics.py:481] Avg prompt throughput: 204.8 tokens/s, Avg generation throughput: 156.8 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Profiling iterations:  60%|███████████████████████████████████████████████████████████████████████████████████████████▊                                                             | 3/5 [00:19<00:13,  6.52s/it]INFO 04-28 11:19:09 [metrics.py:481] Avg prompt throughput: 204.7 tokens/s, Avg generation throughput: 156.7 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.INFO 04-28 11:19:14 [metrics.py:481] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 157.7 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Profiling iterations:  80%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████▍                              | 4/5 [00:26<00:06,  6.52s/it]INFO 04-28 11:19:19 [metrics.py:481] Avg prompt throughput: 204.7 tokens/s, Avg generation throughput: 156.9 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.Profiling iterations: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5/5 [00:32<00:00,  6.52s/it]Avg latency: 6.522189523799898 seconds10% percentile latency: 6.517169274200024 seconds25% percentile latency: 6.51796872199975 seconds50% percentile latency: 6.518479874999684 seconds75% percentile latency: 6.528756830999555 seconds90% percentile latency: 6.528966261599999 seconds99% percentile latency: 6.529091919960265 secondsAvg latency: 6.52 secondsp50 6.52 | p90 6.53 | p99 6.53
```





9. 多模态推理 Demo

9‑A. 准备图片

```
apt-get update
apt-get install -y wget         # 只有几十 KB，很快
mkdir -p /dockerx/data
wget -O /dockerx/data/test.jpg \
  https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg
```



9‑B. 创建脚本 `/dockerx/data/qwen_vl_demo.py`

```
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



vi /dockerx/data/qwen_vl_demo.py

```\
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



9‑C. 运行

```
python /dockerx/data/qwen_vl_demo.py
```



期望输出：对图片内容的一段中文描述。

❌ 报 `RuntimeError: ... backend not supported`

```
pip install --force-reinstall flash-attn-rocm==2.5.6 xformers
```



或临时

```
export VLLM_ATTEN_BACKEND=torch
```



# ================================================================== 10. 退出与复用

```
exit   # 退出容器
```



以后复用同一镜像+挂载目录直接重复 **步骤 5** 进入容器即可，模型已在 `/dockerx/models` 无需重下。

# ================================================================== 速查表：错误 → 纠正

| 错误信息                            | 纠正操作                                                     |
| ----------------------------------- | ------------------------------------------------------------ |
| Cannot connect to the Docker daemon | `systemctl enable --now docker` （宿主机执行）               |
| docker: unknown server OS           | 你在容器里运行了 `docker` → `exit` 回宿主机后再 run          |
| ModuleNotFoundError: qwen2_5_vl     | `pip install -U 'vllm[rocm]' flash-attn-rocm`                |
| 401/404 下载失败                    | 设置 `HUGGING_FACE_HUB_TOKEN`，检查模型名称拼写              |
| backend not supported (flash‑attn)  | 重新安装 flash-attn-rocm；或 `export VLLM_ATTEN_BACKEND=torch` |
| GPU OOM                             | 降 `--batch-size` / 调低 `gpu_memory_utilization`            |

至此，一个完整可复现、包含正确操作、验证输出和错误纠正的 **Qwen2‑5‑VL on AMD ROCm** 手册编写完成。祝测试顺利!

可选：上传/粘贴图片（PNG, JPG）



Drag and drop files hereLimit 200MB per file • PNG, JPG, JPEG

Browse files



压测中 用到了几个GPU？



本次 benchmark 日志里面的关键信息说明 **只用了 1 张 GPU** ：

1. 运行脚本时没有显式设置 `HIP_VISIBLE_DEVICES` / `VLLM_VISIBLE_DEVICES`，而 vLLM 在 ROCm 下默认只拿 **编号 0** 的 GPU 做单卡推理。

2. CLI 参数保持默认：

   ```
   --tensor-parallel-size 1   (TP 并行 1)
   --pipeline-parallel-size 1 (PP 并行 1)
   ```

   

   这意味着 vLLM 仅会为 rank‑0 分配一张卡。

3. 日志打印

   ```
   rank 0 in world size 1 is assigned as ... TP rank 0
   ```

   

   world size=1 → 整个进程组只有一个 GPU。

4. Memory profiling 行

   ```
   total_gpu_memory (191.45GiB) ...
   model weights take 15.95GiB ...
   ```

   

   191 GiB 正好是 MI300X 单卡 HBM 容量；如果在 8 卡机上启用多卡，单卡可用显存会 < 191 GiB，并且会出现 “rank 1…7” 的日志。

因此，这次压测是 **单卡（GPU 0）** 延迟测试，并未并行利用到机内其他 GPU。
若要多卡测试，需要：

```
export HIP_VISIBLE_DEVICES=0,1,2,3          # 或列出全部 8 卡
python ... --tensor-parallel-size 4          # 例：4 卡 TP 并行
```



或者在启动容器时加 `--device=/dev/dri/renderD129` 等方式限定/启用多卡。

### Megatron-LM框架训练qwen2-vl

如果使用Megatron-LM框架训练qwen2-vl的话，如果有nv的代码，只需要替换这个部分的load function：https://github.com/NVIDIA/Megatron-LM/blob/4429e8ebe21fb011529d7401c370841ce530785a/megatron/legacy/fused_kernels/__init__.py#L17 到amd的版本：https://github.com/ROCm/Megatron-LM/blob/rocm_dev/megatron/legacy/fused_kernels/__init__.py#L18 就可以了





### Llama 4 on AMD

[https://rocm.blogs.amd.com/artificial-intelligence/llama4-day-0-support/README.html#how-to-run-llama4-on-line-inference-mode-with-vllm-on-amd-instinct-gpus](https://nam06.safelinks.protection.outlook.com/?url=https%3A%2F%2Frocm.blogs.amd.com%2Fartificial-intelligence%2Fllama4-day-0-support%2FREADME.html%23how-to-run-llama4-on-line-inference-mode-with-vllm-on-amd-instinct-gpus&data=05|02|xinyuwei@microsoft.com|fdee5bf483fa48c4a98a08dd8379530d|72f988bf86f141af91ab2d7cd011db47|1|0|638811279380317136|Unknown|TWFpbGZsb3d8eyJFbXB0eU1hcGkiOnRydWUsIlYiOiIwLjAuMDAwMCIsIlAiOiJXaW4zMiIsIkFOIjoiTWFpbCIsIldUIjoyfQ%3D%3D|0|||&sdata=ZatRWnNRXgUPy1e5ehNgLC1x5ST0DAd%2FjQrTFpxuLig%3D&reserved=0)



Make sure you pull the latest image recommended there (currently rocm/vllm-dev:llama4-20250407).

Enabling V1 can also improve performance at this point. That is: VLLM_USE_V1=1





## vLLM Setup for Benchmarking Large Language Models on an NVads V710 v5-series Instance

```
#pip install num2words
```



https://github.com/dasilvajm/V710-VLLM-inference





### AMD 微调

https://github.com/ROCm/gpuaidev/blob/main/docs/notebooks/fine_tune/fine_tuning_lora_qwen2vl.ipynb





## Qwen3

rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410

这个镜像能支持qwen3，里面的vllm的版本比较新

