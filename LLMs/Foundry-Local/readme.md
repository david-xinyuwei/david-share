# Foundry Local Functionality Verification

Your system must meet the following requirements to run Foundry Local:
Operating System: Windows 10 (x64), Windows 11 (x64/ARM), Windows Server 2025, macOS.
Hardware: Minimum 8GB RAM, 3GB free disk space. Recommended 16GB RAM, 15GB free disk space.
Network: Internet connection for initial model download (optional for offline use)
Acceleration (optional): NVIDIA GPU (2,000 series or newer), AMD GPU (6,000 series or newer), Qualcomm Snapdragon X Elite (8GB or more of memory), or Apple silicon.

*Refer to：https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started*

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Foundry-Local/images/1.png)

### Install and Run Foundry Local on my Surface Laptop

On Powershell to install

```
winget install Microsoft.FoundryLocal
```

Start foundry service for open-webui  connection:

```
PS C:\Users\xinyuwei> foundry service status
🔴 Model management service is not running!
To start the service, run the following command: foundry service start


PS C:\Users\xinyuwei>  foundry service start
🟢 Service is Started on http://localhost:5273, PID 42864!


PS C:\Users\xinyuwei> foundry service status
🟢 Model management service is running on http://localhost:5273/openai/status

```

On  WLS of my Laptop:

```
pip install open-webui
open-webui serve
```

Access  http://localhost:8080/ of open-webui

**Connect Open Web UI to Foundry Local**:

1. Select **Settings** in the navigation menu
2. Select **Connections**
3. Select **Manage Direct Connections**
4. Select the **+** icon to add a connection
5. For the **URL**, enter `http://localhost:PORT/v1` where `PORT` is replaced with the port of the Foundry Local endpoint, which you can find using the CLI command `foundry service status`. Note, that Foundry Local dynamically assigns a port, so it's not always the same.
6. Type any value (like `test`) for the API Key, since it can't be empty.
7. Save your connection

**Note:** The local models visible on Open-WebUI are models that have already been pulled locally using Foundry through PowerShell.

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Foundry-Local/images/2.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/NpYDsGXFrAU)

## Load sepacial AI model from Hugging face

The models currently available in the Foundry Local repository may not necessarily include the specific models we intend to use. However, we can utilize the Olive tool to convert any model from Hugging Face into the ONNX format and save it locally, then load it into Foundry Local. **It's important to note** that converting models often requires significant memory resources. If your laptop can't meet these memory requirements, it may be necessary to perform this operation on an Azure VM with larger memory capacity.

*Refer to:https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models?tabs=Bash*

```
pip install olive-ai[auto-opt]
pip install transformers==4.44.2 onnxruntime-genai
```

Use the Olive `auto-opt` command to download, convert, quantize, and optimize the model:

```
(olive) root@linuxworkvm:~# olive auto-opt \
    --model_name_or_path meta-llama/Llama-3.2-1B-Instruct \
    --trust_remote_code \
    --output_path models/llama \
    --device cpu \
    --provider CPUExecutionProvider \
    --use_ort_genai \
    --precision int4 \
    --log_level 1
```

Convert result:

```
 shape is same as output: [5]
2025-05-27 08:09:35,961 fusion_utils [INFO] - Remove reshape node /model/layers.15/self_attn/Reshape_3 since its input shape is same as output: [5]
2025-05-27 08:09:35,962 fusion_utils [INFO] - Remove reshape node /model/layers.15/self_attn/Reshape_5 since its input shape is same as output: [5]
2025-05-27 08:09:36,119 onnx_model [INFO] - Removed 40 nodes
2025-05-27 08:09:36,128 onnx_model_gpt2 [INFO] - postprocess: remove Reshape count: 0
2025-05-27 08:09:36,152 onnx_model_bert [INFO] - opset version: 20
[2025-05-27 08:11:10,727] [INFO] [engine.py:757:_run_pass] Pass transformer_optimizer:orttransformersoptimization finished in 323.248973 seconds
[2025-05-27 08:11:10,773] [INFO] [engine.py:683:_run_pass] Running pass matmul4:onnxmatmul4quantizer
[2025-05-27 08:12:06,972] [INFO] [engine.py:757:_run_pass] Pass matmul4:onnxmatmul4quantizer finished in 56.200519 seconds
[2025-05-27 08:12:06,974] [INFO] [engine.py:683:_run_pass] Running pass extract_adapters:extractadapters
[2025-05-27 08:12:08,325] [INFO] [extract_adapters.py:177:_run_for_config] No lora modules found in the model. Returning the original model.
[2025-05-27 08:12:08,345] [INFO] [engine.py:757:_run_pass] Pass extract_adapters:extractadapters finished in 1.370458 seconds
[2025-05-27 08:12:08,346] [INFO] [engine.py:241:run] Run history for cpu-cpu:
[2025-05-27 08:12:08,348] [INFO] [engine.py:499:dump_run_history] Please install tabulate for better run history output
[2025-05-27 08:12:08,348] [INFO] [cache.py:195:load_model] Loading model 36d160e9 from cache.
[2025-05-27 08:12:09,240] [INFO] [engine.py:266:run] Saved output model to /root/models/llama
Model is saved at /root/models/llama
```

