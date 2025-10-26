# Deep Analysis: RTX PRO 6000 Blackwell Server Edition in Microsoft Azure NCv6 Cloud Form
*— A Cost-effective GPU Platform for AI Model Inference / SFT / Visual Computing*

By `Xinyu Wei` • Sr Solution Engineer (AI Apps GBB - China)

## Introduction & Microsoft Strategic Background
As AI enters the large-model era, inference workloads have shifted toward high concurrency, low latency, and controllable costs as primary goals.  
Microsoft Azure's integrated GPU cloud product — **NCv6 series** — supports three major workload types within one unified VM family:

- **Compute Optimized ** — for light-to-mid AI models inference and SFT
- **General Purpose** — for professional graphics, rendering, and visualization  
- **Memory Optimized** — for multi-user VDI and large-memory visualization  

<img src="./rtx-pro/17.png" alt="Overview of RTX PRO 6000 BSE" class="content-image-full !my-12"/>

### Strategic Significance

Integrating the NVIDIA Blackwell RTX PRO 6000 BSE into NCv6 brings three key values:

1. **End-to-end workload convergence**: Run AI inference, rendering, simulation, and video processing on a single VM without SKU switching.
2. **Maximized GPU utilization**: MIG multi-instance support enables precise GPU resource partitioning for multi-tenant or mixed workload co-existence.
3. **Software-hardware co-optimization**: Azure delivers GPU driver rtx-pro and pre-integrated environments, reducing integration costs.



**GA Regions(Tentative):** East US2, East US, Japan East, Sweden Central, Australia East, North Europe, UK South, West Europe, South Central US, Germany West Central 

---

## Hardware & Architecture: Blackwell + Azure NC Series
### Background
The Blackwell architecture replaces the previous Ada Lovelace generation, delivering step-change improvements in compute cores, memory capacity & bandwidth, and inference precision capabilities.  

<img src="./rtx-pro/1.png" alt="Blackwell Architecture Platform Form" class="content-image-full !my-12" />


### Performance Data Interpretation
- **Compute Units**: 24,064 CUDA Cores, 752 × 5th-gen Tensor Cores, 188 × 4th-gen RT Cores  
- **Memory System**: 96GB GDDR7 ECC (1.6 TB/s) — double the capacity & bandwidth of the L40S  
- **Inference Engine**: 2nd-gen Transformer Engine capable of FP4/FP8 automatic mixed-precision inference  
- **Media Engine**: 4× NVENC / 4× NVDEC / NVJPEG  
- **Virtualization Capabilities**: Up to 4 MIG slices (24 GB each)

### Differences Explained
Compared to the L40S, the Blackwell BSE's core improvements are doubled memory capacity and bandwidth, and greater Tensor Core precision diversity (added NVFP4).  
These advances directly reduce Host–GPU exchange bottlenecks, which matter especially in Azure’s networked architecture where cross-host latency is higher.

### Impact in Azure Scenarios
- **Compute Optimized SKU**: Can host full 70B model weights + KV Cache within a single GPU (NVFP4).  
- **General Purpose SKU**: RT Cores support ray-traced rendering while performing simultaneous inference tasks.  
- **Memory Optimized SKU**: Under MIG slicing, supports multiple VDI users with 3D graphics.

### Deployment & Operations
- **Drivers & CUDA**: Azure provides official GPU VM rtx-pro containing Blackwell support.  
- **MIG Management**: Select MIG-enabled SKU via Azure Portal or CLI — whole GPU for large jobs, slices for cost reduction in smaller jobs.  
- **Software Stack**: For compute workloads use vLLM/Transformers; for rendering workloads use Omniverse or NVIDIA SDK.

### Cost & ROI
With MIG slicing, customers pay GPU fees according to actual slice usage, avoiding full-card cost waste.

## Quantized Inference Accuracy: NVFP4 vs FP8

RTX PRO 6000 support NVFP4 by default, quantization precision can significantly affect model performance during inference. The chart below shows the accuracy comparison of the **DeepSeek-R1 0528** model under FP8 and NVFP4 quantization:

<img src="./rtx-pro/19.png" alt="DeepSeek-R1 Quantization Accuracy Comparison" class="content-image-full !my-12" />

Across multiple tasks, the accuracy difference between NVFP4 and FP8 is minimal:

- **Math-500**: Maintains 98% accuracy, with no loss
- **AIME 2024**: Even slightly higher accuracy than FP8 (91% vs 89%)
- Others like MMLU-PRO and LIVE CODE BENCH drop by only about 1%

This demonstrates that NVFP4 can greatly reduce compute/memory usage while keeping accuracy nearly intact, making it highly suitable for large-scale inference deployment.

For a detailed introduction to NVFP4, see my repo:
*https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/NVFP4*

