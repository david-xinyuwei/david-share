# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.5.2 生成多样化的回答

from datasets import load_dataset
from transformers import pipeline, AutoTokenizer
import torch
# 加载少量提示数据 (仅第一条用于测试)
dataset = load_dataset("fka/awesome-chatgpt-prompts", split="train[:1]")
print(f"Dataset length: {len(dataset)}")
# 组装prompt为所需的字符串列表格式
prompts = [{"role": "user", "content": p} for p in dataset["prompt"]]
batch_size = 8
model_a = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_a, padding_side='left')
pipe = pipeline(
    task="text-generation",
    model=model_a,
    tokenizer=tokenizer,
    device_map="auto",
    torch_dtype=torch.float16,
    batch_size=batch_size
)
# 调用pipeline生成结果
output_a = pipe(prompts, do_sample=True, top_p=0.8, max_length=1024)
output_b = pipe(prompts, do_sample=True, top_p=1.0, max_length=1024)
# 定义一个函数安全处理输出结构，以避免管道不同返回格式导致的错误
def extract_generated_text(item):
    # 如果 item 是 list 类型，那么取第一个元素
    if isinstance(item, list):
        item = item[0]
    if isinstance(item, dict):
        return item.get('generated_text', '')
    else:
        raise ValueError(f"未知的数据结构类型：{type(item)}，内容：{item}")
# 先打印prompt原文，再依次打印两个output
for idx, prompt_dict in enumerate(prompts):
    prompt_content = prompt_dict['content']
    print(f"\nPrompt {idx + 1}: {prompt_content}\n")
    generated_text_a = extract_generated_text(output_a[idx])
    print(f"Output A (top_p=0.8) 的生成结果:\n{generated_text_a}\n{'-'*80}\n")
    generated_text_b = extract_generated_text(output_b[idx])
    print(f"Output B (top_p=1.0) 的生成结果:\n{generated_text_b}\n{'='*80}\n")
