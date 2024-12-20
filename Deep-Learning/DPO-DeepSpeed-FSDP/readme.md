# DPO 72B Model Fine-Tuning with DeepSpeed and FSDP

**Direct Preference Optimization (DPO)** is currently one of the popular methods for aligning large language models (LLMs) with human preferences. With parameter-efficient fine-tuning techniques like **LoRA** and **QLoRA**, we can perform DPO training on models with 8 billion parameters (such as Llama 3.1 8B and Qwen2.5 7B) on a single GPU, though the training sequences might be shorter. However, for larger models, like 72B, multiple GPUs are required. 

 

### Technical Points

For example, suppose we want to perform DPO training on a 70 billion-parameter model on a machine with 8 H100 GPUs (totaling 640 GB of VRAM). We need to consider the following points:

- **Policy Model**: The model we want to train, which occupies about 140 GB of VRAM.

- **Reference Model**: DPO requires a reference model, usually with the same architecture as the policy model, also occupying about 140 GB of VRAM.

  Thus, just the model parameters alone consume 280 GB of VRAM, approximately 43.75% of the total VRAM. In addition, there are optimizer states. For example, using the AdamW optimizer, each parameter has two additional state variables. If these state variables are stored in 16-bit precision, they will take up an extra 280 GB of VRAM. Adding it all up, we've used 560 GB of VRAM, leaving only 80 GB. This remaining VRAM is needed to store activations and gradients. Without special methods, it's unlikely to train on a single machine.

## Distributed training technology 

To address the above challenges, we could use PyTorch's **Fully Sharded Data Parallel (FSDP)** technology, combined with parameter-efficient fine-tuning methods like LoRA and QLoRA. 

**FSDP is similar to DeepSpeed's ZeRO technology.** **Accelerate** is a library from Hugging Face (HF).  FSDP is a distributed training technique that shards the model's parameters, optimizer states, and gradients, distributing them across multiple devices (such as GPUs). During the forward and backward passes, only the required parameter shards are loaded into memory and released after computation. This greatly reduces memory requirements.  Of course, when training even larger models, **DeepSpeed** can be used. DeepSpeed requires a large amount of memory to store full-precision model parameters. 

In my repo, I used both DeepSpeed ZeRO-3 technology and FSDP technology, and the training results were the same. I will showcase the scripts and configuration files for both training methods. 

 ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAcwEYpAcnqXWdicELzh4cFtibVKK8HonEFffN03MKhIluSb7lD8kxvmVA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

In the following DeepSpeed and Accelerate FSDP training, I use an adapter from HF:

```
(Multi-GPU-DPO-Training) root@h100vm:~# ls -al ./SFT_LoRA/
total 838112
drwxr-xr-x  5 root root      4096 Dec 19 06:49 .
drwx------ 48 root root      4096 Dec 19 11:24 ..
drwxr-xr-x  9 root root      4096 Dec 19 06:49 .git
-rw-r--r--  1 root root      2345 Dec 19 06:48 .gitattributes
-rw-r--r--  1 root root       264 Dec 19 06:48 README.md
-rw-r--r--  1 root root       728 Dec 19 06:48 adapter_config.json
-rw-r--r--  1 root root 842289128 Dec 19 06:49 adapter_model.safetensors
-rw-r--r--  1 root root       605 Dec 19 06:48 added_tokens.json
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-10
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-5
-rw-r--r--  1 root root   1671853 Dec 19 06:48 merges.txt
-rw-r--r--  1 root root       499 Dec 19 06:48 special_tokens_map.json
-rw-r--r--  1 root root  11421896 Dec 19 06:48 tokenizer.json
-rw-r--r--  1 root root      7306 Dec 19 06:48 tokenizer_config.json
-rw-r--r--  1 root root      5496 Dec 19 06:48 training_args.bin
-rw-r--r--  1 root root   2776833 Dec 19 06:48 vocab.json

(Multi-GPU-DPO-Training) root@h100vm:~/SFT_LoRA# cat adapter_config.json
{
  "alpha_pattern": {},
  "auto_mapping": null,
  "base_model_name_or_path": "Qwen/Qwen2.5-72B-Instruct",
  "bias": "none",
  "fan_in_fan_out": false,
  "inference_mode": true,
  "init_lora_weights": true,
  "layer_replication": null,
  "layers_pattern": null,
  "layers_to_transform": null,
  "loftq_config": {},
  "lora_alpha": 16,
  "lora_dropout": 0.05,
  "megatron_config": null,
  "megatron_core": "megatron.core",
  "modules_to_save": null,
  "peft_type": "LORA",
  "r": 16,
  "rank_pattern": {},
  "revision": null,
  "target_modules": [
    "up_proj",
    "q_proj",
    "k_proj",
    "down_proj",
    "gate_proj",
    "v_proj",
    "o_proj"
  ],
  "task_type": "CAUSAL_LM",
  "use_dora": false,
  "use_rslora": false
```