---

## Specification Comparison & Impact on Azure Workloads
### Background
Understanding the differences between Blackwell and L40S helps in selecting the right Azure NCv6 SKU and planning capacity.

### Data Interpretation

| Metric          | RTX PRO 6000 BSE       | L40S                 | Azure Impact |
|-----------------|------------------------|----------------------|--------------|
| CUDA Cores      | 24,064                 | 18,176               | Significantly higher concurrent compute capacity |
| Tensor Cores    | 752                    | 568                  | Stronger FP4/FP8 Transformer inference acceleration |
| RT Cores        | 188                    | 142                  | Improved rendering and physics simulation efficiency |
| Memory          | 96GB ECC GDDR7         | 48GB ECC GDDR6       | Larger models can fit in a single MIG or full GPU |
| Bandwidth       | 1.6 TB/s               | 864 GB/s             | Reduced inference latency, higher throughput |
| Power           | 600W                   | 350W                 | More performance, requires optimized cooling |

<img src="./rtx-pro/9.png" alt="Specification Comparison: RTX PRO 6000 vs L40S" class="content-image-full !my-12" />

### Differences Explained

- Increased process capability and core volume boost compute density.  
- GDDR7 improves memory frequency & bandwidth, mitigating multi-stream inference saturation points.  
- More RT Cores are suited to complex rendering scenarios.

### Azure Scenario Impacts
- **Latency Equivalence**: At same latency, Blackwell VM can host 3–5× concurrent connections.  
- **Large Model Hosting**: 70B AI models can run on a single card (FP4), reducing multi-card communication cost & complexity.  
- **Rendering Real-time Gains**: Beneficial for design collaboration.



## Workload Analysis

### 1. LLM Inference and SFT
<img src="./rtx-pro/12.png" alt="LLM Inference Performance Comparison" class="content-image-full !my-12" />

#### Background

LLM inference, due to high concurrency and latency sensitivity, is crucial in cloud services architectures (Azure OpenAI, Copilot, search augmentation). It often requires finding the maximum balance between GPU count and response speed.  
On Azure NCv6 Compute Optimized SKUs, the RTX PRO 6000 BSE’s large memory and FP4 inference path significantly extend this balance point.

#### Performance Data Interpretation
- **Llama3 8B**: +4.8× throughput, 1.9 SFT performance (vs. L40S) 
- **Llama3 70B**: +5.6× throughput, 2.1 SFT performance (vs. L40S)   
- **Mixtral 8×7B**: +3.6× throughput, 1.8 SFT performance (vs. L40S)   

#### Differences Explained
- FP4 weight quantization: greatly reduces memory & bandwidth usage  
- 96GB GDDR7: allows full KV Cache to reside in GPU memory, avoiding Host–GPU swaps  
- 5th-gen Tensor Core FP8/FP4 mixed support: Transformer Engine auto precision scheduling  
- Bandwidth doubled: lower multi-stream concurrent latency

### 2 Graphics & Visualization
 <img src="./rtx-pro/6.png" alt="Cost-effectiveness Comparison" class="content-image-full !my-12"/>

#### Background
Visual workloads in Azure cloud (Omniverse, film rendering, design visualization) require high RT Core performance, low-latency frame rendering, and high-bandwidth media encode/decode. These used to need dedicated rendering SKUs; now, in NCv6 General Purpose (NC…gs_v6), they can co-exist with inference.

#### Performance Data
- Pure performance increase: up to +3.3× over L40S
- In interactive rendering scenarios like Omniverse, FPS increases and frame generation latency decreases simultaneously.

#### Differences Explained
- 4th-gen RT Core yields higher ray-tracing throughput
- PCIe Gen6 and doubled bandwidth reduce texture swap latency in large-scene rendering
- Media engines doubled (4× NVENC / 4× NVDEC) → higher encode/decode throughput

#### Azure Impacts
- General Purpose SKUs can run Omniverse, 3D modeling, or render farms directly
- Crowdsourced rendering can leverage Azure Batch to save peak resource costs
- Multi-stream video encoding can run alongside inference tasks to boost overall utilization

### 3 Industrial Simulation & Synthetic Data
<img src="./rtx-pro/7.png" alt="Cost-effectiveness Comparison" class="content-image-full !my-12"/>

#### Background
Industrial simulation (digital twin, physics simulation) and synthetic data generation for autonomous driving/robotics require both graphics rendering and physics computation. These were traditionally distributed between HPC clusters and rendering nodes. NCv6 Memory Optimized (NC…ms_v6) unifies these workloads.

#### Performance Data
- Digital twin simulation: +3.3×  over L40S
- Layout planning: +3.7×  over L40S
- Synthetic video generation: +2.6×  over L40S
- Batch rendering generation: +2.8× over L40S

