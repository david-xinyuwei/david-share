# Foundry Local 功能验证

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## Running on Azure

**Azure AI Foundry Local** 可以在本地设备上直接运行 AI 模型，无需云端 GPU。

| 项目 | 详情 |
|---|---|
| **Azure 产品** | [Azure AI Foundry Local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started) |
| **计算资源** | 本地 CPU/GPU（Windows、macOS）— 支持 NVIDIA、AMD、Qualcomm、Apple Silicon |
| **网络** | 仅首次下载模型需联网，之后支持离线使用 |

**系统要求**：
- 操作系统：Windows 10 (x64)、Windows 11 (x64/ARM)、Windows Server 2025、macOS
- 硬件：最低 8GB RAM + 3GB 磁盘空间；推荐 16GB RAM + 15GB 磁盘空间
- 加速（可选）：NVIDIA GPU (2000 系列+)、AMD GPU (6000 系列+)、Qualcomm Snapdragon X Elite (8GB+)、Apple Silicon

*来源：https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started*

![Foundry Local 架构](images/1.png)

### 在 Surface Laptop 上安装和运行 Foundry Local

PowerShell 安装：

```
winget install Microsoft.FoundryLocal
```

启动 Foundry 服务（用于 Open-WebUI 连接）：

```
PS C:\Users\xinyuwei> foundry service status
🔴 Model management service is not running!
To start the service, run the following command: foundry service start

PS C:\Users\xinyuwei> foundry service start
🟢 Service is Started on http://localhost:5273, PID 42864!

PS C:\Users\xinyuwei> foundry service status
🟢 Model management service is running on http://localhost:5273/openai/status
```

在笔记本的 WSL 上：

```
pip install open-webui
open-webui serve
```

访问 http://localhost:8080/ 打开 Open-WebUI。

**将 Open-WebUI 连接到 Foundry Local**：

1. 选择导航菜单中的 **Settings**
2. 选择 **Connections**
3. 选择 **Manage Direct Connections**
4. 点击 **+** 添加连接
5. **URL** 填写 `http://localhost:PORT/v1`，其中 `PORT` 替换为 Foundry Local 端点的端口号（使用 `foundry service status` 命令查看，注意端口会动态分配）
6. **API Key** 随意填写（如 `test`），不能为空
7. 保存连接

**注意**：Open-WebUI 上可见的本地模型是通过 PowerShell 的 Foundry 命令已拉取到本地的模型。

![Open-WebUI 连接 Foundry Local](images/2.png)

***点击下图观看 YouTube 演示视频***：
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/NpYDsGXFrAU)

## 从 Hugging Face 加载自定义 AI 模型

Foundry Local 仓库中现有的模型不一定包含我们需要的特定模型。但我们可以使用 Olive 工具将 Hugging Face 上的任意模型转换为 ONNX 格式并保存到本地，然后加载到 Foundry Local 中。**请注意**，模型转换通常需要较大的内存资源。如果笔记本内存不够，可能需要在 Azure VM 上进行转换操作。

*来源：https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models?tabs=Bash*

```
pip install olive-ai[auto-opt]
pip install transformers==4.44.2 onnxruntime-genai
```

> **注意**：`transformers==4.44.2` 是测试时与 Olive 兼容的版本。请查看 [Olive 文档](https://github.com/microsoft/Olive) 获取最新版本要求。

使用 Olive `auto-opt` 命令下载、转换、量化和优化模型：

```
olive auto-opt \
    --model_name_or_path meta-llama/Llama-3.2-1B-Instruct \
    --trust_remote_code \
    --output_path models/llama \
    --device cpu \
    --provider CPUExecutionProvider \
    --use_ort_genai \
    --precision int4 \
    --log_level 1
```

转换完成后检查模型文件（model.onnx 约 1.7GB）：

```
ls -al /root/models/llama/model
-rw-r--r-- 1 root root 1823915746 model.onnx
-rw-r--r-- 1 root root       1540 genai_config.json
-rw-r--r-- 1 root root    9085657 tokenizer.json
...
```

重命名模型目录：

```
cd models/llama
mv model llama-3.2
```

编写 `generate_inference_model.py` 脚本生成推理配置文件：

```python
import json, os
from transformers import AutoTokenizer

model_path = "models/llama/llama-3.2"
tokenizer = AutoTokenizer.from_pretrained(model_path)
chat = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "{Content}"},
]
template = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)

json_template = {
    "Name": "llama-3.2",
    "PromptTemplate": {"assistant": "{Content}", "prompt": template}
}

with open(os.path.join(model_path, "inference_model.json"), "w") as f:
    json.dump(json_template, f, indent=2)
```

运行脚本后，从 Azure VM 下载模型到笔记本：

```
scp -r root@<your-vm-ip>:/root/models/llama/llama-3.2 C:\Users\xinyuwei\models\llama-3.2
```

将模型添加到 Foundry 缓存并运行：

```
PS C:\Users\xinyuwei> foundry cache cd models
🟢 Service is Started on http://localhost:5273, PID 16216!

PS C:\Users\xinyuwei> foundry model run llama-3.2 --verbose
🕕 Loading model...
🟢 Model llama-3.2 loaded successfully
```

> **注意**：`foundry cache ls` 显示 `Model was not found in catalog` 是正常的 — 通过 Olive 转换的自定义模型不在官方目录中，但作为本地模型可以正常运行。

**本地推理性能**（Llama-3.2-1B-Instruct，INT4 量化，Surface Laptop CPU）：

| 指标 | 值 |
|------|-----|
| 吞吐量 | 13.24 tokens/s |
| 首 Token 延迟 (TTFT) | 1436 ms |
| 平均 Token 生成时间 | 74.9 ms |
| 总 Token 数 | 235 |
| 总时间 | 17.75 s |

## Foundry Local vs AI Dev Gallery 的区别

| 场景 | 选择 |
|------|------|
| 需要**本地 REST API 推理服务**，采用 OpenAI 兼容协议 | **Foundry Local** |
| 需要**快速开发 Windows 桌面 UI**，零延迟进程内推理 | **AI Dev Gallery** |

两者的核心架构差异：

| 特性 | Foundry Local（后台服务） | AI Dev Gallery（进程内调用） |
|------|--------------------------|----------------------------|
| 架构 | 客户端-服务端（REST API 进程间通信） | 单进程（DLL 函数调用） |
| 协议 | OpenAI REST API、HTTP、JSON | 内存内函数调用（无 HTTP） |
| 网络开销 | 少量（本地回环） | 无 |
| 延迟 | 略高（序列化 + 进程通信） | 最低（进程内直接调用） |
| 应用场景 | 后台服务、多进程共享、远程调用 | Windows 桌面 GUI 应用 |
| 模型管理 | Foundry 服务统一管理 | 应用程序自己管理 |

**Foundry Local 架构**：应用程序通过 HTTP 请求（OpenAI REST API）调用 `localhost:PORT/v1/chat/completions`，后台的 Foundry Local 服务守护进程使用 ONNX Runtime 加载模型推理。

**AI Dev Gallery 架构**：WinUI 应用通过 `OnnxRuntimeGenAIChatClient`（C# 封装层）直接在进程内调用 ONNX Runtime DLL，模型直接加载进当前 UI 进程内存。
