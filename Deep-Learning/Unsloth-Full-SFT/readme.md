## Unsloth的全微调：从Adapter到Full Fine-tuning

大语言模型（LLM）最近发展得非常快，一动就是好几亿甚至上百亿的参数，让很多AI工程师在微调这些大模型时犯了难。Unsloth这个框架，原本主要是靠支持LoRA、QLoRA等Adapter微调而出名，重点就是省内存、训练快。现在它又更进一步，支持了全参数微调（Full Fine-tuning），也就是说，单卡环境就能搞定大规模模型的完整训练。接下来我想聊一聊Unsloth全微调的背景、它用到的关键技术，以及在实际工程中怎么把它用好。

**一、从 LoRA/QLoRA 到 Full Fine-tuning：Unsloth 的进化历程**

1. 初期聚焦：LoRA & QLoRA 早期的 Unsloth 仅支持基于 LoRA/QLoRA 的适配器微调（Adapter Fine-tuning）。它通过动态量化、稀疏优化、梯度检查点等技术手段，大幅减少显存占用，让工程师能在单卡或少卡环境下，对 LLM 进行有效训练。

2. 为什么最初只支持 Adapter 微调？ 

   • 实惠的硬件门槛：Adapter 微调只需更新部分额外参数，不必动用整套模型，从而有效减少 GPU 显存需求和训练开销。
   • 高性价比：对于大部分应用场景来说，使用 LoRA/QLoRA 得到的微调效果已足以解决“任务定制”需求，而且成本远低于全量微调。
   • 工程实现相对简单：无须管理全部模型权重的更新和保存，只需管理 LoRA 等附加层的参数即可。

3. 全参数微调走上日程 随着用户对微调需求的精细化、对模型性能的极致追求，以及在更大规模的 LLM 上进行高保真的领域适配需求日益增长，Unsloth 社区在 2024 ~ 2025 年间逐步加入了对 full fine-tuning 的支持，使得你无需额外插入Adapter，也能直接训练整个模型的全部参数。

**二、Unsloth 全微调：关键技术解析**

1. 梯度检查点（Gradient Checkpointing） 

   • 在单 GPU 进行全微调时，重新计算部分前向激活以节省显存成为了必然需求。
   • PyTorch 本身提供了 checkpoint 工具，但 Unsloth 在此基础上做了更深入的工程优化，大幅降低部分场景下的额外重算开销。

2. 激活值卸载（Activation Offloading） 

   • 当显存不足时，将部分激活值转存到 CPU 内存。Unsloth 会智能地在训练过程中安排卸载与回传时机，确保在最“恰当”的时刻介入，从而减小对训练速度的冲击。

3. 优化器状态分页（Optimizer Paging）

   • 在大模型训练中，单卡不仅需要存储模型本身的参数，还要存储优化器状态，这也是显存占用的一大来源。
   • 通过 8-bit 甚至更低精度的优化器（如 paged_adamw_8bit），即能把部分优化器状态分页至 CPU，释放 GPU 显存，进一步帮助单卡支持更大规模的模型。

**三、工程上的部署实例与硬件选择**

**以常用的H100 94GB，H200 141GB， AMD MI300X 192为例：**

| GPU 型号            | 显存容量 | 推荐模型规模 | 实践优化建议                                                 |
| ------------------- | -------- | ------------ | ------------------------------------------------------------ |
| NVIDIA H100（PCIe） | 94 GB    | 14B          | 1. Unsloth 默认开启梯度检查点（Gradient Checkpointing）与分页优化器（Paged Optimizer），无需额外手动配置，建议保持为默认开启状态。 2. 单卡 batch size 建议设定为 1 或 2，减少显存压力与 CPU 激活值卸载频率，确保更佳的训练效率。 3. 接近推荐最大规模（20B）时，需注意 CPU 内存大小是否足够，以避免频繁卸载激活值所引发的性能瓶颈。 |
| NVIDIA H200         | 141 GB   | **15B～25B** | 1. 可适当增加 batch size，但仍需保留一定显存空间，避免频繁的激活值卸载。 2. 若逼近30B规模上限，尝试降低序列长度或适当减少 batch size，以平衡性能表现与内存占用。 3. 实时监控训练日志以观察显存占用和卸载频率，及时优化参数。 |
| AMD MI300X          | 192 GB   | **30B～50B** | 1. 特别适用于微调 LLaMA2 或 LLaMA3 类的 40B ～ 65B 更大规模模型，并支持更长序列长度的训练。 2. 对于序列长度较长（≥4K tokens）仍建议维持Unsloth默认优化策略。 3. 在只训练约40B级别模型时，可适度增大单卡 batch size，提升 GPU 使用效率和微调吞吐量。 |

