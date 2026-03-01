# Fine-Tuning Tools: Axolotl & LLaMA-Factory

This article covers two popular fine-tuning tools for large language models: **Axolotl** and **LLaMA-Factory**. It also provides a deep dive into parallel training strategies (DP, FSDP, TP, PP) that are essential for understanding how these tools scale across GPUs.

**Notice:**

- After fine tuning with Axolotl, suggest inference with vLLM.
- Pay attention to version compatibility of Linux kernel, CUDA, torch, deepspeed (if you use).

---


## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | vLLM, DeepSpeed, LoRA/PEFT, Unsloth, Axolotl, torch.compile |


## Part I: Fine-Tuning with Axolotl and Inference with vLLM/Transformers

### Axolotl Overview

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
  
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/modelsupport.png)

### Overall Scenario

- Step 1: Use Axolotl to call DeepSpeed for QLoRA quantization (bnb) on phi-3-mini-4k, generating the quantized weight files. 
- Step 2: Dequantize the parameters and weights generated in the first step, and merge them with the original phi-3-mini-4k to create a complete model.

Then do 4 tests:

- Merge adapter and original model together, then do inference with FP/BF16 on vLLM.
- Merge adapter and original model together, then do inference with FP/BF16 on HF transformer.
- Based on merged model #1, use bnb to quantization and inference on HF transformer.
- Use bnb to dynamically load the phi-3 base model, load the post-FT checkpoints as adapter, and then use the INFERENCE on HF transformer.


**Notice:**
1. Flash atten2 is enable in 4 scenarios.
2. Inference parameters are same in 4 scenarios.

### 4 Inference Scenario Results Analyze

#### Scenario 1:

Description: Merge adapter and original model together, then do inference with FP/BF16 on vLLM.

Inference Results:

Generation time: 11.48 seconds
Tokens per second: 219.90
Prompt: 'Who is the current president of United States?'
Generated text: Detailed and accurate response about Joe Biden being the current president.

Analysis:
Model merging: Adapter and original model merged.
Inference framework: vLLM.
Precision: FP/BF16.
Performance: Short generation time, high tokens per second, fast inference speed.
Output quality: Generated text is detailed and accurate.

#### Scenario 2:

##### Description: 
Merge adapter and original model together, then do inference with FP/BF16 on HF transformer.

##### Inference Results:
Generation time: 45.78 seconds
Tokens per second: 43.47
Prompt: 'Who is the current president of United States?'
Generated text: Accurate response about Joe Biden being the current president, but with additional context and examples.

##### Analysis:
Model merging: Adapter and original model merged.
Inference framework: HF transformer.
Precision: FP/BF16.
Performance: Longer generation time, lower tokens per second, slower inference speed.
Output quality: Generated text is accurate but includes more context and examples, which may be more suitable for scenarios requiring detailed explanations.

#### Scenario 3:

##### Description: 
Based on merged model #1, use bnb to quantize and infer on HF transformer.

##### Inference Results:
Generation time: 21.50 seconds
Tokens per second: 24.93
Prompt: 'Who is the current president of United States?'
Generated text: Accurate response about Joe Biden being the current president, with brief context.

##### Analysis:
Model merging: Based on merged model #1.
Inference framework: HF transformer.
Quantization method: bnb quantization.
Performance: Moderate generation time, lower tokens per second, moderate inference speed.
Output quality: Generated text is accurate with brief context, suitable for scenarios requiring concise answers.

#### Scenario 4:

##### Description: Use bnb to dynamically load the phi-3 base model, load the post-FT checkpoints as adapter, and then use the INFERENCE on HF transformer.

##### Inference Results:
Model loading time: 1.92 seconds
Generation time: 95.35 seconds
Tokens per second: 20.87
Prompt: 'Who is the current president of United States?'
Generated text: Accurate response about Joe Biden being the current president, with repetitive context.

##### Analysis:
Model loading: Dynamically load phi-3 base model, load post-FT checkpoints as adapter.
Inference framework: HF transformer.
Quantization method: bnb quantization.
Performance: Short model loading time, but longest generation time, lowest tokens per second, slowest inference speed.
Output quality: Generated text is accurate but contains repetitive context, which may need further optimization to reduce redundancy.

