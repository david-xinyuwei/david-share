# Fara-7B Azure H100 Validation & Streamlit Demo

End-to-end validation of Microsoft's first open-source Computer Use Agent (CUA) model on Azure GPU VMs.

## 🎯 Project Overview

This project validates the deployment and performance of **Microsoft Fara-7B** on Azure H100 GPU, with a Streamlit web interface for demonstration.

### About Fara-7B
- **Parameters**: 7B
- **License**: MIT (Open source, commercially usable)
- **Base Model**: Qwen2.5-VL-7B
- **Core Capabilities**: Autonomous web browsing, form filling, information extraction, complex task completion

## ✅ Validated Demo Cases

| Demo | Task | Result |
|------|------|--------|
| Tesla Pricing | Search Model Y starting price in US | **$37,490** (with tax credits) |
| Azure VM Pricing | Find NC A100 v4 series hourly price | **$3.673/hr** (on-demand) |
| Beijing Housing Portal | Navigate to online signing system login | Successfully located "Other Users Login" |
| Form Auto-Fill | Fill and submit test form | Successfully submitted with response |

## 🖥️ Hardware Requirements

| Config | Minimum | Recommended |
|--------|---------|-------------|
| GPU | A100 40GB | **H100 80GB** |
| VRAM Usage | ~35GB | ~87GB (max_model_len=32768) |
| CPU | 8 cores | 16+ cores |
| RAM | 64GB | 128GB |

> ⚠️ A10 (24GB) has insufficient VRAM for Fara-7B

## 🚀 Quick Deployment

### 1. Environment Setup

```bash
# SSH into Azure GPU VM
ssh root@<your-vm-ip>

# Clone Fara repository
git clone https://github.com/microsoft/Fara.git
cd Fara

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
pip install vllm>=0.6.0

# Install browser
playwright install firefox
apt install -y xvfb firefox
```

### 2. Download Model

```bash
# Using huggingface-cli (requires token)
huggingface-cli download microsoft/Fara-7B \
    --local-dir ./model_checkpoints/fara-7b \
    --token YOUR_HF_TOKEN

# Or use mirror site (for China)
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download microsoft/Fara-7B \
    --local-dir ./model_checkpoints/fara-7b
```

### 3. Start VLLM Server

```bash
# Recommended config for H100 (87GB VRAM)
vllm serve ./model_checkpoints/fara-7b \
    --port 5000 \
    --dtype auto \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.9 \
    --served-model-name microsoft/Fara-7B \
    --trust-remote-code

# Config for A100 40GB (limited context)
vllm serve ./model_checkpoints/fara-7b \
    --port 5000 \
    --dtype float16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.9
```

### 4. Run Tasks

```bash
# Start virtual display
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &

# Execute CUA task
python -m fara.run_fara \
    --task "Search for Tesla Model Y price" \
    --start_page "https://www.tesla.com" \
    --max_rounds 15 \
    --save_screenshots
```

## 🌐 Streamlit Demo Application

### File Structure
```
streamlit_app/
├── app.py              # Main app (remote SSH mode)
├── requirements.txt    # Dependencies
└── README.md           # Documentation
```

### Deploy Streamlit

```bash
# Install dependencies
pip install streamlit paramiko Pillow

# Start server
streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
```

### Features
- 📊 Real-time GPU monitoring (VRAM usage, temperature)
- 🎬 Task execution visualization
- 📸 Automatic screenshot display
- 🤖 Model inference status display

## 📈 Performance Data

**Test Environment**: Azure NC40ads H100 v5 (Korea Central)

| Metric | Value |
|--------|-------|
| VRAM Usage | 87GB / 95GB (91%) |
| Single Step Inference | ~2-5 seconds |
| Full Task Duration | 1-3 minutes (varies by complexity) |
| Idle GPU Temperature | ~40°C |
| Inference GPU Temperature | ~55-65°C |

## 🏠 Business Scenario Examples

### Real Estate Transaction Automation
```bash
python -m fara.run_fara \
    --task "Navigate to existing house online signing system, find personal user login" \
    --start_page "https://zjw.beijing.gov.cn" \
    --max_rounds 10
```

### Price Monitoring
```bash
python -m fara.run_fara \
    --task "Find Azure NC A100 v4 series VM hourly price" \
    --start_page "https://azure.microsoft.com" \
    --max_rounds 8
```

## ⚠️ Known Limitations

1. **Anti-scraping**: Some websites (Zillow, Realtor) block access
2. **Search Rate Limiting**: Frequent Bing searches trigger captchas
3. **Network Latency**: Overseas servers have slower access to Chinese websites
4. **Privacy Protection**: Model refuses operations involving real personal information

## 📚 References

- [Microsoft Fara GitHub](https://github.com/microsoft/Fara)
- [Fara-7B HuggingFace](https://huggingface.co/microsoft/Fara-7B)
- [VLLM Documentation](https://docs.vllm.ai/)
- [Azure GPU VM Pricing](https://azure.microsoft.com/pricing/details/virtual-machines/linux/)

## 📄 License

This project code is under MIT License. Fara-7B model is also under MIT License.

---

*Validation Date: 2025-11-26 | Validated by: Microsoft GBB AI Architect*