## DeepSpeed Training

Deepspeed Configuration file:

```
# cat deepspeed_config.json
{  
  "zero_optimization": {  
    "stage": 3,  
    "overlap_comm": true,  
    "contiguous_gradients": true,  
    "reduce_bucket_size": 104857600,  
    "stage3_prefetch_bucket_size": 104857600,  
    "stage3_param_persistence_threshold": 1048576  
  },  
  "bf16": {  
    "enabled": true  
  },  
  "train_micro_batch_size_per_gpu": 1,  
  "gradient_accumulation_steps": 16,  
  "steps_per_print": 10,  
  "wall_clock_breakdown": false  
}  
```

Training code:

```
#cat fsdp+QLoRA_deepspeed.py
import torch  
import os  
import multiprocessing  
from datasets import load_dataset  
from peft import PeftModel  
from transformers import (  
    AutoModelForCausalLM,  
    AutoTokenizer,  
    BitsAndBytesConfig,  
    set_seed  
)  
from trl import DPOTrainer, DPOConfig  
  
set_seed(1234)  
  
model_name = "Qwen/Qwen2.5-72B-Instruct"  
sft_adapter = "./SFT_LoRA/"  # 一个使用 SFT 微调的 LoRA 适配器  
  
compute_dtype = torch.bfloat16  
  
# 如果在使用 FlashAttention 时遇到问题，可以改用 'sdpa'  
attn_implementation = 'flash_attention_2'  
  
# 如果内存不足，可以修改以下三个训练参数  
bs = 1        # 每个设备的批大小（训练和验证）  
gas = 16      # 梯度累积步骤数  
mseqlen = 512 # 最大序列长度  
  
lr = 1e-5     # 学习率  
QLoRA = True  # 是否量化基模型  
  
output_dir = "/workspace/DPO_LoRA"  
  
# 初始化 Tokenizer  
tokenizer = AutoTokenizer.from_pretrained(model_name)  
tokenizer.pad_token = "<|image_pad|>"  
tokenizer.pad_token_id = 151655  
tokenizer.padding_side = 'right'  # 对于 Qwen2.5，左右 padding 都可以  
  
# 加载并处理数据集  
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)  
ds_train = ds['train']  
ds_test = ds['test']  
  
def process(row):  
    # 第一个消息是提示  
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)  
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token  
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token  
    row["prompt"] = prompt_messages  
    row["chosen"] = chosen_messages  
    row["rejected"] = rejected_messages  
    return row  
  
ds_train = ds_train.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
ds_test = ds_test.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
if QLoRA:  
    bnb_config = BitsAndBytesConfig(  
        load_in_4bit=True,  
        bnb_4bit_quant_type="nf4",  
        bnb_4bit_compute_dtype=compute_dtype,  
        bnb_4bit_use_double_quant=True,  
        bnb_4bit_quant_storage=compute_dtype,  
    )  
  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        quantization_config=bnb_config,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
    # 冻结基模型的参数  
    for name, param in model.named_parameters():  
        param.requires_grad = False  
  
    # 让输入嵌入支持梯度  
    def make_inputs_require_grad(module, input, output):  
        output.requires_grad_(True)  
  
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)  
else:  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': True})  
  
# 加载 LoRA 适配器  
model = PeftModel.from_pretrained(  
    model,  
    sft_adapter,  
    is_trainable=True,  
    adapter_name="DPO"  
)  
model.load_adapter(sft_adapter, adapter_name="reference")  
  
# 将模型移动到设备上  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
  
training_arguments = DPOConfig(  
    output_dir=output_dir,  
    eval_strategy="steps",  
    do_eval=True,  
    optim="adamw_torch",  
    per_device_train_batch_size=bs,  
    gradient_accumulation_steps=gas,  
    per_device_eval_batch_size=bs,  
    log_level="debug",  
    save_strategy="steps",  
    save_steps=5,  
    logging_steps=2,  
    learning_rate=lr,  
    bf16=True,  
    beta=0.1,  
    eval_steps=2,  
    max_steps=10,  
    warmup_ratio=0.1,  
    lr_scheduler_type="linear",  
    max_length=mseqlen,  
    max_prompt_length=512,  
    dataset_num_proc=multiprocessing.cpu_count(),  
    model_adapter_name="DPO",  
    ref_adapter_name="reference",  
    deepspeed="deepspeed_config.json",  # 指定 DeepSpeed 配置文件  
)  
  
trainer = DPOTrainer(  
    model=model,  
    args=training_arguments,  
    train_dataset=ds_train,  
    eval_dataset=ds_test,  
    tokenizer=tokenizer,  
)  
  
# 开始训练  
trainer.train()  
  
# 保存模型  
trainer.save_model(output_dir)  
```