#### Overall Summary:
- Performance: Scenario 1 has the fastest inference speed, while Scenario 4 has the slowest.
- Output Quality: Scenarios 1 and 2 have higher output quality, Scenario 3 provides concise output, and Scenario 4 has repetitive content.
- Applicable Scenarios: 
Scenario 1 is suitable for applications requiring quick responses
Scenario 2 is suitable for applications requiring detailed explanations
Scenario 3 is suitable for applications requiring concise answers
Scenario 4 may need further optimization to reduce redundancy.



### Fine Tuning Configuration Steps

#### Configure accelerate
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
false

Where to offload optimizer states?
none

Where to offload parameters?
none

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



#### Config Training Profile
Create yaml file on Azure GPU VM:

(axolotl-test) root@h100vm:~/axolotl-test# cat 1.yaml
```
base_model: microsoft/Phi-3-mini-4k-instruct
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
  - path: PhilipMay/UltraChat-200k-ShareGPT-clean
    split: train
    type: sharegpt
    conversation: chatml
#For the chat template, I use chatml.
chat_template: chatml
output_dir: ./ultrachat-200k-sharegpt1

#We must set that we are fine-tuning a QLoRA adapter with this line
adapter: qlora

sequence_len: 4096

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

gradient_accumulation_steps: 1
micro_batch_size: 32 
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
num_epochs: 1
logging_steps: 10
eval_steps: 100
saves_per_epoch: 1
weight_decay: 0.0

#The special token used for padding Llama 3
special_tokens:
  pad_token: <|eot_id|>

```

#### Training Result
Launch training:
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
Training steps:
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/trainingsteps.png)

GPU consumption during training:
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/phi3minigpu.png)


Check the trained models:
```
root@h100vm:~/axolotl-test/ultrachat-200k-sharegpt1# ls
adapter_config.json  added_tokens.json  checkpoint-63    config.json  special_tokens_map.json  tokenizer.json  tokenizer.model  tokenizer_config.json
```

### 4 Inference Scenarios

#### Merge FT Checkpoints with Base Model Code
```
# Base model and adapter paths  
model_name = "microsoft/Phi-3-mini-4k-instruct"  
adapter_path = "/root/axolotl-test/ultrachat-200k-sharegpt1/checkpoint-63"  
compute_dtype = torch.bfloat16  
save_dir = os.path.abspath("./dqz_merge1") 
  
def dequantize_model(model, to='./dequantized_model', dtype=torch.float16, device="cuda"):  
    os.makedirs(to, exist_ok=True)  
    cls = bnb.nn.Linear4bit  
    with torch.no_grad():  
        for name, module in model.named_modules():  
            if isinstance(module, cls):  
                print(f"Dequantizing `{name}`...")  
                quant_state = copy.deepcopy(module.weight.quant_state)  
                quant_state.dtype = dtype  
                weights = dequantize_4bit(module.weight.data, quant_state=quant_state, quant_type="nf4").to(dtype)  
                new_module = torch.nn.Linear(module.in_features, module.out_features, bias=None, dtype=dtype)  
                new_module.weight = torch.nn.Parameter(weights)  
                new_module.to(device=device, dtype=dtype)  
                parent, target, target_name = _get_submodules(model, name)  
                setattr(parent, target_name, new_module)  
        model.is_loaded_in_4bit = False  
        print("Saving dequantized model...")  
        model.save_pretrained(to)  
        config_data = json.loads(open(os.path.join(to, 'config.json'), 'r').read())  
        config_data.pop("quantization_config", None)  
        config_data.pop("pretraining_tp", None)  
        with open(os.path.join(to, 'config.json'), 'w') as config:  
            config.write(json.dumps(config_data, indent=2))  
        return model  
  
quantization_config = BitsAndBytesConfig(  
    load_in_4bit=True,  
    bnb_4bit_compute_dtype=compute_dtype,  
    bnb_4bit_use_double_quant=True,  
    bnb_4bit_quant_type="nf4",  
)  
  
try:  
    print(f"Starting to load the model {model_name} into memory")  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        quantization_config=quantization_config,  
        torch_dtype=compute_dtype,  
        device_map={"": 0}  
    )  
    model = dequantize_model(model, to='./dqz_model1/', dtype=compute_dtype)  
    model = PeftModel.from_pretrained(model, adapter_path)  
    model = model.merge_and_unload()  
    print(f"Successfully loaded the model {model_name} into memory")  
    model.save_pretrained(save_dir, safe_serialization=True)  
      
    # Save the tokenizer as well  
    tokenizer = AutoTokenizer.from_pretrained(model_name)  
    tokenizer.save_pretrained(save_dir)  
  
    config_data = json.loads(open(os.path.join(save_dir, 'config.json'), 'r').read())  
    config_data.pop("quantization_config", None)  
    config_data.pop("pretraining_tp", None)  
    with open(os.path.join(save_dir, 'config.json'), 'w') as config:  
        config.write(json.dumps(config_data, indent=2))  
```
Merge Result:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/mergemodel.png)



