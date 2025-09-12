# Customer AI Training Proposal

**Objective**
The primary objective of this training program is to equip your technical teams with in‑depth knowledge and hands‑on skills in three critical areas of enterprise AI adoption:

1. **Secure Deployment of Azure AI Foundry** – ensuring that AI resources are protected with enterprise‑grade private networking, RBAC, and governance controls.
2. **Fine‑Tuning of Azure OpenAI Models** – enabling the customization of state‑of‑the‑art language models to meet domain‑specific business requirements with improved accuracy, efficiency, and cost‑effectiveness.
3. **Supervised and Reinforcement Fine‑Tuning for Multimodal Models on Azure GPU VMs** – providing practical knowledge in training and deploying advanced models such as *Phi‑4 multimodal*, which can process and reason over text, audio, and images.

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

------

**Format**

- Blended approach: theory sessions + hands‑on labs
- Full command‑line examples and reference code provided
- Real‑world enterprise scenarios tailored to your environment

**Target Audience**

- AI Engineers & Data Scientists
- Enterprise Cloud & Security Architects
- AI Platform Operations & Governance Teams