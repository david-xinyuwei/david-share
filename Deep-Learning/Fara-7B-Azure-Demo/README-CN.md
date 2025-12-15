# Fara-7B Azure H100 验证与 Streamlit Demo

微软首个开源 Computer Use Agent (CUA) 模型在 Azure GPU VM 上的端到端验证。

## 🎯 项目概述

本项目验证了 **Microsoft Fara-7B** 模型在 Azure H100 GPU 上的部署和运行效果，并提供了一个 Streamlit Web 界面用于演示。

### Fara-7B 模型简介

Microsoft Fara-7B 是**首个专为计算机自动化操作设计的开源智能体小语言模型**。

| 属性 | 详情 |
|------|------|
| **参数量** | 7.6B (76亿) |
| **许可证** | MIT (开源可商用) |
| **基座模型** | Qwen2.5-VL-7B-Instruct |
| **架构** | Qwen2_5_VLForConditionalGeneration |
| **上下文长度** | 128K tokens (max_position_embeddings) |
| **滑动窗口** | 32K tokens |

## 🧠 模型架构详解

### 文本编码器 (LLM Backbone)
| 组件 | 规格 |
|------|------|
| Hidden Size | 3584 |
| Intermediate Size | 18944 |
| 注意力头数 | 28 |
| KV头数 | 4 (GQA分组查询注意力) |
| 隐藏层数 | 28 |
| 激活函数 | SiLU |
| RoPE θ | 1,000,000 |
| 归一化 | RMSNorm (eps=1e-6) |

### 视觉编码器 (ViT)
| 组件 | 规格 |
|------|------|
| 深度 | 32层 |
| Hidden Size | 1280 |
| 注意力头数 | 16 |
| Patch Size | 14×14 |
| 空间合并尺寸 | 2 |
| 时间Patch尺寸 | 2 (支持视频) |
| 全注意力层 | 第7、15、23、31层 |
| 输出维度 | 3584 (投影到LLM维度) |

## 🎮 智能体能力

### 可用动作 (11种)
Fara 实现了 `computer_use` 工具，支持以下动作：

| 动作 | 描述 | 参数 |
|------|------|------|
| `left_click` | 鼠标左键点击 | `coordinate: [x, y]` |
| `mouse_move` | 移动鼠标到坐标 | `coordinate: [x, y]` |
| `type` | 键盘输入文本 | `text`, `press_enter`, `delete_existing_text` |
| `key` | 按下键盘按键 | `keys: ["Enter", "Tab", ...]` |
| `scroll` | 滚动鼠标滚轮 | `pixels` (正值向上，负值向下) |
| `visit_url` | 访问URL | `url` |
| `web_search` | 执行网页搜索 | `query` |
| `history_back` | 浏览器后退 | - |
| `wait` | 等待页面加载 | `time` (秒) |
| `pause_and_memorize_fact` | 记忆信息 | `fact` |
| `terminate` | 结束任务 | `status: "success" | "failure"` |

### 核心Agent函数
```
FaraAgent
├── initialize()              # 初始化浏览器和OpenAI客户端
├── run()                     # 主执行循环
├── generate_model_call()     # 调用视觉语言模型
├── execute_action()          # 执行解析后的动作
├── _get_scaled_screenshot()  # 截屏并缩放 (1440×900)
├── _parse_thoughts_and_action()  # 提取推理和动作
└── close()                   # 清理资源
```

### 智能体循环 (ReAct模式)
```
1. 截图 → 2. 模型推理 → 3. 解析思考/动作 → 4. 执行 → 5. 重复
    ↑                                                      |
    └──────────────────────────────────────────────────────┘
```

## ✅ 验证成功案例