#### Scenario 1
```
def load_llm_model(save_dir, gpu_memory_utilization=0.6, disable_sliding_window=True):  
    # Load the fine-tuned model with vllm  
    print(f"Loading LLM model from directory: {save_dir}")  
    llm = LLM(  
        model=save_dir,  
        trust_remote_code=True,  
        gpu_memory_utilization=gpu_memory_utilization,  
        disable_sliding_window=disable_sliding_window  
    )  
    return llm  
  
# Define prompts  
prompts = [  
    "Who is the current president of United States?",  
    "Hello, my name is",  
    "The capital of France is",  
    "The future of AI is",  
]  
  
# Define sampling parameters  
sampling_params = SamplingParams(  
    temperature=1,  
    top_p=0.95,  
    max_tokens=2000,  
)  
  
if __name__ == "__main__":  
    try:  
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  
        print(f"Loading model from {save_dir}")  
  
        start_time = time.time()  
        llm = load_llm_model(save_dir)  
        load_time = time.time()  
  
        print("Model loaded successfully")  
        print(f"Model loading time: {load_time - start_time:.2f} seconds")  
  
        # Generate outputs  
        gen_start_time = time.time()  
        outputs = llm.generate(prompts, sampling_params)  
        gen_end_time = time.time()  
  
        print("Generation completed")  
        print(f"Generation time: {gen_end_time - gen_start_time:.2f} seconds")  
  
        # Calculate tokens per second  
        total_generated_tokens = sum(len(output.outputs[0].text.split()) for output in outputs)  
        gen_time = gen_end_time - gen_start_time  
        tokens_per_second = total_generated_tokens / gen_time if gen_time > 0 else float('inf')  
        print(f"Tokens per second: {tokens_per_second:.2f}")  
  
        # Print the outputs  
        for output in outputs:  
            prompt = output.prompt  
            generated_text = output.outputs[0].text  
            print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")  
  
        total_time = time.time()  
        print(f"Total execution time: {total_time - start_time:.2f} seconds")  
  
    except Exception as e:  
        print(f"An error occurred: {e}")  
        traceback.print_exc()  
```


