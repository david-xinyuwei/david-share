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

## Training Architecture and Hyperparameters

 
The SmolLM 135M and 360M versions were trained on 600B tokens, while the 1.7B version was trained on 1T tokens. The model uses an architecture with a large number of layers but smaller embedding and hidden dimensions, making it deep and narrow. All models support a context size of 2048 tokens and use a tokenizer with 49,152 vocabulary items.

### Supervised Full Fine-Tuning (SFT)


Supervised fine-tuning (SFT) involves teaching the model how to respond to human prompts. SmolLM was fine-tuned using the HuggingFaceH4/ultrachat_200k dataset.

### Distillation DPO


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
Resources consuption during training:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/SmolLM-Full-Fine-Tuning/images/2.png)

Training result：
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/SmolLM-Full-Fine-Tuning/images/1.png)

## DPO Traing Code

Load model：
```
model_name = "HuggingFaceTB/SmolLM-135M"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|im_end|>"
tokenizer.pad_token_id = 2
tokenizer.padding_side = 'left' #Necessary for FlashAttention compatibility

model = AutoModelForCausalLM.from_pretrained(
          model_name, attn_implementation=attn_implementation, device_map={"": 0}
)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})
```
use as a reference model our checkpoint trained with SFT of above steps.
```
ref_model = AutoModelForCausalLM.from_pretrained(
          "./sft_smollm_135M/checkpoint-500", attn_implementation=attn_implementation, device_map={"": 0}
)
```
Format UltraFeedback with a default chat template for DPO training.
```
# 加载数据集  
dataset = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split=["train_prefs", "test_prefs"])  
  
# 加载tokenizer并设置聊天模板  
tokenizer = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM-135M")  
tokenizer.pad_token = tokenizer.eos_token   
# 定义聊天模板  
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
  
# 设置聊天模板  
tokenizer.chat_template = chat_template  
  
def process(row):  
    # 提取内容为字符串  
    def extract_content(data):  
        if isinstance(data, list):  
            return " ".join(item['content'] for item in data if isinstance(item, dict) and 'content' in item)  
        return data  
  
    chosen_content = extract_content(row["chosen"])  
    rejected_content = extract_content(row["rejected"])  
      
    # 使用聊天模板格式化消息  
    chat = [  
        {"role": "user", "content": chosen_content},  
        {"role": "assistant", "content": rejected_content}  
    ]  
    formatted_chat = tokenizer.apply_chat_template(chat, tokenize=False)  
    row["chosen"] = formatted_chat  
    row["rejected"] = formatted_chat  
    return row  
  
# 处理数据集  
dataset[0] = dataset[0].map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
dataset[1] = dataset[1].map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
print(dataset) 

```
Result is as following:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/SmolLM-Full-Fine-Tuning/images/5.png)

Set DPO training parameters:
```
training_arguments = DPOConfig(
        output_dir="./dpo_smollm_135M/",
        evaluation_strategy="steps",
        do_eval=True,
        optim="adamw_torch",
        per_device_train_batch_size=32,
        gradient_accumulation_steps=2,
        per_device_eval_batch_size=32,
        log_level="debug",
        save_steps=500,
        fp16= not torch.cuda.is_bf16_supported(),
        bf16= torch.cuda.is_bf16_supported(),
        logging_steps=50,
        learning_rate=1e-7,
        eval_steps=50,
        max_steps=4000,
        warmup_steps=30,
        lr_scheduler_type="linear",
        beta=0.1,
)
trainer = DPOTrainer(
    model,
    ref_model=ref_model,
    args=training_arguments,
    train_dataset=dataset[0],
    eval_dataset=dataset[1],
    tokenizer=tokenizer,
)

trainer.train()
```
Training Result is as following:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/SmolLM-Full-Fine-Tuning/images/6.png)

Explain the rows in above picture:
1. Step
   - **Meaning**: This is the number of steps in the training process.
   - **Function**: Indicates the current step of the training. Each step usually corresponds to one parameter update.
2. Training Loss
   - **Meaning**: Training loss.
   - **Function**: Measures the model's performance on the training data. The lower the loss value, the better the model's performance on the training data. Common loss functions include cross-entropy loss, etc.
   - **Negative Value Explanation**: In your table, the training loss and validation loss are both positive values (0.693100 and 0.693147), which indicates that the loss values are reasonable. This value is close to the loss value of random guessing in a binary classification problem (log(2) ≈ 0.693), which may suggest that the model has not significantly learned effective features.
