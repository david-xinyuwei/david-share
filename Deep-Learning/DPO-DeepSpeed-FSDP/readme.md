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

### **The Core Idea of DPO (Direct Preference Optimization)**

1. **Core Objective of DPO**

- **Goal**: To directly optimize the model using human preference data without explicitly training a reward model.

- **Introduction of Reference Model**: To prevent the model from deviating from its original language capabilities during optimization, DPO introduces a reference model (usually a copy of the initial model with fixed parameters) as a regularization term.

  

2. **Training Data**

- **Prompt**: User input, e.g., "Please explain the phase changes of water."

- **Chosen Reply**: A response evaluated by humans as high-quality and meeting expectations.

- **Rejected Reply**: A response evaluated by humans as lower quality and not meeting expectations.

  

3. **Training Process**

**Step 1:** Calculate Log Probabilities**For the current model (parameters ( \theta )):

- **Log probability of the chosen reply**:

  ```
  log_p_model_chosen = log( π_θ(chosen_reply | prompt) )  
  ```

- **Log probability of the rejected reply**:

  ```
  log_p_model_rejected = log( π_θ(rejected_reply | prompt) )  
  ```


For the reference model (parameters fixed):

- **Log probability of the chosen reply**:

  ```
  log_p_ref_chosen = log( π_ref(chosen_reply | prompt) )  
  ```

- **Log probability of the rejected reply**:

  ```
  log_p_ref_rejected = log( π_ref(rejected_reply | prompt) )  
  ```



**Step 2:** Calculate Preference Differences**

 

- **Preference difference for the chosen reply**:

  ```
  delta_chosen = log_p_model_chosen - log_p_ref_chosen  
  ```

 

- **Preference difference for the rejected reply**:

  ```
  delta_rejected = log_p_model_rejected - log_p_ref_rejected  
  ```

 

**Step 3**: Construct the Loss Function**

 

- **Loss function form**:

  ```
  L(θ) = -log( exp( delta_chosen / β ) / [ exp( delta_chosen / β ) + exp( delta_rejected / β ) ] )  
  ```

  Where ( β ) is a hyperparameter controlling the temperature.

- **Objective**: Minimize the loss function ( L(θ) ) to make the model more inclined to generate the chosen reply over the rejected reply.

  

### **Example**

Using your example:

- **Prompt**: "Please explain the phase changes of water."

- **Chosen Reply**:

  ```
  "Water exists in three states: solid, liquid, and gas. Changes in temperature cause water to transition between these states. For example, ice melts into water, and water evaporates into water vapor."  
  ```

- **Rejected Reply**:

  ```
  "Water is a liquid that is very common in nature."  
  **Steps:**
  ```

- **Calculate Log Probabilities**

  ```
  log_p_model_chosen = -5  
  log_p_model_rejected = -7  
  log_p_ref_chosen = -6  
  log_p_ref_rejected = -6  
  ```

  *Hypothetical values for illustration purposes:*

- **Calculate Preference Differences**

  ```
  delta_chosen = -5 - (-6) = 1  
  delta_rejected = -7 - (-6) = -1  
  ```

 

- **Calculate Loss Function (β = 1)**

  - **Calculate the numerator**:

    ```
    exp( delta_chosen / β ) = exp(1) ≈ 2.718  
    ```

  - **Calculate the denominator**:

    ```
    exp( delta_chosen / β ) + exp( delta_rejected / β ) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
    ```

  - **Calculate the loss**:

    ```
    L(θ) = -log( 2.718 / 3.086 ) ≈ -log(0.880) ≈ 0.127  
    ```

  The loss is small, indicating that the model already prefers the chosen reply over the rejected reply.

- **Optimize Model Parameters**

  ```
  Through backpropagation, minimize the loss \( L(θ) \) to further enhance the model's preference for the chosen reply.  
  ```

 

#### Role of the Reference Model

- **Regularization Effect**: Prevents the model from excessively deviating from the initial language model, ensuring the quality and diversity of the generated text.
- **Stabilizes the Training Process**: Provides a fixed benchmark, making the model updates smoother and avoiding gradient explosion or vanishing problems.

### **Summary**

- **DPO Training Process**: The model utilizes the prompt, chosen, rejected replies, and the reference model to directly optimize itself, making its generated replies more aligned with human preferences.
- **The Indispensable Reference Model**: It provides a regularization term in the loss function, ensuring that while the model learns human preferences, it also maintains its original language capabilities and knowledge.