| Demo | 任务 | 结果 |
|------|------|------|
| Tesla 价格查询 | 搜索 Model Y 美国起售价 | **$37,490** (含税收抵免) |
| Azure VM 定价 | 查找 NC A100 v4 系列价格 | **$3.673/hr** (按需) |
| 北京住建委导航 | 找到存量房网签系统登录入口 | 成功定位"其他人员登录" |
| 表单自动填写 | 填写并提交测试表单 | 成功提交并获取响应 |
| GitHub 搜索 | 查找微软 Fara 仓库和 Star 数 | 成功导航并提取信息 |
| 美国政府网站 | 浏览 usa.gov 住房信息 | 成功提取关键要点 |

## 🖥️ 硬件要求

| 配置 | 最低要求 | 推荐配置 |
|------|----------|----------|
| GPU | A100 40GB | **H100 80GB** |
| VRAM 占用 | ~35GB | ~87GB (max_model_len=32768) |
| CPU | 8核 | 16核+ |
| 内存 | 64GB | 128GB |

> ⚠️ A10 (24GB) 显存不足，无法运行 Fara-7B
https://github.com/user-attachments/assets/90e8acc2-d8db-447e-8e30-cb2b157229cd

https://github.com/user-attachments/assets/d7041c81-b2e4-4413-980e-428135f8f62c

## 🚀 快速部署

### 1. 环境准备

```bash
# SSH 登录 Azure GPU VM
ssh root@<your-vm-ip>

# 克隆 Fara 仓库
git clone https://github.com/microsoft/Fara.git
cd Fara

# 创建虚拟环境
python3.10 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
pip install vllm>=0.6.0

# 安装浏览器
playwright install firefox
apt install -y xvfb firefox
```

### 2. 下载模型 (~16GB)

必须先下载模型才能运行 Streamlit 应用。

```bash
# 创建模型目录
mkdir -p /root/fara/model_checkpoints

# 方式1: 使用 huggingface-cli (需要 HF token)
huggingface-cli download microsoft/Fara-7B \
    --local-dir /root/fara/model_checkpoints/fara-7b \
    --token YOUR_HF_TOKEN

# 方式2: 使用镜像站 (中国大陆，无需token)
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download microsoft/Fara-7B \
    --local-dir /root/fara/model_checkpoints/fara-7b

# 验证下载 (约16GB)
ls -lh /root/fara/model_checkpoints/fara-7b/
# 应看到: config.json, 模型文件, tokenizer 文件等
```

> **注意**: Streamlit 应用 (`app.py`) 默认使用 `/root/fara/model_checkpoints/fara-7b` 路径。如使用其他位置，请修改 `app.py` 中的 `MODEL_PATH` 变量。

### 3. 启动 VLLM 服务

```bash
# H100 推荐配置 (87GB VRAM)
vllm serve ./model_checkpoints/fara-7b \
    --port 5000 \
    --dtype auto \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.9 \
    --served-model-name microsoft/Fara-7B \
    --trust-remote-code

# A100 40GB 配置 (限制上下文)
vllm serve ./model_checkpoints/fara-7b \
    --port 5000 \
    --dtype float16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.9
```

### 4. 运行任务

```bash
# 启动虚拟显示
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &

# 执行 CUA 任务
python -m fara.run_fara \
    --task "搜索Tesla Model Y的价格" \
    --start_page "https://www.tesla.com" \
    --max_rounds 15 \
    --save_screenshots
```

## 🌐 Streamlit Demo 应用

### 文件结构
```
streamlit_app/
├── app.py              # 主应用 (自动管理 VLLM 后端)
├── requirements.txt    # 依赖
└── README.md           # 说明
```

### 部署 Streamlit

> **注意**: Streamlit 应用现在会自动管理 VLLM 后端。启动时会检查 VLLM 是否运行，如未运行会自动启动。

```bash
# 安装依赖 (无需 SSH 库 - 直接在 GPU VM 本地运行)
pip install streamlit Pillow

# 启动服务 (VLLM 未运行时会自动启动)
streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
```

### 功能特性
- 🚀 **自动后端管理**: 自动检测并启动 VLLM 服务
- 📊 实时 GPU 监控 (VRAM 使用、温度、推理吞吐量)
- 🎬 任务执行可视化，结构化展示思考/动作/观察过程
- 📸 自动截图画廊，每个动作独立标签页
- 🤖 模型推理状态和实时 token 吞吐量显示
- 🛑 人工介入支持 (验证码、人机验证等)
- 🏠 内置示例任务 (GitHub、Hacker News、Wikipedia、US Housing 等)

