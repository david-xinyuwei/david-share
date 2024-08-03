# Llama3.1-8B Fine Tuning
Llama 3.1 and Llama 3 do not differ significantly in terms of fine-tuning implementation. In this article, I will first introduce the differences between the two models and then present the code for QLoRA and LoRA

## Detailed Technical Differences Between Llama 3 and Llama 3.1

### 1. Language Support

- **Llama 3.1**: Added official support for German, French, Italian, Portuguese, Hindi, Spanish, and Thai.
- **Llama 3**: Does not have these additional language supports.

### 2. Function Calling

- **Llama 3.1**: Added support for function calling, specifically introducing new special tokens such as “<|eom_id|>” and “<|python_tag|>”.
- **Llama 3**: Does not have this function calling support.

### 3. Long Sequence Processing

- **Llama 3.1**: Underwent post-training on very long sequences (up to 128k tokens), capable of handling longer contexts without significantly reducing accuracy.
- **Llama 3**: Did not undergo such long sequence post-training.

### 4. Training Data

- **Llama 3.1**: Trained on long context data containing 800 billion tokens, accounting for 5% of the total pre-training data.
- **Llama 3**: Was not specifically trained on long context data.

### 5. Tokenizer Updates

- Llama 3.1

  : The tokenizer was modified, and certain special tokens were changed. For example:

  - Added “<|finetune_right_pad_id|>” as a padding token.
  - Added “<|eom_id|>” and “<|python_tag|>” for function calling.

- **Llama 3**: Does not have these new special tokens, using other special tokens such as “<|reserved_special_token_2|>” and “<|reserved_special_token_3|>”.

### 6. Padding Direction

- **Llama 3.1**: Introduced a new padding token “<|finetune_right_pad_id|>”. Experiments show that using right padding during fine-tuning is more effective than left padding.
- **Llama 3**: Does not have a specific padding token, usually using “<|eot_id|>” for padding.

### 7. Fine-Tuning Effectiveness

- **Llama 3.1**: Demonstrates faster learning speed and better effectiveness during fine-tuning. When using QLoRA for fine-tuning, the loss value is lower than when using LoRA for fine-tuning.
- **Llama 3**: Learning speed and effectiveness are not as good as Llama 3.1. The effectiveness is also not as good as Llama 3.1 when using QLoRA for fine-tuning.

### Summary

Llama 3.1 has made significant technical improvements in multilingual support, function calling, long sequence processing, and tokenizer updates. It also shows better learning effectiveness during fine-tuning, especially with the introduction of new special tokens and padding strategies, making the fine-tuning process more efficient.


## Fine Tuning Code of Llama 3.1 8B
QLoRA with right padding
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

LoRA with right padding
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


model = AutoModelForCausalLM.from_pretrained(
          model_name, torch_dtype=torch.bfloat16, device_map={"": 0}, attn_implementation=attn_implementation
)

model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_LoRA_right",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=16,
        per_device_eval_batch_size=2,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        bf16 = True,
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