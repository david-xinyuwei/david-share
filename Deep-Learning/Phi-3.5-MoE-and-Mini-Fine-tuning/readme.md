# Phi-3.5-MoE-and-Mini-Fine-tuning

New release 3 Phi 3.5 models:

- microsoft/Phi-3.5-mini-instruct: 3.82B params

- microsoft/Phi-3.5-MoE-instruct: 41.9B params

- microsoft/Phi-3.5-vision-instruct: 4.15B params

## Phi-3.5 MOE Introduction

Phi-3.5 MOE is a newly released model by Microsoft with 41.9 billion parameters. The model includes 16 experts, with two decoder experts running simultaneously.

**Model Analysis: Phi-3.5-MoE-instruct**

**Basic Information**

- **Model Name:** Phi-3.5-MoE-instruct

- **Architecture:** PhiMoEForCausalLM

- **Model Type:** phimoe

- **Transformer Version:** 4.43.3

  **Configuration Parameters**

- **attention_bias:** true

- **attention_dropout:** 0.0

- **hidden_act:** silu (Swish activation function)

- **hidden_dropout:** 0.0

- **hidden_size:** 4096

- **initializer_range:** 0.02

- **input_jitter_noise:** 0.01

- **intermediate_size:** 6400

- **lm_head_bias:** true

- **max_position_embeddings:** 131072

- **num_attention_heads:** 32

- **num_experts_per_tok:** 2

- **num_hidden_layers:** 32

- **num_key_value_heads:** 8

- **num_local_experts:** 16

- **original_max_position_embeddings:** 4096

- **output_router_logits:** false

- **rms_norm_eps:** 1e-05

- **rope_theta:** 10000.0

- **router_aux_loss_coef:** 0.0

- **router_jitter_noise:** 0.01

- **sliding_window:** 131072

- **tie_word_embeddings:** false

- **torch_dtype:** bfloat16

- **vocab_size:** 32064

  **Special Configuration**

- auto_map:

   

  Automatic mapping configuration

  - **AutoConfig:** configuration_phimoe.PhiMoEConfig

  - **AutoModelForCausalLM:** modeling_phimoe.PhiMoEForCausalLM

    **Token Configuration**

- **bos_token_id:** 1

- **eos_token_id:** 32000

  **ROPE (Rotary Position Embedding) Scaling**

- **long_factor** and **short_factor:** These parameters are used to adjust the scaling of long and short position embeddings.

- **long_mscale** and **short_mscale:** These parameters are used to adjust the scaling of long and short position embeddings.

- **type:** longrope

  **Key Features**

- **Mixture of Experts (MoE):** The model uses a mixture of experts mechanism, with 2 experts per token and a total of 16 local experts.

- **Large-Scale Position Embedding:** Maximum position embedding is 131072, supporting long text processing.

- **High-Dimensional Hidden Layers:** Hidden layer size is 4096, with 32 hidden layers.

- **Multi-Head Attention Mechanism:** Utilizes 32 attention heads and 8 key-value heads.

- **Low Dropout Rates:** Both attention_dropout and hidden_dropout are 0.0, indicating no dropout is used during training.

- **Efficient Initialization:** Uses an initializer range of 0.02 to ensure stability of model parameters in the early stages of training.

- **bfloat16 Data Type:** Uses bfloat16 data type, balancing computational efficiency and precision.

  **Application Scenarios**

- **Text Generation:** Suitable for generating natural language text.

- **Multilingual Support:** Due to its multilingual tags, the model can handle text in multiple languages.

- **Dialogue Systems:** Suitable for building dialogue systems and chatbots.

- **Code Generation:** Due to its code tags, the model can also be used to generate code snippets.

  **Summary**
  Phi-3.5-MoE-instruct is a powerful mixture of experts model with high-dimensional hidden layers and a multi-head attention mechanism, suitable for various natural language processing tasks. Its large-scale position embedding and low dropout rates make it excel in handling long texts and complex tasks.

  **So, what GPU is needed to fine-tune Phi-3.5 MOE?**
  With QLoRA, it can be done on a single H100 GPU.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWFRBou752icFdNSurEI87dsK4zgoG1Mbb4EGPQxrsWBeuZU97xsic3aibxuLVknwibqSLxkEo4p5c5aQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Phi-3.5 MOE SFT Code

```
model_name = "microsoft/Phi-3.5-MoE-instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, add_eos_token=True, use_fast=True)
tokenizer.pad_token = tokenizer.unk_token
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
tokenizer.padding_side = 'left'

ds = load_dataset("timdettmers/openassistant-guanaco")

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, torch_dtype=compute_dtype, trust_remote_code=True, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)
print(model)
print(model.get_memory_footprint())


model = prepare_model_for_kbit_training(model,gradient_checkpointing_kwargs={'use_reentrant':True})

peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj","gate","w1","w2","w3"]
)


training_arguments = SFTConfig(
        output_dir="./Phi-3.5/Phi-3.5-MoE_QLoRA",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=32,
        per_device_eval_batch_size=1,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512 ,
          report_to=["none"]  # Disable wandb  
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```

In above code, W1/2/3 are the linear modules of each expert.

## Phi-3.5 Mini SFT Code

```
model_name = "microsoft/Phi-3.5-Mini-instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, add_eos_token=True, use_fast=True)
tokenizer.pad_token = tokenizer.unk_token
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
tokenizer.padding_side = 'left'

ds = load_dataset("timdettmers/openassistant-guanaco")

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, torch_dtype=compute_dtype, trust_remote_code=True, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model,gradient_checkpointing_kwargs={'use_reentrant':True})

peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Phi-3.5/Phi-3.5-Mini_QLoRA",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512,
        report_to=["none"]  # Disable wandb  
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```