#### Scenario 2
```
def load_llm_model(save_dir, gpu_memory_utilization=0.9):  
    # Load the fine-tuned model with transformers  
    print(f"Loading LLM model from directory: {save_dir}")  
  
    # Load tokenizer  
    tokenizer = AutoTokenizer.from_pretrained(save_dir, trust_remote_code=True)  
  
    # Load model  
    model = AutoModelForCausalLM.from_pretrained(  
        save_dir,  
        device_map="auto",  
        trust_remote_code=True,  
        attn_implementation="flash_attention_2",  
        max_memory={0: f'{int(gpu_memory_utilization * 100)}GB'},  
        torch_dtype=compute_dtype  # Ensure the model uses bf16  
    )  
  
    return model, tokenizer  
  
# Define prompts  
prompts = [  
    "Who is the current president of United States?",  
    "Hello, my name is",  
    "The capital of France is",  
    "The future of AI is",  
]  
  
def generate(model, tokenizer, prompts, max_tokens=2000, temperature=1.0, top_p=0.95):  
    inputs = tokenizer(prompts, return_tensors="pt", padding=True)  
    input_ids = inputs.input_ids.to(model.device)  # Keep input_ids as Long type  
  
    start_gen_time = time.time()  
    with torch.no_grad():  
        outputs = model.generate(  
            input_ids=input_ids,  
            max_length=max_tokens,  
            temperature=temperature,  
            top_p=top_p,  
            do_sample=True  
        )  
    end_gen_time = time.time()  
  
    gen_time = end_gen_time - start_gen_time  
    generated_tokens = outputs.size(1) - input_ids.size(1)  # Subtract input length to get the number of generated tokens  
    tokens_per_second = generated_tokens / gen_time if gen_time > 0 else float('inf')  
  
    return outputs, tokens_per_second  
  
if __name__ == "__main__":  
    try:  
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  
        print(f"Loading model from {save_dir}")  
  
        start_time = time.time()  
        model, tokenizer = load_llm_model(save_dir)  
        load_time = time.time()  
  
        print("Model loaded successfully")  
        print(f"Model loading time: {load_time - start_time:.2f} seconds")  
  
        # Generate outputs  
        gen_start_time = time.time()  
        outputs, tokens_per_second = generate(model, tokenizer, prompts)  
        gen_end_time = time.time()  
  
        print("Generation completed")  
        print(f"Generation time: {gen_end_time - gen_start_time:.2f} seconds")  
        print(f"Tokens per second: {tokens_per_second:.2f}")  
  
        # Print the outputs  
        for i, output in enumerate(outputs):  
            prompt = prompts[i]  
            generated_text = tokenizer.decode(output, skip_special_tokens=True)  
            print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")  
  
        total_time = time.time()  
        print(f"Total execution time: {total_time - start_time:.2f} seconds")  
  
    except Exception as e:  
        print(f"An error occurred: {e}")  
        traceback.print_exc()  

```
#### Scenario 3
```
def load_llm_model(save_dir):  
    # Load the fine-tuned model with transformers  
    print(f"Loading LLM model from directory: {save_dir}")  
  
    # Load tokenizer  
    tokenizer = AutoTokenizer.from_pretrained(save_dir, trust_remote_code=True)  
  
    quantization_config = BitsAndBytesConfig(  
        load_in_4bit=True,  
        bnb_4bit_compute_dtype=compute_dtype,  # Ensure the model uses bf16  
        bnb_4bit_use_double_quant=True,  
        bnb_4bit_quant_type="nf4",  
    )  
  
    # Load model with quantization  
    model = AutoModelForCausalLM.from_pretrained(  
        save_dir,  
        device_map="auto",  
        trust_remote_code=True,  
        attn_implementation="flash_attention_2",  
        max_memory={0: f'{int(gpu_memory_utilization * 100)}GB'},  
        torch_dtype=compute_dtype,  
        quantization_config=quantization_config  # Add quantization config  
    )  
  
    return model, tokenizer  
  
# Define prompts  
prompts = [  
    "Who is the current president of United States?",  
    "Hello, my name is",  
    "The capital of France is",  
    "The future of AI is",  
]  
  
def generate(model, tokenizer, prompts, max_tokens=2000, temperature=1.0, top_p=0.95):  
    inputs = tokenizer(prompts, return_tensors="pt", padding=True)  
    input_ids = inputs.input_ids.to(model.device)  # Keep input_ids as Long type  
  
    start_gen_time = time.time()  
    with torch.no_grad():  
        outputs = model.generate(  
            input_ids=input_ids,  
            max_length=max_tokens,  
            temperature=temperature,  
            top_p=top_p,  
            do_sample=True  
        )  
    end_gen_time = time.time()  
  
    gen_time = end_gen_time - start_gen_time  
    generated_tokens = outputs.size(1) - input_ids.size(1)  # Subtract input length to get the number of generated tokens  
    tokens_per_second = generated_tokens / gen_time if gen_time > 0 else float('inf')  
  
    return outputs, tokens_per_second  
  
if __name__ == "__main__":  
    try:  
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  
        print(f"Loading model from {save_dir}")  
  
        start_time = time.time()  
        model, tokenizer = load_llm_model(save_dir)  
        load_time = time.time()  
  
        print("Model loaded successfully")  
        print(f"Model loading time: {load_time - start_time:.2f} seconds")  
  
        # Generate outputs  
        gen_start_time = time.time()  
        outputs, tokens_per_second = generate(model, tokenizer, prompts)  
        gen_end_time = time.time()  
  
        print("Generation completed")  
        print(f"Generation time: {gen_end_time - gen_start_time:.2f} seconds")  
        print(f"Tokens per second: {tokens_per_second:.2f}")  
  
        # Print the outputs  
        for i, output in enumerate(outputs):  
            prompt = prompts[i]  
            generated_text = tokenizer.decode(output, skip_special_tokens=True)  
            print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")  
  
        total_time = time.time()  
        print(f"Total execution time: {total_time - start_time:.2f} seconds")  
  
    except Exception as e:  
        print(f"An error occurred: {e}")  
        traceback.print_exc()  
```

