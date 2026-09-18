# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.2.2 训练范式代码展现 —— 1. SFT训练Phi-4的Reasoning能力

# 补充：书中分段展示时省略的导入语句
import multiprocessing
import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

# 加载分词器
tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-4")
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.padding_side = 'right'
# 添加特殊标记'<think>'和'</think>'
new_tokens = ['<think>', '</think>']
tokenizer.add_tokens(new_tokens)

# 加载数据集(取3万条样本)
ds = load_dataset(
    "cognitivecomputations/dolphin-r1",
    'reasoning-deepseek',
    split='train[:30000]'
).train_test_split(test_size=0.1)
# 数据预处理函数
def process(row):
    assistant_message = "<think>" + row['reasoning'] + "</think>\n\n" + row['answer']
    row['messages'].append({'role': 'assistant', 'content': assistant_message})
    conversations = ''
    for message in row['messages']:
        conversations += f"{message['role']}: {message['content']}\n"
    row['text'] = conversations.strip()
    return row
ds['train'] = ds['train'].map(process, num_proc=multiprocessing.cpu_count())
ds['test'] = ds['test'].map(process, num_proc=multiprocessing.cpu_count())

# 配置LoRA参数
peft_config = LoraConfig(
    lora_alpha=16,
    lora_dropout=0.05,
    r=16,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=['k_proj', 'o_proj', 'q_proj', 'v_proj', 'up_proj', 'down_proj', 'gate_proj'],
    modules_to_save=["lm_head", "embed_tokens"],
)

# 训练超参配置
training_arguments = SFTConfig(
    output_dir="./LoRA/",
    evaluation_strategy="steps",
    per_device_train_batch_size=16,
    gradient_accumulation_steps=4,
    learning_rate=1e-5,
    bf16=True,
    num_train_epochs=1,
    save_steps=200,
    eval_steps=200,
    logging_steps=25,
    dataset_text_field="text",
    max_seq_length=1024,
    save_total_limit=3,
    report_to='none',
)
# 加载模型并调整词嵌入维度
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-4",
    device_map={"":0},
    torch_dtype=torch.bfloat16
)
# 适配新增的特殊token
model.resize_token_embeddings(len(tokenizer))
# 初始化训练器
trainer = SFTTrainer(
    model=model,
    train_dataset=ds['train'],
    eval_dataset=ds['test'],
    peft_config=peft_config,
    tokenizer=tokenizer,
    args=training_arguments,
)
# 开始训练
trainer.train()
