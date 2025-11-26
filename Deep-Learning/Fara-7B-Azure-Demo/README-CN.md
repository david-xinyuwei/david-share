# Fara-7B Azure H100 验证与 Streamlit Demo

微软首个开源 Computer Use Agent (CUA) 模型在 Azure GPU VM 上的端到端验证。

## 🎯 项目概述

本项目验证了 **Microsoft Fara-7B** 模型在 Azure H100 GPU 上的部署和运行效果，并提供了一个 Streamlit Web 界面用于演示。

### Fara-7B 模型简介
- **参数量**: 7B
- **许可证**: MIT (开源可商用)
- **基座模型**: Qwen2.5-VL-7B
- **核心能力**: 自主浏览网页、填写表单、提取信息、完成复杂任务

## ✅ 验证成功案例

| Demo | 任务 | 结果 |
|------|------|------|
| Tesla 价格查询 | 搜索 Model Y 美国起售价 | **$37,490** (含税收抵免) |
| Azure VM 定价 | 查找 NC A100 v4 系列价格 | **$3.673/hr** (按需) |
| 北京住建委导航 | 找到存量房网签系统登录入口 | 成功定位"其他人员登录" |
| 表单自动填写 | 填写并提交测试表单 | 成功提交并获取响应 |

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

### 2. 下载模型

```bash
# 使用 huggingface-cli (需要 token)
huggingface-cli download microsoft/Fara-7B \
    --local-dir ./model_checkpoints/fara-7b \
    --token YOUR_HF_TOKEN

# 或使用镜像站 (中国大陆)
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download microsoft/Fara-7B \
    --local-dir ./model_checkpoints/fara-7b
```

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
├── app.py              # 主应用 (远程 SSH 模式)
├── requirements.txt    # 依赖
└── README.md           # 说明
```

### 部署 Streamlit

```bash
# 安装依赖
pip install streamlit paramiko Pillow

# 启动服务
streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
```

### 功能特性
- 📊 实时 GPU 监控 (VRAM 使用、温度)
- 🎬 任务执行可视化
- 📸 自动截图展示
- 🤖 模型推理状态显示

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

## 📚 参考资源

- [Microsoft Fara GitHub](https://github.com/microsoft/Fara)
- [Fara-7B HuggingFace](https://huggingface.co/microsoft/Fara-7B)
- [VLLM 文档](https://docs.vllm.ai/)
- [Azure GPU VM 定价](https://azure.microsoft.com/pricing/details/virtual-machines/linux/)

## 📄 许可证

本项目代码采用 MIT 许可证。Fara-7B 模型同样采用 MIT 许可证。

---

*验证日期: 2025-11-26 | 验证者: Microsoft GBB AI Architect*