Launch training 

```
(dpo) root@h1002gpu:~# deepspeed fsdp+QLoRA_deepspeed.py
```

```
{'loss': 0.6914, 'grad_norm': 3.3615094645372428, 'learning_rate': 8.888888888888888e-06, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': -536.0, 'logps/rejected': -532.0, 'logits/chosen': 0.1, 'logits/rejected': 0.0, 'epoch': 0.0}
 20%|████████████████████████████▊   
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DPO-DeepSpeed-FSDP/images/1.png)

## Accelerate FSDP training

 Configuration file:

```
(Multi-GPU-DPO-Training) root@h100vm:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 2
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
```



Training code:

```
(Multi-GPU-DPO-Training) root@h100vm:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 1
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
(Multi-GPU-DPO-Training) root@h100vm:~# cat fsdp+QLoRA.py
import torch
import os
import multiprocessing
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from peft.utils.other import fsdp_auto_wrap_policy
from accelerate import Accelerator, FullyShardedDataParallelPlugin
from trl import DPOTrainer, DPOConfig

# Set seed for reproducibility
set_seed(1234)

# Configure FSDP Plugin
fsdp_plugin = FullyShardedDataParallelPlugin(
    sharding_strategy="FULL_SHARD",
    backward_prefetch="BACKWARD_PRE",
    forward_prefetch=False,
    cpu_offload=False,
    use_orig_params=True,  # Set use_orig_params to True
    auto_wrap_policy="TRANSFORMER_BASED_WRAP",
    mixed_precision_policy={
        "param_dtype": torch.float16,
        "reduce_dtype": torch.float16,
        "buffer_dtype": torch.float16,
    },
)

# Initialize accelerator with fsdp_plugin
accelerator = Accelerator(
    mixed_precision="no",
    fsdp_plugin=fsdp_plugin,
    log_with=None,
)

# Model and training configuration
model_name = "Qwen/Qwen2.5-72B-Instruct"
sft_adapter = "./SFT_LoRA/"  # Path to your LoRA adapter fine-tuned with SFT

compute_dtype = torch.float16  # Use torch.float16 for consistency

# If you have troubles with FlashAttention, use 'standard' or 'triton' instead
attn_implementation = 'eager'

# Modify the following training arguments if you run out of memory
bs = 1  # Batch size per device
gas = 1  # Gradient accumulation steps
mseqlen = 32  # Maximum sequence length

lr = 1e-6  # Learning rate
QLoRA = True  # Quantize the base model
lora_alpha = 16
lora_dropout = 0.0
lora_r = 4

output_dir = "/workspace/DPO_LoRA"

# Tokenizer setup
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = "<|image_pad|>"
tokenizer.pad_token_id = 151655
tokenizer.padding_side = 'right'  # Adjust as needed

# Load and process the dataset
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)
ds_train = ds['train']
ds_test = ds['test']

def process(row):
    # The first message is the prompt
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token
    row["prompt"] = prompt_messages
    row["chosen"] = chosen_messages
    row["rejected"] = rejected_messages
    return row

ds_train = ds_train.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)
ds_test = ds_test.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)

# Model loading and preparation
if QLoRA:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage=compute_dtype,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
    for name, param in model.named_parameters():
        param.requires_grad = False

    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)

    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
else:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )

# Load the LoRA adapter
model = PeftModel.from_pretrained(model, sft_adapter, is_trainable=True, adapter_name="DPO")
model.load_adapter(sft_adapter, adapter_name="reference")