- Unsloth 已默认开启多种优化机制（包括梯度检查点与分页式优化器），一般情况下无需额外配置。
- 全参数微调时显存压力高于 LoRA/QLoRA 等适配器方法，特别需注意的是：
  - 若单卡 GPU 显存不足（低于80GB），请务必维持分页优化器 (Paged Optimizer) 默认开启的状态。
  - 适当减小 batch size 通常会减少激活值卸载频率，从而获得整体更高的训练速度。
- 实际微调过程建议进行小规模实验验证，逐步调整相关超参数（batch size、序列长度等），结合自身的硬件配置和应用场景找到最佳性能与内存占用平衡点。



**四、为什么不直接自己实现这些内存优化？**

1. 维护难度高 • 手动在代码层面开发 offload、checkpoints 等逻辑，面对不同版本的 PyTorch / CUDA / 驱动，以及不同模型结构，调试复杂度极高，且易产生潜在内存泄露、兼容性问题。
2. 社区打磨与更新 • Unsloth 在社区中已有大量真实使用场景与案例，经过了版本迭代与优化，加之官方维护的更新日志（release notes），更易确保长久可用与持续优化。
3. 专注业务逻辑 • 使用 Unsloth 可将时间投入到数据集清洗、任务工程化、下游效果评估，而不是消耗在重复开发类似的底层内存管理功能上。

**五、最佳实践：如何平衡内存占用与训练效率**

1. 保持小 Batch Size（1~2 常见）、

    • 过大的 batch size 会导致 Unsloth 频繁进行激活值卸载，反而拖慢训练速度。
   • 在单 GPU 场景中，小 batch + 累积梯度(gradient_accumulation_steps) 通常更优。

2. 分阶段调试 

   • 先用小模型、短序列长度跑通流程，观察 GPU 负载与日志，用以确认 offloading 时机与显存开销。
   • 一旦找到稳定训练配置，再逐步扩展到更大模型或更长序列。

3. 充分启用 paged optimizer 

   • 对于全参数微调而言，优化器状态空间非常可观，将其分页至 CPU，可以显著降低 GPU 显存峰值占用。

**六、代码展示**

全微调meta-llama/Llama-3.1-8B

执行代码：

```
(Unsloth) root@h100vmxinyu:~# python 1.py 
🦥 Unsloth: Will patch your computer to enable 2x faster free finetuning.
Unsloth: Failed to patch Gemma3ForConditionalGeneration.
🦥 Unsloth Zoo will now patch everything to make training faster!
Unsloth: You selected full finetuning support, but 4bit / 8bit is enabled - disabling LoRA / QLoRA.
==((====))==  Unsloth 2025.3.19: Fast Llama patching. Transformers: 4.51.3.
   \\   /|    NVIDIA H100 NVL. Num GPUs = 1. Max memory: 93.016 GB. Platform: Linux.
O^O/ \_/ \    Torch: 2.6.0+cu124. CUDA: 9.0. CUDA Toolkit: 12.4. Triton: 3.2.0
\        /    Bfloat16 = TRUE. FA [Xformers = 0.0.29.post3. FA2 = True]
 "-____-"     Free license: http://github.com/unslothai/unsloth
Unsloth: Fast downloading is enabled - ignore downloading bars which are red colored!
Unsloth: Using bfloat16 full finetuning which cuts memory usage by 50%.
Loading checkpoint shards: 100%|█████████████████████████████████████████| 4/4 [00:02<00:00,  1.90it/s]
Map (num_proc=40): 100%|█████████████████████████████| 939343/939343 [01:02<00:00, 14913.88 examples/s]
Using auto half precision backend
Currently training with a batch size of: 2
The following columns in the training set don't have a corresponding argument in `LlamaForCausalLM.forward` and have been ignored: id, text, source. If id, text, source are not expected by `LlamaForCausalLM.forward`,  you can safely ignore this message.
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 939,343 | Num Epochs = 2 | Total steps = 14,676
O^O/ \_/ \    Batch size per device = 2 | Gradient accumulation steps = 64
\        /    Data Parallel GPUs = 1 | Total batch size (2 x 64 x 1) = 128
 "-____-"     Trainable parameters = 8,030,261,248/8,030,261,248 (100.00% trained)
  0%|                                                                        | 0/14676 [00:00<?, ?it/s]`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`.
Unsloth: Will smartly offload gradients to save VRAM!
  0%|                                                             | 5/14676 [02:07<99:36:40, 24.44s/it]
```