#### Differences Explained
- Blackwell’s doubled memory & bandwidth handle large scene files  
- RT Core + Tensor Core coordination accelerates physics sims with AI components  
- Multiple NVENC paths ensure video output without bottlenecks

#### Azure Impacts
- Memory Optimized SKU can run CAD/CAE-level simulation and directly produce synthetic training data  
- MIG slices possible to run varied simulation flows for different users/tasks  
- Render output can directly upload to Azure Blob Storage or Data Lake for downstream training

---

### 4 Vision AI Agents
<img src="./rtx-pro/10.png" alt="Vision AI Agents Performance" class="content-image-full !my-12"/>

#### Background
Vision AI Agents perform perception tasks (classification, segmentation, detection) through multi-model collaboration. These workloads require both throughput and low latency, usually for office automation, quality inspection, and auto labeling.

#### Performance Data
- Classification: +61%  over L40S
- Segmentation: +69%  over L40S
- Detection: +33% over L40S

#### Differences Explained
- Blackwell Tensor Cores accelerate both CNN and Transformer architectures  
- Increased memory reduces overflow in large-resolution image batch processing

#### Azure Impacts
- Compute Optimized SKU can run multiple inference processes in a single MIG slice for different departments/applications  
- Integrate with Azure AI Vision and Cognitive Services for direct cloud deployment

---

### 5 Generative Models
<img src="./rtx-pro/11.png" alt="Generative Model Performance" class="content-image-full !my-12" />

#### Background
Multi-modal generation on Azure (text-to-image, text-to-video) requires high memory, media engines, and ML acceleration combined. Blackwell’s specs fit well in this space.

#### Performance Data
- Cosmos 7B: +3.3×  over L40S
- Flux 12B: +2.9×  over L40S
- SDXL: +1.8× over L40S

#### Azure Impacts
- General Purpose SKU can co-locate generation tasks with rendering  
- Output flows directly into Azure Blob/Media Services pipelines

## SFT Performance Comparison with A100 / H100

<img src="./rtx-pro/18.png" alt="Training Performance Comparison" class="content-image-full !my-12" />

Using Qwen3-8B with different fine-tuning approaches:

- **Full fine-tuning**: RTX 6000 Pro is ~10% faster than H100, ~50% faster than A100
- **LoRA** fine-tuning: Also leads in performance
- **QLoRA** fine-tuning: Maintains its advantage

In single-GPU training scenarios, the RTX 6000 Pro achieves near-H100 speed at a much lower cost.



#### Demo code for SFT on RTX/H100/A100

You could run following code on jupyter file cells.

Install PyTorch nightly for CUDA >= 12.8

```shell
!pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
!pip install ninja
!pip install flash_attn --no-build-isolation
!pip install --upgrade transformers bitsandbytes peft accelerate datasets trl hf_transfer hf_xet
```

Install vLLM for TX Pro 6000D:

```shell
!git clone https://github.com/vllm-project/vllm.git
%cd vllm
!python use_existing_torch.py
!pip install -r requirements/build.txt
!pip install setuptools_scm
!mkdir ./tmp
!MAX_JOBS=10 CCACHE_DIR=./tmp python setup.py develop
```

Download models:

```shell
!HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download Qwen/Qwen3-8B-Base
```

 **Fine-Tuning Code**