## 📈 性能数据

**测试环境**: Azure NC40ads H100 v5 (Korea Central)

| 指标 | 数值 |
|------|------|
| VRAM 占用 | 87GB / 95GB (91%) |
| 单步推理时间 | ~2-5秒 |
| 完整任务耗时 | 1-3分钟 (视复杂度) |
| GPU 空闲温度 | ~40°C |
| GPU 推理温度 | ~55-65°C |

## 🏠 业务场景示例

### 房产交易自动化 (贝壳场景)
```bash
python -m fara.run_fara \
    --task "进入存量房网上签约系统，找到个人用户登录入口" \
    --start_page "https://zjw.beijing.gov.cn" \
    --max_rounds 10
```

### 价格监控
```bash
python -m fara.run_fara \
    --task "查找Azure NC A100 v4系列虚拟机的每小时价格" \
    --start_page "https://azure.microsoft.com" \
    --max_rounds 8
```

## ⚠️ 已知限制

1. **反爬机制**: 部分网站 (Zillow, Realtor) 会拒绝访问
2. **搜索频率**: 频繁使用 Bing 搜索会触发验证码
3. **网络延迟**: 海外服务器访问中国网站较慢
4. **隐私保护**: 模型会拒绝涉及真实个人隐私的操作

## 🔄 Human-in-the-Loop (HITL) 人机协作

https://github.com/user-attachments/assets/b62f7a34-aa41-4a69-8fdb-59a1c65eeb72

### 什么是 HITL？

HITL 允许智能体**暂停执行、请求用户输入、然后根据人类指导继续**。这对以下场景至关重要：
- 确认敏感操作（购买、预订）
- 任务中途获取额外信息
- 智能体卡住时重新引导

### Fara 原生 HITL：Critical Points（关键点）

Fara 模型内置了 "Critical Points" 机制 - 在敏感操作前自动停止：

```
任务: "预订飞往纽约的机票"
→ 智能体导航到预订网站
→ 智能体填写表单
→ 智能体到达支付页面
→ 关键点: 智能体停止并报告 "准备进行支付"
```

这是**任务终止**，而非暂停后继续。

### 框架级 HITL：暂停 → 输入 → 继续

要实现真正的交互式 HITL（暂停、获取输入、继续），需要框架支持。我们使用 **Magentic-UI** 验证了此功能，但需要修改代码。

### Magentic-UI + Fara HITL 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Magentic-UI                              │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │   前端      │◄──►│  connection.py   │◄──►│ _fara_web_     │ │
│  │  (React)    │    │  (WebSocket)     │    │  surfer.py     │ │
│  └─────────────┘    └──────────────────┘    └───────┬────────┘ │
│                                                      │          │
│                                              ┌───────▼────────┐ │
│                                              │  OpenAI API    │ │
│                                              │    客户端       │ │
│                                              └───────┬────────┘ │
└──────────────────────────────────────────────────────┼──────────┘
                                                       │
                                               ┌───────▼────────┐
                                               │     vLLM       │
                                               │    Fara-7B     │
                                               │  (port 5000)   │
                                               └────────────────┘
```

**关键点**：
- `connection.py` 和 `_fara_web_surfer.py` 在 **Magentic-UI 内部**（需要修改）
- vLLM 在 **框架外部** 作为独立推理服务运行
- Magentic-UI 通过 OpenAI 兼容 API 调用 vLLM

### ⚠️ 必需的代码修改（3个文件）

Magentic-UI 默认的 HITL 实现不完全支持 Fara 的 `pause_and_memorize_fact` 动作。需要修改 3 个文件：

#### 1. `_fara_web_surfer.py`（2处修改）

**文件**: `.venv/lib/python3.10/site-packages/magentic_ui/agents/web_surfer/fara/_fara_web_surfer.py`

**问题**: 当 Fara 调用 `pause_and_memorize_fact` 时，agent 设置 `is_paused=True` 然后 `break`，导致任务结束。

**如何定位**: 搜索 `self.is_paused = True`，会找到 2 处，都紧跟着 `break`。

**修复**: 将两处都从：

```python
self.is_paused = True
break
```

改为：

```python
self.is_paused = True
while self.is_paused:
    await asyncio.sleep(0.5)
