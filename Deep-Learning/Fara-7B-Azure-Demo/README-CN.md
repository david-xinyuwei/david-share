# Fara-7B Azure H100 验证与 Streamlit Demo

微软首个开源 Computer Use Agent (CUA) 模型在 Azure GPU VM 上的端到端验证。

#### Demo 1

https://github.com/user-attachments/assets/d7041c81-b2e4-4413-980e-428135f8f62c

#### Demo 2

https://github.com/user-attachments/assets/90e8acc2-d8db-447e-8e30-cb2b157229cd

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

### 房产交易自动化
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

## 📚 参考资源

- [Microsoft Fara GitHub](https://github.com/microsoft/Fara)
- [Fara-7B HuggingFace](https://huggingface.co/microsoft/Fara-7B)
- [VLLM 文档](https://docs.vllm.ai/)
- [Azure GPU VM 定价](https://azure.microsoft.com/pricing/details/virtual-machines/linux/)

## 📄 许可证

本项目代码采用 MIT 许可证。Fara-7B 模型同样采用 MIT 许可证。

---

*验证日期: 2025-11-27 | 验证者: Microsoft GBB AI Architect*