# Ensure all model parameters are in torch.float16
model.to(torch.float16)

# Ensure all model parameters are on the correct device
model.to(accelerator.device)

# Training arguments
training_arguments = DPOConfig(
    output_dir=output_dir,
    eval_strategy="steps",
    do_eval=True,
    optim="adamw_hf",  # Use the PyTorch fused optimizer
    per_device_train_batch_size=bs,
    gradient_accumulation_steps=gas,
    per_device_eval_batch_size=bs,
    log_level="debug",
    save_strategy="steps",
    save_steps=5,
    logging_steps=2,
    learning_rate=lr,
    bf16=True,
    fp16=False,
    beta=0.1,
    eval_steps=2,
    max_steps=10,
    warmup_ratio=0.1,
    lr_scheduler_type="linear",
    max_length=mseqlen,
    max_prompt_length=512,
    dataset_num_proc=multiprocessing.cpu_count(),
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    report_to="none",
    max_grad_norm=1.0,
)

# Initialize the DPOTrainer
trainer = DPOTrainer(
    model=model,
    args=training_arguments,
    train_dataset=ds_train,
    eval_dataset=ds_test,
    processing_class=tokenizer,
)

# Start training
```

Launch training 

```
 accelerate launch --config_file config_fsdp.yaml fsdp+QLoRA.py
