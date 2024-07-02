# E2E Fine tuning with Axolotl and Inference with vLLM/TF.

**Notice:**

- After FT Axolotl fine tuning, suggest inference with vLLM
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

## Overall scenario
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

## 4 Inference Scenario results analyze

### Scenario 1:

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

### Scenario 2:

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

### Scenario 3:

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

### Scenario 4:

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

### Overall Summary:
- Performance: Scenario 1 has the fastest inference speed, while Scenario 4 has the slowest.
- Output Quality: Scenarios 1 and 2 have higher output quality, Scenario 3 provides concise output, and Scenario 4 has repetitive content.
- Applicable Scenarios: 
Scenario 1 is suitable for applications requiring quick responses
Scenario 2 is suitable for applications requiring detailed explanations
Scenario 3 is suitable for applications requiring concise answers
Scenario 4 may need further optimization to reduce redundancy.



## Fine tuning Configuration steps
### Configure accelerate
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



### Config training profile
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
Training steps:
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/trainingsteps.png)

GPU cumsuption during training:
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/phi3minigpu.png)


Check the trained models:
```
root@h100vm:~/axolotl-test/ultrachat-200k-sharegpt1# ls
adapter_config.json  added_tokens.json  checkpoint-63    config.json  special_tokens_map.json  tokenizer.json  tokenizer.model  tokenizer_config.json
```
## 4 Inference Scenarios
#### Merge FT checkpoints with base model code
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

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Fine-tuning-with-Axolotl/images/mergemodel.png)



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
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  # 使用绝对路径  
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
        save_dir = os.path.abspath("/root/axolotl-test/ultrachat-200k-sharegpt/dqz_merge1")  # 使
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