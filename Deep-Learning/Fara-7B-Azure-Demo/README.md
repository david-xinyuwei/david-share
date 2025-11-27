# Fara-7B Azure H100 Validation & Streamlit Demo

End-to-end validation of Microsoft's first open-source Computer Use Agent (CUA) model on Azure GPU VMs.

## 🎯 Project Overview

This project validates the deployment and performance of **Microsoft Fara-7B** on Azure H100 GPU, with a Streamlit web interface for demonstration.

### About Fara-7B

Microsoft Fara-7B is the **first open-source agentic small language model** specifically designed for computer use automation.

| Attribute | Details |
|-----------|---------|
| **Parameters** | 7.6B (7,615M) |
| **License** | MIT (Open source, commercially usable) |
| **Base Model** | Qwen2.5-VL-7B-Instruct |
| **Architecture** | Qwen2_5_VLForConditionalGeneration |
| **Context Length** | 128K tokens (max_position_embeddings) |
| **Sliding Window** | 32K tokens |

## 🧠 Model Architecture Details

### Text Encoder (LLM Backbone)
| Component | Specification |
|-----------|---------------|
| Hidden Size | 3584 |
| Intermediate Size | 18944 |
| Num Attention Heads | 28 |
| Num Key-Value Heads | 4 (GQA) |
| Num Hidden Layers | 28 |
| Activation | SiLU |
| RoPE θ | 1,000,000 |
| Normalization | RMSNorm (eps=1e-6) |

### Vision Encoder (ViT)
| Component | Specification |
|-----------|---------------|
| Depth | 32 layers |
| Hidden Size | 1280 |
| Num Heads | 16 |
| Patch Size | 14×14 |
| Spatial Merge Size | 2 |
| Temporal Patch Size | 2 (video support) |
| Full Attention Blocks | Layers 7, 15, 23, 31 |
| Output Hidden Size | 3584 (projects to LLM dim) |

## 🎮 Agent Capabilities

### Available Actions (11 types)
Fara implements a `computer_use` tool with the following actions:

| Action | Description | Parameters |
|--------|-------------|------------|
| `left_click` | Click the left mouse button | `coordinate: [x, y]` |
| `mouse_move` | Move cursor to coordinates | `coordinate: [x, y]` |
| `type` | Type text on keyboard | `text`, `press_enter`, `delete_existing_text` |
| `key` | Press keyboard keys | `keys: ["Enter", "Tab", ...]` |
| `scroll` | Scroll mouse wheel | `pixels` (positive=up, negative=down) |
| `visit_url` | Navigate to URL | `url` |
| `web_search` | Perform web search | `query` |
| `history_back` | Browser back button | - |
| `wait` | Wait for page load | `time` (seconds) |
| `pause_and_memorize_fact` | Store information | `fact` |
| `terminate` | End task | `status: "success" | "failure"` |

### Core Agent Functions
```
FaraAgent
├── initialize()              # Set up browser & OpenAI client
├── run()                     # Main execution loop
├── generate_model_call()     # Call vision-language model
├── execute_action()          # Execute parsed action
├── _get_scaled_screenshot()  # Capture & resize screen (1440×900)
├── _parse_thoughts_and_action()  # Extract reasoning & action
└── close()                   # Cleanup resources
```

### Agent Loop (ReAct Pattern)
```
1. Screenshot → 2. Model Inference → 3. Parse Thought/Action → 4. Execute → 5. Repeat
     ↑                                                                           |
     └───────────────────────────────────────────────────────────────────────────┘
```

## ✅ Validated Demo Cases

| Demo | Task | Result |
|------|------|--------|
| Tesla Pricing | Search Model Y starting price in US | **$37,490** (with tax credits) |
| Azure VM Pricing | Find NC A100 v4 series hourly price | **$3.673/hr** (on-demand) |
| Beijing Housing Portal | Navigate to online signing system login | Successfully located "Other Users Login" |
| Form Auto-Fill | Fill and submit test form | Successfully submitted with response |
| GitHub Search | Find Microsoft Fara repo and star count | Successfully navigated and extracted |
| US Government Sites | Browse usa.gov housing information | Successfully extracted key points |

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
├── app.py              # Main app (auto-manages VLLM backend)
├── requirements.txt    # Dependencies
└── README.md           # Documentation
```

### Deploy Streamlit

> **Note**: The Streamlit app now automatically manages the VLLM backend. When launched, it will check if VLLM is running and start it if needed.

```bash
# Install dependencies (no SSH libraries needed - runs locally on GPU VM)
pip install streamlit Pillow

# Start server (VLLM will be auto-started if not running)
streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
```

### Features
- 🚀 **Auto Backend Management**: Automatically starts VLLM if not running
- 📊 Real-time GPU monitoring (VRAM usage, temperature, throughput)
- 🎬 Task execution visualization with structured thought/action/observation display
- 📸 Automatic screenshot gallery with tabs for each action
- 🤖 Model inference status and real-time token throughput
- 🛑 Human intervention support for captchas and verification
- 🏠 Built-in example tasks (GitHub, Hacker News, Wikipedia, US Housing, etc.)

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

*Validation Date: 2025-11-27 | Validated by: Microsoft GBB AI Architect*