```

```
***** Running training *****
  Num examples = 43,802
  Num Epochs = 1
  Instantaneous batch size per device = 1
  Total train batch size (w. parallel, distributed & accumulation) = 1
  Gradient Accumulation steps = 1
  Total optimization steps = 10
  Number of trainable parameters = 210,534,400
{'loss': 0.6931, 'grad_norm': 0.0, 'learning_rate': 8.888888888888888e-07, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': 0.0, 'logps/rejected': 0.0, 'logits/chosen': 0.1, 'logits/rejected': nan, 'epoch': 0.0}
 20%|████████████████████████████▊                                                                                                                   | 2/10 [00:07<00:26,  3.37s/it]The following columns in the evaluation set don't have a corresponding argument in `FullyShardedDataParallel.forward` and have been ignored: source, prompt, question, rejected, chosen. If source, prompt, question, rejected, chosen are not expected by `FullyShardedDataParallel.forward`,  you can safely ignore this message.

```



## Training result analyze

In DPO training, the model is provided with a set of conversations, each containing the same **"prompt"** or **"question"**, along with corresponding **"chosen"** and **"rejected"** replies. The model needs to learn to distinguish between these replies and prefer generating high-quality **"chosen"** responses.

### Training data and results

The training data includes:

- **Source**: Airoboros

- **Chosen Reply**: Contains multiple rounds of dialogue

- **Rejected Reply**: Contains multiple rounds of dialogue

- **Prompt**: A descriptive text

- **Question**: The same text as the prompt

  Sometimes in the data, the **"prompt"** and **"question"** may be identical, which can serve as the starting point for the conversation in certain training settings.

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAl6sIF5iaooXZPcDtkfNgmDaYiczO6Kb9VMHuia3KzFAkEUTrUZGTRSmYg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

  Training results are as following:

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAG0lGSUZEgnusjGQ4IIkqWJtvKJa6r42TJcKXguutu2xuuEATUibY3sg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Next, I will combine the training data to roughly introduce the DPO training process and results.

### DPO training process and results explanation


**Core Objective of DPO**

- **Objective:** Directly optimize the model parameters to reflect human preferences without the need for a separate reward model. DPO uses human preference data to adjust the model directly, making its generated responses more aligned with human expectations.

- **Introducing the Reference Model:** To prevent the model from **deviating from its original language capabilities** during optimization, DPO introduces a **reference model** (usually a copy of the initial model with fixed parameters) as a **regularization term**.

  **Role of the Reference Model:**

  - **Maintaining Language Capabilities:** The reference model provides a baseline of the model before adjustment. By comparing with the reference model, the trained model can learn human preferences while avoiding overfitting and deviation from its original abilities, ensuring that its language understanding and generation capabilities remain intact. This helps prevent the model from prioritizing human preferences at the expense of core language skills like grammatical correctness and factual accuracy.



#### Training Data

- **Prompt:** User input, for example: "Please explain the phase changes of water."

- **Chosen Reply:** Responses evaluated by humans as high-quality, fully answering the question, and meeting expectations. These replies are typically **accurate**, **complete**, **relevant**, and **fluent**, satisfying user needs.

- **Rejected Reply:** Responses evaluated by humans as lower quality, not adequately answering the question, or not meeting expectations. These replies may lack **accuracy**, contain **incomplete information**, be **irrelevant** to the prompt, or be **less fluent**.

  **Human Evaluation Criteria:**

- **Accuracy:** Is the content of the reply correct and free from misleading information?

- **Completeness:** Does the reply fully answer the user's question?

- **Relevance:** Is the reply closely related to the user's prompt?

- **Fluency:** Is the reply grammatically correct and clearly expressed?

  **Example:**

- **Prompt:** "Please explain the phase changes of water."

- **Chosen Reply:**

  ```
  Water exists in three states: solid, liquid, and gas. Through changes in temperature and pressure, water can transition between these states. For example, ice (solid) melts into water (liquid) when heated, and water vaporizes into steam (gas) upon further heating.  
  ```

  - **Evaluation Reasoning:** The reply **accurately** explains the process of water's phase changes, provides **complete** information, is **highly relevant** to the prompt, and is **fluent**.

- **Rejected Reply:**

  ```
  Water is a very common substance found everywhere in daily life.  
  ```

  - **Evaluation Reasoning:** The reply does not address the question about the phase changes of water; the information is **incomplete**, and the **relevance is insufficient**.



#### Training Process

**Step 1: Calculate Log Probabilities**

 
**For the trained model (parameters θ):**

- **Log probability of the chosen reply:**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**For the reference model (fixed parameters):**

- **Log probability of the chosen reply:**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

**Step 2: Calculate Preference Differences**

 

- **Preference difference for the chosen reply:**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **Preference difference for the rejected reply:**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

**Step 3: Construct the Loss Function**

 

- **Loss function:**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  Where **β** is the temperature hyperparameter controlling sensitivity to preference differences.

- **Objective:** Minimize the loss function **loss** to make the model more inclined to generate the "chosen" reply over the "rejected" reply.

#### Training Process Example


**Assumed Values (for Illustration):**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **Calculate Preference Differences:**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **Calculate the Loss Function (assuming β = 1):**

1. **Calculate the numerator:**

   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **Calculate the denominator:**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **Calculate the loss:**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**Result Analysis:**

- **The loss value is relatively small (approximately 0.127), indicating that the model tends to prefer the "chosen" reply.**
- **Optimize Model Parameters:**
  - Through backpropagation, minimize the loss function **loss** to further enhance the model's preference for the "chosen" reply.



#### Explanation of Training Log Fields

 
Based on the DPO training process, here's a detailed explanation of each field in the training log and their importance in evaluating training effectiveness:

**Example Training Log:**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### 1. `loss`

- **Meaning:**
  - Represents the loss value at the current training step, measuring the model's ability to distinguish between the "chosen" and "rejected" replies.
- **Importance:**
  - **Core Indicator:** The primary metric to evaluate training effectiveness.
  - **Training Goal:** Minimizing **loss** indicates successful learning toward preferring the "chosen" reply.
- **Indicator Trend:**
  - **Initial Stage:** `loss` is typically higher (around `0.6931`), indicating no preference.
  - **During Training:** Should decrease over time, showing the model is learning to prefer the "chosen" reply.

#### 2. `grad_norm`

- **Meaning:**
  - Represents the gradient norm of the model parameters, indicating the overall magnitude of parameter updates.
- **Importance:**
  - **Learning Intensity:** Reflects how much the model is adjusting its parameters.
  - **Training Stability:** Helps detect issues like vanishing or exploding gradients.
- **Indicator Trend:**
  - **Normal Range:** Should be within a reasonable range (e.g., `0.01` to `1`).
  - Abnormal Situations:
    - **Too Small:** Near zero may indicate lack of learning.
    - **Too Large:** May require gradient clipping to prevent instability.

#### 3. `learning_rate`

- **Meaning:**
  - Controls the step size in parameter updates during training.
- **Importance:**
  - **Convergence Speed and Stability:** Affects how quickly and smoothly the model learns.
- **Adjustment Strategy:**
  - **Slow Loss Decrease:** Consider increasing the learning rate.
  - **Unstable Training:** If loss fluctuates, decreasing the learning rate might help.

#### 4. `rewards/chosen` and `rewards/rejected`

- **Meaning:**
  - `rewards/chosen`: Reward value for the "chosen" reply (`Δ_chosen`).
  - `rewards/rejected`: Reward value for the "rejected" reply (`Δ_rejected`).
- **Importance:**
  - **Model Preference:** Indicates the model's inclination towards each reply.
- **Indicator Trend:**
  - **Initial Stage:** Both may be around `0.0` (no preference).
  - During Training:
    - `rewards/chosen` should increase.
    - `rewards/rejected` should decrease.

#### 5. `rewards/accuracies`

- **Meaning:**
  - The proportion of times the model correctly prefers the "chosen" reply.
- **Importance:**
  - **Performance Measure:** Directly evaluates preference learning.
- **Indicator Trend:**
  - **Initial Stage:** Around `0.5` (random guess).
  - **During Training:** Should approach `1.0`, indicating improved preference accuracy.

#### 6. `rewards/margins`

- **Meaning:**

  - The difference between `rewards/chosen` and `rewards/rejected`.

  ```
  rewards/margins = rewards/chosen - rewards/rejected  
  ```

- **Importance:**
  - **Discrimination Ability:** Larger margins indicate better distinction between replies.
- **Indicator Trend:**
  - Should increase during training.

#### 7. `logps/chosen` and `logps/rejected`

- **Meaning:**
  - Total log probabilities of generating the "chosen" and "rejected" replies.
- **Importance:**
  - **Probability Basis:** Used in calculating preference differences and rewards.
- **Indicator Trend:**
  - **Increasing `logps/chosen`** indicates higher probability for the "chosen" reply.
  - **Stable or decreasing `logps/rejected`** shows reduced preference for the "rejected" reply.

#### 8. `logits/chosen` and `logits/rejected`

- **Meaning:**
  - Raw output scores from the final layer before applying softmax, for both replies.
- **Importance:**
  - **Probability Calculation:** Used to compute probabilities for each token, affecting log probabilities.
- **Indicator Trend:**
  - **Ensure Valid Values:** Avoid `nan` or `inf` values.
  - **Monitor Changes:** Changes in logits reflect learning progress.

#### 9. `epoch`

- **Meaning:**
  - Indicates the current training epoch or iteration over the training dataset.
- **Importance:**
  - **Training Progress:** Helps track how far along the training is.
- **Indicator Trend:**
  - As `epoch` increases, expect improvements in other metrics.

#### Summary 

- **Adjust Training Strategies Based on Indicators:**

  - **Slow Loss Decrease:** Increase learning rate or check data quality.
  - **Gradient Issues:** If `grad_norm` is abnormal, inspect gradient computations or adjust optimizer settings.
  - **Low Preference Accuracy:** Enhance data quality or quantity.
  - **Small Reward Margins:** Adjust the temperature parameter β to influence sensitivity.

- **Emphasize the Importance of the Reference Model:**

  - **Maintaining Language Capabilities:** Ensures the model doesn't overfit human preferences at the cost of language understanding and generation skills.
  - **Balancing Objectives:** Optimizes for human preference while retaining overall model performance.

- **Continuous Monitoring and Adjustment:**

  - **Regular Evaluation:** Use a validation set to assess performance and prevent overfitting.

  - **Dynamic Adjustment:** Modify training strategies based on log indicators to optimize the model.

    By understanding DPO's core concepts, training processes, and how to interpret key training metrics, you can effectively train a model that aligns with human preferences while maintaining strong language capabilities.



### DPO training process and results explanation in Chinese

- **目标：** 直接优化模型参数来反映人类偏好，而无需通过单独的奖励模型。DPO 利用人类偏好数据直接调整模型，使其生成的回复更符合人类期望。

- **引入参考模型：** 为了防止模型在优化过程中**偏离其原有的语言能力**，DPO 引入了一个**参考模型**（通常是初始模型的副本，参数固定）作为**正则化项**。

  **参考模型的作用：**

  - **保持语言能力：** 参考模型提供了模型在未调整前的基线。通过与参考模型的对比，被训练模型在学习人类偏好的同时，避免过度拟合和偏离原有能力，确保自身的语言理解和生成能力不受损。这有助于防止模型为追求符合人类偏好而忽视语言能力，例如语法正确性、知识准确性等。

**训练数据**

- **提示（Prompt）：** 用户输入，例如：“请解释水的物态变化。”

- **选择回复（Chosen Reply）：** 被人类评估为高质量、完整回答了问题且符合预期的回复。这些回复通常**准确**、**完整**、**相关**，并且语言**流畅**，满足用户需求。

- **拒绝回复（Rejected Reply）：** 被人类评估为质量较低、未充分回答问题或不符合预期的回复。这些回复可能**准确性不足**、**信息不完整**、**与提示不相关**，或语句**不流畅**。

  

  **人类评估的标准：**

- **准确性（Accuracy）：** 回复内容是否正确、无误导性。

- **完整性（Completeness）：** 回复是否全面地回答了用户的问题。

- **相关性（Relevance）：** 回复是否与用户的提示紧密相关。

- **语言流畅度（Fluency）：** 回复是否语言通顺、表达清晰。

  

  **示例：**

- **提示：**“请解释水的物态变化。”

- **选择回复：**

  ```
  水有三种物态：固态、液态和气态。通过温度和压力的变化，水可以在这三种物态之间转换。例如，冰（固态）受热会融化成水（液态），水加热会变成水蒸气（气态）。  
  ```

  - **评估理由：** 回复**准确**地解释了水的物态变化过程，信息**完整**，与提示**高度相关**，语言**流畅**。

- **拒绝回复：**

  ```
  水是一种非常常见的物质，生活中到处都有。  
  ```

  - **评估理由：** 回复没有针对提示回答物态变化的问题，信息**不完整**，**相关性不足**。



#### **训练过程**

#### **步骤 1：计算对数概率**

 
**对于被训练模型（参数为 θ）：**

- **选择回复的对数概率：**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **拒绝回复的对数概率：**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**对于参考模型（参数固定）：**

- **选择回复的对数概率：**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **拒绝回复的对数概率：**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

#### **步骤 2：计算偏好差值**

 

- **选择回复的偏好差值：**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **拒绝回复的偏好差值：**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

#### **步骤 3：构建损失函数**

 

- **损失函数形式：**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  其中，**β** 是温度超参数，控制对偏好差异的敏感程度。

- **目标：** 最小化损失函数 **loss**，使模型更倾向于生成“选择”回复而非“拒绝”回复。



### **训练过程示例**

 
**假设值（用于说明）：**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **计算偏好差值：**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **计算损失函数（假设 β = 1）：**

1. **计算分子：**

   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **计算分母：**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **计算损失：**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**结果分析：**

- **损失值较小（约 0.127），表明模型倾向于偏好“选择”回复。**
- **优化模型参数：**
  - 通过反向传播，最小化损失函数 **loss**，进一步增强模型对“选择”回复的偏好。 

### **训练日志字段解释**

 
结合上述 DPO 训练过程，以下是训练日志中每个字段的详细解释，以及它们在评估训练效果时的重要性。我们还将通过实际训练中的示例，说明这些指标的变化趋势。

**训练日志示例：**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### **1. `loss`**

- **含义：**
  - **损失值**，衡量模型在当前训练步骤中对“选择”回复和“拒绝”回复的区分能力。
- **重要性：**
  - **核心指标：** 评估模型训练效果的主要依据。
  - **训练目标：** 最小化 **loss**，表示模型更成功地偏好“选择”回复。
- **指标变化趋势：**
  - **初始阶段：** `loss` 值通常较高，例如约 `0.6931`，对应于模型对两种回复没有偏好。
  - **训练过程中：** 随着训练进行，`loss` 应该逐渐降低，表明模型正在学习更偏好“选择”回复。

#### **2. `grad_norm`**

- **含义：**
  - **梯度范数**，表示模型参数更新的总体变化量。
- **重要性：**
  - **学习力度：** 反映模型在当前训练步骤中的学习强度。
  - **训练稳定性：** 监控梯度大小，防止梯度消失或爆炸。
- **指标变化趋势：**
  - **正常范围：** `grad_norm` 应保持在适当范围内，例如 `0.01` 到 `1`。
  - **异常情况：**
    - **过小（接近 0）：** 可能表示模型未在学习。
    - **过大：** 需要考虑梯度裁剪，防止梯度爆炸。

#### **3. `learning_rate`**

- **含义：**
  - **学习率**，控制模型参数更新步长的大小。
- **重要性：**
  - **收敛速度和稳定性：** 决定模型的学习速度和训练的稳定性。
- **指标调整策略：**
  - **根据训练效果：** 如果 `loss` 下降缓慢，可以适当增大学习率；如果损失震荡或增大，可能需要减小学习率。
- **示例：**
  - **初始学习率：** 常见设置为 `1e-5`。
  - **调整策略：** 根据训练效果，动态调整学习率。

#### **4. `rewards/chosen` 和 `rewards/rejected`**

- **含义：**
  - `rewards/chosen`：模型对“选择”回复的奖励值，即偏好差值 `Δ_chosen`。
  - `rewards/rejected`：模型对“拒绝”回复的奖励值，即偏好差值 `Δ_rejected`。
- **重要性：**
  - **模型倾向性：** 反映模型对两种回复的倾向程度。
- **指标变化趋势：**
  - **初始阶段：** 两者可能接近 `0.0`，表示无明显偏好。
  - **训练过程中：**
    - **`rewards/chosen` 应逐渐增大**，表示模型对“选择”回复的倾向增强。
    - **`rewards/rejected` 应逐渐减小**，表示模型对“拒绝”回复的倾向减弱。

#### **5. `rewards/accuracies`**

 **含义：**

- - **偏好准确率**，模型正确偏好“选择”回复的比例。
- **重要性：**
  - **性能衡量：** 直接评估模型是否成功地偏好高质量回复。
- **指标变化趋势：**
  - **初始阶段：** 可能接近 `0.5`，相当于随机选择。
  - **训练过程中：** 应逐渐提升，朝 `1.0` 逼近，表示模型越来越多地正确偏好“选择”回复。

#### **6. `rewards/margins`**

- **含义：**

  - **奖励差距**，即 `rewards/chosen` 和 `rewards/rejected` 之间的差值。

  - **计算公式：**

    ```
    rewards/margins = rewards/chosen - rewards/rejected  
    ```

- **重要性：**
  - **区分能力：** 差距越大，模型对两种回复的区分度越高。
- **指标变化趋势：**
  - **初始阶段：** 可能接近 `0.0`。
  - **训练过程中：** 应逐渐增大，表示模型更好地区分并偏好“选择”回复。

#### **7. `logps/chosen` 和 `logps/rejected`**

- **含义：**
  - `logps/chosen`：模型生成“选择”回复的总对数概率。
  - `logps/rejected`：模型生成“拒绝”回复的总对数概率。
- **重要性：**
  - **概率基础：** 用于计算偏好差值和奖励值。
- **指标变化趋势：**
  - **训练过程中：**
    - **`logps/chosen` 应逐渐增大（数值趋向于 0）**，表示模型对“选择”回复的生成概率增加。
    - **`logps/rejected` 可能保持不变或减小**，表示对“拒绝”回复的生成概率降低。

#### **8. `logits/chosen` 和 `logits/rejected`**

- **含义：**
  - **原始输出得分**，模型在最后一层对两种回复的未归一化得分（一般是一个向量）。
- **重要性：**
  - **概率计算：** `logits` 用于计算每个词元的概率分布，进而计算对数概率。
- **指标变化趋势：**
  - **数值正常：** 确保 `logits` 的数值没有异常（如 `nan` 或 `inf`）。

#### **9. `epoch`**

- **含义：**
  - **训练轮次**，模型遍历整个训练数据的次数。
- **重要性：**
  - **训练进度：** 了解模型当前所处的训练阶段。
- **指标变化趋势：**
  - **随着 `epoch` 增加：** 应该看到模型各项性能指标的提升。



### **总结**

- **根据指标调整训练策略：**
  - **损失下降缓慢：** 可以适当增大学习率或检查数据质量。
  - **梯度异常：** 如果 `grad_norm` 异常，检查梯度计算或调整优化器参数。
  - **偏好准确率低：** 增加训练数据量或改进数据质量。
  - **奖励差距小：** 调整温度参数 β，影响模型对偏好差异的敏感程度。
- **强调参考模型的重要性：**
  - **保持语言能力：** 参考模型确保被训练模型不会过度偏向人类偏好而丧失原有的知识和语言表达能力。
  - **平衡优化目标：** 在优化人类偏好的同时，保持模型的整体性能。
- **持续监控与调整：**
  - **定期评估：** 使用验证集评估模型性能，防止过拟合。
  - **动态调整：** 根据训练日志中的指标，适时调整训练策略以优化模型。