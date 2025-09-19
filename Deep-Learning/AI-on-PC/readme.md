

# AI Model on PC的验证

## TL;DR

- 在纯CPU环境下，通过 Llama.cpp + 量化GGUF模型（4-bit 或 FP16），可在16GB RAM 的笔记本上获得最高 **16 tokens/sec** 性能。
- 对资源紧张场景，优先选择小于8B参数的模型 + 低比特量化（4-bit/8-bit）。

---

## 背景与问题
许多开发者无法持续租用GPU，即便偶尔按需租用也因成本高、灵活性差而不可行。  
在需要私有化推理（offline inference）、原型开发或低预算测试时，仅有CPU环境必须寻求高效运行LLM的方案。  
目标是：
1. 在无GPU笔记本或边缘设备上运行可用LLM。
2. 兼顾响应速度（tokens/sec）、内存占用和推理能力。
3. 保证方法可复现、可部署并可快速切换模型。

---

## 方法

### 1. 选择并下载模型（GGUF 格式）
- 推荐模型：
  - **Llama 3.2 3B Instruct (4-bit)**: `unsloth/Llama-3.2-3B-Instruct-GGUF`
  - **Phi-3-mini-4k-instruct (4-bit)**: `microsoft/Phi-3-mini-4k-instruct-gguf`
  - **DeepSeek-R1-Distill-Llama-8B**: `unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF`
  - **Gemma-3–27b-it**: `unsloth/gemma-3-27b-it-GGUF`
  - **Qwen2.5–7B-Instruct**: `Qwen/Qwen2.5-7B-Instruct-GGUF`

示例：用 HuggingFace `huggingface-cli` 下载（确保安装了 `huggingface_hub`）
```bash
pip install huggingface_hub
huggingface-cli download unsloth/Llama-3.2-3B-Instruct-GGUF \
  --include "*.gguf" \
  --local-dir ./models/llama3_3b_q4
```

### 2. 创建 Python 环境并安装 Llama.cpp Python 绑定

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install llama-cpp-python
```

### 3. 推理完整示例代码

下面为完整可运行的本地推理Python脚本（保存为 `run_llm.py` 直接执行）：

```
from llama_cpp import Llama

# 模型路径：确保为GGUF格式
MODEL_PATH = "./models/llama3_3b_q4/model.gguf"

# 初始化模型
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=128,            # 上下文窗口
    n_threads=4           # CPU线程数（可调节至 CPU 核数）
)

# 定义推理参数
prompt = "Write a poem about the moon"
max_tokens = 100
temperature = 0.3
top_p = 0.1
echo = True
stop = ["Q", "\n"]

# 执行推理
output = llm(
    prompt,
    max_tokens=max_tokens,
    temperature=temperature,
    top_p=top_p,
    echo=echo,
    stop=stop
)

# 输出结果
result_text = output["choices"][0]["text"].strip()
print("=== LLM Output ===")
print(result_text)
```

运行：

```
python run_llm.py
```

### 4. 量化内存占用参考

- **FP32**: 每参数4字节；8B模型需 ~32GB RAM
- **FP16**: 每参数2字节；8B模型降至 ~16GB RAM
- **4-bit**: 每参数0.5字节；8B模型降至 ~4GB RAM（精度损失较多）

## 实验与基准

| 模型                         | 参数规模 | 量化     | CPU设备         | Tokens/sec | 内存占用(运行中) | 场景说明                |
| ---------------------------- | -------- | -------- | --------------- | ---------- | ---------------- | ----------------------- |
| Llama 3.2 3B Instruct        | 3B       | 4-bit    | Intel i5 / 16GB | ~16        | 不知道           | 默认首选，均衡方案      |
| Phi-3-mini-4k-instruct       | 3.82B    | 4-bit    | Intel i5 / 16GB | ~12        | 不知道           | 推理能力略优            |
| DeepSeek-R1-Distill-Llama-8B | 8B       |          | Intel i5 / 16GB | 5~6        | 不知道           | reasoning能力强，速度慢 |
| Gemma-3–27b-it               | 27B      | GGUF量化 | AWS CPU         | 不知道     | 大               | 最佳多模态CPU模型       |
| Qwen2.5–7B-Instruct          | 7B       | 4-bit    | Intel i5 / 16GB | ~9         | 不知道           | 编程任务强              |

## 工程化建议（Checklist）

-  **选模型**：<8B 参数，优先 4-bit 量化，减少内存占用和推理延迟。
-  **选格式**：必须使用 GGUF（Llama.cpp 原生支持），避免加载失败。
-  **量化优先级**： 4-bit (原型) → 8-bit (产线低配) → FP16 (较高精度)。
-  **多核优化**：绑定 CPU 线程数 `n_threads`。
-  **批量推理**：合并输入任务减少初始化开销。
-  **监控性能**：记录 tokens/sec、TTFT、内存占用，按需优化。
-  **备用工具**：Ollama 可作为 OpenAI API 兼容替代方案。但需要注意的是ollama最多执行两个并发。



## 部署Runbook

### 环境要求

- OS: Linux/macOS/Windows
- Python: ≥3.9
- CPU: 4核以上
- 内存: ≥8GB（推荐≥16GB）
- 存储：根据模型大小预留（例如 Llama 3.2 3B Q4 约 2GB）

### 方法1：Docker运行（无需本地Python环境）

```
docker run --rm -it \
  -v $(pwd)/models:/models \
  ghcr.io/ggerganov/llama.cpp:latest \
  --model /models/model.gguf \
  --prompt "Hello, world"
```



### 方法2：Python直接运行（适合本地脚本开发）

```
python run_llm.py
```



------

## 风险与故障应对

| 问题         | 原因               | 解决方法                             |
| ------------ | ------------------ | ------------------------------------ |
| 慢 / 卡顿    | 模型参数过大未量化 | 换小模型或使用4-bit量化版本          |
| OOM内存溢出  | 模型加载超出RAM    | 更换小模型 / 提升内存 / 使用交换分区 |
| 推理质量下降 | 量化等级过低       | 改用8-bit或FP16                      |
| 无法加载模型 | 格式不支持         | 确认下载GGUF版本                     |

------

## 结论与下一步

**短期优先任务：**

1. **P1**: 下载并测试 Llama 3.2 3B (4-bit) GGUF 版本，验证本机性能。
2. **P2**: 搭建本地 Llama.cpp 批量推理服务（Python API + 性能监控）。
3. **P3**: 在云CPU环境对比 Gemma 3 多模态性能，择优纳入方案库。