```python
import torch, os, multiprocessing
from datasets import load_dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed
)
from trl import SFTTrainer, SFTConfig
set_seed(1234)

compute_dtype = torch.bfloat16
attn_implementation = 'flash_attention_2'

def fine_tune(model_name, batch_size=1, gradient_accumulation_steps=32, LoRA=False, QLoRA=False):

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.eos_token = "<|im_end|>"
    ds_train = load_dataset("allenai/tulu-3-sft-olmo-2-mixture-0225", split="train[:15000]")

    def process(row):
        row["text"] = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False, enable_thinking=False)
        return row

    ds_train = ds_train.map(
        process,
        num_proc= multiprocessing.cpu_count(),
        load_from_cache_file=False,
    )

    print(ds_train[0]['text'])

    ds_train = ds_train.remove_columns(["messages"])

    if QLoRA:
        bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
                  model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
        )
        model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})
    else:
        model = AutoModelForCausalLM.from_pretrained(
                  model_name, device_map={"": 0}, torch_dtype=compute_dtype, attn_implementation=attn_implementation
        )
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})



    if LoRA or QLoRA:
        peft_config = LoraConfig(
                lora_alpha=32,
                lora_dropout=0.05,
                r=32,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"],
                modules_to_save = ["embed_tokens", "lm_head"]
        )
    else:
      peft_config = None

    if LoRA:
        output_dir = "./LoRA/"
    elif QLoRA:
        output_dir = "./QLoRA/"
    else:
        output_dir = "./FFT/"

    training_arguments = SFTConfig(
        output_dir=output_dir,
        optim="adamw_8bit",
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        log_level="debug",
        save_strategy="no",
        logging_steps=25,
        learning_rate=1e-5,
        bf16 = True,
        max_steps=100,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=4096,
        padding_free=True,
        report_to="none"
    )

    trainer = SFTTrainer(
          model=model,
          train_dataset=ds_train,
          peft_config=peft_config,
          processing_class=tokenizer,
          args=training_arguments,
    )

    #--code by Unsloth: https://colab.research.google.com/drive/1Ys44kVvmeZtnICzWz0xgpRnrIOjZAuxp?usp=sharing#scrollTo=pCqnaKmlO1U9

    gpu_stats = torch.cuda.get_device_properties(0)
    start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
    print(f"{start_gpu_memory} GB of memory reserved.")

    trainer_ = trainer.train()


    used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    used_memory_for_trainer= round(used_memory - start_gpu_memory, 3)
    used_percentage = round(used_memory         /max_memory*100, 3)
    trainer_percentage = round(used_memory_for_trainer/max_memory*100, 3)
    print(f"{trainer_.metrics['train_runtime']} seconds used for training.")
    print(f"{round(trainer_.metrics['train_runtime']/60, 2)} minutes used for training.")
    print(f"Peak reserved memory = {used_memory} GB.")
    print(f"Peak reserved memory for training = {used_memory_for_trainer} GB.")
    print(f"Peak reserved memory % of max memory = {used_percentage} %.")
    print(f"Peak reserved memory for training % of max memory = {trainer_percentage} %.")
    print("-----")
    #----
```

Run the same test code on three different GPU-based virtual machines  (VMs), using various combinations of the following four parameter  settings:

- `batch_size`
- `gradient_accumulation_steps`
- `LoRA` (Low-Rank Adaptation)
- `QLoRA` (Quantized Low-Rank Adaptation)

These combinations are used to evaluate the performance and  effectiveness of different GPU hardware under multiple training  configurations.

```python
fine_tune("Qwen/Qwen3-8B-Base", batch_size=4, gradient_accumulation_steps=32, LoRA=False, QLoRA=False)
```

```python
fine_tune("Qwen/Qwen3-8B-Base", batch_size=4, gradient_accumulation_steps=32, LoRA=True, QLoRA=False)
```

```python
fine_tune("Qwen/Qwen3-8B-Base", batch_size=4, gradient_accumulation_steps=32, LoRA=False, QLoRA=True)
```



---

## Final Summary and Recommendations

### Overall Assessment
The NVIDIA Blackwell RTX PRO 6000 BSE in Azure NCv6 represents a major step forward for cloud-based GPU workloads, delivering high performance, flexible workload deployment, and strong cost efficiency within Microsoft’s latest converged VM architecture.

**Key Advantages**
1. **High FP4 Tensor Core performance** — exceptionally strong in quantized inference for LLMs and other transformer-based models.
2. **Large memory capacity (96GB GDDR7 ECC)** — enables single-GPU hosting of large models (up to 70B parameters) with KV Cache fully in-memory.
3. **Broad workload competency** — outperforms H100 and A100 in many single-GPU inference and SFT tasks.
4. **Cost efficiency** — ideal for single-GPU or small/medium workloads where NVL ultra-high bandwidth is not essential.
5. **Versatile deployment** — Compute Optimized, General Purpose, and Memory Optimized SKUs allow unified management of AI inference, rendering, and VDI under one VM family.

### Recommended Workload Strategies
- **Mixed Schedule**:  
  - Rendering / VDI workloads  
  - Inference / SFT tasks  
- **Image Management**: Centralize GPU images, drivers, CUDA toolkit, and libraries in Azure Compute Gallery for consistency across teams.
- **Network Optimization**: Keep inference and rendering tasks in the same Azure region to capitalize on low-latency networking.
- **Cost Control**:  
  - Use 1/4 MIG slices for lightweight jobs to lower hourly billing.  
  - Batch inference and synthetic data generation to minimize idle GPU periods.
- **Monitoring & SLA**: Track KPIs — throughput, latency, memory utilization, encoder load — via Azure Monitor + NVIDIA DCGM to ensure SLAs.

### Best Fit Use Cases
- **Single/Double-GPUs large-model inference** — leveraging NVFP4 quantization for maximum throughput per card.
- **Single/Double-GPU fine-tuning** — including full fine-tuning or parameter-efficient methods like LoRA/QLoRA.
- **Cost-sensitive applications** — such as enterprise LLM APIs, media pipelines, and simulation workloads that do not need NVL extreme bandwidth.









