```

#### 2. `connection.py` - 暂停时发送 input_request

**文件**: `.venv/lib/python3.10/site-packages/magentic_ui/backend/web/managers/connection.py`

**问题**: 前端只有收到 `type: "input_request"` 才显示输入框，但 FaraWebSurfer 发送的是 `type: "paused"`。

**如何定位**: 搜索 `async for message in run_context` 或 WebSocket 消息处理循环。

**修复**: 在消息处理循环内添加以下检测：

```python
async for message in run_context:
    # ... 现有的消息处理 ...
    
    # 添加此代码块:
    if '"type": "paused"' in str(message) or (hasattr(message, 'type') and getattr(message, 'type', None) == 'paused'):
        await websocket.send_json({
            "type": "input_request", 
            "prompt": "Agent paused. Enter your instruction to continue:",
            "run_id": run_id
        })
```

#### 3. `connection.py` - 用户输入后恢复执行

**文件**: 同上

**问题**: 用户提交输入后，agent 不会从暂停状态恢复。

**如何定位**: 搜索 `async def handle_input_response` 或 `handle_input_response`。

**修复**: 在 `handle_input_response` 方法末尾添加：

```python
async def handle_input_response(self, run_id: str, response: str):
    # ... 现有的保存响应代码 ...
    
    # 在末尾添加此行:
    await self.resume_run(run_id)
```

### 前置条件

配置 Magentic-UI HITL 前，确保：

1. **vLLM 已启动** 并加载 Fara-7B 模型：
```bash
vllm serve /path/to/fara-7b \
    --port 5000 \
    --dtype auto \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.9 \
    --served-model-name microsoft/Fara-7B \
    --trust-remote-code
```

2. **验证 vLLM 正常响应**：
```bash
curl http://localhost:5000/v1/models
# 应返回: {"data":[{"id":"microsoft/Fara-7B",...}]}
```

### 配置 Magentic-UI 与 Fara

```bash
# 克隆并安装
git clone https://github.com/microsoft/magentic-ui.git
cd magentic-ui
pip install -e .

# 应用上述 3 处代码修改

# 创建 Fara 配置文件
cat > fara_config.yaml << 'CONFIG'
base_url: "http://127.0.0.1:5000/v1"
api_key: "not-needed"
model: "microsoft/Fara-7B"
structured_output: true
json_output: true
CONFIG

# 启动 (需要 vLLM 在 5000 端口运行)
export OPENAI_API_KEY=not-needed
magentic ui --fara --port 8081 --config fara_config.yaml
```

### HITL 验证结果

| 步骤 | 动作 | 结果 |
|------|------|------|
| 1 | 任务: "搜索微软股价" | 智能体导航到金融网站 |
| 2 | 智能体找到价格: $483.47 | 智能体调用 `pause_and_memorize_fact` |
| 3 | UI 显示输入提示 | 用户看到 "等待您的输入" |
| 4 | 用户输入: "现在搜索 NVIDIA 股价" | 智能体继续执行新任务 |
| 5 | 智能体找到 NVIDIA: $180.93 | 成功完成 |

### Learn Plan（学习计划）功能

Magentic-UI 的 "Learn Plan" 可从任务执行中提取可复用的工作流。此功能需要配置中设置 `structured_output: true`。

## 📄 许可证

本项目代码采用 MIT 许可证。Fara-7B 模型同样采用 MIT 许可证。

---

*验证日期: 2025-11-27 | HITL 验证: 2025-12-12 | 验证者: Microsoft GBB AI Architect*