显存开销 58%：

```
(py38_default) root@h100vmxinyu:~# nvidia-smi
Sat Apr 19 04:17:50 2025       
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.183.01             Driver Version: 535.183.01   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA H100 NVL                On  | 00000001:00:00.0 Off |                    0 |
| N/A   79C    P0             392W / 400W |  55485MiB / 95830MiB |     92%      Default |
|                                         |                      |             Disabled |
+-----------------------------------------+----------------------+----------------------+
                                                                                         
+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     10993      C   python                                    40108MiB |
+---------------------------------------------------------------------------------------+
```

如果将模型换成14B microsoft/phi-4：

```
(Unsloth) root@h100vmxinyu:~# python 2.py 
🦥 Unsloth: Will patch your computer to enable 2x faster free finetuning.
Unsloth: Failed to patch Gemma3ForConditionalGeneration.
🦥 Unsloth Zoo will now patch everything to make training faster!
Unsloth: You selected full finetuning support, but 4bit / 8bit is enabled - disabling LoRA / QLoRA.
==((====))==  Unsloth 2025.3.19: Fast Llama patching. Transformers: 4.51.3.
   \\   /|    NVIDIA H100 NVL. Num GPUs = 1. Max memory: 93.016 GB. Platform: Linux.
O^O/ \_/ \    Torch: 2.6.0+cu124. CUDA: 9.0. CUDA Toolkit: 12.4. Triton: 3.2.0
\        /    Bfloat16 = TRUE. FA [Xformers = 0.0.29.post3. FA2 = True]
 "-____-"     Free license: http://github.com/unslothai/unsloth
Unsloth: Fast downloading is enabled - ignore downloading bars which are red colored!
Unsloth: Using bfloat16 full finetuning which cuts memory usage by 50%.
model.safetensors.index.json: 100%|████████████████████████████████| 29.9k/29.9k [00:00<00:00, 171MB/s]
model-00001-of-00006.safetensors: 100%|███████████████████████████▉| 4.93G/4.93G [00:05<00:00, 880MB/s]
model-00002-of-00006.safetensors: 100%|███████████████████████████▉| 4.95G/4.95G [00:05<00:00, 923MB/s]
model-00003-of-00006.safetensors: 100%|███████████████████████████▉| 4.90G/4.90G [00:11<00:00, 444MB/s]
model-00004-of-00006.safetensors: 100%|███████████████████████████▉| 4.95G/4.95G [00:13<00:00, 361MB/s]
model-00005-of-00006.safetensors: 100%|██████████████████████████▉| 4.95G/4.95G [00:04<00:00, 1.01GB/s]
model-00006-of-00006.safetensors: 100%|███████████████████████████▉| 4.62G/4.62G [00:04<00:00, 952MB/s]
Loading checkpoint shards: 100%|█████████████████████████████████████████| 6/6 [00:08<00:00,  1.43s/it]
generation_config.json: 100%|█████████████████████████████████████████| 147/147 [00:00<00:00, 1.94MB/s]
tokenizer_config.json: 100%|███████████████████████████████████████| 18.0k/18.0k [00:00<00:00, 127MB/s]
vocab.json: 100%|█████████████████████████████████████████████████| 1.61M/1.61M [00:00<00:00, 30.2MB/s]
merges.txt: 100%|███████████████████████████████████████████████████| 917k/917k [00:00<00:00, 44.7MB/s]
tokenizer.json: 100%|█████████████████████████████████████████████| 7.15M/7.15M [00:00<00:00, 11.0MB/s]
special_tokens_map.json: 100%|████████████████████████████████████████| 456/456 [00:00<00:00, 5.25MB/s]
Map (num_proc=40): 100%|█████████████████████████████| 939343/939343 [01:12<00:00, 12993.77 examples/s]
Unsloth: Tokenizing ["text"] (num_proc=40): 100%|█████| 939343/939343 [02:39<00:00, 5887.42 examples/s]
Using auto half precision backend
Currently training with a batch size of: 2
The following columns in the training set don't have a corresponding argument in `LlamaForCausalLM.forward` and have been ignored: source, text, id. If source, text, id are not expected by `LlamaForCausalLM.forward`,  you can safely ignore this message.
==((====))==  Unsloth - 2x faster free finetuning | Num GPUs used = 1
   \\   /|    Num examples = 939,343 | Num Epochs = 2 | Total steps = 14,676
O^O/ \_/ \    Batch size per device = 2 | Gradient accumulation steps = 64
\        /    Data Parallel GPUs = 1 | Total batch size (2 x 64 x 1) = 128
 "-____-"     Trainable parameters = 14,659,507,200/14,659,507,200 (100.00% trained)
  0%|                                                                        | 0/14676 [00:00<?, ?it/s]`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`.
Unsloth: Will smartly offload gradients to save VRAM!
  0%|                                                            | 1/14676 [00:58<239:57:36, 58.87s/it]
```

