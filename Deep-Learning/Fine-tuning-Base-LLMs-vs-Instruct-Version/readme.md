# Fine-tuning-Base-LLMs-vs-Instruct-Version

In the application of large language models (LLMs), fine-tuning is a critical step. Fine-tuning allows the model to better adapt to specific tasks or datasets. However, with the development of LLMs, two main versions have emerged: base LLMs and instruct LLMs. This article will explore the differences between these two versions and discuss which version should be chosen for fine-tuning in practical applications.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nV2OasoxzlibKMkawNmnVETPsicGxQagJ5rklAAOJoUic5qYuCr0vEeoSiaNAicCvag9SHhXxVGLZpdq1Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## What are Base LLMs and Instruct LLMs?

### Base LLMs

Base LLMs are models pre-trained on a large amount of text data, with the training objective of predicting the next token. These models do not have specific format constraints and can generate highly diverse text. However, base LLMs may not directly answer user prompts and may repeat or deviate from the topic during generation.

### Instruct LLMs

Instruct LLMs are fine-tuned versions of base LLMs, processed through a complex pipeline to better respond to user instructions. These models undergo several post-training stages, including supervised fine-tuning (SFT), reinforcement learning with human feedback (RLHF), and direct preference optimization (DPO). They are capable of generating answers that align more closely with human preferences and are commonly used in chat applications.

## Differences Between Fine-Tuning Base LLMs and Instruct LLMs

 

### Fine-Tuning Base LLMs

When fine-tuning base LLMs, the model updates its weights based on new data, gradually adapting to new tasks or datasets. Since base LLMs do not have specific format constraints, they can more quickly learn new features and styles.

### Fine-Tuning Instruct LLMs

Instruct LLMs have already undergone a complex post-training process and have specific formats and system instructions. Fine-tuning instruct LLMs may introduce conflicts with the original system instructions and templates, leading to unexpected results. Additionally, instruct LLMs may partially lose their original safety and preference alignment capabilities during fine-tuning.

## Why Fine-Tuning Instruct LLMs is Not Recommended

- **Disruption of Original Training**: Fine-tuning instruct LLMs can partially undo the results of their original SFT and DPO training, causing the model to generate answers that no longer fully align with human preferences.

- **System Instruction Conflicts**: Fine-tuning instruct LLMs introduces new system instructions that may conflict with the original instructions, leading to inconsistent results.

- **Safety Issues**: Instruct LLMs undergo safety training, and fine-tuning may disrupt these safety constraints, resulting in the generation of unsafe content.

  In most cases, fine-tuning base LLMs is preferable to fine-tuning instruct LLMs. Base LLMs do not have specific format constraints and can more quickly adapt to new data and tasks. For applications requiring specific formats and safety, instruct LLMs can be considered, but potential conflicts and inconsistencies should be noted.
  
## SFT code

### Base Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

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


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_QLoRA_right/",
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
### Instruct Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

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


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_Instruct_QLoRA_right/",
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