#### Scenario 4
```
model_name = "microsoft/Phi-3-mini-4k-instruct"  
adapter_path = "/root/axolotl-test/ultrachat-200k-sharegpt1/checkpoint-63"  
  
quantization_config = BitsAndBytesConfig(  
    load_in_4bit=True,  
    bnb_4bit_compute_dtype=torch.bfloat16,  
    bnb_4bit_use_double_quant=True,  
    bnb_4bit_quant_type="nf4",  
)  
  
model = AutoModelForCausalLM.from_pretrained(  
    model_name,  
    quantization_config=quantization_config,  
    attn_implementation="flash_attention_2",  
    torch_dtype=torch.bfloat16,  
    device_map={"": 0}  
)  
  

model = PeftModel.from_pretrained(model, adapter_path)  
  

tokenizer = AutoTokenizer.from_pretrained(model_name)  
  

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
   
prompts = [  
    "Who is the current president of United States?",  
    "Hello, my name is",  
    "The capital of France is",  
    "The future of AI is",  
]  
  
def generate(model, tokenizer, prompts, max_tokens=2000, temperature=1.0, top_p=0.95):  
    inputs = tokenizer(prompts, return_tensors="pt", padding=True)  
    input_ids = inputs.input_ids.to(model.device)  # Keep input_ids as Long type  
  
    start_gen_time = time.time()  
    with torch.no_grad():  
        outputs = model.generate(  
            input_ids=input_ids,  
            max_length=max_tokens,  
            temperature=temperature,  
            top_p=top_p,  
            do_sample=True  
        )  
    end_gen_time = time.time()  
  
    gen_time = end_gen_time - start_gen_time  
    generated_tokens = outputs.size(1) - input_ids.size(1)  # Subtract input length to get the number of generated tokens  
    tokens_per_second = generated_tokens / gen_time if gen_time > 0 else float('inf')  
  
    return outputs, tokens_per_second  
  
if __name__ == "__main__":  
    try:  
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  
        print(f"Loading model from {save_dir}")  
  
        start_time = time.time()  
        def load_llm_model(save_dir):  
            model = AutoModelForCausalLM.from_pretrained(  
                model_name,  
                quantization_config=quantization_config,  
                attn_implementation="flash_attention_2",  
                torch_dtype=torch.bfloat16,  
                device_map={"": 0}  
            )  
            model = PeftModel.from_pretrained(model, adapter_path)  
            tokenizer = AutoTokenizer.from_pretrained(model_name)  
            return model, tokenizer  
  
        model, tokenizer = load_llm_model(save_dir)  
        load_time = time.time()  
  
        print("Model loaded successfully")  
        print(f"Model loading time: {load_time - start_time:.2f} seconds")  
  
        # Generate outputs  
        gen_start_time = time.time()  
        outputs, tokens_per_second = generate(model, tokenizer, prompts)  
        gen_end_time = time.time()  
  
        print("Generation completed")  
        print(f"Generation time: {gen_end_time - gen_start_time:.2f} seconds")  
        print(f"Tokens per second: {tokens_per_second:.2f}")  
  
        # Print the outputs  
        for i, output in enumerate(outputs):  
            prompt = prompts[i]  
            generated_text = tokenizer.decode(output, skip_special_tokens=True)  
            print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")  
  
        total_time = time.time()  
        print(f"Total execution time: {total_time - start_time:.2f} seconds")  
  
    except Exception as e:  
        print(f"An error occurred: {e}")  
        import traceback  
        traceback.print_exc()  
```

---

## Part II: Parallel Training Strategies and LLaMA-Factory Usage

深入解析大模型并行训练方法：DP、FSDP、TP、PP 详解与实践指南以及LLaMA-Factory的使用。

近年来，大语言模型（LLM）快速发展，参数规模迅速增长至数十亿甚至数千亿级别，推动了 GPT、LLaMA 等模型广泛应用。但模型参数的增长也带来了巨大挑战：如何高效地在 GPU 集群上进行大模型训练或微调？针对这个问题，业界常用的模型并行策略包括数据并行（DP/DDP）、全参数分片并行（ZeRO/FSDP）、张量并行（TP）和流水线并行（PP）。然而，很多人在实践时容易混淆它们之间的本质区别与适用场景。

