# LLM Inference Memory Estimation Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Azure](https://img.shields.io/badge/Azure-Ready-0078D4?logo=microsoft-azure)](https://azure.microsoft.com/)

A comprehensive tool for estimating memory consumption of Large Language Models (LLMs) during inference. Supports multiple interfaces (CLI, Web, Notebook) and one-click deployment to Azure.

## Table of Contents

- [Scenario](#scenario)
- [Azure One-Click Deployment](#azure-one-click-deployment)
- [Local Deployment](#local-deployment)
- [Usage Options](#usage-options)
- [Architecture](#architecture)
- [Memory Calculation Formula](#memory-calculation-formula)
- [Limitations](#limitations)
- [Contributing](#contributing)

---

## Scenario

When deploying Large Language Models for inference, understanding memory requirements is critical for:

- **Infrastructure Planning**: Determine GPU/CPU memory requirements before deployment
- **Cost Optimization**: Select appropriate hardware configurations to balance performance and cost
- **Performance Tuning**: Evaluate the impact of optimization techniques (FlashAttention, GQA, KV Cache)
- **Batch Size Planning**: Find the optimal batch size for your hardware constraints

This tool provides accurate memory estimates by considering:
- Model parameter memory (FP32, FP16, INT8, INT4, etc.)
- Activation memory (intermediate computations)
- KV Cache memory (for efficient autoregressive generation)
- Optimization techniques (FlashAttention, Grouped Query Attention)

**Example Use Cases**:
- Estimate memory for deploying Llama 3.1 70B with FlashAttention
- Compare memory requirements across different quantization levels
- Plan GPU requirements for batch inference scenarios
- Optimize deployment costs by finding the right precision/hardware balance

---

## Azure One-Click Deployment

### Deploy with Azure Developer CLI (Recommended)

Deploy the Streamlit web application to Azure App Service with a single command.

#### Prerequisites

- **Azure Developer CLI** (azd)
- **Azure Subscription**
- **Azure CLI** (az)

#### Four-Step Deployment

**On Linux**:

```bash
# 1. Clone only this project directory (sparse checkout)
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/Estimate-Inference-Memory
cd Deep-Learning/Estimate-Inference-Memory

# 2. Install Azure Developer CLI
curl -fsSL https://aka.ms/install-azd.sh | bash

# 3. Login to Azure (device code authentication)
az login --use-device-code

# 4. Deploy!
azd up
```

**On Windows**:

```powershell
# 1. Clone only this project directory (sparse checkout)
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/Estimate-Inference-Memory
cd Deep-Learning\Estimate-Inference-Memory

# 2. Install Azure Developer CLI
winget install microsoft.azd

# 3. Login to Azure (device code authentication)
az login --use-device-code

# 4. Deploy!
azd up
```

**That's it!** 

The deployment will:
- Create Azure resources (App Service Plan, Web App, Application Insights)
- Configure HTTPS and security settings
- Deploy Streamlit web application
- Set up monitoring and logging
- Return the application URL

#### First-Time Deployment

When running `azd up` for the first time, you ll be prompted:

```
? Enter a new environment name: dev
? Select an Azure Subscription: [Select your subscription]
? Select an Azure location: East US
```

**Recommended Configuration**:
- Environment name: `dev` (development) or `prod` (production)
- Location: `eastus`, `westus2`, `eastasia`, or closest to your users

#### Post-Deployment Commands

```powershell
# View application URL
azd env get-value WEB_URI

# Open in browser
azd browse

# View monitoring dashboard
azd monitor

# View real-time logs
azd monitor --logs

# Redeploy after code changes
azd deploy

# Delete all Azure resources
azd down
```

#### What Gets Deployed

The Azure deployment creates:

| Resource | Configuration | Purpose |
|----------|--------------|---------|
| **App Service Plan** | B1 SKU (Basic), Linux | Hosting environment |
| **Web App** | Python 3.11 | Streamlit application |
| **Application Insights** | Standard tier | Monitoring and logging |
| **Log Analytics** | Pay-as-you-go | Log storage (5GB free) |

All resources are:
- **HTTPS only** (TLS 1.2+)
- **Auto-configured** for monitoring
- **Infrastructure as Code** (Bicep templates)
- **Environment isolated** (dev/test/prod)

#### Cost Estimation

**Development (Free Tier - F1 SKU)**:
```
App Service Plan (F1):  $0/month
Application Insights:   $0/month (free tier)
Total:                  $0/month
```
F1 limitations: 60 min/day CPU quota, 1GB disk, no custom domain

**Production (Basic Tier - B1 SKU)**:
```
App Service Plan (B1):  ~$55/month
Application Insights:   ~$5/month
Log Analytics:          $0 (5GB free quota)
Total:                  ~$60/month
```

To use free tier, edit `infra/main.bicep` before deployment:
```bicep
sku: {
  name:  F1
  tier:  Free
}
```

#### Environment Variables

Set environment variables for Hugging Face token (optional):

```powershell
# Using azd
azd env set HF_API_TOKEN "your-huggingface-token"
azd deploy

# Or using Azure CLI
az webapp config appsettings set \
  --name app-<env-name> \
  --resource-group rg-<env-name> \
  --settings HF_API_TOKEN="your-token"
```

---

## Local Deployment

### Prerequisites

- Python 3.8 or higher
- Internet access to Hugging Face Hub
- Hugging Face API token (optional, for accessing gated models)

### Quick Start (Automated Setup)

#### Windows PowerShell

```powershell
# Clone repository
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory

# Run setup script
.\scripts\setup.ps1

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run CLI tool
python src/cli_estimator.py
```

#### Linux/Mac

```bash
# Clone repository
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Activate virtual environment
source venv/bin/activate

# Run CLI tool
python src/cli_estimator.py
```

The setup script automatically:
- Checks Python installation
- Creates a virtual environment
- Installs dependencies from `requirements.txt`
- Provides usage instructions

### Manual Installation

If you prefer manual installation:

```bash
# 1. Clone repository
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory

# 2. Create virtual environment (recommended)
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

**Dependencies**:
- `transformers>=4.30.0` - Hugging Face model configurations
- `torch>=2.0.0` - PyTorch (for model calculations)
- `streamlit>=1.28.0` - Web interface framework

### Set Hugging Face Token (Optional)

For accessing gated models or higher rate limits:

```bash
# Windows PowerShell
$env:HF_API_TOKEN="your_huggingface_token_here"

# Linux/Mac
export HF_API_TOKEN="your_huggingface_token_here"
```

Get your token at: https://huggingface.co/settings/tokens

---

## Usage Options

This tool provides three interfaces for different use cases:

### 1. Command Line Interface (Quick Estimates)

Best for: Quick calculations, scripting, CI/CD integration

```bash
python src/cli_estimator.py
```

**Interactive prompts**:
```
Enter the model name from Hugging Face Hub: meta-llama/Meta-Llama-3-70B
Enter the precision (fp32/fp16/int8/int4): fp16
Enable FlashAttention? (yes/no): yes
Enter the number of layers to run: 80
Enter the sequence length: 2048
Enter the batch size: 1
```

**Output**:
```
Model Configuration:
  Model: meta-llama/Meta-Llama-3-70B
  Parameters: 70.55B
  Precision: FP16
  FlashAttention: Enabled

Memory Breakdown:
  Parameters:    141.10 GB
  Activations:   12.58 GB  
  KV Cache:      5.24 GB
  Total:         158.92 GB

Recommendation: Use 2x A100 80GB GPUs with tensor parallelism
```

### 2. Streamlit Web Interface (Interactive Analysis)

Best for: Interactive exploration, parameter tuning, visualization

```bash
streamlit run src/web_estimator.py
```

Opens a web browser with an interactive interface featuring:
- Real-time memory calculations
- Sliders for batch size and sequence length
- Checkboxes for optimization techniques
- Visual memory breakdown
- Export results

**Access**: http://localhost:8501

**Features**:
- Input model names from Hugging Face Hub
- Adjust parameters with sliders
- Toggle FlashAttention, GQA optimizations
- See instant memory updates
- Compare different configurations

### 3. Jupyter Notebook (Educational Deep-Dive)

Best for: Learning, customization, detailed analysis

```bash
jupyter notebook notebooks/memory_estimation.ipynb
```

**Contains**:
- Detailed explanations of formulas
- Step-by-step calculations
- Memory breakdown visualizations
- Customizable calculations
- Optimization recommendations

---

## Architecture

### System Overview

```
User Interface Layer
  CLI Tool      Streamlit      Jupyter
  (Terminal)     Web App       Notebook

Core Calculation Layer
  Memory Estimator Engine
  - Parameter Memory Calculator
  - Activation Memory Calculator
  - KV Cache Calculator
  - Optimization Adjuster (FlashAttention, GQA)

Model Configuration Layer
  Hugging Face Hub Integration
  - AutoConfig loader
  - Model architecture parser
  - Parameter extraction
```

### Project Structure

```
Estimate-Inference-Memory/
 azure.yaml                      # Azure Developer CLI configuration
 infra/                          # Infrastructure as Code (Bicep)
    main.bicep                  # Main Azure resources template
    core/
        host/                   # App Service modules
        monitor/                # Monitoring modules
 src/                            # Application source code
    __init__.py
    cli_estimator.py            # Command-line interface
    web_estimator.py            # Streamlit web interface
 notebooks/
    memory_estimation.ipynb     # Educational Jupyter notebook
 scripts/
    deploy-azd.ps1              # Azure deployment (azd)
    setup.ps1                   # Local setup (Windows)
    setup.sh                    # Local setup (Linux/Mac)
 requirements.txt                # Python dependencies
 startup.sh                      # Azure App Service startup script
 .streamlit/
    config.toml                 # Streamlit configuration
 README.md                       # This file
```

### Technology Stack

- **Python 3.8+**: Core language
- **Transformers**: Hugging Face model configurations
- **PyTorch**: Tensor operations and calculations
- **Streamlit**: Web interface framework
- **Bicep**: Azure infrastructure templates
- **Azure App Service**: Cloud hosting platform

---

## Memory Calculation Formula

### Components

The tool calculates total inference memory as:

```
Total Memory = Parameter Memory + Activation Memory + KV Cache Memory
```

#### 1. Parameter Memory

```
Parameter Memory = Number of Parameters  Bytes per Parameter
```

**Precision mapping**:
- FP32: 4 bytes per parameter
- FP16: 2 bytes per parameter
- INT8: 1 byte per parameter
- INT4: 0.5 bytes per parameter

**Example**:
```
Llama 3.1 70B in FP16:
= 70.55B parameters  2 bytes
= 141.10 GB
```

#### 2. Activation Memory

Activations are intermediate tensors during forward pass:

```
Activation Memory = Batch Size  Sequence Length  Hidden Size  Number of Layers  Multiplier
```

**Multiplier factors**:
- Standard Attention: ~34 (Q, K, V projections, attention scores, etc.)
- FlashAttention: ~10 (optimized memory access patterns)

**Example**:
```
Llama 3.1 70B, batch=1, seq_len=2048, hidden=8192, 80 layers, FlashAttention:
= 1  2048  8192  80  10  2 bytes (FP16)
= 26.84 GB
```

#### 3. KV Cache Memory

For autoregressive generation, past key-value pairs are cached:

```
KV Cache = 2  Batch Size  Sequence Length  Num Layers  Num KV Heads  Head Dim  Precision
```

**With Grouped Query Attention (GQA)**:
```
KV Heads = Total Heads / GQA Groups
```

**Example**:
```
Llama 3.1 70B, batch=1, seq_len=2048, 80 layers, 8 KV heads, head_dim=128, FP16:
= 2  1  2048  80  8  128  2 bytes
= 6.71 GB
```

### Optimization Techniques

| Technique | Memory Reduction | Implementation |
|-----------|------------------|----------------|
| **FlashAttention** | ~70% activation memory | Recompute attention on-the-fly |
| **Grouped Query Attention** | ~60% KV cache | Fewer KV heads than Q heads |
| **INT8 Quantization** | ~50% parameter memory | 8-bit integer precision |
| **INT4 Quantization** | ~75% parameter memory | 4-bit integer precision |
| **Paged Attention** | Dynamic KV cache | Efficient memory paging |

### Accuracy Considerations

This tool provides **estimates** based on standard transformer architectures. Actual memory usage may vary due to:

- Framework overhead (PyTorch, ONNX, TensorRT)
- Gradient checkpointing (if enabled during fine-tuning)
- Custom model architectures
- Batch padding and variable sequence lengths
- CUDA kernel optimizations

**Recommendation**: Add 10-20% buffer for production deployments.

---

## Limitations

### Current Limitations

1. **Training Memory Not Supported**
   - This tool estimates **inference-only** memory
   - Training requires additional memory for:
     - Gradients (equal to parameter memory)
     - Optimizer states (2-3 parameter memory for Adam)
     - Intermediate gradients for backpropagation

2. **Standard Transformer Architectures Only**
   - Assumes standard attention mechanisms
   - May not accurately estimate for:
     - Mixture of Experts (MoE) models
     - Sparse attention models
     - Custom architectures

3. **Framework Overhead Not Included**
   - Estimates exclude:
     - PyTorch framework memory (~1-2GB)
     - CUDA context memory (~0.5-1GB)
     - Model loading overhead

4. **Dynamic Batch Sizes**
   - Estimates assume fixed batch size
   - Dynamic batching may have different memory patterns

5. **Model-Specific Optimizations**
   - Some models have custom memory optimizations
   - Verify estimates with actual deployments

### Best Practices

- Add 15-20% buffer for production deployments
- Test with actual models before production
- Monitor memory usage in real deployments
- Use profiling tools (NVIDIA NSight, PyTorch Profiler)
- Consider batch size variability in production

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### How to Contribute

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m  Add some AmazingFeature `)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/david-share.git
cd david-share/Deep-Learning/Estimate-Inference-Memory

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/
```

### Areas for Contribution

- Bug fixes
- Documentation improvements
- New features (e.g., support for MoE models)
- Additional test cases
- UI/UX improvements
- Internationalization

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- **Hugging Face** for the Transformers library and model hub
- **Streamlit** for the amazing web framework
- **Microsoft Azure** for cloud infrastructure support
- **Open source community** for inspiration and tools

---

## Support

- **Issues**: [GitHub Issues](https://github.com/david-xinyuwei/david-share/issues)
- **Discussions**: [GitHub Discussions](https://github.com/david-xinyuwei/david-share/discussions)
- **Email**: Contact via GitHub profile

---

## Related Resources

- [Hugging Face Model Hub](https://huggingface.co/models)
- [Azure App Service Documentation](https://learn.microsoft.com/azure/app-service/)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Transformers Documentation](https://huggingface.co/docs/transformers/)

---

**Made with  for the AI/ML community**

**Star  this repository if you find it helpful!**
