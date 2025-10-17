# LLM Inference Memory Estimation Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A comprehensive tool for estimating memory consumption of Large Language Models (LLMs) during inference. This tool helps you plan hardware requirements and optimize deployment configurations for transformer-based models.

## 📋 Table of Contents

- [Scenario](#scenario)
- [QuickStart](#quickstart)
- [Azure Deployment](#azure-deployment)
- [Architecture](#architecture)
- [Features](#features)
- [Usage Options](#usage-options)
- [Memory Calculation Formula](#memory-calculation-formula)
- [Limitations](#limitations)
- [Demo Video](#demo-video)
- [Contributing](#contributing)

## 🎯 Scenario

When deploying Large Language Models for inference, understanding memory requirements is critical for:

- **Infrastructure Planning**: Determine GPU/CPU memory requirements before deployment
- **Cost Optimization**: Select appropriate hardware configurations to balance performance and cost
- **Performance Tuning**: Evaluate the impact of different optimization techniques (FlashAttention, GQA, KV Cache)
- **Batch Size Planning**: Find the optimal batch size for your hardware constraints

This tool provides accurate memory estimates by considering:
- Model parameter memory (based on precision: FP32, FP16, INT8, etc.)
- Activation memory (intermediate computations)
- KV Cache memory (for efficient autoregressive generation)
- Optimization techniques (FlashAttention, Grouped Query Attention)

## 🚀 QuickStart

### Prerequisites

- Python 3.8 or higher
- Internet access to Hugging Face Hub
- Hugging Face API token (for accessing model configurations)

### One-Click Setup and Run

#### Quick Start (Automated Setup)

**Windows PowerShell**:
```powershell
# Clone and run setup script
git clone https://github.com/xinyuwei-david/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory
.\scripts\setup.ps1

# After setup, activate environment and run
.\venv\Scripts\Activate.ps1
python src/cli_estimator.py
```

**Linux/Mac**:
```bash
# Clone and run setup script
git clone https://github.com/xinyuwei-david/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory
chmod +x scripts/setup.sh
./scripts/setup.sh

# After setup, activate environment and run
source venv/bin/activate
python src/cli_estimator.py
```

The setup script will:
- ✅ Check Python installation
- ✅ Create a virtual environment
- ✅ Install all dependencies from `requirements.txt`
- ✅ Provide next steps

#### Option 2: Manual Installation

1. **Clone the repository**:
```bash
git clone https://github.com/xinyuwei-david/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory
```

2. **Install dependencies**:
```bash
pip install transformers torch streamlit
```

3. **Set your Hugging Face API token** (optional but recommended):
```bash
# Windows PowerShell
$env:HF_API_TOKEN="your_huggingface_token_here"

# Linux/Mac
export HF_API_TOKEN="your_huggingface_token_here"
```

### First Demo - Command Line Tool

Run the Python script for interactive memory estimation:

```bash
python src/cli_estimator.py
```

**Example Output**:
```
######################################################################
#                                                                    #
#              Model Memory Consumption Calculator V1.0              #
#         https://github.com/xinyuwei-david/david-share.git          #
#                                                                    #
######################################################################

Enter the model name from Hugging Face: microsoft/phi-4

--- Model Parameters ---
Model Name: microsoft/phi-4
Number of Hidden Layers (L): 40
Hidden Size (h): 5120
Number of Attention Heads (a): 40
Number of Key-Value Heads (g): 10
The model uses Grouped Query Attention (GQA).

--- Adjustable Parameters ---
Number of parameters in the model (n) (in billions): 14.7
Bitwidth of the model's parameters (p) (in bits) [Default 16]: 
Sequence length (s): 16384
Batch size (b) [Default 1]: 1
Use FlashAttention? [Y/n] (Default Y): Y
Use KV Cache? [Y/n] (Default Y): Y

--- Memory Consumption Results ---
Memory consumption of the model: 29.4 GB
Memory consumption of vanilla inference: 91.27 GB
Memory consumption of inference with GQA: 26.26 GB
Memory consumption of inference with FlashAttention: 5.39 GB
Memory consumption of the KV cache (with GQA): 1.34 GB

Total Memory consumption (given the selected configuration): 36.13 GB
```

### First Demo - Web Interface

For a more user-friendly experience, run the Streamlit web application:

```bash
streamlit run src/web_estimator.py
```

This will open a web browser with an interactive interface where you can:
- Enter model names from Hugging Face Hub
- Adjust parameters with sliders and checkboxes
- See real-time memory consumption estimates

### First Demo - Jupyter Notebook

For detailed explanations and step-by-step calculations:

1. Open the Jupyter Notebook:
```bash
jupyter notebook notebooks/memory_estimation.ipynb
```

2. Follow the cells to:
   - Understand the mathematical formulas
   - Customize calculations for your specific use case
   - Visualize memory breakdown by component

## ☁️ Azure 一键部署

### 🚀 使用 Azure Developer CLI (推荐)

**真正的一键部署** - 自动创建资源、构建应用、部署上线

#### 三步部署

```powershell
# 1. 安装 Azure Developer CLI
winget install microsoft.azd

# 2. 登录 Azure
azd auth login

# 3. 一键部署！
azd up
```

**就这么简单！** 🎉

部署完成后会自动：
- ✅ 创建 Azure 资源 (App Service, Application Insights)
- ✅ 配置 HTTPS 和安全设置
- ✅ 部署 Streamlit Web 应用
- ✅ 配置监控和日志
- ✅ 返回应用访问 URL

#### 常用命令

```powershell
# 查看应用 URL
azd env get-value WEB_URI

# 在浏览器中打开
azd browse

# 查看监控和日志
azd monitor

# 重新部署代码
azd deploy

# 删除所有资源
azd down
```

#### 详细文档

查看完整的部署指南、故障排除和高级配置：
📖 [AZURE_AZD_DEPLOYMENT.md](./AZURE_AZD_DEPLOYMENT.md)

---

### 传统方式部署 (可选)

如果您更喜欢使用 Azure CLI 手动部署：

**Step 1: Check Prerequisites**

```powershell
# Windows: Run prerequisites check
.\scripts\check-azure-prerequisites.ps1
```

**Step 2: Deploy**

```powershell
# Windows
.\scripts\deploy-azure.ps1

# Linux/Mac
chmod +x scripts/deploy-azure.sh
./scripts/deploy-azure.sh
```

#### 部署的资源

使用 azd 部署会自动创建：
- ✅ **App Service Plan** (B1 SKU) - 托管环境
- ✅ **Web App** (Python 3.11, Linux) - 运行 Streamlit 应用
- ✅ **Application Insights** - 监控和日志
- ✅ **Log Analytics Workspace** - 日志存储
- ✅ **HTTPS** - 自动配置和强制启用
- ✅ **基础设施即代码 (IaC)** - Bicep 模板版本控制

#### 部署后

部署完成后，您将获得：
- **应用 URL**: `https://app-<env-name>-xxxxx.azurewebsites.net`
- **资源组**: `rg-<env-name>` (管理所有 Azure 资源)
- **监控**: Application Insights 监控面板
- **日志**: 实时应用日志和性能指标

#### 环境变量配置

```powershell
# 使用 azd 设置
azd env set HF_API_TOKEN "your-token-here"
azd deploy

# 或使用 Azure CLI
az webapp config appsettings set \
  --name app-<env-name> \
  --resource-group rg-<env-name> \
  --settings HF_API_TOKEN="your-token-here"
```

#### 相关文档

- 📖 **完整部署指南**: [AZURE_AZD_DEPLOYMENT.md](./AZURE_AZD_DEPLOYMENT.md) - azd 详细文档
- 📖 **传统部署方式**: [AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md) - Azure CLI 手动部署
- 📖 **前置条件**: [AZURE_PREREQUISITES.md](./AZURE_PREREQUISITES.md) - 工具安装指南

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   CLI Tool   │  │   Streamlit  │  │   Jupyter    │      │
│  │ (Interactive)│  │  Web App     │  │  Notebook    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Memory Calculator  │
                  │   Core Engine       │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
┌─────────▼─────────┐ ┌─────▼──────┐ ┌────────▼────────┐
│  Hugging Face     │ │  Model     │ │  Optimization   │
│  Transformers API │ │  Config    │ │  Parameters     │
│  (AutoConfig)     │ │  Parser    │ │  (FA, GQA, KV)  │
└───────────────────┘ └────────────┘ └─────────────────┘
```

### Component Description

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **CLI Tool** | Python 3.8+ | Interactive command-line interface for quick estimates |
| **Web Interface** | Streamlit | User-friendly web UI for non-technical users |
| **Jupyter Notebook** | Jupyter | Educational tool with detailed explanations |
| **Core Calculator** | Python | Implements memory estimation algorithms |
| **Model Config** | Transformers | Fetches model architecture from Hugging Face Hub |
| **Optimization Engine** | Custom Logic | Calculates impact of FlashAttention, GQA, KV Cache |

### Data Flow

1. **Input**: User provides model name (e.g., "meta-llama/Llama-3.3-70B-Instruct")
2. **Configuration Fetch**: Tool retrieves model architecture from Hugging Face
3. **Parameter Collection**: User specifies sequence length, batch size, precision
4. **Memory Calculation**: Core engine computes memory for each component
5. **Optimization Analysis**: Applies selected optimizations (FlashAttention, GQA)
6. **Output**: Displays detailed memory breakdown and total estimate

## ✨ Features

- **Automatic Model Configuration**: Fetches model architecture directly from Hugging Face Hub
- **Multiple Interfaces**: 
  - Command-line tool for automation and scripting
  - Web interface for interactive exploration
  - Jupyter notebook for learning and customization
- **Optimization Support**:
  - FlashAttention memory reduction
  - Grouped Query Attention (GQA)
  - KV Cache memory estimation
- **Flexible Parameters**:
  - Variable precision (FP32, FP16, INT8, INT4)
  - Custom sequence lengths
  - Configurable batch sizes
- **Detailed Breakdown**: Shows memory consumption by component (model, activation, KV cache)

## 📖 Usage Options

### 1. Command Line Tool (src/cli_estimator.py)

Best for: Automation, scripting, CI/CD pipelines

```bash
python src/cli_estimator.py
```

Features:
- Interactive prompts for all parameters
- Supports environment variable for HF token
- Detailed console output

### 2. Streamlit Web Application (src/web_estimator.py)

Best for: Non-technical users, quick experiments, demonstrations

```bash
streamlit run src/web_estimator.py
```

Features:
- Visual interface with forms and sliders
- Real-time results
- No coding required

### 3. Jupyter Notebook (notebooks/memory_estimation.ipynb)

Best for: Learning, research, customization

```bash
jupyter notebook notebooks/memory_estimation.ipynb
```

Features:
- Step-by-step explanations
- Editable code cells
- Visualization support
- Based on [KaitChup's methodology](https://kaitchup.substack.com/p/estimating-memory-usage-for-llms)

## 🧮 Memory Calculation Formula

### Total Memory Formula

```
Total Memory = Model Parameter Memory + Activation Memory + KV Cache Memory + Buffer Memory
```

### Component Breakdown

1. **Model Parameter Memory**:
   ```
   Model Memory = n × (p / 8) GB
   ```
   - `n`: Number of parameters (in billions)
   - `p`: Bits per parameter (16 for FP16, 8 for INT8, etc.)

2. **Activation Memory** (Vanilla Inference):
   ```
   Activation Memory = (32 × s × b × h + 4 × a × s² × b) × 2 / 10⁹ GB
   ```
   - `s`: Sequence length
   - `b`: Batch size
   - `h`: Hidden size
   - `a`: Number of attention heads

3. **Activation Memory with GQA**:
   ```
   GQA Activation = (28 × s × b × h + ((2 × g) / a) × s × b × h + 4 × g × s² × b) × 2 / 10⁹ GB
   ```
   - `g`: Number of key-value heads

4. **Activation Memory with FlashAttention**:
   ```
   FA Activation = (32 × s × b × h + 4 × tile_size × s × b) × 2 / 10⁹ GB
   ```
   - `tile_size`: Typically 128

5. **KV Cache Memory**:
   ```
   KV Cache = 2 × L × s × b × h × 2 / 10⁹ GB
   ```
   - `L`: Number of hidden layers

6. **KV Cache with GQA**:
   ```
   KV Cache (GQA) = 2 × L × s × b × (h / g) × 2 / 10⁹ GB
   ```

### Example Calculation

For **microsoft/phi-4** with:
- Parameters: 14.7B
- Precision: FP16 (16-bit)
- Sequence length: 16,384
- Batch size: 1
- FlashAttention: Enabled
- GQA: Enabled (10 KV heads)

**Results**:
- Model: 29.4 GB
- Activation (FlashAttention): 5.39 GB
- KV Cache (GQA): 1.34 GB
- **Total: 36.13 GB**

## ⚠️ Limitations

### Current Limitations

1. **Approximation Only**: 
   - Estimates are theoretical and may differ from actual runtime memory usage by 5-15%
   - Does not account for framework overhead (PyTorch, TensorFlow)
   - Ignores memory fragmentation

2. **Optimization Assumptions**:
   - FlashAttention tile size fixed at 128
   - Does not model all attention variants (e.g., Multi-Query Attention)
   - Buffer memory is not explicitly calculated

3. **Model Coverage**:
   - Primarily tested on transformer-based models
   - May not accurately estimate memory for models with custom architectures
   - Mixture-of-Experts (MoE) models require special handling

4. **Input Requirements**:
   - Requires manual input of parameter count
   - Needs internet access to fetch model configurations
   - Requires Hugging Face token for gated models

### Recommended Use Cases

✅ **Good For**:
- Planning hardware requirements before deployment
- Comparing memory requirements across different models
- Understanding impact of optimization techniques
- Educational purposes and learning

❌ **Not Suitable For**:
- Precise production capacity planning (use profiling tools instead)
- Models with non-standard architectures
- Training memory estimation (different formula required)

### Accuracy Notes

- Estimates are typically within **10-15%** of actual memory usage for standard transformer models
- For production deployments, always validate with profiling tools:
  - PyTorch: `torch.cuda.memory_allocated()`, `torch.cuda.max_memory_allocated()`
  - NVIDIA: `nvidia-smi`, `nsys`, `ncu`
  - Cloud Monitoring: Azure Monitor, AWS CloudWatch, GCP Cloud Monitoring

## 🎥 Demo Video

***Click the image below to watch the demo video on YouTube***:

[![Estimating Memory Demo](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/nYATNXRr4tA)

## 📚 Additional Resources

- **Hugging Face Transformers**: [Documentation](https://huggingface.co/docs/transformers)

## 🤝 Contributing

Contributions are welcome! Please feel free to:

- Report bugs or issues
- Suggest new features or improvements
- Submit pull requests
- Improve documentation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👤 Author

**David Xinyu Wei**
- GitHub: [@xinyuwei-david](https://github.com/xinyuwei-david)
- Repository: [david-share](https://github.com/xinyuwei-david/david-share)

## 📁 Project Structure

### ✅ Current Structure (Reorganized)

The project has been reorganized for better maintainability:

```
Estimate-Inference-Memory/
├── src/                           # Source code
│   ├── __init__.py               # Python package marker
│   ├── cli_estimator.py          # Command-line tool
│   └── web_estimator.py          # Web interface (Streamlit)
├── notebooks/                     # Jupyter notebooks
│   └── memory_estimation.ipynb   # Main notebook with detailed explanations
├── scripts/                       # Installation and utility scripts
│   ├── setup.sh                  # Linux/Mac setup
│   └── setup.ps1                 # Windows setup
├── docs/                          # Documentation and assets
│   └── images/                   # Screenshots and diagrams
│       ├── 1.png
│       ├── 2.png
│       └── 3.png
├── README.md                      # Main documentation (this file)
├── requirements.txt               # Python dependencies
├── .gitignore                    # Git ignore rules
├── MIGRATION_GUIDE.md            # Migration instructions (if needed)
├── QUICK_REFERENCE.md            # Quick reference guide
├── REORGANIZE.md                 # Reorganization documentation
├── migrate.sh                    # Auto-migration script (Linux/Mac)
└── migrate.ps1                   # Auto-migration script (Windows)
```

### Benefits of This Structure

- 📦 **Better Organization**: Source code, notebooks, and scripts in separate directories
- 🔍 **Easier Navigation**: Clear separation of concerns
- 🛠️ **Professional Standard**: Follows Python project best practices
- 📈 **Scalability**: Easier to add new features and tests
- 🤝 **Collaboration**: Clearer for contributors to understand the project
- ✨ **Cleaner Root**: Less clutter in the root directory

## �🙏 Acknowledgments

- Based on research and methodologies from the machine learning community
- Inspired by [KaitChup's work](https://kaitchup.substack.com/) on LLM memory estimation
- Uses Hugging Face Transformers library for model configuration

---

**Note**: This is an estimation tool. For production deployments, always validate memory requirements with actual profiling and monitoring tools.