显存使用情况，显存开销96%：

```
(py38_default) root@h100vmxinyu:~# nvidia-smi
Sat Apr 19 04:28:38 2025       
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.183.01             Driver Version: 535.183.01   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA H100 NVL                On  | 00000001:00:00.0 Off |                    0 |
| N/A   80C    P0             392W / 400W |  91839MiB / 95830MiB |    100%      Default |
|                                         |                      |             Disabled |
+-----------------------------------------+----------------------+----------------------+
                                                                                         
+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     11825      C   python                                    63778MiB |
+---------------------------------------------------------------------------------------
```

微调代码如下：

```
#cat 1.py
from unsloth import FastLanguageModel
import torch, os, multiprocessing, gc
from datasets import load_dataset
from peft import LoraConfig
from transformers import set_seed, AutoTokenizer

from trl import SFTTrainer, SFTConfig

set_seed(42)

model_name = "meta-llama/Llama-3.1-8B"
tokenizer_name_chat_template = "allenai/Llama-3.1-Tulu-3-8B"
compute_dtype = torch.bfloat16

bs = 2 #Batch size per device (training and validation), bs = 1 *can* be faster
gas = 64 #Gradient accumulation steps
mseqlen = 4096 #Maximum sequence length; reduce if you run out of memory

lr = 5e-6 #Default learning rate, way too small for Unsloth. Multiply it by 10 or 20 .

output_dir = "./SFT/"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    fix_tokenizer=False,
    max_seq_length = mseqlen,
    dtype = compute_dtype,
    full_finetuning=True
)

ds_train = load_dataset("allenai/tulu-3-sft-mixture", split="train")

# Apply the chat template from TULU's tokenizer
tokenizer_chat = AutoTokenizer.from_pretrained(tokenizer_name_chat_template)
def process(row):
    row["text"] = tokenizer_chat.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
    return row

ds_train = ds_train.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

ds_train = ds_train.remove_columns(["messages"])

training_arguments = SFTConfig(
        output_dir=output_dir,
        #eval_strategy="steps",
        #do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=bs,
        gradient_accumulation_steps=gas,
        #per_device_eval_batch_size=bs,
        log_level="debug",
        save_strategy="steps",
        save_steps=10000,
        logging_steps=25,
        learning_rate=lr,
        bf16 = True,
        #eval_steps=25,
        num_train_epochs=2,
        warmup_ratio=0.03,
        report_to = "none",
        lr_scheduler_type="linear",
        max_seq_length=mseqlen,
        dataset_text_field='text',
        dataset_num_proc=multiprocessing.cpu_count()
)

trainer = SFTTrainer(
    model = model,
    train_dataset=ds_train,
    #eval_dataset=ds_test,
    processing_class=tokenizer,
    args = training_arguments
)

trainer_ = trainer.train()

```

