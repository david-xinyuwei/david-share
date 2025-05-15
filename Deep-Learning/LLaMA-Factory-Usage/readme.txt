# LLaMA-Factory的使用

### LLaMA-Factory的功能



| 维度                                 | LLaMA-Factory (基于HF Trainer)                               | DeepSpeed/Megatron-LM 原生脚本                 |
| ------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------- |
| ZeRO (1/2/3) 数据并行优化技术        | ✔ 支持                                                       | ✔ 支持                                         |
| ZeRO-Infinity (NVMe/CPU Offload)     | ◑ 支持(理论√,实际经验少）                                    | ✔ 较成熟、有实践案例                           |
| Pipeline Parallel(PP) 流水线并行     | ✘                                                            | ✔ 深度原生集成                                 |
| Tensor Parallel(TP) 张量并行         | ✘                                                            | ✔ 深度原生集成                                 |
| Mixture-of-Experts(MoE) 专家混合架构 | ✘                                                            | ✔ 深度原生支持                                 |
| 自动化启动器与多机配置(hostfile等)   | ◑ 需外部torchrun / DS启动手动配置                            | ✔ 原生launcher可自动优化                       |
| 容错与断点续训                       | ◑ 基于HF简单checkpoint，容错有限                             | ✔ Elastic性强，容错完善                        |
| 深度调优(prefix阶段重算、自定义通信) | ◑ 深度底层调参需改源码                                       | ✔ 充分暴露，深度可定制                         |
| 易用性与初学者友好                   | ✔✔ 一键CLI启动优化                                           | ✘ 手写脚本门槛相对较高                         |
| 支持Prompt模板(SFT,DPO,RLHF内置)     | ✔✔ 内置20+常见Prompt模板                                     | ✘ 一般需自行实现prompt模板                     |
| 多种微调方法(SFT,DPO,PPO,ORPO一键式) | ✔✔ stage配置切换即可                                         | ◑ 需重写或修改training loop                    |
| UI/Web界面友好                       | ✔✔ Web UI与CLI双支持                                         | ✘ 命令行与脚本为主                             |
| wandb/TensorBoard 观测工具无缝支持   | ✔✔ 默认支持                                                  | ◑ 需额外插件或自定义                           |
| PEFT (LoRA/QLoRA 等) 开箱即用        | ✔✔ 内置 LoRA/QLoRA示例                                       | ◑ 通常需手写整合喊call微调库(e.g. PEFT)        |
| vLLM推理快速评测工具内置             | ✔✔ 现成scripts/vLLM_infer.py可用                             | ✘ 推理评测脚本需要自行整合                     |
| 模型生态兼容                         | ✔✔ 官方测试了上百种热门中文/英文Base模型                     | ◑ 需手动适配特定模型和tokenizer格式            |
| 推荐使用场景                         | 小至中规模（≤32 GPU）LoRA/QLoRA快速微调、学生/探索者、高效原型 | 百卡级大规模连续预训练、企业生产上线、复杂并行 |

### 安装LLaMA-Factory的方法

```
mkdir /content/
cd /content/
rm -rf LLaMA-Factory
git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e .[torch,bitsandbytes]
```



```
cd /content/LLaMA-Factory/
sed -i 's/{{name}}/Llama-3/g' data/identity.json
sed -i 's/{{author}}/LLaMA Factory/g' data/identity.json
```



```
cat train_llama3.json
{
  "stage": "sft",
  "do_train": true,
  "model_name_or_path": "unsloth/llama-3-8b-Instruct-bnb-4bit",
  "dataset": "identity,alpaca_en_demo",
  "template": "llama3",
  "finetuning_type": "lora",
  "lora_target": "all",
  "output_dir": "llama3_lora",
  "per_device_train_batch_size": 2,
  "gradient_accumulation_steps": 4,
  "lr_scheduler_type": "cosine",
  "logging_steps": 5,
  "warmup_ratio": 0.1,
  "save_steps": 1000,
  "learning_rate": 5e-05,
  "num_train_epochs": 3.0,
  "max_samples": 500,
  "max_grad_norm": 1.0,
  "loraplus_lr_ratio": 16.0,
  "fp16": true,
  "report_to": "none"
}
```

开始训练

```
(llamafactory) root@h100vm:/content/LLaMA-Factory# llamafactory-cli train train_llama3.json
```

训练日志：

```

[INFO|2025-05-15 07:22:21] llamafactory.hparams.parser:401 >> Process rank: 0, world size: 1, device: cuda:0, distributed training: False, compute dtype: torch.float16
tokenizer_config.json: 100%|██████████████████████████████████████████████████████████████████████████████████████████| 51.1k/51.1k [00:00<00:00, 60.6MB/s]
tokenizer.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████| 9.09M/9.09M [00:00<00:00, 9.47MB/s]
special_tokens_map.json: 100%|████████████████████████████████████████████████████████████████████████████████████████████| 345/345 [00:00<00:00, 3.78MB/s]
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file tokenizer.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/tokenizer.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file tokenizer.model from cache at None
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file added_tokens.json from cache at None
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file special_tokens_map.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/special_tokens_map.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file tokenizer_config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/tokenizer_config.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:24,875 >> loading file chat_template.jinja from cache at None
[INFO|tokenization_utils_base.py:2323] 2025-05-15 07:22:25,140 >> Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained.
config.json: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████| 1.26k/1.26k [00:00<00:00, 14.1MB/s]
[INFO|configuration_utils.py:693] 2025-05-15 07:22:26,252 >> loading configuration file config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/config.json
[INFO|configuration_utils.py:765] 2025-05-15 07:22:26,253 >> Model config LlamaConfig {
  "architectures": [
    "LlamaForCausalLM"
  ],
  "attention_bias": false,
  "attention_dropout": 0.0,
  "bos_token_id": 128000,
  "eos_token_id": 128009,
  "head_dim": 128,
  "hidden_act": "silu",
  "hidden_size": 4096,
  "initializer_range": 0.02,
  "intermediate_size": 14336,
  "max_position_embeddings": 8192,
  "mlp_bias": false,
  "model_type": "llama",
  "num_attention_heads": 32,
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "pad_token_id": 128255,
  "pretraining_tp": 1,
  "quantization_config": {
    "_load_in_4bit": true,
    "_load_in_8bit": false,
    "bnb_4bit_compute_dtype": "bfloat16",
    "bnb_4bit_quant_storage": "uint8",
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_use_double_quant": true,
    "llm_int8_enable_fp32_cpu_offload": false,
    "llm_int8_has_fp16_weight": false,
    "llm_int8_skip_modules": null,
    "llm_int8_threshold": 6.0,
    "load_in_4bit": true,
    "load_in_8bit": false,
    "quant_method": "bitsandbytes"
  },
  "rms_norm_eps": 1e-05,
  "rope_scaling": null,
  "rope_theta": 500000.0,
  "tie_word_embeddings": false,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.51.3",
  "unsloth_version": "2024.9",
  "use_cache": true,
  "vocab_size": 128256
}

[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file tokenizer.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/tokenizer.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file tokenizer.model from cache at None
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file added_tokens.json from cache at None
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file special_tokens_map.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/special_tokens_map.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file tokenizer_config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/tokenizer_config.json
[INFO|tokenization_utils_base.py:2060] 2025-05-15 07:22:26,470 >> loading file chat_template.jinja from cache at None
[INFO|tokenization_utils_base.py:2323] 2025-05-15 07:22:26,719 >> Special tokens have been added in the vocabulary, make sure the associated word embeddings are fine-tuned or trained.
[INFO|2025-05-15 07:22:26] llamafactory.data.template:143 >> Add <|eom_id|> to stop words.
[WARNING|2025-05-15 07:22:26] llamafactory.data.template:148 >> New tokens have been added, make sure `resize_vocab` is True.
[INFO|2025-05-15 07:22:26] llamafactory.data.loader:143 >> Loading dataset identity.json...
Generating train split: 91 examples [00:00, 16289.60 examples/s]
Converting format of dataset: 100%|██████████████████████████████████████████████████████████████████████████████| 91/91 [00:00<00:00, 16649.87 examples/s]
[INFO|2025-05-15 07:22:27] llamafactory.data.loader:143 >> Loading dataset alpaca_en_demo.json...
Generating train split: 1000 examples [00:00, 115285.14 examples/s]
Converting format of dataset: 100%|████████████████████████████████████████████████████████████████████████████| 500/500 [00:00<00:00, 29695.03 examples/s]
Running tokenizer on dataset: 100%|█████████████████████████████████████████████████████████████████████████████| 591/591 [00:00<00:00, 3165.15 examples/s]
training example:
input_ids:
[128000, 128006, 882, 128007, 271, 6151, 128009, 128006, 78191, 128007, 271, 9906, 0, 358, 1097, 445, 81101, 12, 18, 11, 459, 15592, 18328, 8040, 555, 445, 8921, 4940, 17367, 13, 2650, 649, 358, 7945, 499, 3432, 30, 128009]
inputs:
<|begin_of_text|><|start_header_id|>user<|end_header_id|>

hi<|eot_id|><|start_header_id|>assistant<|end_header_id|>

Hello! I am Llama-3, an AI assistant developed by LLaMA Factory. How can I assist you today?<|eot_id|>
label_ids:
[-100, -100, -100, -100, -100, -100, -100, -100, -100, -100, -100, 9906, 0, 358, 1097, 445, 81101, 12, 18, 11, 459, 15592, 18328, 8040, 555, 445, 8921, 4940, 17367, 13, 2650, 649, 358, 7945, 499, 3432, 30, 128009]
labels:
Hello! I am Llama-3, an AI assistant developed by LLaMA Factory. How can I assist you today?<|eot_id|>
[INFO|configuration_utils.py:693] 2025-05-15 07:22:28,237 >> loading configuration file config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/config.json
[INFO|configuration_utils.py:765] 2025-05-15 07:22:28,237 >> Model config LlamaConfig {
  "architectures": [
    "LlamaForCausalLM"
  ],
  "attention_bias": false,
  "attention_dropout": 0.0,
  "bos_token_id": 128000,
  "eos_token_id": 128009,
  "head_dim": 128,
  "hidden_act": "silu",
  "hidden_size": 4096,
  "initializer_range": 0.02,
  "intermediate_size": 14336,
  "max_position_embeddings": 8192,
  "mlp_bias": false,
  "model_type": "llama",
  "num_attention_heads": 32,
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "pad_token_id": 128255,
  "pretraining_tp": 1,
  "quantization_config": {
    "_load_in_4bit": true,
    "_load_in_8bit": false,
    "bnb_4bit_compute_dtype": "bfloat16",
    "bnb_4bit_quant_storage": "uint8",
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_use_double_quant": true,
    "llm_int8_enable_fp32_cpu_offload": false,
    "llm_int8_has_fp16_weight": false,
    "llm_int8_skip_modules": null,
    "llm_int8_threshold": 6.0,
    "load_in_4bit": true,
    "load_in_8bit": false,
    "quant_method": "bitsandbytes"
  },
  "rms_norm_eps": 1e-05,
  "rope_scaling": null,
  "rope_theta": 500000.0,
  "tie_word_embeddings": false,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.51.3",
  "unsloth_version": "2024.9",
  "use_cache": true,
  "vocab_size": 128256
}

[INFO|2025-05-15 07:22:28] llamafactory.model.model_utils.quantization:143 >> Loading ?-bit BITSANDBYTES-quantized model.
[INFO|2025-05-15 07:22:28] llamafactory.model.model_utils.kv_cache:143 >> KV cache is disabled during training.
[INFO|quantization_config.py:436] 2025-05-15 07:22:28,477 >> Unused kwargs: ['_load_in_4bit', '_load_in_8bit', 'quant_method']. These kwargs are not used in <class 'transformers.utils.quantization_config.BitsAndBytesConfig'>.
Xet Storage is enabled for this repo, but the 'hf_xet' package is not installed. Falling back to regular HTTP download. For better performance, install the package with: `pip install huggingface_hub[hf_xet]` or `pip install hf_xet`
model.safetensors: 100%|██████████████████████████████████████████████████████████████████████████████████████████████| 5.70G/5.70G [03:42<00:00, 25.6MB/s]
[INFO|modeling_utils.py:1124] 2025-05-15 07:26:15,360 >> loading weights file model.safetensors from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/model.safetensors
[INFO|modeling_utils.py:2167] 2025-05-15 07:26:15,361 >> Instantiating LlamaForCausalLM model under default dtype torch.float16.
[INFO|configuration_utils.py:1142] 2025-05-15 07:26:15,362 >> Generate config GenerationConfig {
  "bos_token_id": 128000,
  "eos_token_id": 128009,
  "pad_token_id": 128255,
  "use_cache": false
}

[INFO|modeling_utils.py:4930] 2025-05-15 07:26:18,224 >> All model checkpoint weights were used when initializing LlamaForCausalLM.

[INFO|modeling_utils.py:4938] 2025-05-15 07:26:18,224 >> All the weights of LlamaForCausalLM were initialized from the model checkpoint at unsloth/llama-3-8b-Instruct-bnb-4bit.
If your task is similar to the task the model of the checkpoint was trained on, you can already use LlamaForCausalLM for predictions without further training.
generation_config.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████| 220/220 [00:00<00:00, 2.82MB/s]
[INFO|configuration_utils.py:1097] 2025-05-15 07:26:18,654 >> loading configuration file generation_config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/generation_config.json
[INFO|configuration_utils.py:1142] 2025-05-15 07:26:18,654 >> Generate config GenerationConfig {
  "bos_token_id": 128000,
  "do_sample": true,
  "eos_token_id": [
    128001,
    128009
  ],
  "max_length": 8192,
  "pad_token_id": 128255,
  "temperature": 0.6,
  "top_p": 0.9
}

[INFO|2025-05-15 07:26:18] llamafactory.model.model_utils.checkpointing:143 >> Gradient checkpointing enabled.
[INFO|2025-05-15 07:26:18] llamafactory.model.model_utils.attention:143 >> Using torch SDPA for faster training and inference.
[INFO|2025-05-15 07:26:18] llamafactory.model.adapter:143 >> Upcasting trainable params to float32.
[INFO|2025-05-15 07:26:18] llamafactory.model.adapter:143 >> Fine-tuning method: LoRA
[INFO|2025-05-15 07:26:18] llamafactory.model.model_utils.misc:143 >> Found linear modules: o_proj,down_proj,up_proj,v_proj,q_proj,gate_proj,k_proj
[INFO|2025-05-15 07:26:19] llamafactory.model.loader:143 >> trainable params: 20,971,520 || all params: 8,051,232,768 || trainable%: 0.2605
[INFO|trainer.py:748] 2025-05-15 07:26:19,095 >> Using auto half precision backend
[INFO|2025-05-15 07:26:19] llamafactory.train.trainer_utils:143 >> Using LoRA+ optimizer with loraplus lr ratio 16.00.
[INFO|trainer.py:2414] 2025-05-15 07:26:19,308 >> ***** Running training *****
[INFO|trainer.py:2415] 2025-05-15 07:26:19,308 >>   Num examples = 591
[INFO|trainer.py:2416] 2025-05-15 07:26:19,308 >>   Num Epochs = 3
[INFO|trainer.py:2417] 2025-05-15 07:26:19,308 >>   Instantaneous batch size per device = 2
[INFO|trainer.py:2420] 2025-05-15 07:26:19,308 >>   Total train batch size (w. parallel, distributed & accumulation) = 8
[INFO|trainer.py:2421] 2025-05-15 07:26:19,308 >>   Gradient Accumulation steps = 4
[INFO|trainer.py:2422] 2025-05-15 07:26:19,308 >>   Total optimization steps = 222
[INFO|trainer.py:2423] 2025-05-15 07:26:19,311 >>   Number of trainable parameters = 20,971,520
{'loss': 1.266, 'grad_norm': 0.8577702641487122, 'learning_rate': 8.695652173913044e-06, 'epoch': 0.07}                                                    
{'loss': 1.2327, 'grad_norm': 0.44337940216064453, 'learning_rate': 1.956521739130435e-05, 'epoch': 0.14}                                                  
{'loss': 1.207, 'grad_norm': 0.6676920652389526, 'learning_rate': 3.0434782608695656e-05, 'epoch': 0.2}                                                    
{'loss': 1.2355, 'grad_norm': 1.0849775075912476, 'learning_rate': 4.130434782608696e-05, 'epoch': 0.27}                                                   
{'loss': 0.9941, 'grad_norm': 0.6350672245025635, 'learning_rate': 4.999688473794144e-05, 'epoch': 0.34}                                                   
{'loss': 1.0698, 'grad_norm': 0.7085476517677307, 'learning_rate': 4.9887932065027656e-05, 'epoch': 0.41}                                                  
{'loss': 1.1396, 'grad_norm': 0.802344560623169, 'learning_rate': 4.962399180850277e-05, 'epoch': 0.47}                                                    
{'loss': 1.0549, 'grad_norm': 0.5175556540489197, 'learning_rate': 4.920670763496268e-05, 'epoch': 0.54}                                                   
{'loss': 0.9872, 'grad_norm': 0.4580995440483093, 'learning_rate': 4.863867814784168e-05, 'epoch': 0.61}                                                   
{'loss': 1.0754, 'grad_norm': 1.2809611558914185, 'learning_rate': 4.792344070481972e-05, 'epoch': 0.68}                                                   
{'loss': 1.0266, 'grad_norm': 0.8734893202781677, 'learning_rate': 4.706544938921368e-05, 'epoch': 0.74}                                                   
{'loss': 1.0538, 'grad_norm': 0.7838897109031677, 'learning_rate': 4.6070047272533765e-05, 'epoch': 0.81}                                                  
{'loss': 1.1168, 'grad_norm': 0.5366086363792419, 'learning_rate': 4.4943433140937986e-05, 'epoch': 0.88}                                                  
{'loss': 1.0687, 'grad_norm': 0.7647867798805237, 'learning_rate': 4.369262289279273e-05, 'epoch': 0.95}                                                   
{'loss': 0.9302, 'grad_norm': 1.7908470630645752, 'learning_rate': 4.2325405847733294e-05, 'epoch': 1.01}                                                  
{'loss': 0.7998, 'grad_norm': 1.6611608266830444, 'learning_rate': 4.085029623930597e-05, 'epoch': 1.08}                                                   
{'loss': 0.6749, 'grad_norm': 0.9149978160858154, 'learning_rate': 3.927648019326737e-05, 'epoch': 1.15}                                                   
{'loss': 0.7292, 'grad_norm': 0.6326663494110107, 'learning_rate': 3.7613758521729436e-05, 'epoch': 1.22}                                                  
{'loss': 0.6618, 'grad_norm': 0.4195830523967743, 'learning_rate': 3.587248568939483e-05, 'epoch': 1.28}                                                   
{'loss': 0.7913, 'grad_norm': 0.6591249704360962, 'learning_rate': 3.406350533196562e-05, 'epoch': 1.35}                                                   
{'loss': 0.7461, 'grad_norm': 0.7141778469085693, 'learning_rate': 3.219808272827917e-05, 'epoch': 1.42}                                                   
{'loss': 0.7119, 'grad_norm': 0.8500687479972839, 'learning_rate': 3.0287834646695477e-05, 'epoch': 1.49}                                                  
{'loss': 0.6357, 'grad_norm': 0.7155753374099731, 'learning_rate': 2.834465700261198e-05, 'epoch': 1.55}                                                   
{'loss': 0.703, 'grad_norm': 0.7760538458824158, 'learning_rate': 2.6380650777612705e-05, 'epoch': 1.62}                                                   
{'loss': 0.6655, 'grad_norm': 0.7388576865196228, 'learning_rate': 2.4408046661584408e-05, 'epoch': 1.69}                                                  
{'loss': 0.7347, 'grad_norm': 0.9201497435569763, 'learning_rate': 2.2439128887084673e-05, 'epoch': 1.76}                                                  
{'loss': 0.7333, 'grad_norm': 1.214197039604187, 'learning_rate': 2.0486158730277454e-05, 'epoch': 1.82}                                                   
{'loss': 0.7217, 'grad_norm': 0.5917288064956665, 'learning_rate': 1.856129815482759e-05, 'epoch': 1.89}                                                   
{'loss': 0.6586, 'grad_norm': 1.7250254154205322, 'learning_rate': 1.667653407425598e-05, 'epoch': 1.96}                                                   
{'loss': 0.556, 'grad_norm': 0.8077885508537292, 'learning_rate': 1.4843603704405279e-05, 'epoch': 2.03}                                                   
{'loss': 0.4381, 'grad_norm': 0.9334748387336731, 'learning_rate': 1.307392147087777e-05, 'epoch': 2.09}                                                   
{'loss': 0.4025, 'grad_norm': 1.1001027822494507, 'learning_rate': 1.1378507926623247e-05, 'epoch': 2.16}                                                  
{'loss': 0.386, 'grad_norm': 0.737207293510437, 'learning_rate': 9.76792112233709e-06, 'epoch': 2.23}                                                      
{'loss': 0.4355, 'grad_norm': 0.9195957183837891, 'learning_rate': 8.252190857053626e-06, 'epoch': 2.3}                                                    
{'loss': 0.4407, 'grad_norm': 0.6842745542526245, 'learning_rate': 6.840756218384023e-06, 'epoch': 2.36}                                                   
{'loss': 0.4001, 'grad_norm': 1.3696553707122803, 'learning_rate': 5.542406801361758e-06, 'epoch': 2.43}                                                   
{'loss': 0.4258, 'grad_norm': 0.599327027797699, 'learning_rate': 4.3652279719506e-06, 'epoch': 2.5}                                                       
{'loss': 0.5361, 'grad_norm': 1.1350016593933105, 'learning_rate': 3.316550516082137e-06, 'epoch': 2.57}                                                   
{'loss': 0.357, 'grad_norm': 0.8104240894317627, 'learning_rate': 2.402904987779414e-06, 'epoch': 2.64}                                                    
{'loss': 0.2796, 'grad_norm': 0.9202777743339539, 'learning_rate': 1.6299810406600419e-06, 'epoch': 2.7}                                                   
{'loss': 0.3755, 'grad_norm': 1.0832188129425049, 'learning_rate': 1.0025919960785724e-06, 'epoch': 2.77}                                                  
{'loss': 0.4879, 'grad_norm': 0.9248091578483582, 'learning_rate': 5.246448685571365e-07, 'epoch': 2.84}                                                   
{'loss': 0.4777, 'grad_norm': 0.7324397563934326, 'learning_rate': 1.9911603516855338e-07, 'epoch': 2.91}                                                  
{'loss': 0.4072, 'grad_norm': 0.7875744700431824, 'learning_rate': 2.8032700388910814e-08, 'epoch': 2.97}                                                  
100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 222/222 [04:05<00:00,  1.06s/it][INFO|trainer.py:3984] 2025-05-15 07:30:24,686 >> Saving model checkpoint to llama3_lora/checkpoint-222
[INFO|configuration_utils.py:693] 2025-05-15 07:30:25,167 >> loading configuration file config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/config.json
[INFO|configuration_utils.py:765] 2025-05-15 07:30:25,168 >> Model config LlamaConfig {
  "architectures": [
    "LlamaForCausalLM"
  ],
  "attention_bias": false,
  "attention_dropout": 0.0,
  "bos_token_id": 128000,
  "eos_token_id": 128009,
  "head_dim": 128,
  "hidden_act": "silu",
  "hidden_size": 4096,
  "initializer_range": 0.02,
  "intermediate_size": 14336,
  "max_position_embeddings": 8192,
  "mlp_bias": false,
  "model_type": "llama",
  "num_attention_heads": 32,
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "pad_token_id": 128255,
  "pretraining_tp": 1,
  "quantization_config": {
    "_load_in_4bit": true,
    "_load_in_8bit": false,
    "bnb_4bit_compute_dtype": "bfloat16",
    "bnb_4bit_quant_storage": "uint8",
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_use_double_quant": true,
    "llm_int8_enable_fp32_cpu_offload": false,
    "llm_int8_has_fp16_weight": false,
    "llm_int8_skip_modules": null,
    "llm_int8_threshold": 6.0,
    "load_in_4bit": true,
    "load_in_8bit": false,
    "quant_method": "bitsandbytes"
  },
  "rms_norm_eps": 1e-05,
  "rope_scaling": null,
  "rope_theta": 500000.0,
  "tie_word_embeddings": false,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.51.3",
  "unsloth_version": "2024.9",
  "use_cache": true,
  "vocab_size": 128256
}

[INFO|tokenization_utils_base.py:2510] 2025-05-15 07:30:25,280 >> tokenizer config file saved in llama3_lora/checkpoint-222/tokenizer_config.json
[INFO|tokenization_utils_base.py:2519] 2025-05-15 07:30:25,280 >> Special tokens file saved in llama3_lora/checkpoint-222/special_tokens_map.json
[INFO|trainer.py:2681] 2025-05-15 07:30:25,556 >> 

Training completed. Do not forget to share your model on huggingface.co/models =)


{'train_runtime': 246.2454, 'train_samples_per_second': 7.2, 'train_steps_per_second': 0.902, 'train_loss': 0.742836398852838, 'epoch': 3.0}               
100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 222/222 [04:06<00:00,  1.11s/it]
[INFO|trainer.py:3984] 2025-05-15 07:30:25,557 >> Saving model checkpoint to llama3_lora
[INFO|configuration_utils.py:693] 2025-05-15 07:30:26,017 >> loading configuration file config.json from cache at /root/.cache/huggingface/hub/models--unsloth--llama-3-8b-Instruct-bnb-4bit/snapshots/fd5a4dc328319c1cfe9489eccfb9c6406bdfd469/config.json
[INFO|configuration_utils.py:765] 2025-05-15 07:30:26,018 >> Model config LlamaConfig {
  "architectures": [
    "LlamaForCausalLM"
  ],
  "attention_bias": false,
  "attention_dropout": 0.0,
  "bos_token_id": 128000,
  "eos_token_id": 128009,
  "head_dim": 128,
  "hidden_act": "silu",
  "hidden_size": 4096,
  "initializer_range": 0.02,
  "intermediate_size": 14336,
  "max_position_embeddings": 8192,
  "mlp_bias": false,
  "model_type": "llama",
  "num_attention_heads": 32,
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "pad_token_id": 128255,
  "pretraining_tp": 1,
  "quantization_config": {
    "_load_in_4bit": true,
    "_load_in_8bit": false,
    "bnb_4bit_compute_dtype": "bfloat16",
    "bnb_4bit_quant_storage": "uint8",
    "bnb_4bit_quant_type": "nf4",
    "bnb_4bit_use_double_quant": true,
    "llm_int8_enable_fp32_cpu_offload": false,
    "llm_int8_has_fp16_weight": false,
    "llm_int8_skip_modules": null,
    "llm_int8_threshold": 6.0,
    "load_in_4bit": true,
    "load_in_8bit": false,
    "quant_method": "bitsandbytes"
  },
  "rms_norm_eps": 1e-05,
  "rope_scaling": null,
  "rope_theta": 500000.0,
  "tie_word_embeddings": false,
  "torch_dtype": "bfloat16",
  "transformers_version": "4.51.3",
  "unsloth_version": "2024.9",
  "use_cache": true,
  "vocab_size": 128256
}

[INFO|tokenization_utils_base.py:2510] 2025-05-15 07:30:26,121 >> tokenizer config file saved in llama3_lora/tokenizer_config.json
[INFO|tokenization_utils_base.py:2519] 2025-05-15 07:30:26,121 >> Special tokens file saved in llama3_lora/special_tokens_map.json
***** train metrics *****
  epoch                    =        3.0
  total_flos               = 16222836GF
  train_loss               =     0.7428
  train_runtime            = 0:04:06.24
  train_samples_per_second =        7.2
  train_steps_per_second   =      0.902
[INFO|modelcard.py:450] 2025-05-15 07:30:26,218 >> Dropping the following result as it does not have all the necessary fields:
{'task': {'name': 'Causal Language Modeling', 'type': 'text-generation'}}
```

推理验证

(llamafactory) root@h100vm:/content/LLaMA-Factory# cat chat_llama3.json 

```
{
  "model_name_or_path": "unsloth/llama-3-8b-Instruct-bnb-4bit",
  "adapter_name_or_path": "/content/LLaMA-Factory/llama3_lora",
  "template": "llama3",
  "finetuning_type": "lora"
}
(llamafactory) root@h100vm:/content/LLaMA-Factory# 
```



(llamafactory) root@h100vm:/content/LLaMA-Factory# llamafactory-cli chat chat_llama3.json

```

[INFO|2025-05-15 07:55:55] llamafactory.model.model_utils.attention:143 >> Using torch SDPA for faster training and inference.
[INFO|2025-05-15 07:55:55] llamafactory.model.adapter:143 >> Loaded adapter(s): /content/LLaMA-Factory/llama3_lora
[INFO|2025-05-15 07:55:55] llamafactory.model.loader:143 >> all params: 8,051,232,768
Welcome to the CLI application, use `clear` to remove the history, use `exit` to exit the application.

User: 你能解答的最难的数学题是什么？
Assistant: 作为 Llama-3，我能解答的最难的数学题可能会因人而异，但是在我的知识范围内，我可以尝试解答一些著名的难题。例如，Riemann猜想、 Navier-Stokes方程的解决方案、Poincaré猜想等。这些问题都是数学界的挑战目标之一，我可以尝试解释和解决它们。

User: 哥德巴赫猜想可以么
Assistant: 哥德巴赫猜想是指任意一个大于 2 的整数都可以被分解为三个或三个以上的素数的积。这个猜想被证明了对一些特定的范围内的整数是正确的，但是对于所有的整数是否正确仍然是未解决的问题。作为 Llama-3，我不能直接证明哥德巴赫猜想，但是可以解释和提供相关的信息。

```

### 使用UI进行微调

```
cd /content/LLaMA-Factory/
GRADIO_SHARE=1 llamafactory-cli webui
```

接下来的操作，就可以通过浏览器实现，确实生态十分强大。