Check model files:

```
(olive) root@linuxworkvm:~# ls -al /root/models/llama
total 16
drwxr-xr-x 3 root root 4096 May 27 08:12 .
drwxr-xr-x 5 root root 4096 May 27 07:58 ..
drwxr-xr-x 2 root root 4096 May 27 08:12 model
-rw-r--r-- 1 root root 4031 May 27 08:12 model_config.json
(olive) root@linuxworkvm:~# ls -al /root/models/llama/model
total 1790124
drwxr-xr-x 2 root root       4096 May 27 08:12 .
drwxr-xr-x 3 root root       4096 May 27 08:12 ..
-rw-r--r-- 1 root root        951 May 27 08:12 config.json
-rw-r--r-- 1 root root       1540 May 27 08:12 genai_config.json
-rw-r--r-- 1 root root 1823915746 May 27 08:11 model.onnx
-rw-r--r-- 1 root root        325 May 27 08:12 special_tokens_map.json
-rw-r--r-- 1 root root    9085657 May 27 08:12 tokenizer.json
-rw-r--r-- 1 root root      54557 May 27 08:12 tokenizer_config.json
(olive) root@linuxworkvm:~# 
```

Rename model directory's name:

```

cd models/llama
mv model llama-3.2
```

Write down generate_inference_model.py script:

```
(olive) root@linuxworkvm:~# pwd
/root
(olive) root@linuxworkvm:~# cat generate_inference_model.py
# generate_inference_model.py
# This script generates the inference_model.json file for the Llama-3.2 model.
import json
import os
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
  "PromptTemplate": {
    "assistant": "{Content}",
    "prompt": template
  }
}

json_file = os.path.join(model_path, "inference_model.json")

with open(json_file, "w") as f:
    json.dump(json_template, f, indent=2)
```

Run the programme:

```
python generate_inference_model.py
```

Next, download the entire "model" directory to my laptop under the following location:

```
C:\Users\xinyuwei>
```

Add model to  foundry cache 

```
PS C:\Users\xinyuwei> foundry cache cd models
Restarting service...
🔴 Service is stopped.
🟢 Service is Started on http://localhost:5273, PID 16216!
```

Check added model:

```
PS C:\Users\xinyuwei> foundry cache ls
Models cached on device:
   Alias                         Model ID
💾 Model was not found in catalogllama-3.2
💾 Model was not found in catalogmodel
PS C:\Users\xinyuwei>
```

Run the model locally:

```
PS C:\Users\xinyuwei> foundry model run llama-3.2 --verbose
Model llama-3.2 was found in the local cache.
🕕 Loading model...
Time cost to load model: 00:00:05.6293161
🟢 Model llama-3.2 loaded successfully

Interactive Chat. Enter /? or /help for help.

Interactive mode, please enter your prompt
```