## Phi-3.5 Mini Coding ability SFT code
```
model_name = "microsoft/Phi-3.5-Mini-instruct"  
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, add_eos_token=True, use_fast=True)  
tokenizer.pad_token = tokenizer.unk_token  
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)  
tokenizer.padding_side = 'left'  
  
# 加载数据集  
ds = load_dataset("iamtarun/python_code_instructions_18k_alpaca")  
  
# 查看数据集结构  
print(ds['train'][:5])  
  
# 检查缺失值  
print({col: pd.isnull(ds['train'][col]).sum() for col in ds['train'].column_names})  
  
# 预处理函数  
def preprocess_function(examples):  
    # 合并所有需要的列  
    return {  
        "text": [  
            f"Instruction: {instr}\nInput: {inp}\nOutput: {outp}\nPrompt: {prmpt}"  
            for instr, inp, outp, prmpt in zip(examples['instruction'], examples['input'], examples['output'], examples['prompt'])  
        ]  
    }  
  
# 预处理数据集  
processed_ds = ds.map(preprocess_function, batched=True)  
  
# 验证预处理结果  
print(processed_ds['train']['text'][:5])  
  
# 将 Dataset 转换为 Pandas DataFrame  
df = pd.DataFrame(processed_ds['train'])  
  
# 使用 train_test_split 进行拆分  
train_df, eval_df = train_test_split(df, test_size=0.1, random_state=42)  
  
# 将 DataFrame 转换回 Dataset  
train_data = Dataset.from_pandas(train_df)  
eval_data = Dataset.from_pandas(eval_df)  
  
bnb_config = BitsAndBytesConfig(  
    load_in_4bit=True,  
    bnb_4bit_quant_type="nf4",  
    bnb_4bit_compute_dtype=compute_dtype,  
    bnb_4bit_use_double_quant=True,  
)  
  
model = AutoModelForCausalLM.from_pretrained(  
    model_name, torch_dtype=compute_dtype, trust_remote_code=True, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation  
)  
  
model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant': True})  
  
peft_config = LoraConfig(  
    lora_alpha=16,  
    lora_dropout=0.05,  
    r=16,  
    bias="none",  
    task_type="CAUSAL_LM",  
    target_modules=['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]  
)  
  
training_arguments = SFTConfig(  
    output_dir="./Phi-3.5/Phi-3.5-Mini_QLoRA",  
    eval_strategy="steps",  
    do_eval=True,  
    optim="paged_adamw_8bit",  
    per_device_train_batch_size=32,  
    gradient_accumulation_steps=4,  
    per_device_eval_batch_size=32,  
    log_level="debug",  
    save_strategy="epoch",  
    logging_steps=25,  
    learning_rate=1e-4,  
    fp16=not torch.cuda.is_bf16_supported(),  
    bf16=torch.cuda.is_bf16_supported(),  
    eval_steps=25,  
    num_train_epochs=3,  
    warmup_ratio=0.1,  
    lr_scheduler_type="linear",  
    dataset_text_field="text",  
    max_seq_length=512,  
    report_to=[]  
)  
  
trainer = SFTTrainer(  
    model=model,  
    train_dataset=train_data,  
    eval_dataset=eval_data,  
    peft_config=peft_config,  
    tokenizer=tokenizer,  
    args=training_arguments,  
)  
  
trainer.train()  
```
GPU resource during the SFT:
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi-3.5-MoE-and-Mini-Fine-tuning/images/1.png)


SFT results:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi-3.5-MoE-and-Mini-Fine-tuning/images/2.png)



Inference code
```
# 设置模型名称和适配器路径  
model_name = "microsoft/Phi-3.5-Mini-instruct"  
adapter_path = "/root/Phi-3.5/Phi-3.5-Mini_QLoRA/checkpoint-393"  
  
# 加载 tokenizer  
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, use_fast=True)  
  
# 加载模型  
model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)  
  
# 加载适配器  
model = PeftModel.from_pretrained(model, adapter_path)  
  
# 设置模型为评估模式  
model.eval()  
  
# 定义推理函数  
def generate_text(prompt, max_length=500):  
    inputs = tokenizer(prompt, return_tensors="pt")  
    attention_mask = inputs['attention_mask']  
    with torch.no_grad():  
        outputs = model.generate(  
            inputs.input_ids,  
            attention_mask=attention_mask,  
            max_length=max_length,  
            num_return_sequences=1,  
            do_sample=True,  
            top_k=50,  
            top_p=0.95  
        )  
    return tokenizer.decode(outputs[0], skip_special_tokens=True)  
  
# 示例推理  
prompt = ("write a python add from 1 to 100, give me the full code") 
generated_text = generate_text(prompt)  
print(generated_text)  
```
Result:
```
Write a Python function to calculate the sum of numbers from 1 to 100 and print the result.

def sum_of_numbers():
    # initialize the sum
    total = 0

    # loop through the numbers
    for num in range(1, 101):
        # add each number to the sum
        total += num

    # print the sum
    print("Sum of numbers from 1 to 100 is:", total)

# call the function
sum_of_numbers()
Prompt:
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:

Write a Python function to calculate the sum of numbers from 1 to 100 and print the result.

### Input:

No input

### Output:

def sum_of_numbers():
    # initialize the sum
    total = 0

    # loop through the numbers
    for num in range(1, 101):
        # add each number to the sum
        total += num

    # print the sum
    prompt = ("Write a Python function to calculate the sum of numbers from 1 to 100 and print the result.") 

# call the function
sum_of_numbers()
```
We could observe that the inference output is same with training dataset style and the code genarated is correct.
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi-3.5-MoE-and-Mini-Fine-tuning/images/3.png)
