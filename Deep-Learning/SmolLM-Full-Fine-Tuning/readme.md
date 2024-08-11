# SmolLM Full Fine-Tuning

Hugging Face has launched a series of miniatures: the SmolLM, including 135M, 360M and 1.7B parameter versions.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX087KgSEQiaOe4SmFibX4Lcu4Tr3B05Y2RzcWGDsUDnzX5iamrDnSwEBpkgZdQuq1BCscb73jOb3IGA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

1. Currently, the model's performance in practical tests is average, showing a significant gap compared to the Phi-3 Mini. Of course, HF is likely continuing its training.

   We can explore the model's training dataset and methods for full fine-tuning.

   SmolLM was trained using three high-quality datasets:

   1. **Cosmopedia v2**: Contains 28B tokens of synthetic stories and code, covering over 4,000 topics.

   2. **FineWeb-Edu**: A high-quality educational content dataset, with 220B tokens after deduplication.

   3. **Python-Edu**: Contains 4B tokens of Python code.

      In total, 252B training tokens were used, distributed across the SmolLM corpus.

#### ## Training Architecture and Hyperparameters

 
The SmolLM 135M and 360M versions were trained on 600B tokens, while the 1.7B version was trained on 1T tokens. The model uses an architecture with a large number of layers but smaller embedding and hidden dimensions, making it deep and narrow. All models support a context size of 2048 tokens and use a tokenizer with 49,152 vocabulary items.

#### ### Supervised Full Fine-Tuning (SFT)


Supervised fine-tuning (SFT) involves teaching the model how to respond to human prompts. SmolLM was fine-tuned using the HuggingFaceH4/ultrachat_200k dataset.

#### ### Distillation DPO


Direct Preference Optimization (DPO) is used to align the model with human preferences. SmolLM underwent distillation DPO training using the ultrafeedback_binarized dataset.

## Fine Tuning code

Import necessary package:

```
import torch, multiprocessing
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments
)
from trl import SFTTrainer, SFTConfig, DPOTrainer, DPOConfig
```

Load model and dataset:

```
model_name = "HuggingFaceTB/SmolLM-135M"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|im_end|>"
tokenizer.pad_token_id = 2
tokenizer.padding_side = 'left' #Necessary for FlashAttention compatibility
dataset_train_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft")
dataset_test_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="test_sft[:5%]")
```

Load the model that we will train with SFT and activate gradient checkpointing to save memory.

```
model = AutoModelForCausalLM.from_pretrained(
          model_name, attn_implementation=attn_implementation, device_map={"": 0}
)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})

# Define a chat template  
chat_template = """  
{%- for message in messages %}  
    {%- if message['role'] == 'user' %}  
        {{ '<|user|>' + message['content'] + '</s>' }}  
    {%- elif message['role'] == 'assistant' %}  
        {{ '<|assistant|>' + message['content'] + '</s>' }}  
    {%- elif message['role'] == 'system' %}  
        {{ '<|system|>' + message['content'] + '</s>' }}  
    {%- endif %}  
{%- endfor %}  
"""  
  
# Set the chat template  
tokenizer.chat_template = chat_template  
  
# Training configuration  
training_arguments = SFTConfig(  
    output_dir="./sft_smollm_135M/",  
    eval_strategy="steps",  
    do_eval=True,  
    optim="adamw_torch",  
    per_device_train_batch_size=32,  
    gradient_accumulation_steps=2,  
    per_device_eval_batch_size=32,  
    log_level="debug",  
    save_steps=500,  
    logging_steps=50,  
    learning_rate=2e-5,  
    fp16=not torch.cuda.is_bf16_supported(),  
    bf16=torch.cuda.is_bf16_supported(),  
    eval_steps=50,  
    max_steps=4000,  
    warmup_steps=30,  
    max_seq_length=2048,  
    lr_scheduler_type="linear",  
)  
```

Start training

```
import os  
# Disable Weights & Biases  
os.environ["WANDB_DISABLED"] = "true"  
trainer = SFTTrainer(
        model=model,
        train_dataset=dataset_train_sft,
        eval_dataset=dataset_test_sft,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```

![image-20240810211013696](C:\Users\xinyuwei\AppData\Roaming\Typora\typora-user-images\image-20240810211013696.png)

![image-20240810211049793](C:\Users\xinyuwei\AppData\Roaming\Typora\typora-user-images\image-20240810211049793.png)