本文基于我最近一次与技术同事的长时间探讨记录，系统全面地剖析 DP、FSDP、TP 与 PP 的原理、优缺点、适用场景，并给出实操指导，以期帮助更多的工程师牢牢掌握并灵活运用它们。

### 基础知识与核心概念

#### 一个 Transformer 模型的结构组成有哪些？

以经典的 Transformer 为例，结构包含以下部分：

- **多层堆叠结构**：一个Transformer模型由大量层（如12层、24层、40层甚至更多）串联组成；
- 参数 (参数/权重): 在每一层中，可训练的浮点数张量，就是模型的"参数"或"权重"，如：
  - 自注意力中用于计算 Q、K、V、O 的线性映射矩阵
  - Feed Forward（MLP）层中的投影矩阵
  - Layer Norm 层中的 γ 和 β 向量
  - 嵌入表（Embedding Matrix）
- **激活**: 前向传播时每层输出的中间结果
- **梯度**: 反向传播时计算的相对于每个参数的损失函数导数，维度与参数相同
- **优化器状态**: 如 Adam 中的 m 和 v，通常大小约为参数的 1～2 倍

明确这些概念，对于理解后续的并行策略至关重要。

### DP、FSDP、TP、PP 深入解析

现在我们了解了大模型底层存储的这些张量，我们来看一下 DP、FSDP、TP 和 PP 本质上区别与联系。

#### Data Parallel (DP/DDP)

最经典和传统的并行方式，每个 GPU 都完整复制一份模型。

- **核心操作**：
  - 每个 GPU 存储一份完整模型。
  - batch 样本均匀划分，每个 GPU 独立前向传播。
  - 反向传播后，各 GPU 权重梯度进行一次 All-reduce 同步。
- **显存消耗**： 单个 GPU 显存 ≥ 模型整体参数（完整存储参数/梯度/m/v）+ 批次对应的激活内存。
- **优点**： 最容易实现，工程易用，框架成熟；
- **缺点**（尤为重要）： 随模型变大，单 GPU 显存显著制约 DP 规模，模型参数超过单个 GPU 显存就无法使用 DP。

#### Fully-Sharded Data Parallel（FSDP / ZeRO-3）

为了突破 DP 单卡显存的限制，FSDP 将所有参数张量切成碎片均匀分配到各 GPU 存储。

- **核心操作**：

  1. **参数常驻**：每层每个参数张量切片，每个 GPU 仅保存模型全参数的 1/N 碎片（记住不是"部分层"，而是"所有层的 1/N 片段"）

  2. 计算时：

     - 计算层前先 `all-gather`：从其他 GPU 拉取对应层剩余的 `N-1/N` 碎片，拼装出完整矩阵；
     - 执行前向、反向传播；
     - 计算完成后立即 `reduce-scatter` 将梯度矩阵拆回碎片返回对应 GPU。
     - 释放临时完整权重矩阵的显存。
  
- **显存用量峰值关键点**：

  FSDP 的限制因素并不是模型总大小（因为参数平摊了），而是**「模型的单层完整矩阵能否存进单 GPU 显存」**。

  直观而言，因为计算每层时，都存在一次完整矩阵的拼接动作，因此当某一层矩阵本身就大于单张 GPU 显存时，FSDP 无能为力，必须求助于张量并行（TP）方法。

#### Tensor Parallel（TP）

TP 是一种更加精妙的策略，专门解决单层超大矩阵无法塞进单 GPU 的问题。

- **核心操作**：

  - 同层内大矩阵权重按行或列切割至多卡存储；
  - 每个 GPU 只完成"局部"矩阵乘；
  - 局部结果用 `all-reduce` 拼回全局结果。

与 FSDP 最本质区别是，**张量并行 TP 从不在单 GPU 中出现完整矩阵**，而 FSDP 每次计算时必定出现一次完整矩阵拼接。因此，TP 才能训练单个超大矩阵超过了一张卡显存的情景。

- 缺点：高度频繁的局部聚合和全局通信，通常要求 GPU 间为 NVlink 级别的高速互连。

#### Pipeline Parallel (PP)

PP 的出发点截然不同，从层的维度切割模型，每张 GPU 专门负责模型连续的一部分层，例如：

