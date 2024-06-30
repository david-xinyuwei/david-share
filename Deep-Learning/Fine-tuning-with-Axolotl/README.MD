# Fine tuning with Axolotl

**Notice:**

- After FT Axolotl， suggest inference with vLLM
- Pay attention to version compatibility of Linux kernel, CUDA, torch, deepspeed(if you use).



## Axolotl
Axolotl is a tool designed to streamline the fine-tuning of various AI models, offering support for multiple configurations and architectures.
You should install Axolotl and related library according to the following link:

*https://github.com/OpenAccess-AI-Collective/axolotl*

Features:

- Train various Huggingface models such as llama, pythia, falcon, mpt
- Supports fullfinetune, lora, qlora, relora, and gptq
- Customize configurations using a simple yaml file or CLI overwrite
- Load different dataset formats, use custom formats, or bring your own tokenized datasets
- Integrated with xformer, flash attention, rope scaling, and multipacking
- Works with single GPU or multiple GPUs via FSDP or Deepspeed
- Easily run with Docker locally or on the cloud
- Log results and optionally checkpoints to wandb or mlflow

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/modelsupport.png)

Before to use axolotl run fine tuning, we need set accelerate.

```
(axolotl) root@h100vm:~/axolotl-test# accelerate config
In which compute environment are you running?
This machine

Which type of machine are you using?
No distributed training

Do you want to run your training on CPU only (even if a GPU / Apple Silicon / Ascend NPU device is available)? [yes/NO]:

Do you wish to optimize your script with torch dynamo?[yes/NO]:yes

Which dynamo backend would you like to use?
cudagraphs

Do you want to customize the defaults sent to torch.compile? [yes/NO]:

Do you want to use DeepSpeed? [yes/NO]: yes

Do you want to specify a json file to a DeepSpeed config? [yes/NO]: no
What should be your DeepSpeed's ZeRO optimization stage?
2
Where to offload optimizer states?
cpu
Where to offload parameters?
cpu

How many gradient accumulation steps you're passing in your script? [1]: 0

Do you want to use gradient clipping? [yes/NO]: no

Do you want to enable `deepspeed.zero.Init` when using ZeRO Stage-3 for constructing massive models? [yes/NO]: yes

Do you want to enable Mixture-of-Experts training (MoE)? [yes/NO]: no

How many GPU(s) should be used for distributed training? [1]:1
Do you wish to use FP16 or BF16 (mixed precision)?
fp16
accelerate configuration saved at /root/.cache/huggingface/accelerate/default_config.yaml
```
All setting is saved in /root/.cache/huggingface/accelerate/default_config.yaml, we could change it as need: 
*/root/.cache/huggingface/accelerate/default_config.yaml*

## Config training profile
Create yaml file on Azure GPU VM:

(axolotl-test) root@h100vm:~/axolotl-test# cat 1.yaml
```
base_model: microsoft/Phi-3-mini-128k-instruct
trust_remote_code: true
lora_modules_to_save:
  - embed_tokens
  - lm_head
deepspeed_config:
  zero_optimization:
    stage: 2  # Set the appropriate stage (1, 2, or 3)
    offload_optimizer: true
    offload_param: true
  zero3_init_flag: false  
gradient_accumulation_steps: auto
bnb_config_kwargs:
  llm_int8_has_fp16_weight: false
  bnb_4bit_quant_type: nf4
  bnb_4bit_use_double_quant: true

load_in_4bit: true

strict: false

datasets:
  - path:  UltraChat-200k-ShareGPT-clean
    split: train
    type: sharegpt
    conversation: chatml
chat_template: chatml
output_dir: ./ultrachat-200k-sharegpt

adapter: qlora

sequence_len: 512

sample_packing: false
eval_sample_packing: false

pad_to_sequence_len: true

lora_r: 16
lora_alpha: 16
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj
  - gate_proj
  - down_proj
  - up_proj

#lora_target_linear: true

gradient_accumulation_steps: 4
micro_batch_size: 8
optimizer: paged_adamw_8bit
lr_scheduler: linear
learning_rate: 0.0001

test_datasets:
  - path: PhilipMay/UltraChat-200k-ShareGPT-clean
    split: test
    type: sharegpt
    conversation: chatml

bf16: auto

gradient_checkpointing: true
gradient_checkpointing_kwargs:
   use_reentrant: true

flash_attention: true

warmup_ratio: 0.1
num_epochs: 4
logging_steps: 10
eval_steps: 100
saves_per_epoch: 1
weight_decay: 0.0

#The special token used for padding Llama 3
special_tokens:
  pad_token: <|eot_id|>
```
### Training result
Lanuch training:
```
(axolotl-test2) root@h100vm:~/axolotl-test# accelerate launch -m axolotl.cli.train 1.yaml
[2024-06-30 08:58:01,632] [INFO] [comm.py:668:init_distributed] Initializing TorchBackend in DeepSpeed with backend nccl
                                 dP            dP   dP
                                 88            88   88
      .d8888b. dP.  .dP .d8888b. 88 .d8888b. d8888P 88
      88'  `88  `8bd8'  88'  `88 88 88'  `88   88   88
      88.  .88  .d88b.  88.  .88 88 88.  .88   88   88
      `88888P8 dP'  `dP `88888P' dP `88888P'   dP   dP
```      
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/trainingsteps.png)

Resource during training:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/traininggpu.png)


Check the trained models:
```
root@h100vm:~/axolotl-test/ultrachat-200k-sharegpt# ls
adapter_config.json  added_tokens.json  checkpoint-220  checkpoint-440  config.json  special_tokens_map.json  tokenizer.json  tokenizer.model  tokenizer_config.json
root@h100vm:~/axolotl-test/ultrachat-200k-sharegpt#
```
### Inference with Fine-Tuned model
TODO!!!