3. Validation Loss
   - **Meaning**: Validation loss.
   - **Function**: Measures the model's performance on the validation data. Similar to training loss, the lower the loss value, the better the model's performance on the validation data. Validation loss is used to evaluate the model's generalization ability.
4. Rewards/chosen
   - **Meaning**: Reward value for chosen actions.
   - **Function**: Indicates the reward the model receives when choosing a particular action. The higher the reward value, the better the choice of that action. Negative values indicate a penalty.
   - **Negative Value Explanation**: Negative values indicate a penalty. In your table, the reward values for both chosen and rejected actions are negative (around -5.77), which suggests that the model is being penalized for both choosing and rejecting actions. This may be because the model's strategy is not yet well-optimized, leading to low reward values.
5. Rewards/rejected
   - **Meaning**: Reward value for rejected actions.
   - **Function**: Indicates the reward the model receives when rejecting a particular action. Similar to the reward value for chosen actions, negative values indicate a penalty.
6. Rewards/accuracies
   - **Meaning**: Accuracy of rewards.
   - **Function**: Usually used to measure the accuracy of the reward signals in the model. The higher the value, the better the model's performance in terms of reward signals. In this table, the values in this column are all 0, which may indicate that this metric was not calculated under the current settings.
7. Rewards/margins
   - **Meaning**: Margins of rewards.
   - **Function**: Indicates the difference in rewards between chosen and rejected actions. The larger the value, the greater the difference in rewards between chosen and rejected actions. In this table, the values in this column are all 0, which may indicate that this metric was not calculated under the current settings.
8. Logps/rejected
   - **Meaning**: Log probability of rejected actions.
   - **Function**: Indicates the log probability of the model rejecting a particular action. Log probabilities are used to calculate loss functions and optimize model parameters. The lower the value, the higher the likelihood of the action being rejected.
   - **Negative Value Explanation**: Log probabilities are usually negative because probability values are between 0 and 1, and taking the logarithm of these values results in negative values. In your table, these values are around -578. The absolute size of this value is not important; what matters is their relative change. If these values gradually decrease (absolute value increases) during training, it may indicate that the model is gradually learning.
9. Logps/chosen
   - **Meaning**: Log probability of chosen actions.
   - **Function**: Indicates the log probability of the model choosing a particular action. Similar to the log probability of rejected actions, the lower the value, the higher the likelihood of the action being chosen.
10. Logits/rejected
    - **Meaning**: Logits value for rejected actions.
    - **Function**: Logits are the unnormalized probability distributions output by the model. The logits value for rejected actions is used to calculate log probabilities and loss functions. The higher the value, the higher the likelihood of the action being rejected.
    - **Negative Value Explanation**: Logits values can be either positive or negative, depending on the model's output. In your table, these values are around 3.6 and are relatively stable. The absolute size of the logits values is not important; what matters is the difference between the logits values for chosen and rejected actions.
11. Logits/chosen
    - **Meaning**: Logits value for chosen actions.
    - **Function**: Similar to the logits value for rejected actions, the logits value for chosen actions is used to calculate log probabilities and loss functions. The higher the value, the higher the likelihood of the action being chosen.

### Judging Training Effectiveness

- **Changes in Loss Values**: If the training loss and validation loss do not significantly decrease during training, it may indicate that the model has not effectively learned features. You can try adjusting the learning rate, model structure, or data preprocessing methods.
- **Changes in Reward Values**: If the reward values for chosen and rejected actions do not significantly change during training, it may indicate that the model's strategy is not well-optimized. You can try adjusting the reward function or training strategy.
- **Changes in Log Probabilities and Logits Values**: The absolute size of these values is not important; what matters is their relative change during training. If these values gradually decrease (absolute value increases) during training, it may indicate that the model is gradually learning.

### Improvement Suggestions

- **Adjust Learning Rate**: Try different learning rates to see if it can accelerate the model's convergence.
- **Increase Training Data**: More data can help the model learn better features.
- **Adjust Model Structure**: Try different model structures to see if it can improve the model's performance.
- **Check Data Preprocessing**: Ensure that the data preprocessing steps are correct to avoid data quality issues affecting the training effectiveness.