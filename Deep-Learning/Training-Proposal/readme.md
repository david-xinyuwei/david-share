# Customer AI Training Proposal

This training equips participants with practical expertise in secure Azure AI deployments, model fine‑tuning workflows, and advanced large model optimization on Azure infrastructure. The curriculum focuses on:

1. Implementing secure, private, and compliant AI Foundry environments.
2. Performing supervised fine‑tuning on Azure OpenAI models with optimal dataset preparation and deployment practices.
3. Training, quantizing, and deploying cutting‑edge multimodal and open‑source foundation models such as *Phi‑4‑multimodal* and *OpenAI GPT‑OSS* on Azure GPU and containerized environments with performance‑oriented techniques like LoRA, FlashAttention, MXFP4 quantization, and Sink Token optimization.

Knowledge points in this course：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Training-Proposal/images/1.png)


## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | LoRA/PEFT |


## **Takeaways**

By the conclusion of the training, participants will be able to:

- Design and implement secure, “zero public exposure” AI environments on Azure.
- Prepare and format high‑quality datasets for fine‑tuning models.
- Operate both Azure‑hosted and custom‑trained multimodal AI systems with optimized performance.
- Integrate trained models into enterprise applications while adhering to compliance and governance requirements.

------

## Course Modules

### 1. **AI Foundry Security**

This module covers the design and deployment of a secure Azure AI Foundry environment, incorporating Private Endpoints, Azure Bastion, and NAT Gateways to achieve end‑to‑end private connectivity and eliminate public network exposure. It includes step‑by‑step creation of custom RBAC roles (for example, “AI Developer without Compute”) to enforce fine‑grained access control, as well as the use of Azure Policy to enforce model deployment whitelists. Attendees will gain hands‑on experience configuring network security groups (NSGs), validating private access, and ensuring that all administrative operations conform to enterprise security standards.

**Reference:**

- [AI Foundry Private Endpoint – Secure Networking Guide](https://github.com/david-xinyuwei/david-share/tree/master/Agents/AI-Agent-Private-Endpoint)
- [Microsoft Official Documentation – Configure Private Link in AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/configure-private-link?tabs=azure-portal&pivots=fdp-project)

------

### 2. **Azure OpenAI Fine‑Tuning**

This module introduces the end‑to‑end fine‑tuning workflow for Azure OpenAI models via Azure AI Foundry. Participants will learn when and why to fine‑tune, differences between LoRA (Low‑Rank Adaptation), Supervised Fine‑Tuning (SFT), Direct Preference Optimization (DPO), and Reinforcement Fine‑Tuning (RFT). Practical exercises guide learners through dataset preparation and formatting in JSONL, managing training and validation datasets, selecting base models, and monitoring training progress. The module also addresses key quality assurance techniques, continuous fine‑tuning strategies, deployment options, and best practices to maximize return on investment for AI model customization.

**Reference:**

- [Azure AI Foundry – Azure OpenAI Fine‑Tuning Portal](https://ai.azure.com/resource/overview)

------

### 3. **Azure GPU VM SFT/RL for Phi‑4 Multimodal**

In this module, attendees will explore supervised and reinforcement fine‑tuning techniques for *Phi‑4 multimodal*, a Microsoft model capable of understanding and generating text, audio, and vision inputs. Through hands‑on labs using Azure H100 GPU VMs, participants will train the audio encoder for speech translation tasks (e.g., English to Chinese or Slovenian) and fine‑tune the vision encoder for domain‑specific visual question answering (VQA). The training covers environment setup, LoRA parameter‑efficient fine‑tuning, Flash Attention for optimization, distributed training on Azure GPU resources, and integration with interactive user interfaces such as Gradio for demonstration and testing.

**Reference:**

- [Full Code & Examples – Phi‑4 Multimodal SFT](https://github.com/david-xinyuwei/david-share/tree/master/Multimodal-Models/SFT-Phi-4-mm)



**MediaTek** runs AI models natively to better facilitate real-time interactions by incorporating Phi-3.5 into its Dimensity 9400 chipsets. The Phi models offer advanced AI capabilities at a lower cost, provide high-quality training data, and include safety measures to yield accurate and reliable outputs. “Our customers use the Phi-3.5 mini model, which allows them to rapidly customize their product,” says Yannic Peng, Product Manager at MediaTek.

**Reference:**

[MediaTek boosts on-device AI speed by 50% using Phi models from Microsoft](https://www.microsoft.com/en/customers/story/23680-mediatek-azure-ai-model-catalog)

​		

| microsoft/Phi-3.5-mini-instruct     | 3.82B params |
| ----------------------------------- | ------------ |
| microsoft/Phi-4-multimodal-instruct | 5.57B params |

​	





In this module, attendees will explore deploy and optimize *gpt‑oss‑20B/120B* on Azure GPU and AKS with KAITO integration. Includes post‑training quantization, MXFP4 quantization‑aware training, Sink Token inference optimization with FlashAttention‑3, and performance tuning for Hopper vs. Ampere GPUs. Discuss fine‑tuning strategies and trade‑offs between quantized and FP16 deployments.

**Reference:**

- [Full Code & Examples – GPT-OSS SFT](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/OAI-OSS-on-Azure)

------

## **Format**

- Blended approach: theory sessions + hands‑on labs
- Full command‑line examples and reference code provided
- Real‑world enterprise scenarios tailored to your environment

## **Target Audience**

- AI Engineers & Data Scientists
- Enterprise Cloud & Security Architects
- AI Platform Operations & Governance Teams