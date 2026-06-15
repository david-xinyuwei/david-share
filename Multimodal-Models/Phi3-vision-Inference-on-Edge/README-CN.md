# Phi3-Vision 边缘端推理

[English](README.MD) | 中文

**说明：**

- 已上传 Jupyter 文件 Phi3-vision-Inference-on-Edge.ipynb，代码在 Azure NC A100 GPU VM 上运行测试
- 本测试评估 Phi3-Vision 边缘端推理方案，包括 GPU/CPU 推理和不同推理框架的性能对比


## 在 Azure 上运行

本项目的所有实验均在 **Azure GPU 虚拟机**上完成。

| 项目 | 详情 |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **框架** | vLLM, TensorRT-LLM, ONNX Runtime |


## Phi3-Vision 基准评分

此前 AI 计算机视觉主要使用 Llava 和 GPT-4o 等模型。Phi3-Vision 于 2024 年 5 月发布后，在多个方面超越了 Llava：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/2.jpg)

Phi3-Vision 参数量相对较小，因此除了能力强大外，还非常适合边缘端推理：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/3.jpg)

上图展示了不同数据类型下 Phi3-V 模型加载所消耗的显存。

## 边缘端推理考量因素

**1. 是否需要微调模型以满足特定业务需求。微调方法参考：**
*https://github.com/davidsajare/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning*

**2. 边缘端推理时模型运行的硬件环境。例如 GPU 或 CPU（CUDA/ROCm）。**

**3. 是否有足够的资源，特别是内存。算力不足导致推理变慢，但内存不足会直接导致 OOM。**

## Phi3-Vision CUDA + HF Transformer 测试结果

目前 Phi3-V 在 HF 和 ONNX 格式中均只有 128K 上下文版本。

*https://huggingface.co/microsoft/Phi-3-vision-128k-instruct*

不同数据类型下 Phi3-Vision 的显存需求：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/3.jpg)

***测试图片为美国护照样本：***

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/usa-passport.jpg)

### 三点注意事项：

##### 1. BNB 动态量化是否导致推理精度下降？答案是否。

##### 2. 动态量化是否导致推理速度下降？答案是肯定的。

对于英文，无论是否动态量化，在图片意图识别、图片描述或 OCR（如护照识别）方面都非常准确，且不需要编写太多提示词。
对于中文，OCR 准确率有待提高，意图识别还可以。

在 A100 上，量化后的图片推理（以护照为例）约 17 秒，显存 6GB：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/int4infer.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/int4gpu.jpg)

未量化时，FP16 推理（以护照为例）约 13 秒，显存约 12GB：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/fp16infer.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/fp16gpu.jpg)

##### 3. 中文识别遇到的问题

以中国身份证为例：

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/1.png)

***推理结果：***

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/chinaidres.jpg)

从姓名和地址来看，准确度不高。

此外，对图片的总结和意图识别用英文描述更清晰，中文则不然。

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/car.jpg)

***推理时间：4.555504083633423 秒***

*图片显示一辆白色卡车在两侧有树的道路上行驶。卡车前方有一辆汽车，卡车似乎在行进中。道路看起来位于农村或车流较少的地区。没有立即的危险迹象，但卡车的位置和汽车的距离表明需要谨慎。*

## Phi3-Vision FP16 CUDA + vLLM 测试结果

目前 vLLM 对 Phi3-V 的支持仍处于预览状态。如需测试，需要从源码编译安装 vLLM。本地编译时间约 5-10 分钟。

```bash
conda activate vllm-phi3-v
git clone https://github.com/vllm-project/vllm.git
cd vllm/
pip install -r requirements-common.txt
pip install -r requirements-cuda.txt
pip install .
```

vLLM 性能方面，使用 Transformer FP16 和 vLLM FP16 进行对比。仍使用美国护照识别示例，推理速度为 2.96 秒。

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/vllm-h100-infer.png)

显存占用约 22GB。

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/vllm-h100-gpu.png)

如果在 H100 上使用 HF FP16 推理，推理速度为 8.5 秒。虽然较慢，但比 vLLM 方法节省 2/3 显存。这主要是因为 vLLM 底层使用的 accelerate 库需要预分配 KV 缓存。即使在代码中设置了 max_model_len 和 gpu_memory_utilization，仍需要比 HF 更多显存。因此在边缘推理时，需要同时评估显存利用率和速度。

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/TF-h100-FP16-infer.png)

## Phi3-Vision FP8 CUDA + vLLM 测试结果

vLLM 的 Phi3-V FP8 支持仍在开发中。之前的 AMMO 库已弃用：

https://github.com/vllm-project/vllm/blob/v0.5.0/examples/fp8/quantizer/quantize.py

```bash
python quantize.py --model_dir phi3-v-fp16 --dtype float16 --qformat fp8 --kv_cache_dtype fp8 --output_dir phi3-v-fp8 --calib_size 512 --tp_size 1
```

*注：`nvidia-ammo` 包已弃用并更名为 `nvidia-modelopt`。详见 https://github.com/NVIDIA/TensorRT-Model-Optimizer*

## Phi3-Vision ONNX 测试结果

目前 ONNX Runtime 需要 CUDA 11：

```bash
nvcc --version
# nvcc: NVIDIA (R) Cuda compiler driver
# Cuda compilation tools, release 11.0

nvidia-smi
# NVIDIA H100 NVL, Driver 555.42.02, CUDA 12.5
```

基于 ONNX 的 Phi3-V 推理参考：
https://onnxruntime.ai/docs/genai/tutorials/phi3-v.html

稍微修改了推理脚本以测量推理时间。FP16 推理速度很快，约 4 秒，但推理准确率不如 HF 和 vLLM。