- GPU-0负责第1-6层，GPU-1负责第7-12层...
- 激活数据逐层顺次传递，计算如流水线般进行。
- 优点：
  - 跨机器分层存储灵活（多机架集群友好）；
  - 只传递激活数据，通信开销适当。
- 局限：
  - 对单层巨大矩阵不起作用（适合层数众多但单层矩阵适中的情况）；
  - 流水线调度容易产生空闲时间（气泡bubble），需要精细调优。

### Parallel Strategy Comparison

**FSDP（Fully-Sharded Data Parallel）适用于这种场景：**

- 模型整体参数量很大（所有层参数之和大于单个GPU显存），以至于无法用纯DP/DDP加载全部参数。
- 但是单个模型层的矩阵（比如最大的那个projection矩阵）可以放进单个GPU显存中。

这句话最关键的是：

> ❗**FSDP的瓶颈不在于模型全部参数有多大，而在于模型的单层矩阵大小。**
> ❗因此，使用FSDP前必须保证最大单层的完整参数 **(含梯度/优化器状态)** 能够放入单一GPU显存。



**什么情况下FSDP不行？**

- 当模型的**单层完整矩阵本身**已经大于单个GPU显存，
  即便每张GPU保存的只是碎片，但在计算该层时总需要`all-gather`一次完整矩阵，这个瞬间就会OOM。
- 因此，这种时候FSDP一定**无法适用**，而只能求助于TP（Tensor Parallel）方法。



- 模型较大，但单层矩阵依然比单GPU显存小 ⇒ 使用 FSDP

- 模型大而且单层最大矩阵超出单GPU显存 ⇒ 无法使用 FSDP，需采用 TP（如 Megatron-LM、DeepSpeed-TP 等）。

  | 模型场景                 | DP(DDP)             | FSDP/ZeRO           | TP                     | PP                        |
  | ------------------------ | ------------------- | ------------------- | ---------------------- | ------------------------- |
  | ≤ 单GPU显存              | ✅（推荐）           | 🔴（不必要）         | 🔴（不必要）            | 🔴（不必要）               |
  | 整体大，但单层≤单GPU显存 | 🔴(无法装载全部模型) | ✅（推荐）           | 🔴（不必要）            | 🔶(考虑多节点时可选)       |
  | 单层 > 单 GPU 显存       | 🔴(无法装载全部模型) | 🔴 （单层拼接时OOM） | ✅（唯一方案）          | 🔶(结合TP扩展集群规模可选) |
  | 层数非常多，多机集群     | 🔴（可能放不下）     | ✅ （可选）          | 🔶 （可能需要配合FSDP） | ✅（推荐）                 |

### LLaMA-Factory Practical Usage

目前LLaMA-Factory：

- 默认支持 DP（torchrun + DDP）；
- 支持 FSDP（PyTorch原生）；
- 支持 ZeRO（deepspeed）；
- 暂不支持 TP、PP（后续框架可能支持）。

快速调用示例：

```
# DP模式调用：
torchrun --nproc-per-node 4 llamafactory-cli train config.json

# 原生FSDP模式调用：
torchrun --nproc-per-node 4 llamafactory-cli train config.json --fsdp "full_shard auto_wrap"
```

真正TP、PP需要Megatron-LM、Colossal-AI、DeepSpeed扩展框架进行。

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



### Installing LLaMA-Factory

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

Start training:

```
(llamafactory) root@YOUR-VM:/content/LLaMA-Factory# llamafactory-cli train train_llama3.json
```

Training log:

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

Inference validation:

(llamafactory) root@YOUR-VM:/content/LLaMA-Factory# cat chat_llama3.json 

```
{
  "model_name_or_path": "unsloth/llama-3-8b-Instruct-bnb-4bit",
  "adapter_name_or_path": "/content/LLaMA-Factory/llama3_lora",
  "template": "llama3",
  "finetuning_type": "lora"
}
```



(llamafactory) root@YOUR-VM:/content/LLaMA-Factory# llamafactory-cli chat chat_llama3.json

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

### Using the Web UI for Fine-Tuning

```
cd /content/LLaMA-Factory/
GRADIO_SHARE=1 llamafactory-cli webui
```

接下来的操作，就可以通过浏览器实现，确实生态十分强大。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/1.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/2.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/4.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/5.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Fine-Tuning-Tools-Axolotl-LLaMA-Factory/images/6.png)