```
> Where is china?
🤖 China is a country located in East Asia. It is the world's most populous country, with a population of over 1.4 billion people, and is situated in the Far East. China is bordered by several countries, including:

* North Korea to the north
* Mongolia to the north
* India to the south
* Nepal to the south
* Bhutan to the south
* Myanmar (Burma) to the west
* Vietnam to the west
* Taiwan to the east

China is a vast country, with a long coastline along the Pacific Ocean to the east and the South China Sea to the south. It is also home to many different ethnic groups, languages, and cultures, making it a diverse and fascinating country to learn about.

Here's a rough outline of China's geography:

* China is divided into 23 provinces, 4 autonomous regions, and 2 special administrative regions.
* The country has a total area of approximately 9.6 million square kilometers (3.7 million square miles).
* China is home to many major cities, including Shanghai, Beijing, Guangzhou, and Shenzhen.

I hope that helps!
======================Perf Info======================
Total Tokens/Second: 13.23943661971831
Time to First Token: 1436 ms
Average Token Generation Time: 74.9063829787234 ms
Total Time: 17750 ms
Total Tokens: 235
=====================================================
```

## Different between Foundry Local and AI Dev Gallery

- 想要“本地REST API推理服务”，采用OpenAI 兼容协议 → 选择 **Foundry Local**
- 想要“快速开发Windows单机交互UI、0延迟进程内直接推理” → 选择 **AI Dev Gallery默认**

```
+------------------------+                                 +---------------------------------------+
| 你的客户端程序          |                                 | Foundry Local 本地服务守护进程          |
| (Python/JS/C#/Java..)  |                                 |                                       |
|                        |                                 |   +-------------------------------+   |
|                        |                                 |   |  ONNX Runtime (CPU/GPU/NPU)   |   |
|                        |                                 |   +---------------▲---------------+   |
+-----------+------------+                                 |                   |                   |
            |                                              |   +---------------▼---------------+   |
            |  HTTP请求(OpenAI REST API, JSON)             |   |       ONNX 模型(.ort/.onnx)     |   |
            |                                              |   +-------------------------------+   |
            |                                              +---------------------------------------+
            ▼
http://localhost:端口/v1/chat/completions
(JSON请求和响应完全兼容OpenAI API)
```

**说明：**

- 你的应用与模型推理服务是一种典型的 **客户端 - 服务端** 架构。
- Foundry Local 后台以 HTTP REST API 提供推理服务，因此适合多进程、多应用甚至远程调用。
- 调用协议完全是 OpenAI API 兼容，易于集成已有代码。

```
+-------------------------------------------------------+
|                AI Dev Gallery 示例应用(WinUI)          |
|                                                       |
|   +-----------------------------------------------+   |
|   | WinUI 页面 (XAML, UI控件, 消息窗口等)          |   |
|   +-----------------------------------------------+   |
|                    ▲         |                        |
|                    |         | IChatClient接口调用     |
|                    |         ▼                        |
|    +---------------------------------------------+    |
|    |  OnnxRuntimeGenAIChatClient (封装层C#)      |    |
|    +-------------------------▲-------------------+    |
|                              | P/Invoke(调用DLL内API) |
|    +-------------------------▼-------------------+    |
|    |   ONNX Runtime (Microsoft.ML.OnnxRuntime)   |    |
|    +-------------------------▲-------------------+    |
|                              | 加载模型数据到内存     |
|    +-------------------------▼-------------------+    |
|    |       本地保存的ONNX模型(.ort/.onnx)        |    |
|    +---------------------------------------------+    |
+-------------------------------------------------------+
```

**说明：**

- 没有HTTP/API调用，只是普通的 **进程内函数/DLL调用**。
- 模型是直接加载进当前的UI进程内，所有推理发生在当前进程内。
- 优势：低延迟、适合单机UI程序；劣势：不太适合多进程共享。



| 特性           | Foundry Local(后台服务进程)       | AI Dev Gallery 示例(进程内调用) |
| -------------- | --------------------------------- | ------------------------------- |
| 架构           | 客户端-服务端 (进程通信 REST API) | 单进程 (DLL函数调用)            |
| 调用协议       | OpenAI REST API、HTTP、JSON       | 内存内函数调用 (无HTTP)         |
| 是否有网络开销 | 少量（本地回环）                  | 无网络开销                      |
| 延迟比较       | 略高(因序列化+进程通信)           | 最低(进程内直接调用)            |
| 应用场景       | 后台、多进程共享、远程调用场景    | Windows单机GUI应用(聊天窗口等)  |
| 模型存储       | Foundry服务管理                   | AI Dev Gallery示例程序自己管理  |



