# AML and AI Foundry Model Catalog Models Performance Evaluation

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Azure](https://img.shields.io/badge/Azure-AI%20Foundry-0078D4.svg)](https://azure.microsoft.com/en-us/products/ai-services)
[![Azure Developer CLI](https://img.shields.io/badge/azd-supported-blue.svg)](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
[![Infrastructure as Code](https://img.shields.io/badge/IaC-Bicep-blue.svg)](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 🚀 **Comprehensive performance evaluation toolkit for Azure Machine Learning and AI Foundry Model Catalog**  
> 💡 **One-click deployment with Azure Developer CLI (azd) support**

## 📋 Table of Contents

- [Overview](#overview)
- [Deployment Methods Comparison](#deployment-methods-comparison)
- [Prerequisites](#prerequisites)
- [Part 1: Managed Compute Performance Testing](#part-1-managed-compute-performance-testing)
  - [Infrastructure Setup](#1️⃣-infrastructure-setup)
  - [Model Deployment](#2️⃣-model-deployment)
  - [Quick Cleanup](#🧹-quick-cleanup-delete-endpoints)
  - [Performance Testing](#4️⃣-performance-testing)
- [Part 2: Azure AI Model Inference Performance Testing](#part-2-azure-ai-model-inference-performance-testing)
  - [What is AI Model Inference](#1️⃣-what-is-azure-ai-model-inference)
  - [Quota and Limits](#2️⃣-supported-models--quota)
  - [Performance Testing](#3️⃣-performance-testing)
  - [Test Results](#4️⃣-test-results)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Contributing](#contributing)

## 🎯 Overview

This repository provides comprehensive performance evaluation tools for Azure AI models, supporting **two deployment methods**:

1. **Managed Compute** - Deploy open-source models on Azure GPU VMs (NC/ND series)
2. **Azure AI Model Inference** - Test pre-deployed serverless models (OpenAI, DeepSeek, Phi, Mistral)

### 📊 Deployment Methods Comparison

| Feature | **Managed Compute** | **AI Model Inference (Serverless)** |
|---------|---------------------|-------------------------------------|
| **Model Types** | Open models, custom models | Flagship models (OpenAI, DeepSeek, Phi, Mistral) |
| **Infrastructure** | GPU VMs (NC/ND series) | No infrastructure needed |
| **Deployment Resource** | AI project / AML workspace | Azure AI services resource |
| **Billing** | VM hourly rate | Pay-per-token |
| **Best For** | Custom models, full control, PoC | Production-ready models, quick testing |
| **Quota Type** | VM cores quota | Token/request quota |
| **Deployment Time** | 10-20 minutes | Instant (pre-deployed) |
| **Testing Approach** | Deploy → Test → Delete | Test directly with endpoint |

**Choose your path:**
- 👉 [Part 1: Managed Compute](#part-1-managed-compute-performance-testing) - Full control over GPU resources
- 👉 [Part 2: AI Model Inference](#part-2-azure-ai-model-inference-performance-testing) - Serverless testing

---

### 🎯 What This Repository Does

**For Managed Compute (Part 1):**
- ✅ Automated infrastructure deployment with `azd up`
- ✅ Deploy 15+ open-source models from Model Catalog
- ✅ Performance testing with real prompts
- ✅ Metrics: TTFT, TPS, throughput, concurrency handling
- ✅ Auto-cleanup after testing

**For AI Model Inference (Part 2):**
- ✅ Test pre-deployed serverless models (OpenAI, DeepSeek, Phi, etc.)
- ✅ No infrastructure needed - just endpoint URL + API key
- ✅ Same comprehensive performance metrics
- ✅ Stream mode support
- ✅ High-concurrency testing

## ✨ Features

- ✅ **One-Click Deployment**: Azure Developer CLI (azd) support for automated infrastructure setup
- ✅ **Infrastructure as Code**: Complete Bicep templates for reproducible deployments
- ✅ **Observability Built-in**: Application Insights integration with correlation ID tracking
- ✅ **Automated Deployment**: Quick deployment of AI models on Azure ML/AI Foundry
- ✅ **Performance Testing**: Multi-scenario stress testing with real prompts
- ✅ **Comprehensive Metrics**: TTFT, tokens/s, throughput analysis
- ✅ **Easy Cleanup**: Fast endpoint deletion after PoC
- ✅ **Model Support**: 15+ models including Phi-4, Llama, Mistral, DeepSeek, and more
- ✅ **Easy Cleanup**: Fast endpoint deletion after PoC
- ✅ **Model Support**: 15+ models including Phi-4, Llama, Mistral, DeepSeek, and more

## 📦 Prerequisites

### Common Requirements (Both Parts)

- **Azure Subscription** with active credits
- **Azure CLI** installed and logged in (`az login`)
- **Python 3.9+** installed
- **Git** for cloning the repository

### Additional for Part 1 (Managed Compute)

- **GPU Quota** available in your subscription:
  - NC24/48/96ads_A100_v4 (A100 GPUs)
  - NC40/80ads_H100_v5 (H100 GPUs)
- **Azure Developer CLI (azd)** - [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- **Conda** or **virtualenv** for Python environment management

### Additional for Part 2 (AI Model Inference)

- **Azure AI Foundry** project or **Azure AI services** resource
- **Deployed model endpoint** (DeepSeek, Phi, OpenAI, etc.)
- **API Key** for the endpoint

---

## � Part 1: Managed Compute Performance Testing

> Deploy and test open-source and custom models on Azure GPU VMs with full control

### Complete Workflow

```
1. Infrastructure Setup (azd up)
   ↓
2. Model Deployment (Python script)
   ↓
3. Quick Cleanup (Delete endpoints)
   ↓
4. Performance Testing (Default parameters)
   ↓
5. Cleanup (Delete all resources)
```

---

### 1️⃣ Infrastructure Setup

#### Deploy with Azure Developer CLI (azd)

```bash
# 1. Clone repository (sparse checkout for this project only)
git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Deep-Learning/AI-Foundry-Model-Performance
cd Deep-Learning/AI-Foundry-Model-Performance

# 2. Install azd
curl -fsSL https://aka.ms/install-azd.sh | bash

# 3. Create Python environment and install dependencies
conda create -n aml_env python=3.9 -y
conda activate aml_env
pip install -r requirements.txt

# 4. Login to Azure
az login
azd auth login --use-device-code

# 5. Check GPU quota
bash scripts/deployment/check-gpu-quota.sh

# 6. Deploy infrastructure
azd up
```

**What `azd up` does:**
- ✅ Creates Azure Resource Group
- ✅ Deploys Application Insights + Log Analytics for observability
- ✅ Creates Storage Account for ML workspace
- ✅ Deploys Key Vault for secure credential management

---

#### Alternative: Use Existing Workspace

Skip `azd up` if you already have an Azure ML workspace. The deployment script will auto-detect it.

---

### 2️⃣ Model Deployment

| **Model Name on AML**                         | **Model on HF** (tokenizers name)             | **Azure GPU VM SKU Support in AML**              |
| --------------------------------------------- | --------------------------------------------- | ------------------------------------------------ |
| Phi-4                                         | microsoft/phi-4                               | NC24/48/96 A100                                  |
| Phi-3.5-vision-instruct                       | microsoft/Phi-3.5-vision-instruct             | NC24/48/96 A100                                  |
| financial-reports-analysis                    |                                               | NC24/48/96 A100                                  |
| Llama-3.2-11B-Vision-Instruct                 | meta-llama/Llama-3.2-11B-Vision-Instruct      | NC24/48/96 A100                                  |
| Phi-3-small-8k-instruct                       | microsoft/Phi-3-small-8k-instruct             | NC24/48/96 A100                                  |
| Phi-3-vision-128k-instruct                    | microsoft/Phi-3-vision-128k-instruct          | NC48 A100 or NC96 A100                           |
| microsoft-swinv2-base-patch4-window12-192-22k | microsoft/swinv2-base-patch4-window12-192-22k | NC24/48/96 A100                                  |
| mistralai-Mixtral-8x7B-Instruct-v01           | mistralai/Mixtral-8x7B-Instruct-v0.1          | NC96 A100                                        |
| Muse                                          | microsoft/wham                                | NC24/48/96 A100                                  |
| openai-whisper-large                          | openai/whisper-large                          | NC48 A100 or NC96 A100                           |
| snowflake-arctic-base                         | Snowflake/snowflake-arctic-base               | ND H100V5                                        |
| Nemotron-3-8B-Chat-4k-SteerLM                 | nvidia/nemotron-3-8b-chat-4k-steerlm          | NC24/48/96 A100                                  |
| stabilityai-stable-diffusion-xl-refiner-1-0   | stabilityai/stable-diffusion-xl-refiner-1.0   | Standard_ND96amsr_A100_v4 or Standard_ND96asr_v4 |
| microsoft-Orca-2-7b                           | microsoft/Orca-2-7b                           | NC24/48/96 A100                                  |

```bash
python scripts/deployment/deploymodels-linux-20250405.py
```

https://github.com/user-attachments/assets/cc9065e9-bbf1-4f59-a7b8-57b8c9703db3

**The script will:**

- Auto-detect subscription, resource groups, and ML workspaces
- Prompt for model selection (Phi-4, Llama, Mixtral, etc.)
- Check GPU quota and suggest available regions
- Deploy model to managed online endpoint
- Return endpoint URL + API key

---

#### Supported Models and VM SKUs

By now, the AML names tested in this repo, their full names on Hugging Face, and the Azure GPU VM SKUs that can be deployed on AML are as follows.

> 💡 **Common Issue**: If you see `ERR_CONNECTION_REFUSED` or browser doesn't open, you're on a remote server. Use `azd auth login --use-device-code` instead.

---

### 🧹 Quick Cleanup (Delete Endpoints)

> ⚠️ **Important**: GPU endpoints are expensive! Delete them after testing to avoid unnecessary charges.

```bash
# Delete endpoint after testing
python scripts/deployment/delete-endpoint-20250327.py

# Or delete all Azure resources
azd down
```

https://github.com/user-attachments/assets/8be25ceb-6c47-45b3-bfa6-34dbc79f6732

---

### 4️⃣ Performance Testing 

> ⚠️ **Notes**:
> - Test results are for reference only. Use the provided scripts to test in your environment.
> - Timeout default: 90s (same as `request_settings.request_timeout_ms`). Failed requests after 3x 429 errors.
> - Analyze multiple metrics: success rate, TTFT, tokens/s. Don't focus on a single indicator.
> - Tests use default Endpoint settings without adjusting `max_concurrent_requests_per_instance` or `request_timeout_ms`.

The primary goal of performance testing is to verify tokens/s and TTFT during the inference process. To better simulate real-world scenarios, I have set up several common LLM/SLM use cases in the test script. Additionally, to ensure tokens/s performance, the test script needs to load the corresponding model's tokenizer during execution (Refer to upper table of tokenizers name).

​	Endpoint Default parameters value

| Parameter                                             | Value |
| ----------------------------------------------------- | ----- |
| instance_count                                        | 1     |
| liveness_probe.failure_threshold                      | 30    |
| liveness_probe.initial_delay                          | 600   |
| liveness_probe.period                                 | 10    |
| liveness_probe.success_threshold                      | 1     |
| liveness_probe.timeout                                | 2     |
| readiness_probe.failure_threshold                     | 30    |
| readiness_probe.initial_delay                         | 10    |
| readiness_probe.period                                | 10    |
| readiness_probe.success_threshold                     | 1     |
| readiness_probe.timeout                               | 2     |
| request_settings.max_concurrent_requests_per_instance | 1     |
| request_settings.request_timeout_ms                   | 90000 |

 I will use Phi4 on Azure NC24 A100 as an example to demonstrate the performance changes after adjusting `request_settings.max_concurrent_requests_per_instance` to 10 and `request_settings.request_timeout_ms` to 180 seconds.

[![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/raw/main/images/22.png)](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/22.png)

Modify 2 parameters:

```
az ml online-deployment update -g <resource-group> -w <workspace-name> -n <deployment-name> -e <endpoint-name> --set request_settings.max_concurrent_requests_per_instance=<value> request_settings.max_concurrent_requests_per_instance=<value> 
```



custom-deployment is fix deployment name value in my deployment script

```
xinyu [ ~ ]$  az ml online-deployment update -g A100VM_group -w xinyu-workspace-westus -n custom-deployment -e custom-endpoint-1743836288 --set request_settings.request_timeout_ms=180000 request_settings.max_concurrent_requests_per_instance=10
```

Check new parameters:

```
az ml online-deployment show \
--name custom-deployment \
--endpoint-name custom-endpoint-1743836288 \
--resource-group A100VM_group \
--workspace-name xinyu-workspace-westus \
--output json
```

https://github.com/user-attachments/assets/8bd23c08-6937-4f3b-93d1-a7f3b3e2abd9

#### 4️⃣ Performance Test

Before officially starting the test, you need to log in to HuggingFace on your terminal.

```bash
huggingface-cli login
```

---

<details>
<summary><h4>📝 Phi Text2Text Series (Phi-4/Phi-3-small-8k-instruct)</h4></summary>

**Run the test script:**

```bash
python scripts/testing/press-phi4-0403.py
```

https://github.com/user-attachments/assets/5560e1b8-22ea-4569-988e-7e361422ba0b



**Interactive Input Example:**

```text
Please enter the API service URL: https://david-workspace-westeurop-ldvdq.westeurope.inference.ml.azure.com/score
Please enter the API Key: Ef9DFpATsXs4NiWyoVhEXeR4PWPvFy17xcws5ySCvV2H8uOUfgV4JQQJ99BCAAAAAAAAAAAAINFRAZML3eIO
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/phi-4
Tokenizer loaded successfully: microsoft/phi-4
```

##### Test Result Analysis

**microsoft/phi-4**

**Concurrency = 1**

| Scenario                 | VM 1 (1-nc48) TTFT (s) | VM 2 (2-nc24) TTFT (s) | VM 3 (1-nc24) TTFT (s) | VM 1 (1-nc48) tokens/s | VM 2 (2-nc24) tokens/s | VM 3 (1-nc24) tokens/s |
| ------------------------ | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- |
| **Text Generation**      | 12.473                 | 19.546                 | 19.497                 | 68.07                  | 44.66                  | 44.78                  |
| **Question Answering**   | 11.914                 | 15.552                 | 15.943                 | 72.10                  | 44.56                  | 46.04                  |
| **Translation**          | 2.499                  | 3.241                  | 3.411                  | 47.62                  | 33.32                  | 34.59                  |          | 2.499                  | 3.241                  | 3.411                  | 47.62                  | 33.32                  | 34.59                  |
| **Text Summarization**   | 2.811                  | 4.630                  | 3.369                  | 50.16                  | 37.36                  | 33.84                  |
| **Code Generation**      | 20.441                 | 27.685                 | 26.504                 | 83.12                  | 51.58                  | 52.26                  |
| **Chatbot**              | 5.035                  | 9.349                  | 8.366                  | 64.55                  | 43.96                  | 41.24                  |
| **Sentiment Analysis**   | 1.009                  | 1.235                  | 1.241                  | 5.95                   | 12.96                  | 12.89                  |
| **Multi-turn Reasoning** | 13.148                 | 20.184                 | 19.793                 | 76.44                  | 47.12                  | 47.29                  |

**Concurrency = 2**

| Scenario                 | VM 1 (1-nc48) Total TTFT (s) | VM 2 (2-nc24) Total TTFT (s) | VM 3 (1-nc24) Total TTFT (s) | VM 1 (1-nc48) Total tokens/s | VM 2 (2-nc24) Total tokens/s | VM 3 (1-nc24) Total tokens/s |
| ------------------------ | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- |
| **Text Generation**      | 19.291                       | 19.978                       | 24.576                       | 110.94                       | 90.13                        | 79.26                        |
| **Question Answering**   | 14.165                       | 15.906                       | 21.774                       | 109.94                       | 90.87                        | 66.67                        |
| **Translation**          | 3.341                        | 4.513                        | 10.924                       | 76.45                        | 53.95                        | 68.54                        |
| **Text Summarization**   | 3.494                        | 3.664                        | 6.317                        | 77.38                        | 69.60                        | 59.45                        |
| **Code Generation**      | 16.693                       | 26.310                       | 27.772                       | 162.72                       | 104.37                       | 53.22                        |
| **Chatbot**              | 8.688                        | 9.537                        | 12.064                       | 100.09                       | 87.67                        | 67.23                        |
| **Sentiment Analysis**   | 1.251                        | 1.157                        | 1.229                        | 19.99                        | 20.09                        | 16.60                        |
| **Multi-turn Reasoning** | 20.233                       | 23.655                       | 22.880                       | 110.84                       | 94.47                        | 88.79                        |

> 📊 **Full original test results**: [phi4-test-results.md](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/phi4-test-results.md)

---

**microsoft/Phi-3-small-8k-instruct**

| Scenario                             | Concurrency | VM 1 (1-nc48) TTFT (s) | VM 2 (2-nc24) TTFT (s) | VM 3 (1-nc24) TTFT (s) | VM 1 (1-nc48) tokens/s | VM 2 (2-nc24) tokens/s | VM 3 (1-nc24) tokens/s |
| ------------------------------------ | ----------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- |
| Text Generation                      | 1           | 9.530                  | 9.070                  | 9.727                  | 68.41                  | 69.79                  | 66.31                  |
| Text Generation                      | 2           | 12.526                 | 13.902                 | 15.290                 | 105.02                 | 101.46                 | 92.11                  |
| Question Answering                   | 1           | 6.460                  | 7.401                  | 6.041                  | 65.64                  | 68.50                  | 65.22                  |
| Question Answering                   | 2           | 8.282                  | 6.851                  | 10.502                 | 89.15                  | 135.39                 | 103.23                 |
| Translation                          | 1           | 6.983                  | 8.552                  | 5.640                  | 67.02                  | 69.57                  | 66.13                  |
| Translation                          | 2           | 3.416                  | 5.951                  | 7.472                  | 73.14                  | 117.58                 | 82.20                  |
| Text Summarization                   | 1           | 2.570                  | 2.690                  | 2.004                  | 44.36                  | 55.39                  | 42.42                  |
| Text Summarization                   | 2           | 3.567                  | 3.197                  | 3.705                  | 75.13                  | 77.44                  | 81.46                  |
| Code Generation                      | 1           | 5.757                  | 1.991                  | 13.481                 | 74.69                  | 42.19                  | 83.15                  |
| Code Generation                      | 2           | 11.920                 | 14.886                 | 23.472                 | 91.85                  | 162.29                 | 115.73                 |
| Chatbot                              | 1           | 3.691                  | 3.160                  | 4.172                  | 54.46                  | 60.13                  | 62.80                  |
| Chatbot                              | 2           | 6.593                  | 3.633                  | 6.296                  | 92.07                  | 116.56                 | 100.43                 |
| Sentiment Analysis / Classification  | 1           | 0.957                  | 0.792                  | 0.783                  | 5.22                   | 6.31                   | 6.38                   |
| Sentiment Analysis / Classification  | 2           | 1.189                  | 1.015                  | 2.102                  | 8.44                   | 9.90                   | 52.12                  |
| Multi-turn Reasoning / Complex Tasks | 1           | 16.343                 | 26.220                 | 11.602                 | 72.45                  | 73.91                  | 72.23                  |
| Multi-turn Reasoning / Complex Tasks | 2           | 16.808                 | 12.774                 | 18.725                 | 149.10                 | 145.65                 | 136.84                 |

> 📊 **Full original test results**: [Phi-3-small-8k-instruct-test-results.md](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/Phi-3-small-8k-instruct-test-results.md)

</details>

---

<details>
<summary><h4>🖼️ Phi Vision Series (Phi-3.5-vision-instruct/Phi-3-vision-128k-instruct)</h4></summary>

```bash
python scripts/testing/press-phi35and0v-20250323.py
```

##### Phi-3.5-vision-instruct with Single Image Input

**On NC24 A100 VM:**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.117            | 57.17                                 | 57.17                       | 2.126              |
| 2           | 2                   | 0               | 4.348            | 18.85                                 | 37.71                       | 7.722              |
| 3           | 3                   | 0               | 3.389            | 49.50                                 | 148.50                      | 6.354              |
| **4**       | **4**               | **0**           | **2.898**        | **49.22**                             | **196.86**                  | **7.207**          |
| 5           | 4                   | 1               | 2.708            | 41.63                                 | 166.53                      | 8.942              |
| 6           | 5                   | 1               | 2.095            | 32.30                                 | 161.52                      | 8.951              |
| 7           | 5                   | 2               | 2.774            | 48.95                                 | 244.75                      | 8.966              |
| 8           | 4                   | 4               | 2.841            | 48.30                                 | 193.21                      | 8.953              |
| 9           | 4                   | 5               | 2.996            | 41.86                                 | 167.43                      | 8.960              |
| 10          | 4                   | 6               | 2.874            | 45.60                                 | 182.38                      | 8.958              |

**Phi-3-vision-128k-instruct with single image input test result analyze：**

**On NC48 VM：**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.124            | 46.13                                 | 46.13                       | 2.130              |
| 2           | 2                   | 0               | 2.828            | 44.21                                 | 88.41                       | 3.858              |
| 3           | 3                   | 0               | 3.432            | 47.35                                 | 142.04                      | 6.437              |
| **4**       | **4**               | **0**           | **2.497**        | **42.99**                             | **171.96**                  | **7.060**          |
| 5           | 4                   | 1               | 3.447            | 47.35                                 | 189.39                      | 8.948              |
| 6           | 5                   | 1               | 2.291            | 38.98                                 | 194.92                      | 8.964              |
| 7           | 4                   | 3               | 3.099            | 41.58                                 | 166.34                      | 8.956              |
| 8           | 4                   | 4               | 2.247            | 34.58                                 | 138.31                      | 8.960              |
| 9           | 5                   | 4               | 2.321            | 36.79                                 | 183.96                      | 8.952              |
| 10          | 5                   | 5               | 2.466            | 36.55                                 | 182.77                      | 8.950              |

</details>

---

<details>
<summary><h4>📊 financial-reports-analysis Series test</h4></summary>

```bash
python scripts/testing/press.financial-reports-analysis-20250321.py
```

**1-nc48**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 8.347            | 74.76                                 | 74.76                       | 8.352              |
| **2**       | **2**               | **0**           | **16.248**       | **63.78**                             | **127.56**                  | **21.386**         |
| 3           | 2                   | 1               | 13.939           | 65.47                                 | 130.95                      | 18.746             |
| 4           | 2                   | 2               | 17.377           | 60.21                                 | 120.42                      | 22.402             |
| 5           | 2                   | 3               | 14.266           | 65.39                                 | 130.77                      | 18.840             |
| 1           | 1                   | 0               | 8.835            | 79.23                                 | 79.23                       | 8.839              |
| 2           | 2                   | 0               | 14.554           | 62.45                                 | 124.91                      | 19.864             |
| 3           | 2                   | 1               | 15.182           | 60.29                                 | 120.58                      | 19.113             |
| 4           | 2                   | 2               | 17.206           | 62.18                                 | 124.37                      | 20.955             |
| 5           | 2                   | 3               | 15.526           | 61.92                                 | 123.84                      | 19.806             |
| 1           | 1                   | 0               | 13.329           | 86.73                                 | 86.73                       | 13.334             |
| 2           | 2                   | 0               | 14.185           | 63.47                                 | 126.93                      | 19.196             |
| 3           | 2                   | 1               | 15.376           | 61.93                                 | 123.86                      | 20.004             |
| 4           | 2                   | 2               | 15.405           | 64.14                                 | 128.29                      | 20.872             |
| 5           | 2                   | 3               | 14.909           | 63.94                                 | 127.89                      | 19.572             |
| 1           | 1                   | 0               | 8.002            | 81.48                                 | 81.48                       | 8.006              |
| 2           | 2                   | 0               | 16.834           | 64.28                                 | 128.56                      | 21.731             |
| 3           | 2                   | 1               | 11.225           | 60.16                                 | 120.33                      | 14.274             |
| 4           | 2                   | 2               | 13.520           | 64.58                                 | 129.16                      | 17.599             |
| 5           | 2                   | 3               | 13.541           | 59.00                                 | 118.00                      | 16.613             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-1-nc48.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-1-nc48.txt |grep -A 7 
```

**2-nc24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 9.659            | 62.63                                 | 62.63                       | 9.664              |
| 2           | 2                   | 0               | 11.663           | 65.23                                 | 130.46                      | 13.617             |
| 3           | 3                   | 0               | 20.658           | 55.25                                 | 165.74                      | 28.926             |
| 1           | 1                   | 0               | 16.593           | 53.76                                 | 53.76                       | 16.597             |
| 2           | 2                   | 0               | 20.202           | 50.54                                 | 101.09                      | 26.650             |
| **3**       | **3**               | **0**           | **19.131**       | **58.53**                             | **175.59**                  | **29.766**         |
| 1           | 1                   | 0               | 12.825           | 66.27                                 | 66.27                       | 12.829             |
| 2           | 2                   | 0               | 12.664           | 67.27                                 | 134.54                      | 13.328             |
| 3           | 3                   | 0               | 17.639           | 59.10                                 | 177.30                      | 25.248             |
| 1           | 1                   | 0               | 10.546           | 68.65                                 | 68.65                       | 10.550             |
| 2           | 2                   | 0               | 16.594           | 48.65                                 | 97.31                       | 20.664             |
| 3           | 3                   | 0               | 16.779           | 56.99                                 | 170.98                      | 23.796             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-2-nc24.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-2-nc24.txt |grep -A 7 

```

**1-nc24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 13.339           | 71.15                                 | 71.15                       | 13.344             |
| 2           | 2                   | 0               | 21.675           | 49.30                                 | 98.61                       | 27.741             |
| 3           | 2                   | 1               | 19.226           | 52.44                                 | 104.88                      | 26.149             |
| 1           | 1                   | 0               | 14.241           | 69.38                                 | 69.38                       | 14.245             |
| **2**       | **2**               | **0**           | **17.212**       | **51.91**                             | **103.82**                  | **23.023**         |
| 3           | 2                   | 1               | 19.061           | 52.79                                 | 105.58                      | 25.372             |
| 1           | 1                   | 0               | 10.762           | 65.88                                 | 65.88                       | 10.765             |
| 2           | 2                   | 0               | 20.992           | 52.80                                 | 105.59                      | 28.139             |
| 3           | 2                   | 1               | 19.811           | 47.85                                 | 95.71                       | 24.749             |
| 1           | 1                   | 0               | 10.182           | 66.19                                 | 66.19                       | 10.187             |
| 2           | 2                   | 0               | 18.303           | 52.05                                 | 104.10                      | 24.445             |
| 3           | 2                   | 1               | 11.118           | 48.83                                 | 97.65                       | 14.555             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-1-nc24.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-1-nc24.txt |grep -A 7 "Summary for concurrency"
      
```

</details>

---

<details>
<summary><h4>📊 Llama-3.2-11B-Vision-Instruct (meta-llama/Llama-3.2-11B-Vision-Instruct)</h4></summary>

**Run the test script:**

```bash
python scripts/testing/press-llama3.211bv-20250407.py
```

##### Test Result Analysis

| Scenario           | Concurrency | VM Type       | Successful Requests | Failed Requests (429 errors) | Avg TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ------------------ | ----------- | ------------- | ------------------- | ---------------------------- | ------------ | ------------------------------------- | --------------------------- | ------------------ |
| Text Generation    | 1           | VM1 (1-NC-24) | 1                   | 0                            | 17.439       | 52.98                                 | 52.98                       | 17.477             |
| Text Generation    | 1           | VM2 (2-NC-24) | 1                   | 0                            | 17.400       | 53.10                                 | 53.10                       | 17.432             |
| Text Generation    | 1           | VM3 (1-NC-48) | 1                   | 0                            | 16.988       | 54.39                                 | 54.39                       | 17.019             |
| Text Generation    | 2           | VM1 (1-NC-24) | 2                   | 0                            | 21.813       | 40.63                                 | 81.26                       | 28.467             |
| Text Generation    | 2           | VM2 (2-NC-24) | 2                   | 0                            | 22.046       | 40.25                                 | 80.50                       | 28.810             |
| Text Generation    | 2           | VM3 (1-NC-48) | 2                   | 0                            | 21.544       | 41.16                                 | 82.31                       | 28.132             |
| Text Generation    | 3           | VM1 (1-NC-24) | 2                   | 1                            | 21.969       | 40.09                                 | 80.18                       | 28.545             |
| Text Generation    | 3           | VM2 (2-NC-24) | 2                   | 1                            | 22.135       | 39.84                                 | 79.68                       | 28.813             |
| Text Generation    | 3           | VM3 (1-NC-48) | 2                   | 1                            | 21.531       | 41.05                                 | 82.10                       | 28.096             |
| Question Answering | 1           | VM1 (1-NC-24) | 1                   | 0                            | 2.952        | 24.73                                 | 24.73                       | 2.977              |
| Question Answering | 1           | VM2 (2-NC-24) | 1                   | 0                            | 2.967        | 24.60                                 | 24.60                       | 2.992              |
| Question Answering | 1           | VM3 (1-NC-48) | 1                   | 0                            | 2.953        | 24.72                                 | 24.72                       | 2.978              |
| Question Answering | 2           | VM1 (1-NC-24) | 2                   | 0                            | 4.100        | 18.98                                 | 37.97                       | 4.946              |
| Question Answering | 2           | VM2 (2-NC-24) | 2                   | 0                            | 4.078        | 19.13                                 | 38.25                       | 4.933              |
| Question Answering | 2           | VM3 (1-NC-48) | 2                   | 0                            | 4.037        | 19.24                                 | 38.49                       | 4.863              |
| Question Answering | 3           | VM1 (1-NC-24) | 3                   | 0                            | 13.402       | 23.74                                 | 71.21                       | 20.676             |
| Question Answering | 3           | VM2 (2-NC-24) | 3                   | 0                            | 13.592       | 23.48                                 | 70.45                       | 20.966             |
| Question Answering | 3           | VM3 (1-NC-48) | 3                   | 0                            | 13.274       | 23.96                                 | 71.89                       | 20.488             |
| Translation        | 1           | VM1 (1-NC-24) | 1                   | 0                            | 4.005        | 35.21                                 | 35.21                       | 4.029              |
| Translation        | 1           | VM2 (2-NC-24) | 1                   | 0                            | 4.096        | 34.42                                 | 34.42                       | 4.123              |
| Translation        | 1           | VM3 (1-NC-48) | 1                   | 0                            | 3.999        | 35.26                                 | 35.26                       | 4.026              |
| Translation        | 2           | VM1 (1-NC-24) | 2                   | 0                            | 6.270        | 29.04                                 | 58.08                       | 8.055              |
| Translation        | 2           | VM2 (2-NC-24) | 2                   | 0                            | 6.347        | 28.83                                 | 57.65                       | 8.211              |
| Translation        | 2           | VM3 (1-NC-48) | 2                   | 0                            | 6.143        | 29.77                                 | 59.54                       | 7.938              |
| Translation        | 3           | VM1 (1-NC-24) | 3                   | 0                            | 8.659        | 31.32                                 | 93.97                       | 15.831             |
| Translation        | 3           | VM2 (2-NC-24) | 3                   | 0                            | 8.679        | 31.26                                 | 93.78                       | 15.833             |
| Translation        | 3           | VM3 (1-NC-48) | 3                   | 0                            | 8.561        | 31.59                                 | 94.78                       | 15.623             |

| Scenario           | Concurrency | VM Type       | Successful Requests | Failed Requests (429 errors) | Avg TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ------------------ | ----------- | ------------- | ------------------- | ---------------------------- | ------------ | ------------------------------------- | --------------------------- | ------------------ |
| Text Summarization | 1           | VM1 (1-NC-24) | 1                   | 0                            | 2.134        | 8.91                                  | 8.91                        | 2.158              |
| Text Summarization | 1           | VM2 (2-NC-24) | 1                   | 0                            | 2.061        | 9.22                                  | 9.22                        | 2.086              |
| Text Summarization | 1           | VM3 (1-NC-48) | 1                   | 0                            | 2.057        | 9.24                                  | 9.24                        | 2.080              |
| Text Summarization | 2           | VM1 (1-NC-24) | 2                   | 0                            | 2.632        | 7.53                                  | 15.05                       | 3.198              |
| Text Summarization | 2           | VM2 (2-NC-24) | 2                   | 0                            | 2.640        | 7.52                                  | 15.04                       | 3.222              |
| Text Summarization | 2           | VM3 (1-NC-48) | 2                   | 0                            | 2.568        | 7.73                                  | 15.45                       | 3.132              |
| Text Summarization | 3           | VM1 (1-NC-24) | 3                   | 0                            | 2.947        | 12.87                                 | 38.62                       | 5.140              |
| Text Summarization | 3           | VM2 (2-NC-24) | 3                   | 0                            | 3.009        | 12.62                                 | 37.85                       | 5.249              |
| Text Summarization | 3           | VM3 (1-NC-48) | 3                   | 0                            | 2.973        | 12.76                                 | 38.29                       | 5.211              |
| Code Generation    | 1           | VM1 (1-NC-24) | 1                   | 0                            | 32.118       | 64.76                                 | 64.76                       | 32.146             |
| Code Generation    | 1           | VM2 (2-NC-24) | 1                   | 0                            | 32.268       | 64.46                                 | 64.46                       | 32.298             |
| Code Generation    | 1           | VM3 (1-NC-48) | 1                   | 0                            | 31.698       | 65.62                                 | 65.62                       | 31.726             |
| Code Generation    | 2           | VM1 (1-NC-24) | 2                   | 0                            | 42.762       | 44.21                                 | 88.42                       | 53.003             |
| Code Generation    | 2           | VM2 (2-NC-24) | 2                   | 0                            | 42.834       | 44.11                                 | 88.23                       | 53.065             |
| Code Generation    | 2           | VM3 (1-NC-48) | 2                   | 0                            | 41.980       | 45.02                                 | 90.05                       | 52.024             |
| Code Generation    | 3           | VM1 (1-NC-24) | 2                   | 1                            | 21.515       | 47.86                                 | 95.72                       | 29.578             |
| Code Generation    | 3           | VM2 (2-NC-24) | 2                   | 1                            | 21.605       | 47.72                                 | 95.44                       | 29.735             |
| Code Generation    | 3           | VM3 (1-NC-48) | 2                   | 1                            | 21.152       | 48.81                                 | 97.63                       | 29.160             |
| Chatbot            | 1           | VM1 (1-NC-24) | 1                   | 0                            | 10.092       | 49.94                                 | 49.94                       | 10.117             |
| Chatbot            | 1           | VM2 (2-NC-24) | 1                   | 0                            | 10.101       | 49.90                                 | 49.90                       | 10.126             |
| Chatbot            | 1           | VM3 (1-NC-48) | 1                   | 0                            | 9.761        | 51.63                                 | 51.63                       | 9.787              |
| Chatbot            | 2           | VM1 (1-NC-24) | 2                   | 0                            | 18.097       | 38.82                                 | 77.64                       | 22.841             |
| Chatbot            | 2           | VM2 (2-NC-24) | 2                   | 0                            | 18.149       | 38.75                                 | 77.50                       | 22.930             |
| Chatbot            | 2           | VM3 (1-NC-48) | 2                   | 0                            | 17.827       | 39.34                                 | 78.68                       | 22.455             |
| Chatbot            | 3           | VM1 (1-NC-24) | 2                   | 1                            | 14.984       | 38.19                                 | 76.38                       | 19.321             |
| Chatbot            | 3           | VM2 (2-NC-24) | 2                   | 1                            | 15.016       | 38.02                                 | 76.03                       | 19.312             |
| Chatbot            | 3           | VM3 (1-NC-48) | 2                   | 1                            | 14.847       | 38.43                                 | 76.85                       | 19.080             |

</details>

---

<details>
<summary><h4>🖼️ microsoft-swinv2-base-patch4-window12-192-22k Series</h4></summary>

```bash
python scripts/testing/press-swinv2-20250322.py
```

Test result analyze：

**1-NC48**

| **Concurrency** | **Successful Requests** | **Failed Requests** | **Average TTFT (s)** | **Avg Throughput per Request (tokens/s)** | **Total Throughput (tokens/s)** | **Batch Duration (s)** |
| --------------- | ----------------------- | ------------------- | -------------------- | ----------------------------------------- | ------------------------------- | ---------------------- |
| 1               | 1                       | 0                   | 0.910                | 27.46                                     | 27.46                           | 0.911                  |
| 2               | 2                       | 0                   | 1.055                | 24.12                                     | 48.25                           | 1.198                  |
| 3               | 3                       | 0                   | 1.073                | 23.80                                     | 71.41                           | 2.600                  |
| 4               | 4                       | 0                   | 1.198                | 21.98                                     | 87.93                           | 2.983                  |
| 5               | 5                       | 0                   | 1.031                | 24.69                                     | 123.45                          | 5.209                  |
| **6**           | **6**                   | **0**               | **1.309**            | **20.39**                                 | **122.32**                      | **5.506**              |
| 7               | 6                       | 1                   | 1.059                | 24.04                                     | 144.25                          | 8.957                  |
| 8               | 6                       | 2                   | 1.110                | 23.16                                     | 138.99                          | 8.965                  |
| 9               | 6                       | 3                   | 1.084                | 23.59                                     | 141.56                          | 8.956                  |
| 10              | 6                       | 4                   | 1.108                | 23.07                                     | 138.40                          | 8.963                  |



**2-NC24**

| **Concurrency** | **Successful Requests** | **Failed Requests** | **Average TTFT (s)** | **Avg Throughput per Request (tokens/s)** | **Batch Duration (s)** | **Total Throughput (tokens/s)** |
| --------------- | ----------------------- | ------------------- | -------------------- | ----------------------------------------- | ---------------------- | ------------------------------- |
| 1               | 1                       | 0                   | 1.002                | 24.94                                     | 1.004                  | 24.94                           |
| 2               | 2                       | 0                   | 1.272                | 19.91                                     | 1.421                  | 39.83                           |
| 3               | 3                       | 0                   | 1.093                | 23.22                                     | 1.292                  | 69.65                           |
| 4               | 4                       | 0                   | 1.151                | 22.22                                     | 1.357                  | 88.86                           |
| 5               | 5                       | 0                   | 1.042                | 24.43                                     | 2.582                  | 122.16                          |
| 6               | 6                       | 0                   | 1.047                | 24.33                                     | 2.610                  | 145.98                          |
| 7               | 7                       | 0                   | 1.067                | 23.90                                     | 2.859                  | 167.27                          |
| 8               | 8                       | 0                   | 1.227                | 21.08                                     | 2.881                  | 168.63                          |
| 9               | 9                       | 0                   | 1.074                | 23.82                                     | 5.212                  | 214.39                          |
| **10**          | **10**                  | **0**               | **1.234**            | **21.25**                                 | **5.506**              | **212.51**                      |

**1-NC24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 1.015            | 24.64                                 | 24.64                       | 1.016              |
| 2           | 2                   | 0               | 1.068            | 23.88                                 | 47.75                       | 1.220              |
| 3           | 3                   | 0               | 1.074            | 23.73                                 | 71.18                       | 2.602              |
| 4           | 4                   | 0               | 1.105            | 23.08                                 | 92.31                       | 2.872              |
| 5           | 5                   | 0               | 1.096            | 23.29                                 | 116.43                      | 5.226              |
| **6**       | **6**               | **0**           | **1.130**        | **22.79**                             | **136.74**                  | **5.571**          |
| 7           | 6                   | 1               | 1.100            | 23.19                                 | 139.16                      | 8.958              |
| 8           | 6                   | 2               | 1.101            | 23.16                                 | 138.96                      | 8.951              |
| 9           | 6                   | 3               | 1.079            | 23.63                                 | 141.81                      | 8.951              |
| 10          | 6                   | 4               | 1.075            | 23.71                                 | 142.28                      | 8.946              |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/swinv2-base-results.txt*

</details>

---

<details>
<summary><h4>💬 mistralai-Mixtral-8x7B-Instruct-v01 Series</h4></summary>

```bash
python scripts/testing/press-Mixtral-8x7B-20250323.py
```

Test result analyze：

**1-NC96 mistralai-Mixtral-8x7B-Instruct-v01**

Scenario: Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.828            | 73.19                                 | 73.19                       | 2.838              |
| 2           | 2                   | 0               | 3.884            | 57.69                                 | 115.38                      | 4.978              |
| 3           | 3                   | 0               | 3.541            | 62.94                                 | 188.81                      | 7.155              |
| **4**       | **4**               | **0**           | **3.861**        | **58.24**                             | **232.98**                  | **9.253**          |
| 5           | 4                   | 1               | 3.875            | 58.14                                 | 232.55                      | 9.312              |
| 6           | 4                   | 2               | 3.875            | 57.95                                 | 231.78                      | 9.279              |
| 7           | 4                   | 3               | 3.867            | 58.19                                 | 232.76                      | 9.281              |
| 8           | 4                   | 4               | 3.881            | 57.92                                 | 231.68                      | 9.310              |
| 9           | 4                   | 5               | 3.877            | 57.85                                 | 231.41                      | 9.298              |
| 10          | 4                   | 6               | 3.865            | 58.28                                 | 233.13                      | 9.297              |

Scenario: Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.803            | 73.50                                 | 73.50                       | 2.810              |
| 2           | 2                   | 0               | 3.850            | 58.13                                 | 116.25                      | 4.935              |
| 3           | 3                   | 0               | 3.514            | 63.13                                 | 189.38                      | 7.126              |
| **4**       | **4**               | **0**           | **3.871**        | **57.83**                             | **231.31**                  | **9.270**          |
| 5           | 3                   | 2               | 3.523            | 63.33                                 | 189.98                      | 8.973              |
| 6           | 4                   | 2               | 3.859            | 58.28                                 | 233.13                      | 9.264              |
| 7           | 4                   | 3               | 3.871            | 57.89                                 | 231.56                      | 9.289              |
| 8           | 4                   | 4               | 3.705            | 57.79                                 | 231.18                      | 8.989              |
| 9           | 4                   | 5               | 3.865            | 57.71                                 | 230.86                      | 9.264              |
| 10          | 4                   | 6               | 3.895            | 57.47                                 | 229.87                      | 9.321              |

Scenario: Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.780            | 73.39                                 | 73.39                       | 2.786              |
| 2           | 2                   | 0               | 3.703            | 55.23                                 | 110.46                      | 4.614              |
| **3**       | **3**               | **0**           | **3.435**        | **62.87**                             | **188.60**                  | **7.108**          |
| 4           | 3                   | 1               | 3.529            | 62.62                                 | 187.86                      | 8.966              |
| 5           | 4                   | 1               | 3.542            | 56.86                                 | 227.43                      | 8.967              |
| 6           | 4                   | 2               | 3.804            | 57.82                                 | 231.29                      | 9.168              |
| 7           | 4                   | 3               | 3.836            | 57.28                                 | 229.12                      | 9.266              |
| 8           | 4                   | 4               | 3.419            | 57.01                                 | 228.02                      | 8.983              |
| 9           | 4                   | 5               | 3.735            | 57.41                                 | 229.63                      | 9.272              |
| 10          | 4                   | 6               | 3.876            | 57.53                                 | 230.10                      | 9.266              |

Scenario: Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.787            | 74.27                                 | 74.27                       | 2.794              |
| 2           | 2                   | 0               | 3.530            | 57.45                                 | 114.90                      | 4.620              |
| 3           | 3                   | 0               | 1.848            | 29.89                                 | 89.68                       | 2.625              |
| **4**       | **4**               | **0**           | **3.802**        | **56.54**                             | **226.17**                  | **8.967**          |
| 5           | 4                   | 1               | 2.569            | 54.29                                 | 217.14                      | 8.962              |
| 6           | 4                   | 2               | 2.766            | 49.01                                 | 196.03                      | 8.997              |
| 7           | 4                   | 3               | 3.839            | 56.88                                 | 227.54                      | 9.447              |
| 8           | 5                   | 3               | 2.704            | 47.66                                 | 238.31                      | 9.007              |
| 9           | 4                   | 5               | 3.621            | 58.02                                 | 232.07                      | 8.990              |
| 10          | 4                   | 6               | 3.820            | 56.86                                 | 227.45                      | 9.038              |

Scenario: Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.796            | 79.76                                 | 79.76                       | 2.803              |
| 2           | 2                   | 0               | 3.867            | 63.29                                 | 126.58                      | 4.950              |
| 3           | 3                   | 0               | 3.501            | 68.61                                 | 205.84                      | 7.104              |
| **4**       | **4**               | **0**           | **3.873**        | **62.14**                             | **248.56**                  | **9.270**          |
| 5           | 4                   | 1               | 3.853            | 62.60                                 | 250.39                      | 9.261              |
| 6           | 4                   | 2               | 3.857            | 62.19                                 | 248.77                      | 9.250              |
| 7           | 4                   | 3               | 3.885            | 62.52                                 | 250.10                      | 9.301              |
| 8           | 4                   | 4               | 3.858            | 63.46                                 | 253.84                      | 9.258              |
| 9           | 4                   | 5               | 3.870            | 62.59                                 | 250.36                      | 9.289              |
| 10          | 4                   | 6               | 3.874            | 62.66                                 | 250.63                      | 9.272              |

Scenario: Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.787            | 75.00                                 | 75.00                       | 2.793              |
| 2           | 2                   | 0               | 3.853            | 58.82                                 | 117.65                      | 4.935              |
| **3**       | **3**               | **0**           | **3.506**        | **63.76**                             | **191.28**                  | **7.129**          |
| 4           | 3                   | 1               | 3.535            | 63.32                                 | 189.95                      | 8.969              |
| 5           | 4                   | 1               | 3.888            | 58.03                                 | 232.12                      | 9.302              |
| 6           | 4                   | 2               | 3.888            | 58.06                                 | 232.26                      | 9.309              |
| 7           | 4                   | 3               | 3.880            | 58.18                                 | 232.73                      | 9.285              |
| 8           | 4                   | 4               | 3.876            | 58.17                                 | 232.70                      | 9.278              |
| 9           | 4                   | 5               | 3.884            | 58.09                                 | 232.38                      | 9.313              |
| 10          | 4                   | 6               | 3.874            | 58.20                                 | 232.78                      | 9.281              |

Scenario: Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.960            | 27.10                                 | 27.10                       | 0.966              |
| 2           | 2                   | 0               | 1.036            | 18.06                                 | 36.13                       | 1.131              |
| 3           | 3                   | 0               | 0.861            | 12.88                                 | 38.63                       | 2.469              |
| 4           | 4                   | 0               | 1.000            | 17.96                                 | 71.85                       | 2.630              |
| **5**       | **5**               | **0**           | **0.945**        | **16.28**                             | **81.41**                   | **5.125**          |
| 6           | 6                   | 0               | 0.887            | 12.51                                 | 75.05                       | 5.294              |
| 7           | 6                   | 1               | 1.051            | 20.55                                 | 123.31                      | 8.978              |
| 8           | 6                   | 2               | 0.923            | 13.88                                 | 83.28                       | 8.986              |
| 9           | 6                   | 3               | 0.945            | 16.33                                 | 97.96                       | 8.991              |
| 10          | 6                   | 4               | 0.915            | 14.43                                 | 86.57                       | 8.988              |

Scenario: Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.810            | 74.38                                 | 74.38                       | 2.817              |
| 2           | 2                   | 0               | 3.884            | 58.24                                 | 116.49                      | 4.977              |
| 3           | 3                   | 0               | 3.472            | 64.50                                 | 193.50                      | 7.070              |
| **4**       | **4**               | **0**           | **3.824**        | **59.01**                             | **236.03**                  | **9.204**          |
| 5           | 4                   | 1               | 3.824            | 58.98                                 | 235.94                      | 9.215              |
| 6           | 4                   | 2               | 3.610            | 55.76                                 | 223.05                      | 8.976              |
| 7           | 4                   | 3               | 3.857            | 58.33                                 | 233.32                      | 9.250              |
| 8           | 4                   | 4               | 3.867            | 58.45                                 | 233.81                      | 9.261              |
| 9           | 4                   | 5               | 3.844            | 58.83                                 | 235.30                      | 9.244              |
| 10          | 4                   | 6               | 3.846            | 58.59                                 | 234.35                      | 9.284              |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/Mixtral-8x7B-Instruct-v0.1-result.txt*

</details>

---

<details>
<summary><h4>🎧 openai-whisper-large Series</h4></summary>

**On NC48 VM**

```bash
python scripts/testing/press-whisper-20250323.py
```

Test result analyze：

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) | Output Text                        |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ | ---------------------------------- |
| 1           | 1                   | 0               | 2.037            | 4.91                                  | 4.91                        | 2.040              | This is a test for speech to text. |
| 2           | 2                   | 0               | 2.555            | 4.08                                  | 8.16                        | 3.073              | This is a test for speech to text. |
| 3           | 3                   | 0               | 2.509            | 4.05                                  | 12.14                       | 4.279              | This is a test for speech to text. |
| 4           | 4                   | 0               | 2.273            | 4.46                                  | 17.85                       | 6.849              | This is a test for speech to text. |
| **5**       | **5**               | **0**           | **2.328**        | **4.40**                              | **22.00**                   | **7.471**          | This is a test for speech to text. |
| 6           | 5                   | 1               | 2.310            | 4.43                                  | 22.17                       | 9.533              | This is a test for speech to text. |
| 7           | 5                   | 2               | 2.415            | 4.25                                  | 21.27                       | 9.533              | This is a test for speech to text. |
| 8           | 5                   | 3               | 2.317            | 4.42                                  | 22.11                       | 9.550              | This is a test for speech to text. |
| 9           | 5                   | 4               | 2.408            | 4.26                                  | 21.32                       | 9.536              | This is a test for speech to text. |
| 10          | 5                   | 5               | 2.368            | 4.37                                  | 21.83                       | 9.536              | This is a test for speech to text. |

Check eveny request's TTFT and completion time.

| Concurrency | Request # | TTFT (s) | Completion Time (s) |
| ----------- | --------- | -------- | ------------------- |
| 1           | 1         | 2.037    | 2.037               |
| 2           | 1         | 2.038    | 2.038               |
| 2           | 2         | 3.071    | 3.071               |
| 3           | 1         | 2.167    | 2.167               |
| 3           | 2         | 2.929    | 2.929               |
| 3           | 3         | 2.432    | 2.432               |
| 4           | 1         | 2.006    | 2.006               |
| 4           | 2         | 2.755    | 2.755               |
| 4           | 3         | 2.167    | 2.167               |
| 4           | 4         | 2.165    | 2.165               |
| 5           | 1         | 2.034    | 2.034               |
| 5           | 2         | 2.783    | 2.783               |
| 5           | 3         | 2.027    | 2.027               |
| 5           | 4         | 2.014    | 2.014               |
| 5           | 5         | 2.780    | 2.780               |
| 6           | 1         | 1.996    | 1.996               |
| 6           | 2         | 2.746    | 2.746               |
| 6           | 3         | 2.005    | 2.005               |
| 6           | 4         | 2.029    | 2.029               |
| 6           | 5         | 2.774    | 2.774               |
| 7           | 1         | 2.259    | 2.259               |
| 7           | 2         | 3.018    | 3.018               |
| 7           | 3         | 2.019    | 2.019               |
| 7           | 4         | 2.018    | 2.018               |
| 7           | 5         | 2.762    | 2.762               |
| 8           | 1         | 2.053    | 2.053               |
| 8           | 2         | 2.797    | 2.797               |
| 8           | 3         | 2.006    | 2.006               |
| 8           | 4         | 1.994    | 1.994               |
| 8           | 5         | 2.734    | 2.734               |
| 9           | 1         | 2.172    | 2.172               |
| 9           | 2         | 3.024    | 3.024               |
| 9           | 3         | 2.096    | 2.096               |
| 9           | 4         | 2.001    | 2.001               |
| 9           | 5         | 2.747    | 2.747               |
| 10          | 1         | 2.012    | 2.012               |
| 10          | 2         | 3.054    | 3.054               |
| 10          | 3         | 2.007    | 2.007               |
| 10          | 4         | 2.009    | 2.009               |
| 10          | 5         | 2.755    | 2.755               |

</details>

---

<details>
<summary><h4>⚡ Nemotron-3-8B-Chat-4k-SteerLM Series</h4></summary>

```bash
python scripts/testing/press-nemotron-3-8b-chat-4k-steerlm-20250324.py
```

**On 1 NC24 A100 VM**

Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.822            | 95.27                                 | 95.27                       | 6.836              |
| 2           | **2**               | **0**           | **9.903**        | **72.69**                             | **145.38**                  | **13.002**         |
| 3           | 2                   | 1               | 9.902            | 72.73                                 | 145.45                      | 13.006             |
| 4           | 2                   | 2               | 10.024           | 71.66                                 | 143.32                      | 13.139             |
| 5           | 2                   | 3               | 9.930            | 72.49                                 | 144.97                      | 13.047             |
| 6           | 2                   | 4               | 9.941            | 72.43                                 | 144.87                      | 13.059             |
| 7           | 2                   | 5               | 9.960            | 72.30                                 | 144.60                      | 13.086             |
| 8           | 2                   | 6               | 9.969            | 72.23                                 | 144.45                      | 13.100             |
| 9           | 2                   | 7               | 9.984            | 72.11                                 | 144.22                      | 13.117             |
| 10          | 2                   | 8               | 9.993            | 72.05                                 | 144.10                      | 13.130             |

Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.858            | 92.15                                 | 92.15                       | 6.869              |
| **2**       | **2**               | **0**           | **9.970**        | **70.24**                             | **140.47**                  | **13.095**         |
| 3           | 2                   | 1               | 9.979            | 70.17                                 | 140.35                      | 13.109             |
| 4           | 2                   | 2               | 9.993            | 70.06                                 | 140.11                      | 13.124             |
| 5           | 2                   | 3               | 9.984            | 70.13                                 | 140.26                      | 13.116             |
| 6           | 2                   | 4               | 9.983            | 70.13                                 | 140.27                      | 13.119             |
| 7           | 2                   | 5               | 9.989            | 70.09                                 | 140.18                      | 13.122             |
| 8           | 2                   | 6               | 9.988            | 70.11                                 | 140.21                      | 13.119             |
| 9           | 2                   | 7               | 9.985            | 70.14                                 | 140.28                      | 13.117             |
| 10          | 2                   | 8               | 9.983            | 70.12                                 | 140.23                      | 13.116             |

Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.850            | 114.30                                | 114.30                      | 6.860              |
| **2**       | **2**               | **0**           | **9.955**        | **87.14**                             | **174.29**                  | **13.075**         |
| 3           | 2                   | 1               | 9.958            | 87.10                                 | 174.20                      | 13.080             |
| 4           | 2                   | 2               | 9.956            | 87.13                                 | 174.26                      | 13.080             |
| 5           | 2                   | 3               | 10.064           | 86.00                                 | 172.00                      | 13.187             |
| 6           | 2                   | 4               | 9.970            | 87.03                                 | 174.06                      | 13.099             |
| 7           | 2                   | 5               | 9.965            | 87.04                                 | 174.09                      | 13.091             |
| 8           | 2                   | 6               | 9.965            | 87.03                                 | 174.05                      | 13.087             |
| 9           | 2                   | 7               | 9.957            | 87.11                                 | 174.21                      | 13.078             |
| 10          | 2                   | 8               | 9.968            | 86.99                                 | 173.97                      | 13.091             |

Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.861            | 87.01                                 | 87.01                       | 6.871              |
| **2**       | **2**               | **0**           | **9.972**        | **66.32**                             | **132.64**                  | **13.095**         |
| 3           | 2                   | 1               | 9.966            | 66.37                                 | 132.74                      | 13.093             |
| 4           | 2                   | 2               | 9.963            | 66.38                                 | 132.76                      | 13.087             |
| 5           | 2                   | 3               | 9.969            | 66.32                                 | 132.65                      | 13.101             |
| 6           | 2                   | 4               | 9.963            | 66.36                                 | 132.72                      | 13.093             |
| 7           | 2                   | 5               | 9.980            | 66.26                                 | 132.52                      | 13.107             |
| 8           | 2                   | 6               | 9.971            | 66.29                                 | 132.58                      | 13.103             |
| 9           | 2                   | 7               | 9.974            | 66.31                                 | 132.62                      | 13.108             |
| 10          | 2                   | 8               | 9.969            | 66.35                                 | 132.69                      | 13.102             |

Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.874            | 117.84                                | 117.84                      | 6.884              |
| **2**       | **2**               | **0**           | **9.958**        | **90.11**                             | **180.23**                  | **13.078**         |
| 3           | 2                   | 1               | 9.966            | 90.03                                 | 180.06                      | 13.089             |
| 4           | 2                   | 2               | 9.966            | 90.03                                 | 180.06                      | 13.089             |
| 5           | 2                   | 3               | 9.957            | 90.11                                 | 180.21                      | 13.087             |
| 6           | 2                   | 4               | 10.068           | 88.91                                 | 177.81                      | 13.189             |
| 7           | 2                   | 5               | 9.964            | 90.05                                 | 180.10                      | 13.087             |
| 8           | 2                   | 6               | 9.960            | 90.10                                 | 180.19                      | 13.082             |
| 9           | 2                   | 7               | 9.966            | 90.01                                 | 180.02                      | 13.091             |
| 10          | 2                   | 8               | 9.958            | 90.11                                 | 180.22                      | 13.081             |

Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.856            | 82.55                                 | 82.55                       | 6.866              |
| **2**       | **2**               | **0**           | **9.950**        | **63.03**                             | **126.05**                  | **13.069**         |
| 3           | 2                   | 1               | 9.954            | 62.99                                 | 125.97                      | 13.077             |
| 4           | 2                   | 2               | 9.950            | 63.02                                 | 126.04                      | 13.064             |
| 5           | 2                   | 3               | 9.955            | 62.97                                 | 125.95                      | 13.075             |
| 6           | 2                   | 4               | 9.955            | 62.99                                 | 125.99                      | 13.072             |
| 7           | 2                   | 5               | 9.952            | 63.01                                 | 126.02                      | 13.072             |
| 8           | 2                   | 6               | 9.952            | 62.99                                 | 125.98                      | 13.074             |
| 9           | 2                   | 7               | 9.956            | 62.97                                 | 125.93                      | 13.077             |
| 10          | 2                   | 8               | 9.948            | 63.03                                 | 126.05                      | 13.067             |

Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.857            | 77.14                                 | 77.14                       | 6.866              |
| **2**       | **2**               | **0**           | **9.968**        | **58.79**                             | **117.58**                  | **13.086**         |
| 3           | 2                   | 1               | 9.964            | 58.82                                 | 117.64                      | 13.090             |
| 4           | 2                   | 2               | 9.959            | 58.85                                 | 117.70                      | 13.088             |
| 5           | 2                   | 3               | 9.969            | 58.78                                 | 117.56                      | 13.096             |
| 6           | 2                   | 4               | 9.972            | 58.76                                 | 117.51                      | 13.097             |
| 7           | 2                   | 5               | 10.067           | 58.09                                 | 116.17                      | 13.193             |
| 8           | 2                   | 6               | 9.974            | 58.75                                 | 117.50                      | 13.099             |
| 9           | 2                   | 7               | 9.968            | 58.79                                 | 117.58                      | 13.090             |
| 10          | 2                   | 8               | 9.971            | 58.77                                 | 117.53                      | 13.096             |

Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.861            | 82.35                                 | 82.35                       | 6.871              |
| **2**       | **2**               | **0**           | **9.970**        | **62.78**                             | **125.56**                  | **13.095**         |
| 3           | 2                   | 1               | 9.973            | 62.77                                 | 125.53                      | 13.103             |
| 4           | 2                   | 2               | 9.978            | 62.74                                 | 125.48                      | 13.106             |
| 5           | 2                   | 3               | 9.968            | 62.82                                 | 125.65                      | 13.098             |
| 6           | 2                   | 4               | 9.962            | 62.84                                 | 125.69                      | 13.092             |
| 7           | 2                   | 5               | 9.966            | 62.83                                 | 125.66                      | 13.100             |
| 8           | 2                   | 6               | 9.958            | 62.87                                 | 125.74                      | 13.085             |
| 9           | 2                   | 7               | 9.966            | 62.83                                 | 125.66                      | 13.098             |
| 10          | 2                   | 8               | 9.951            | 62.88                                 | 125.75                      | 13.098             |

**On 2-NC24 VM**

Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.918            | 93.96                                 | 93.96                       | 6.931              |
| **2**       | **2**               | **0**           | **6.954**        | **93.47**                             | **186.93**                  | **7.004**          |
| 3           | 3                   | 0               | 9.062            | 78.70                                 | 236.09                      | 13.311             |
| 4           | 4                   | 0               | 9.977            | 72.17                                 | 288.70                      | 13.192             |
| 5           | 4                   | 1               | 9.976            | 72.19                                 | 288.76                      | 13.190             |
| 6           | 4                   | 2               | 9.966            | 72.27                                 | 289.07                      | 13.175             |
| 7           | 4                   | 3               | 9.972            | 72.23                                 | 288.93                      | 13.171             |
| 8           | 4                   | 4               | 9.974            | 72.20                                 | 288.80                      | 13.176             |
| 9           | 4                   | 5               | 9.981            | 72.17                                 | 288.67                      | 13.184             |
| 10          | 4                   | 6               | 9.991            | 72.11                                 | 288.44                      | 13.206             |

Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.852            | 92.24                                 | 92.24                       | 6.862              |
| **2**       | **2**               | **0**           | **6.859**        | **92.15**                             | **184.29**                  | **6.887**          |
| 3           | 3                   | 0               | 8.978            | 77.23                                 | 231.70                      | 13.185             |
| 4           | 4                   | 0               | 9.987            | 70.12                                 | 280.49                      | 13.191             |
| 5           | 4                   | 1               | 10.001           | 70.01                                 | 280.05                      | 13.196             |
| 6           | 4                   | 2               | 9.992            | 70.11                                 | 280.43                      | 13.187             |
| 7           | 4                   | 3               | 9.994            | 70.06                                 | 280.23                      | 13.193             |
| 8           | 4                   | 4               | 9.996            | 70.07                                 | 280.28                      | 13.206             |
| 9           | 4                   | 5               | 10.004           | 70.01                                 | 280.02                      | 13.231             |
| 10          | 4                   | 6               | 10.006           | 69.99                                 | 279.98                      | 13.204             |

Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.845            | 114.40                                | 114.40                      | 6.854              |
| 2           | 2                   | 0               | 9.952            | 87.14                                 | 174.27                      | 13.067             |
| 3           | 3                   | 0               | 8.957            | 95.92                                 | 287.75                      | 13.156             |
| **4**       | **4**               | **0**           | **9.970**        | **87.01**                             | **348.05**                  | **13.163**         |
| 5           | 4                   | 1               | 9.998            | 86.87                                 | 347.50                      | 13.163             |
| 6           | 4                   | 2               | 10.004           | 86.79                                 | 347.18                      | 13.267             |
| 7           | 4                   | 3               | 9.989            | 86.82                                 | 347.28                      | 13.186             |
| 8           | 4                   | 4               | 9.992            | 86.81                                 | 347.25                      | 13.204             |
| 9           | 4                   | 5               | 9.998            | 86.74                                 | 346.94                      | 13.199             |
| 10          | 4                   | 6               | 9.992            | 86.84                                 | 347.36                      | 13.192             |

Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.849            | 87.16                                 | 87.16                       | 6.859              |
| 2           | 2                   | 0               | 6.876            | 86.83                                 | 173.66                      | 6.916              |
| 3           | 3                   | 0               | 8.952            | 73.17                                 | 219.50                      | 13.154             |
| **4**       | **4**               | **0**           | **9.982**        | **66.27**                             | **265.08**                  | **13.171**         |
| 5           | 4                   | 1               | 9.991            | 66.19                                 | 264.76                      | 13.186             |
| 6           | 4                   | 2               | 9.995            | 66.17                                 | 264.69                      | 13.196             |
| 7           | 4                   | 3               | 9.998            | 66.16                                 | 264.63                      | 13.200             |
| 8           | 4                   | 4               | 9.990            | 66.22                                 | 264.87                      | 13.180             |
| 9           | 4                   | 5               | 9.994            | 66.18                                 | 264.71                      | 13.191             |
| 10          | 4                   | 6               | 9.990            | 66.19                                 | 264.78                      | 13.195             |

Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.905            | 117.31                                | 117.31                      | 6.916              |
| 2           | 2                   | 0               | 6.881            | 117.71                                | 235.43                      | 6.925              |
| 3           | 3                   | 0               | 8.911            | 99.51                                 | 298.54                      | 13.042             |
| **4**       | **4**               | **0**           | **9.967**        | **90.05**                             | **360.20**                  | **13.160**         |
| 5           | 4                   | 1               | 9.973            | 90.03                                 | 360.12                      | 13.165             |
| 6           | 4                   | 2               | 9.989            | 89.85                                 | 359.42                      | 13.177             |
| 7           | 4                   | 3               | 9.981            | 89.89                                 | 359.56                      | 13.184             |
| 8           | 4                   | 4               | 10.005           | 89.84                                 | 359.35                      | 13.186             |
| 9           | 4                   | 5               | 10.003           | 89.85                                 | 359.42                      | 13.264             |
| 10          | 4                   | 6               | 9.984            | 89.87                                 | 359.49                      | 13.168             |

Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.890            | 82.15                                 | 82.15                       | 6.900              |
| 2           | 2                   | 0               | 6.873            | 82.35                                 | 164.70                      | 6.923              |
| 3           | 3                   | 0               | 8.905            | 69.59                                 | 208.76                      | 13.029             |
| **4**       | **4**               | **0**           | **9.972**        | **62.88**                             | **251.50**                  | **13.157**         |
| 5           | 4                   | 1               | 9.964            | 62.93                                 | 251.70                      | 13.143             |
| 6           | 4                   | 2               | 9.983            | 62.82                                 | 251.27                      | 13.168             |
| 7           | 4                   | 3               | 9.973            | 62.87                                 | 251.47                      | 13.158             |
| 8           | 4                   | 4               | 9.978            | 62.85                                 | 251.41                      | 13.165             |
| 9           | 4                   | 5               | 9.976            | 62.84                                 | 251.36                      | 13.165             |
| 10          | 4                   | 6               | 9.982            | 62.80                                 | 251.18                      | 13.175             |

Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.839            | 77.35                                 | 77.35                       | 6.848              |
| 2           | 2                   | 0               | 6.882            | 76.87                                 | 153.75                      | 6.923              |
| 3           | 3                   | 0               | 8.937            | 64.78                                 | 194.33                      | 13.069             |
| **4**       | **4**               | **0**           | **9.981**        | **58.71**                             | **234.84**                  | **13.162**         |
| 5           | 4                   | 1               | 9.994            | 58.65                                 | 234.59                      | 13.180             |
| 6           | 4                   | 2               | 9.990            | 58.67                                 | 234.68                      | 13.183             |
| 7           | 4                   | 3               | 9.984            | 58.69                                 | 234.75                      | 13.173             |
| 8           | 4                   | 4               | 9.988            | 58.68                                 | 234.73                      | 13.176             |
| 9           | 4                   | 5               | 9.989            | 58.68                                 | 234.72                      | 13.179             |
| 10          | 4                   | 6               | 9.987            | 58.68                                 | 234.73                      | 13.187             |

Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.914            | 81.72                                 | 81.72                       | 6.923              |
| 2           | 2                   | 0               | 10.031           | 62.28                                 | 124.57                      | 13.146             |
| 3           | 3                   | 0               | 8.983            | 68.98                                 | 206.93                      | 13.189             |
| **4**       | **4**               | **0**           | **10.014**       | **62.58**                             | **250.33**                  | **13.274**         |
| 5           | 4                   | 1               | 9.990            | 62.65                                 | 250.62                      | 13.181             |
| 6           | 4                   | 2               | 10.000           | 62.63                                 | 250.50                      | 13.201             |
| 7           | 4                   | 3               | 9.998            | 62.63                                 | 250.50                      | 13.191             |
| 8           | 4                   | 4               | 10.004           | 62.56                                 | 250.23                      | 13.203             |
| 9           | 4                   | 5               | 10.003           | 62.58                                 | 250.33                      | 13.203             |
| 10          | 4                   | 6               | 9.995            | 62.65                                 | 250.61                      | 13.200             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/motron-3-8b-chat-4k-steerlm-result.txt*

</details>

---

<details>
<summary><h4>🐋 microsoft-Orca-2-7b Series</h4></summary>

```bash
python scripts/testing/press-orca-20250324.py
```

**On 1 NC24 A100 VM**

Scenario: Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.823            | 123.97                                | 123.97                      | 0.824              |
| 2           | 2                   | 0               | 0.910            | 113.26                                | 226.53                      | 1.001              |
| 3           | 3                   | 0               | 0.934            | 110.67                                | 332.02                      | 2.552              |
| 4           | 4                   | 0               | 0.905            | 113.79                                | 455.15                      | 2.645              |
| 5           | 5                   | 0               | 0.891            | 115.60                                | 577.99                      | 5.122              |
| **6**       | **6**               | **0**           | **0.905**        | **113.90**                            | **683.38**                  | **5.294**          |
| 7           | 6                   | 1               | 0.903            | 114.13                                | 684.80                      | 8.956              |
| 8           | 6                   | 2               | 0.905            | 113.86                                | 683.14                      | 8.948              |
| 9           | 6                   | 3               | 0.901            | 114.40                                | 686.38                      | 8.954              |
| 10          | 6                   | 4               | 0.905            | 113.79                                | 682.73                      | 8.956              |

Scenario: Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 12.923           | 36.91                                 | 36.91                       | 12.924             |
| **2**       | **2**               | **0**           | **18.866**       | **22.66**                             | **45.31**                   | **20.737**         |
| 3           | 2                   | 1               | 19.062           | 24.36                                 | 48.71                       | 21.826             |
| 4           | 2                   | 2               | 21.389           | 24.91                                 | 49.82                       | 26.283             |
| 5           | 2                   | 3               | 15.754           | 23.12                                 | 46.23                       | 17.297             |
| 6           | 3                   | 3               | 16.937           | 31.15                                 | 93.44                       | 30.978             |
| 7           | 2                   | 5               | 15.743           | 32.16                                 | 64.32                       | 43.801             |
| 8           | 2                   | 6               | 13.908           | 32.28                                 | 64.57                       | 21.131             |
| 9           | 2                   | 7               | 18.433           | 27.64                                 | 55.28                       | 24.266             |
| 10          | 2                   | 8               | 21.777           | 24.86                                 | 49.72                       | 27.765             |

Scenario: Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.770            | 85.77                                 | 85.77                       | 0.770              |
| 2           | 2                   | 0               | 0.823            | 80.64                                 | 161.29                      | 0.888              |
| 3           | 3                   | 0               | 0.803            | 82.60                                 | 247.81                      | 2.404              |
| 4           | 4                   | 0               | 0.824            | 80.60                                 | 322.41                      | 2.532              |
| 5           | 5                   | 0               | 0.812            | 81.77                                 | 408.87                      | 5.071              |
| **6**       | **6**               | **0**           | **0.825**        | **80.45**                             | **482.68**                  | **5.191**          |
| 7           | 6                   | 1               | 0.819            | 81.11                                 | 486.69                      | 8.939              |
| 8           | 6                   | 2               | 0.823            | 80.69                                 | 484.14                      | 8.947              |
| 9           | 6                   | 3               | 0.824            | 80.57                                 | 483.39                      | 8.958              |
| 10          | 6                   | 4               | 0.825            | 80.48                                 | 482.88                      | 9.004              |

Scenario: Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 10.704           | 34.29                                 | 34.29                       | 42.212             |
| **2**       | **2**               | **0**           | **12.568**       | **37.60**                             | **75.20**                   | **54.005**         |
| 3           | 2                   | 1               | 23.313           | 16.57                                 | 33.14                       | 24.345             |
| 4           | 2                   | 2               | 13.207           | 21.73                                 | 43.46                       | 14.209             |
| 5           | 2                   | 3               | 18.537           | 17.78                                 | 35.57                       | 46.308             |
| 6           | 2                   | 4               | 9.554            | 30.59                                 | 61.18                       | 13.468             |
| 7           | 2                   | 5               | 20.801           | 17.35                                 | 34.70                       | 21.731             |
| 8           | 2                   | 6               | 4.968            | 31.03                                 | 62.05                       | 37.485             |
| 9           | 2                   | 7               | 20.703           | 28.43                                 | 56.85                       | 49.412             |
| 10          | 2                   | 8               | 13.531           | 30.99                                 | 61.97                       | 34.817             |

Scenario: Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 1.120            | 58.94                                 | 58.94                       | 1.120              |
| 2           | 2                   | 0               | 23.088           | 14.04                                 | 28.07                       | 23.142             |
| 3           | 3                   | 0               | 5.674            | 63.65                                 | 190.96                      | 17.093             |
| 4           | 4                   | 0               | 10.720           | 46.86                                 | 187.44                      | 22.350             |
| 5           | 5                   | 0               | 0.786            | 84.26                                 | 421.29                      | 5.050              |
| 6           | 6                   | 0               | 0.795            | 83.34                                 | 500.05                      | 5.158              |
| **7**       | **7**               | **0**           | **0.817**        | **81.53**                             | **570.71**                  | **5.148**          |
| 8           | 6                   | 2               | 0.789            | 83.98                                 | 503.90                      | 8.952              |
| 9           | 6                   | 3               | 0.782            | 84.77                                 | 508.61                      | 8.961              |
| 10          | 3                   | 7               | 5.550            | 35.41                                 | 106.23                      | 40.336             |

Scenario: Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 9.625            | 32.83                                 | 32.83                       | 9.626              |
| 2           | 2                   | 0               | 2.157            | 33.40                                 | 66.81                       | 2.210              |
| 3           | 3                   | 0               | 2.292            | 47.40                                 | 142.20                      | 4.802              |
| 4           | 4                   | 0               | 4.011            | 38.16                                 | 152.66                      | 9.513              |
| **5**       | **5**               | **0**           | **6.584**        | **47.29**                             | **236.47**                  | **19.182**         |
| 6           | 3                   | 3               | 3.557            | 29.73                                 | 89.18                       | 8.957              |
| 7           | 4                   | 3               | 2.018            | 48.57                                 | 194.28                      | 8.957              |
| 8           | 2                   | 6               | 17.099           | 25.50                                 | 50.99                       | 22.971             |
| 9           | 4                   | 5               | 2.291            | 43.31                                 | 173.23                      | 8.963              |
| 10          | 6                   | 4               | 1.361            | 52.53                                 | 315.18                      | 8.955              |

Scenario: Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 3.386            | 40.46                                 | 40.46                       | 3.386              |
| 2           | 2                   | 0               | 6.789            | 29.99                                 | 59.98                       | 9.033              |
| **3**       | **3**               | **0**           | **6.738**        | **27.11**                             | **81.32**                   | **11.781**         |
| 4           | 3                   | 1               | 6.793            | 27.84                                 | 83.52                       | 12.151             |
| 5           | 3                   | 2               | 6.138            | 29.22                                 | 87.66                       | 11.415             |
| 6           | 3                   | 3               | 6.546            | 27.69                                 | 83.06                       | 11.782             |
| 7           | 3                   | 4               | 6.961            | 26.49                                 | 79.46                       | 11.991             |
| 8           | 3                   | 5               | 6.760            | 27.82                                 | 83.47                       | 12.118             |
| 9           | 3                   | 6               | 7.486            | 26.17                                 | 78.52                       | 12.986             |
| 10          | 3                   | 7               | 7.258            | 26.31                                 | 78.93                       | 13.033             |

Scenario: Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.145            | 36.78                                 | 36.78                       | 6.145              |
| **2**       | **2**               | **0**           | **22.034**       | **23.67**                             | **47.35**                   | **46.358**         |
| 3           | 2                   | 1               | 17.041           | 22.51                                 | 45.01                       | 19.796             |
| 4           | 2                   | 2               | 21.611           | 23.69                                 | 47.38                       | 54.751             |
| 5           | 2                   | 3               | 14.438           | 33.82                                 | 67.64                       | 40.398             |
| 6           | 2                   | 4               | 22.884           | 21.02                                 | 42.03                       | 29.314             |
| 7           | 2                   | 5               | 8.214            | 27.26                                 | 54.52                       | 10.223             |
| 8           | 2                   | 6               | 8.298            | 29.74                                 | 59.49                       | 11.067             |
| 9           | 2                   | 7               | 23.508           | 30.74                                 | 61.47                       | 59.669             |
| 10          | 2                   | 8               | 21.661           | 22.80                                 | 45.60                       | 25.310             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/orca-result.txt*

</details>

---

## Performance test on Azure AI model inference

Currently, an increasing number of new flagship models in the Azure AI Foundry model catalog, including OpenAI, will be deployed using the Azure AI model inference method. 

*https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/deployments-overview*

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/23.png)

Models deployed in this way can be accessed via the AI Inference SDK,which now supports stream mode. Open-source models include DeepSeek R1, V3, Phi, Mistral, and more. 

*https://learn.microsoft.com/en-us/python/api/overview/azure/ai-inference-readme?view=azure-python-preview*

Azure AI model inference has a default quota. If you feel that the quota for the model is insufficient, you can apply for an increase separately. 

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/14.png)

***https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/quotas-limits#request-increases-to-the-default-limits***

| Limit name              | Applies to          | Limit value                                                  |
| ----------------------- | ------------------- | ------------------------------------------------------------ |
| Tokens per minute       | Azure OpenAI models | Varies per model and SKU. See [limits for Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits). |
| Requests per minute     | Azure OpenAI models | Varies per model and SKU. See [limits for Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits). |
| **Tokens per minute**   | **DeepSeek models** | **5.000.000**                                                |
| **Requests per minute** | **DeepSeek models** | **5.000**                                                    |
| **Concurrent requests** | **DeepSeek models** | **300**                                                      |
| Tokens per minute       | Rest of models      | 200.000                                                      |
| Requests per minute     | Rest of models      | 1.000                                                        |
| Concurrent requests     | Rest of models      | 300                                                          |

After you have deployed models on Azure AI model inference, you can check their invocation methods：

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/11.png)

Prepare test env:

```
#conda create -n AImodelinference python=3.11 -y
#conda activate AImodelinference
#pip install azure-ai-inference
```

Run test script, after entering the following three variables, the stress test will begin:

```bash
python scripts/testing/callaiinference-20250406.py
```

https://github.com/user-attachments/assets/bb9606b6-b114-40d1-bcb6-ae51d5de62bc

```text
Please enter the Azure AI endpoint URL, such as https://xinyu.services.ai.azure.com/models format: https://ai-hubeastus869020590911.services.ai.azure.com/models

Please enter the Azure AI key: 4TSBez23vMtPSLPIXgye84oRznpvuYSTDKTr72t***RazJQQJ99BBACYeBjFXJ3w3AAAAACOGmXdu

Please enter the deployment name: DeepSeek-R1 

Please enter concurrency levels separated by commas (e.g. 1,2,3): 10,300
Received concurrency levels: [10, 300]
```

### Performance on DS 671B

<details>
<summary><h4>📊 DeepSeek-R1 Performance Results</h4></summary>
I will use the test results of DeeSeek R1 on Azure AI model inference  as an example:

  **Max performance:**

• When the concurrency is 300 and the prompt length is 1024, TPS = 2110.77, TTFT = 2.201s.
 • When the concurrency is 300 and the prompt length is 2048, TPS = 1330.94, TTFT = 1.861s.

**Overall performance:** 

The overall throughput averages 735.12 tokens/s, with a P90 of 1184.06 tokens/s, full test result is as following:

| **Concurrency** | **Prompt Length** | **Total Requests** | **Success Count** | **Fail Count** | **Average latency (s)** | **Average TTFT (s)** | **Average token throughput (tokens/s)** | **Overall throughput (tokens/s)** |
| --------------- | ----------------- | ------------------ | ----------------- | -------------- | ----------------------- | -------------------- | --------------------------------------- | --------------------------------- |
| 300             | 1024              | 110                | 110               | 0              | 75.579                  | 2.580                | 22.54                                   | 806.84                            |
| 300             | 1024              | 110                | 110               | 0              | 71.378                  | 71.378               | 24.53                                   | 1028.82                           |
| 300             | 1024              | 110                | 110               | 0              | 76.622                  | 2.507                | 23.24                                   | 979.97                            |
| 300             | 1024              | 120                | 120               | 0              | 68.750                  | 68.750               | 24.91                                   | 540.66                            |
| 300             | 1024              | 120                | 120               | 0              | 72.164                  | 2.389                | 22.71                                   | 1094.90                           |
| 300             | 1024              | 130                | 130               | 0              | 72.245                  | 72.245               | 23.68                                   | 1859.91                           |
| 300             | 1024              | 130                | 130               | 0              | 82.714                  | 2.003                | 20.18                                   | 552.08                            |
| 300             | 1024              | 140                | 140               | 0              | 71.458                  | 71.458               | 23.79                                   | 642.92                            |
| 300             | 1024              | 140                | 140               | 0              | 71.565                  | 2.400                | 22.93                                   | 488.49                            |
| 300             | 1024              | 150                | 150               | 0              | 71.958                  | 71.958               | 24.21                                   | 1269.10                           |
| 300             | 1024              | 150                | 150               | 0              | 73.712                  | 2.201                | 22.35                                   | 2110.77                           |
| 300             | 2048              | 10                 | 10                | 0              | 68.811                  | 68.811               | 24.24                                   | 196.78                            |
| 300             | 2048              | 10                 | 10                | 0              | 70.189                  | 1.021                | 23.18                                   | 172.92                            |
| 300             | 2048              | 20                 | 20                | 0              | 73.138                  | 73.138               | 24.14                                   | 390.96                            |
| 300             | 2048              | 20                 | 20                | 0              | 69.649                  | 1.150                | 24.22                                   | 351.31                            |
| 300             | 2048              | 30                 | 30                | 0              | 66.883                  | 66.883               | 26.13                                   | 556.12                            |
| 300             | 2048              | 30                 | 30                | 0              | 68.918                  | 1.660                | 23.46                                   | 571.63                            |
| 300             | 2048              | 40                 | 40                | 0              | 72.485                  | 72.485               | 23.85                                   | 716.53                            |
| 300             | 2048              | 40                 | 40                | 0              | 65.228                  | 1.484                | 24.87                                   | 625.16                            |
| 300             | 2048              | 50                 | 50                | 0              | 68.223                  | 68.223               | 25.12                                   | 887.64                            |
| 300             | 2048              | 50                 | 50                | 0              | 66.288                  | 1.815                | 24.38                                   | 976.17                            |
| 300             | 2048              | 60                 | 60                | 0              | 66.736                  | 66.736               | 25.85                                   | 547.70                            |
| 300             | 2048              | 60                 | 60                | 0              | 69.355                  | 2.261                | 23.94                                   | 615.81                            |
| 300             | 2048              | 70                 | 70                | 0              | 66.689                  | 66.689               | 25.66                                   | 329.90                            |
| 300             | 2048              | 70                 | 70                | 0              | 67.061                  | 2.128                | 23.89                                   | 1373.11                           |
| 300             | 2048              | 80                 | 80                | 0              | 68.091                  | 68.091               | 25.68                                   | 1516.27                           |
| 300             | 2048              | 80                 | 80                | 0              | 67.413                  | 1.861                | 24.01                                   | 1330.94                           |
| 300             | 2048              | 90                 | 90                | 0              | 66.603                  | 66.603               | 25.51                                   | 418.81                            |
| 300             | 2048              | 90                 | 90                | 0              | 70.072                  | 2.346                | 23.41                                   | 1047.53                           |
| 300             | 2048              | 100                | 100               | 0              | 70.516                  | 70.516               | 24.29                                   | 456.66                            |
| 300             | 2048              | 100                | 100               | 0              | 86.862                  | 2.802                | 20.03                                   | 899.38                            |
| 300             | 2048              | 110                | 110               | 0              | 84.602                  | 84.602               | 21.16                                   | 905.59                            |
| 300             | 2048              | 110                | 110               | 0              | 77.883                  | 2.179                | 21.17                                   | 803.93                            |
| 300             | 2048              | 120                | 120               | 0              | 73.814                  | 73.814               | 23.73                                   | 541.03                            |
| 300             | 2048              | 120                | 120               | 0              | 86.787                  | 4.413                | 20.32                                   | 650.57                            |
| 300             | 2048              | 130                | 130               | 0              | 78.222                  | 78.222               | 22.61                                   | 613.27                            |
| 300             | 2048              | 130                | 130               | 0              | 83.670                  | 2.131                | 20.16                                   | 1463.81                           |
| 300             | 2048              | 140                | 140               | 0              | 77.429                  | 77.429               | 22.74                                   | 1184.06                           |
| 300             | 2048              | 140                | 140               | 0              | 77.234                  | 3.891                | 21.90                                   | 821.34                            |
| 300             | 2048              | 150                | 150               | 0              | 72.753                  | 72.753               | 23.69                                   | 698.50                            |
| 300             | 2048              | 150                | 150               | 0              | 73.674                  | 2.425                | 22.74                                   | 1012.25                           |
| 300             | 4096              | 10                 | 10                | 0              | 83.003                  | 83.003               | 25.52                                   | 221.28                            |
| 300             | 4096              | 10                 | 10                | 0              | 89.713                  | 1.084                | 24.70                                   | 189.29                            |
| 300             | 4096              | 20                 | 20                | 0              | 82.342                  | 82.342               | 26.65                                   | 337.85                            |
| 300             | 4096              | 20                 | 20                | 0              | 84.526                  | 1.450                | 24.81                                   | 376.17                            |
| 300             | 4096              | 30                 | 30                | 0              | 87.979                  | 87.979               | 24.46                                   | 322.62                            |
| 300             | 4096              | 30                 | 30                | 0              | 84.767                  | 1.595                | 24.28                                   | 503.01                            |
| 300             | 4096              | 40                 | 40                | 0              | 85.231                  | 85.231               | 26.03                                   | 733.50                            |
| 300             | 4096              | 40                 | 40                | 0              | 81.514                  | 1.740                | 24.17                                   | 710.79                            |
| 300             | 4096              | 50                 | 50                | 0              | 91.253                  | 91.253               | 24.53                                   | 279.55                            |

</details>

---

### Performance Phi-4

<details>
<summary><h4>📊 Phi-4 Performance Results</h4></summary>

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/12.png)

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/13.png)

```bash
python scripts/testing/callaiinference-20250406.py
```

```text
Please enter the Azure AI key: G485wnXwMrAYQKMQPSYpzf7PNLm3sui8qgsXcYFv5Yd3HOmvzZ2GJQQJ99BCACPV0roXJ3w3AAAAACOG9kt1
Please enter the Azure AI endpoint URL: https://xinyu-m7zxv3ow-germanywestcentra.services.ai.azure.com/models
Please enter the deployment name: Phi-4
```

**Max performance:**

• When the concurrency is 300 and the prompt length is 1024, TPS = 1473.44, TTFT = 30.861s (Non-Stream Mode).
• When the concurrency is 300 and the prompt length is 2048, TPS = 849.75, TTFT = 50.730s (Non-Stream Mode).

**Overall performance:**

The overall throughput averages 735.12 tokens/s, with a P90 of 1184.06 tokens/s. Full test results are as follows:

| Concurrency | Prompt Length | Total Requests | Mode       | Success Count | Fail Count | Average Latency (s) | Average TTFT (s) | Average Token Throughput (tokens/s) | Overall Throughput (tokens/s) |
| ----------- | ------------- | -------------- | ---------- | ------------- | ---------- | ------------------- | ---------------- | ----------------------------------- | ----------------------------- |
| 300         | 128           | 20             | Non-Stream | 20            | 0          | 42.786              | 42.786           | 16.25                               | 259.47                        |
| 300         | 128           | 20             | Stream     | 20            | 0          | 41.799              | 0.971            | 15.86                               | 215.46                        |
| 300         | 128           | 30             | Non-Stream | 30            | 0          | 36.526              | 36.526           | 18.79                               | 464.05                        |
| 300         | 128           | 30             | Stream     | 30            | 0          | 29.335              | 1.016            | 22.19                               | 404.16                        |
| 300         | 128           | 40             | Non-Stream | 40            | 0          | 34.573              | 34.573           | 19.98                               | 635.16                        |
| 300         | 128           | 40             | Stream     | 40            | 0          | 37.575              | 1.096            | 17.29                               | 609.03                        |
| 300         | 128           | 50             | Non-Stream | 50            | 0          | 25.340              | 25.340           | 26.43                               | 1092.32                       |
| 300         | 128           | 50             | Stream     | 50            | 0          | 54.118              | 1.994            | 11.59                               | 438.72                        |
| 300         | 256           | 10             | Non-Stream | 10            | 0          | 31.659              | 31.659           | 26.99                               | 217.86                        |
| 300         | 256           | 10             | Stream     | 10            | 0          | 48.118              | 0.411            | 18.50                               | 90.95                         |
| 300         | 256           | 20             | Non-Stream | 20            | 0          | 23.250              | 23.250           | 34.82                               | 623.39                        |
| 300         | 256           | 20             | Stream     | 20            | 0          | 48.669              | 0.887            | 15.52                               | 259.49                        |
| 300         | 256           | 30             | Non-Stream | 30            | 0          | 41.130              | 41.130           | 20.32                               | 456.73                        |
| 300         | 256           | 30             | Stream     | 30            | 0          | 57.212              | 1.548            | 13.65                               | 323.89                        |
| 300         | 256           | 40             | Non-Stream | 40            | 0          | 57.891              | 57.891           | 14.17                               | 496.40                        |
| 300         | 256           | 40             | Stream     | 40            | 0          | 52.031              | 2.474            | 14.83                               | 435.96                        |
| 300         | 256           | 50             | Non-Stream | 50            | 0          | 45.228              | 45.228           | 17.69                               | 725.04                        |
| 300         | 256           | 50             | Stream     | 50            | 0          | 43.595              | 1.257            | 16.95                               | 712.82                        |
| 300         | 512           | 10             | Non-Stream | 10            | 0          | 32.092              | 32.092           | 26.78                               | 242.20                        |
| 300         | 512           | 10             | Stream     | 10            | 0          | 25.930              | 0.568            | 31.35                               | 245.37                        |
| 300         | 512           | 20             | Non-Stream | 20            | 0          | 34.330              | 34.330           | 26.04                               | 444.89                        |
| 300         | 512           | 20             | Stream     | 20            | 0          | 34.694              | 1.629            | 23.48                               | 408.55                        |
| 300         | 512           | 30             | Non-Stream | 30            | 0          | 34.773              | 34.773           | 25.91                               | 632.48                        |
| 300         | 512           | 30             | Stream     | 30            | 0          | 31.973              | 0.970            | 25.72                               | 632.10                        |
| 300         | 512           | 40             | Non-Stream | 40            | 0          | 36.616              | 36.616           | 24.19                               | 851.76                        |
| 300         | 512           | 40             | Stream     | 40            | 0          | 34.922              | 1.091            | 23.83                               | 783.17                        |
| 300         | 512           | 50             | Non-Stream | 50            | 0          | 36.638              | 36.638           | 24.40                               | 1003.91                       |
| 300         | 512           | 50             | Stream     | 50            | 0          | 34.217              | 1.433            | 23.82                               | 940.82                        |
| 300         | 1024          | 10             | Non-Stream | 10            | 0          | 28.029              | 28.029           | 36.46                               | 305.37                        |
| 300         | 1024          | 10             | Stream     | 10            | 0          | 30.585              | 0.428            | 31.08                               | 246.82                        |
| 300         | 1024          | 20             | Non-Stream | 20            | 0          | 31.945              | 31.945           | 32.23                               | 559.50                        |
| 300         | 1024          | 20             | Stream     | 20            | 0          | 24.585              | 0.949            | 37.25                               | 595.32                        |
| 300         | 1024          | 30             | Non-Stream | 30            | 0          | 30.950              | 30.950           | 33.02                               | 852.51                        |
| 300         | 1024          | 30             | Stream     | 30            | 0          | 25.622              | 1.014            | 36.02                               | 951.37                        |
| 300         | 1024          | 40             | Non-Stream | 40            | 0          | 31.642              | 31.642           | 32.85                               | 1198.05                       |
| 300         | 1024          | 40             | Stream     | 40            | 0          | 28.190              | 1.099            | 33.01                               | 1099.36                       |
| 300         | 1024          | 50             | Non-Stream | 50            | 0          | 30.861              | 30.861           | 32.97                               | 1473.44                       |
| 300         | 1024          | 50             | Stream     | 50            | 0          | 31.885              | 1.121            | 29.28                               | 1238.09                       |
| 300         | 2048          | 10             | Non-Stream | 10            | 0          | 27.862              | 27.862           | 42.47                               | 348.38                        |
| 300         | 2048          | 10             | Stream     | 10            | 0          | 27.356              | 0.439            | 36.49                               | 329.59                        |

</details>

---

## 💡 Best Practices

### Performance Optimization Tips

1. **Start with Default Settings**: Test with default endpoint parameters first before making adjustments
2. **Balance Metrics**: Don't optimize for a single metric; consider TTFT, throughput, and success rate together
3. **Monitor Costs**: Always delete endpoints after testing to avoid unexpected charges
4. **Use Appropriate VM SKUs**: Match your model requirements with the correct GPU VM type
5. **Test Incrementally**: Start with low concurrency and gradually increase to find optimal settings

### Testing Recommendations

1. **Use Real Prompts**: Test with prompts similar to your production use cases
2. **Multiple Scenarios**: Cover different use cases (text generation, Q&A, code generation, etc.)
3. **Vary Prompt Lengths**: Test with different input token lengths (128, 256, 512, 1024, 2048+)
4. **Document Results**: Keep detailed logs of all test configurations and results
5. **Consider Business SLAs**: Align performance targets with your application requirements

### Security Best Practices

1. **Protect API Keys**: Never commit API keys or secrets to version control
2. **Use Environment Variables**: Store sensitive information in environment variables
3. **Rotate Keys Regularly**: Change API keys periodically for security
4. **Limit Access**: Use Azure RBAC to control who can deploy and manage models
5. **Monitor Usage**: Track API calls and set up alerts for unusual activity