```bash
python3 1phi3v.py -m cuda-fp16
# Loading model...
# Image Path: usa-passport.jpg
# Loading image...
# Prompt: OCR the text of the image...
# Processing image and prompt...
# Generating response...
```

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/onnxinfer.png)

从结果看，即使编写了非常详细的提示词，扫描结果仍不完整。这比 HF 和 vLLM 差很多。GPU 显存利用率约 11GB。

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/onnxgpu.png)

#### 注意：
测试结果可能与所用库版本或配置有关，需要进一步调查。

---

## VLM 护照 OCR 对比测试（2026-01 更新）

Phi-3-Vision 的 85% 准确率是否已是最优？为验证这一假设，我们与主流开源 VLM 进行了系统对比。

### 测试配置

- **测试任务**：美国护照 13 字段完整提取
- **关键指标**：Surname 字段准确性（身份验证关键字段）
- **正确答案**：Surname = "GUPTA"，Given Names = "RAHUL RAM"
- **测试环境**：NVIDIA A100 80GB GPU
- **测试日期**：2026 年 1 月

### 基准测试结果

| 模型 | 参数量 | 量化 | 显存 | 推理时间 | 准确率 | Surname 输出 | 状态 |
|------|--------|------|------|----------|--------|--------------|------|
| **Qwen2-VL-7B FP16** | 7B | 无 | 15.49GB | 32.94s | **13/13 (100%)** | GUPTA ✓ | **唯一100%** |
| Qwen2-VL-7B-AWQ | 7B | 4-bit | 6.49GB | 1.27s | 11/13 (85%) | USAGUPTA ✗ | 量化损失 |
| Qwen2-VL-2B | 2B | 无 | ~5GB | 6.36s | 11/13 (85%) | RAM ✗ | 姓名混淆 |
| Phi-4-multimodal | 5.6B | 无 | ~12GB | 11.34s | 11/13 (85%) | USAGUPTA ✗ | MRZ误读 |
| Phi-3-Vision | 4.2B | 无 | ~8GB | ~8s | 11/13 (85%) | GUPTA ✓ | 格式问题 |

### 关键发现

#### 1. MRZ 国家代码混淆是普遍问题

护照 MRZ 格式为：`P<USAGUPTA<<RAHUL<RAM<<<`

其中 `USA` 是国家代码，**不是姓氏的一部分**。多数模型错误地将 "USA" 和 "GUPTA" 合并输出 "USAGUPTA"。

仅 **Qwen2-VL-7B FP16** 能正确区分国家代码和姓氏。

#### 2. 4-bit 量化影响 OCR 精度

| 指标 | FP16 | AWQ 4-bit | 变化 |
|------|------|-----------|------|
| Surname 准确性 | ✓ GUPTA | ✗ USAGUPTA | **精度下降** |
| 推理时间 | 32.94s | 1.27s | **26倍加速** |
| 显存占用 | 15.49GB | 6.49GB | **节省58%** |

AWQ 量化在通用任务上效果良好，但在字符级 OCR 任务上会损失关键精度。

#### 3. 模型规模 ≠ 准确率

| 模型 | 参数量 | 准确率 |
|------|--------|--------|
| Qwen2-VL-7B | 7B | 100% |
| Phi-4-multimodal | 5.6B | 85% |
| Phi-3-Vision | 4.2B | 85% |
| Qwen2-VL-2B | 2B | 85% |

仅 Qwen2-VL-7B 达到 100%，其他模型无论大小均为 85%。说明护照 OCR 对训练数据和架构设计有特定要求。

#### 4. 结果具有确定性

所有模型在 3 次测试中输出完全一致（`do_sample=False`），说明：
- 错误是**系统性**的，非随机噪声
- 无法通过多次采样获得正确答案

### 部署建议

| 场景 | 推荐模型 | 配置 | 原因 |
|------|----------|------|------|
| **身份验证（准确性优先）** | Qwen2-VL-7B | FP16 | 唯一 100% 准确 |
| **批量处理（可接受错误）** | Phi-3-Vision | FP16 | 8GB 显存，速度适中 |
| **实时响应（延迟优先）** | Qwen2-VL-7B-AWQ | vLLM | 1.3s 极快，需后处理校验 |
| **边缘设备（资源受限）** | Qwen2-VL-2B | FP16 | 5GB 显存，需姓名校验 |
| **不推荐** | BitsAndBytes INT4 | - | OCR 质量严重下降 |

### 后处理补救方案

针对输出 "USAGUPTA" 的模型：

```python
def fix_mrz_country_code(surname: str) -> str:
    """移除 MRZ 国家代码前缀"""
    country_codes = ["USA", "GBR", "CAN", "AUS", "DEU", "FRA", "JPN", "CHN"]
    for code in country_codes:
        if surname.startswith(code) and len(surname) > len(code):
            return surname[len(code):]
    return surname
```

### 测试脚本

所有测试脚本在 `scripts/` 目录：

```bash
# 测试 Qwen2-VL-7B FP16（100% 准确）
python scripts/test_qwen2vl_7b.py images/usa-passport.jpg

# 测试 Qwen2-VL-7B-AWQ + vLLM（快速但 85%）
python scripts/test_qwen2vl_7b_awq.py images/usa-passport.jpg

# 测试 Qwen2-VL-2B（轻量但 85%）
python scripts/test_qwen2vl_2b.py images/usa-passport.jpg

# 测试 Phi-4-multimodal（85%）
python scripts/test_phi4mm.py images/usa-passport.jpg
```

### 环境配置

```bash
# Qwen2-VL 模型
pip install transformers torch accelerate qwen-vl-utils pillow

# AWQ 模型 + vLLM
pip install vllm
```

---

*作者：魏新宇 (Microsoft AI GBB) | 更新：2026-01*
