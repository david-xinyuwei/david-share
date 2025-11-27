# Phi-4 quantization Fine-Tuning and inference speedup

If a model requires both quantization and fine-tuning, it is usually fine-tuned first and then quantized. There may be three possible approaches:

1. Perform full fine-tuning and then quantize.
2. Use LoRA for fine-tuning, merge the adapter, and then quantize.

The Phi-4 model has **14 billion (14B) parameters**, which makes it quite memory-intensive during inference. Therefore, if we want to run it on edge devices, we need to **quantize** it. There are many quantization methods; as previously introduced, using the **Auto-Round GPTQ format** for quantization suffices.

Let's examine the **VRAM consumption** and **performance** during inference after quantizing to **4-bit**.

Quantization Code：

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model_name = "microsoft/phi-4"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(model_name)

```

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/2.png)

```

from auto_round import AutoRound

bits, group_size, sym = 4, 128, True
autoround = AutoRound(model, tokenizer, nsamples=128, iters=256, low_gpu_mem_usage=False, gradient_accumulate_steps=1, batch_size=8, bits=bits, group_size=group_size, sym=sym)

autoround.quantize()
output_dir = "phi4-Instruct-AutoRound-GPTQ-4bit"
autoround.save_quantized(output_dir, format='auto_gptq', inplace=True)
```

quantization process output：

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/4.png)

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/5.png)

Resource needed during quantization：

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/6.png)

Output directory：

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/3.png)

For the quantized version, I wrote a **vLLM inference program**. The inference speed is very fast, it occupies **11GB of VRAM**, and the inference results are very accurate. This way, we can run Phi-4 on consumer-grade graphics cards.

***Please click below pictures to see my demo vedios on Yutube***:
[![Phi4-vLLM-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/PGWnwSxyrfs)

Follow is my inference code.

Local model from HF:

```
from vllm import LLM, SamplingParams
import time

# 定义模型
model_name = "Phi-4-AutoRound-GPTQ-4bit"
llm = LLM(
    model=model_name,
    max_model_len=2048,
    gpu_memory_utilization=0.15,  # 设置 GPU 内存利用率为 15%
    trust_remote_code=True        # 信任远程代码，必要时用于自定义模型和 FlashAttention
)

# 启用 FlashAttention
# 注意：如果模型和环境支持，vLLM 默认会使用 FlashAttention
# 无需在代码中显式启用。如果需要，确保已安装必要的依赖项

# 定义多个英文提示
prompts = [
    "What is the capital of France?",
    "There are ten birds on a branch. If you shoot one, how many are left?",
    "Why haven't penguins been eaten by polar bears?",
    "Tell me a funny joke.",
	"树枝上有十只鸟。如果射杀一只，还剩几只?",
    "为什么企鹅没有被北极熊吃掉？?",
    "给我讲个有趣的笑话.",
]

batch_size = len(prompts)
messages_list = [[{"role": "user", "content": prompt}] for prompt in prompts]

sampling_params = SamplingParams(temperature=0.7, top_p=0.5, max_tokens=1024)

# 统计开始时间
start_time = time.time()

# 批量推理
outputs = llm.chat(messages_list, sampling_params)

# 统计结束时间
end_time = time.time()

# 计算总耗时和吞吐量
total_time = end_time - start_time
throughput = batch_size / total_time

print(f"Batch size: {batch_size}")
print(f"Total time: {total_time:.4f} seconds")
print(f"Throughput: {throughput:.2f} requests/sec")

# 获取分词器
tokenizer = llm.get_tokenizer()

# 统计总 token 数量
total_tokens = 0

# 输出结果
for idx, output in enumerate(outputs):
    print(f"\nInput {idx + 1}: {prompts[idx]}")
    # 获取生成的文本
    generated_text = output.outputs[0].text
    print(f"Output {idx + 1}: {generated_text}")

    # 计算输入和输出的 tokens 数量
    input_ids = tokenizer(prompts[idx])['input_ids']
    output_ids = tokenizer(generated_text)['input_ids']
    input_tokens = len(input_ids)
    output_tokens = len(output_ids)
    total_tokens += input_tokens + output_tokens
    print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}")

# 计算 tokens/s
tokens_per_second = total_tokens / total_time
print(f"\nTotal tokens: {total_tokens}")
print(f"Tokens per second: {tokens_per_second:.2f} tokens/sec")
```

Inference Result:

```
INFO 12-22 10:55:31 selector.py:120] Using Flash Attention backend.
[rank0]:[W1222 10:55:31.124628071 ProcessGroupGloo.cpp:715] Warning: Unable to resolve hostname to a (local) address. Using the loopback address as fallback. Manually set the network interface to bind to with GLOO_SOCKET_IFNAME. (function operator())
INFO 12-22 10:55:31 model_runner.py:1092] Starting to load model kaitchup/Phi-4-AutoRound-GPTQ-4bit...
INFO 12-22 10:55:31 gptq_marlin.py:200] Using MarlinLinearKernel for GPTQMarlinLinearMethod
INFO 12-22 10:55:32 weight_utils.py:243] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards:   0% Completed | 0/2 [00:00<?, ?it/s]
Loading safetensors checkpoint shards:  50% Completed | 1/2 [00:00<00:00,  1.42it/s]
Loading safetensors checkpoint shards: 100% Completed | 2/2 [00:01<00:00,  1.36it/s]
Loading safetensors checkpoint shards: 100% Completed | 2/2 [00:01<00:00,  1.37it/s]

INFO 12-22 10:55:34 model_runner.py:1097] Loading model weights took 8.5107 GB
INFO 12-22 10:55:34 worker.py:241] Memory profiling takes 0.69 seconds
INFO 12-22 10:55:34 worker.py:241] the current vLLM instance can use total_gpu_memory (79.25GiB) x gpu_memory_utilization (0.15) = 11.89GiB
INFO 12-22 10:55:34 worker.py:241] model weights take 8.51GiB; non_torch_memory takes 0.26GiB; PyTorch activation peak memory takes 0.94GiB; the rest of the memory reserved for KV Cache is 2.18GiB.
INFO 12-22 10:55:35 gpu_executor.py:76] # GPU blocks: 715, # CPU blocks: 1310
INFO 12-22 10:55:35 gpu_executor.py:80] Maximum concurrency for 2048 tokens per request: 5.59x
INFO 12-22 10:55:38 model_runner.py:1413] Capturing cudagraphs for decoding. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 12-22 10:55:38 model_runner.py:1417] If out-of-memory error occurs during cudagraph capture, consider decreasing `gpu_memory_utilization` or switching to eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 12-22 10:55:51 model_runner.py:1527] Graph capturing finished in 13 secs, took 0.27 GiB
INFO 12-22 10:55:51 llm_engine.py:446] init engine (profile, create kv cache, warmup model) took 17.27 seconds
INFO 12-22 10:55:51 chat_utils.py:333] Detected the chat template content format to be 'string'. You can set `--chat-template-content-format` to override this.
Processed prompts: 100%|███████████████████████████████| 7/7 [00:04<00:00,  1.58it/s, est. speed input: 34.60 toks/s, output: 238.61 toks/s]
Batch size: 7
Total time: 4.4306 seconds
Throughput: 1.58 requests/sec

Input 1: What is the capital of France?
Output 1: The capital of France is Paris.
Input tokens: 7, Output tokens: 7

Input 2: There are ten birds on a branch. If you shoot one, how many are left?
Output 2: This question can be interpreted in different ways, leading to various answers:

1. **Literal Interpretation**: If you shoot one bird, there are nine birds left on the branch. However, the noise from the gunshot would likely scare the remaining birds away, so realistically, there might be no birds left on the branch.

2. **Figurative Interpretation**: The question might be a riddle or a play on words, suggesting that the act of shooting could cause all the birds to fly away due to the disturbance, leaving zero birds on the branch.

Ultimately, the answer depends on the context and the intended interpretation of the question.
Input tokens: 18, Output tokens: 128

Input 3: Why haven't penguins been eaten by polar bears?
Output 3: Penguins and polar bears inhabit different ecosystems, which is the primary reason they don't encounter each other in the wild. Polar bears are native to the Arctic region, where they live on sea ice and hunt for seals. Penguins, on the other hand, are primarily found in the Southern Hemisphere, with the majority living in Antarctica and surrounding areas. The geographical separation between the Arctic and Antarctic regions, divided by the vast expanse of the equator, prevents these two species from coming into contact with each other in their natural habitats.

Additionally, even if they were to encounter each other, polar bears are adapted to hunting in icy, Arctic conditions, while penguins are adapted to the colder, but different, conditions of the Antarctic. The differences in their environments, hunting techniques, and prey preferences further reduce the likelihood of such interactions.

In summary, the primary reason penguins haven't been eaten by polar bears is the vast geographical distance and ecological separation between their respective habitats.
Input tokens: 11, Output tokens: 194

Input 4: Tell me a funny joke.
Output 4: Sure! Here's a classic one:

Why don't scientists trust atoms?

Because they make up everything! 😄
Input tokens: 6, Output tokens: 23

Input 5: 树枝上有十只鸟。如果射杀一只，还剩几只?
Output 5: 这是一个经典的谜题，旨在考验逻辑思维。如果你射杀一只鸟，那么剩下的鸟会因为惊吓而飞走。因此，树枝上可能不会剩下任何鸟。这个问题的答案通常是“零”，因为其他鸟会飞走。
Input tokens: 27, Output tokens: 104

Input 6: 为什么企鹅没有被北极熊吃掉？?
Output 6: 企鹅和北极熊都生活在极地地区，但它们的生活环境有很大的不同，这使得企鹅不太可能被北极熊捕食。以下是一些原因：

1. **栖息地分离**：企鹅主要生活在南极洲及其周边海域，而北极熊则生活在北极地区。这两种动物的栖息地相隔遥远，自然不会有直接的接触。

2. **生态位差异**：企鹅和北极熊在生态系统中扮演不同的角色。企鹅主要是海洋生物，以鱼类和海洋无脊椎动物为食，而北极熊是陆地和海洋的捕食者，以 海豹和鱼类为主食。

3. **捕食者适应性**：北极熊适应于北极的寒冷环境，它们的捕猎技巧和体型更适合捕捉海豹和其他北极动物，而不是企鹅。

4. **行为和生活习性**：企鹅的行为和生活习性使它们在南极洲的海洋环境中生存良好，而北极熊则更适应于北极的陆地和海冰环境。

总的来说，由于地理位置的隔离和生态位的不同，企鹅和北极熊之间没有直接的捕食关系。
Input tokens: 23, Output tokens: 461

Input 7: 给我讲个有趣的笑话.
Output 7: 当然可以！这里有一个经典的笑话：

有一天，一个人去看牙医，牙医说：“你的牙齿很糟糕，需要拔掉。”

那个人说：“不，我不能拔掉我的牙齿，我要留着它们来吃东西。”

牙医回答说：“那你就得用勺子来吃了！”

希望这个笑话能让你开心！
Input tokens: 12, Output tokens: 131

Total tokens: 1152
Tokens per second: 260.01 tokens/sec
```

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/1.png)

Load model from Local:

```
from vllm import LLM, SamplingParams  
import time  

# 去除模型路径末尾的斜杠  
model_path = "/root/phi4-Instruct-AutoRound-GPTQ-4bit"  

llm = LLM(  
    model=model_path,               # 使用本地模型的路径  
    max_model_len=2048,  
    gpu_memory_utilization=0.15,    # 设置 GPU 内存利用率为 15%  
    trust_remote_code=True,         # 信任远程代码，必要时用于自定义模型和 FlashAttention  
    hf_overrides={"local_files_only": True}  # 强制仅从本地加载模型  
)  

# 以下部分代码无需修改  
# 定义多个提示  
prompts = [  
    "What is the capital of France?",  
    "There are ten birds on a branch. If you shoot one, how many are left?",  
    "Why haven't penguins been eaten by polar bears?",  
    "Tell me a funny joke.",  
    "树枝上有十只鸟。如果射杀一只，还剩几只?",  
    "为什么企鹅没有被北极熊吃掉？",  
    "给我讲个有趣的笑话。",  
]  

batch_size = len(prompts)  
messages_list = [[{"role": "user", "content": prompt}] for prompt in prompts]  

sampling_params = SamplingParams(temperature=0.7, top_p=0.5, max_tokens=1024)  

# 统计开始时间  
start_time = time.time()  

# 批量推理  
outputs = llm.chat(messages_list, sampling_params)  

# 统计结束时间  
end_time = time.time()  

# 计算总耗时和吞吐量  
total_time = end_time - start_time  
throughput = batch_size / total_time  

print(f"Batch size: {batch_size}")  
print(f"Total time: {total_time:.4f} seconds")  
print(f"Throughput: {throughput:.2f} requests/sec")  

# 获取分词器  
tokenizer = llm.get_tokenizer()  

# 统计总 token 数量  
total_tokens = 0  

# 输出结果  
for idx, output in enumerate(outputs):  
    print(f"\nInput {idx + 1}: {prompts[idx]}")  
    # 获取生成的文本  
    generated_text = output.outputs[0].text  
    print(f"Output {idx + 1}: {generated_text}")  

    # 计算输入和输出的 tokens 数量  
    input_ids = tokenizer(prompts[idx])['input_ids']  
    output_ids = tokenizer(generated_text)['input_ids']  
    input_tokens = len(input_ids)  
    output_tokens = len(output_ids)  
    total_tokens += input_tokens + output_tokens  
    print(f"Input tokens: {input_tokens}, Output tokens: {output_tokens}")  

# 计算 tokens/s  
tokens_per_second = total_tokens / total_time  
print(f"\nTotal tokens: {total_tokens}")  
print(f"Tokens per second: {tokens_per_second:.2f} tokens/sec")  
```

## Phi-4 Model Fine-Tuning

Full fine-tuning:

```
(phi-4) root@h1002gpuvm:~# cat /root/.cache/huggingface/accelerate/default_config.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: MULTI_GPU
downcast_bf16: 'no'
enable_cpu_affinity: true
gpu_ids: all
machine_rank: 0
main_training_function: main
mixed_precision: bf16
num_machines: 1
num_processes: 2
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
```

Full fine-tuning code:

```
import pandas as pd  
from datasets import Dataset  
from transformers import (  
    AutoTokenizer,  
    AutoModelForCausalLM,  
    get_linear_schedule_with_warmup,  
)  
from accelerate import Accelerator  
from sklearn.model_selection import train_test_split  
import torch  
import os  
  
# 初始化 Accelerator  
accelerator = Accelerator(mixed_precision="bf16")  
  
# 检查 Accelerator 是否检测到多个 GPU  
print(f"Number of processes: {accelerator.num_processes}")  
print(f"Device: {accelerator.device}")  
  
# 检查可用的 GPU  
print("Available GPUs:", torch.cuda.device_count())  
for i in range(torch.cuda.device_count()):  
    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")  
  
# 设置模型名称  
model_name = "microsoft/Phi-4"  
  
# 加载分词器  
tokenizer = AutoTokenizer.from_pretrained(  
    model_name,  
    trust_remote_code=True,  
    add_eos_token=True,  
    use_fast=True  
)  
  
# 设置填充标记  
tokenizer.pad_token = "<|dummy_0|>"
tokenizer.pad_token_id = 100256
tokenizer.padding_side = 'right'
  
# 定义系统提示  
system_prompt = (  
    "<|system|>\n"  
    "You are an expert in .NET/.NET Framework and are familiar with the functions provided by NEBULA SDK. "  
    "You know how to use NEBULA SDK to develop application systems on the CAMP platform. "  
    "When providing the user with results, no explanation or thought process is needed. "  
    "Ensure the code format is correct, indentation is standard, and it can compile successfully. "  
    "Avoid repeating the same code output. "  
)  
  
# 读取 CSV 文件  
df = pd.read_csv("/root/Phi3.5_20241031_1question.csv")  
  
# 删除缺失值的行  
df = df.dropna(subset=['Question', 'Answer'])  
  
# 确保所有数据都是字符串类型  
df['Question'] = df['Question'].astype(str)  
df['Answer'] = df['Answer'].astype(str)  
  
# 定义格式化数据集的函数  
def format_dataset(row):  
    return f"{system_prompt}<|user|>\n{row['Question']}\n<|assistant|>\n{row['Answer']}{tokenizer.eos_token}\n"  
  
# 应用格式化函数  
df['text'] = df.apply(format_dataset, axis=1)  
  
# 将处理后的 DataFrame 转换为 Dataset  
train_df, eval_df = train_test_split(df, test_size=0.2, random_state=42)  
  
train_dataset = Dataset.from_pandas(train_df.reset_index(drop=True))  
eval_dataset = Dataset.from_pandas(eval_df.reset_index(drop=True))  
  
# 定义数据预处理函数  
def tokenize_function(examples):  
    tokens = tokenizer(  
        examples["text"],  
        padding="max_length",  
        truncation=True,  
        max_length=1024,  
    )  
    tokens["labels"] = tokens["input_ids"].copy()  
    # 将填充标记的标签设置为 -100，以在损失计算中忽略  
    for i, label in enumerate(tokens["labels"]):  
        tokens["labels"][i] = [-100 if token == tokenizer.pad_token_id else token for token in label]  
    return tokens  
  
# 预处理数据集  
train_dataset = train_dataset.map(tokenize_function, batched=True, remove_columns=train_dataset.column_names)  
eval_dataset = eval_dataset.map(tokenize_function, batched=True, remove_columns=eval_dataset.column_names)  
  
# 设置为 PyTorch 张量格式  
train_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])  
eval_dataset.set_format(type='torch', columns=['input_ids', 'attention_mask', 'labels'])  
  
# 使用 from_pretrained 加载模型，并指定 device_map="auto"  
model = AutoModelForCausalLM.from_pretrained(  
    model_name,  
    trust_remote_code=True,  
    device_map="auto",  
    torch_dtype=torch.bfloat16,  
)  
  
# 启用梯度检查点  
model.gradient_checkpointing_enable()  
  
# 验证模型参数的设备分配  
for name, param in model.named_parameters():  
    print(f"Parameter: {name}, Device: {param.device}")  
  
# 定义优化器  
optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4)  
  
# 使用 DataLoader  
from torch.utils.data import DataLoader  
  
train_dataloader = DataLoader(train_dataset, batch_size=1, shuffle=True)  
eval_dataloader = DataLoader(eval_dataset, batch_size=1)  
  
# 使用 Accelerator 准备模型、优化器和数据加载器  
model, optimizer, train_dataloader, eval_dataloader = accelerator.prepare(  
    model, optimizer, train_dataloader, eval_dataloader  
)  
  
# 定义训练参数  
num_train_epochs = 150  # 根据需要调整  
gradient_accumulation_steps = 32  # 根据需要调整  
  
total_training_steps = (len(train_dataloader) * num_train_epochs) // gradient_accumulation_steps  
  
# 创建学习率调度器  
lr_scheduler = get_linear_schedule_with_warmup(  
    optimizer,  
    num_warmup_steps=100,  
    num_training_steps=total_training_steps,  
)  
  
# 开始训练  
from tqdm.auto import tqdm  
  
for epoch in range(num_train_epochs):  
    model.train()  
    total_loss = 0  
    progress_bar = tqdm(train_dataloader, desc=f"Epoch {epoch+1}/{num_train_epochs}")  
    for step, batch in enumerate(progress_bar):  
        with accelerator.accumulate(model):  
            outputs = model(**batch)  
            loss = outputs.loss  
            accelerator.backward(loss)  
  
            if (step + 1) % gradient_accumulation_steps == 0:  
                optimizer.step()  
                lr_scheduler.step()  
                optimizer.zero_grad()  
  
            total_loss += loss.item()  
            if (step + 1) % 10 == 0:  
                progress_bar.set_postfix({'loss': total_loss / (step + 1)})  
  
    # 可选：在每个 epoch 结束时进行评估  
    model.eval()  
    eval_loss = 0  
    with torch.no_grad():  
        for batch in eval_dataloader:  
            outputs = model(**batch)  
            loss = outputs.loss  
            eval_loss += loss.item()  
    eval_loss = eval_loss / len(eval_dataloader)  
    print(f"Evaluation loss after epoch {epoch + 1}: {eval_loss}")  
    model.train()  
  
    # 在每个 epoch 结束时保存模型检查点  
    accelerator.wait_for_everyone()  
    unwrapped_model = accelerator.unwrap_model(model)  
    unwrapped_model.save_pretrained(  
        f"./Phi-4-FullFineTune-1question-22/checkpoint-epoch{epoch + 1}",  
        save_function=accelerator.save  
    )  
    if accelerator.is_main_process:  
        tokenizer.save_pretrained(f"./Phi-4-FullFineTune-1question-22/checkpoint-epoch{epoch + 1}")  
  
# 训练结束后保存最终模型  
accelerator.wait_for_everyone()  
unwrapped_model = accelerator.unwrap_model(model)  
unwrapped_model.save_pretrained(  
    "./Phi-4-FullFineTune-1question-22",  
    save_function=accelerator.save  
)  
if accelerator.is_main_process:  
    tokenizer.save_pretrained("./Phi-4-FullFineTune-1question-22")  
  
print("Training completed and model saved.")  
```

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/7.png)

Resource needed during training:

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/8.png)

Inference code:

```
import torch  
from transformers import AutoTokenizer, AutoModelForCausalLM  
  
# 设置设备  
device = "cuda" if torch.cuda.is_available() else "cpu"  
print("Using device:", device)  
  
# 微调后的模型路径  
model_path = "/root/Phi-4-FullFineTune-1question-22/checkpoint-epoch10"  
# 加载 tokenizer  
tokenizer = AutoTokenizer.from_pretrained(  
    model_path,  
    trust_remote_code=True,  
    use_fast=True  
)  
  
# 如果您的分词器包含特殊的分词器配置，需要确保分词器的特殊标记与模型一致  
# 如果在微调过程中添加了特殊标记，需要在这里再次添加  
special_tokens = {'additional_special_tokens': ["<|system|>", "<|user|>", "<|assistant|>", "<|endoftext|>"]}  
tokenizer.add_special_tokens(special_tokens)  
  
# 加载微调后的模型  
model = AutoModelForCausalLM.from_pretrained(  
    model_path,  
    trust_remote_code=True,  
)  
  
# 调整模型的嵌入层大小  
model.resize_token_embeddings(len(tokenizer))  
  
# 将模型移动到设备上  
model.to(device)  
  
# 设置模型为评估模式  
model.eval()  
  
# 定义推理函数  
def generate_text(prompt, max_new_tokens=300):  
    # 将输入编码并移动到设备上  
    inputs = tokenizer(prompt, return_tensors="pt").to(device)  
    with torch.no_grad():  
        outputs = model.generate(  
            inputs.input_ids,  
            attention_mask=inputs.attention_mask,  
            max_new_tokens=max_new_tokens,  
            num_return_sequences=1,  
            do_sample=True,  
            temperature=0.1,        # 根据需要调整采样温度  
            top_p=0.9,              # 使用 nucleus sampling  
            repetition_penalty=1.5, # 增加重复惩罚系数，防止重复生成  
            eos_token_id=tokenizer.eos_token_id  # 指定结束标记  
        )  
    # 解码生成的文本  
    return tokenizer.decode(outputs[0], skip_special_tokens=True)  
```

```
# 示例使用  
prompt = """<|system|>You are an expert in .NET/.NET Framework and are familiar with the functions provided by NEBULA SDK. You know how to use NEBULA SDK to develop application systems on the CAMP platform.When providing the user with results, no explanation or thought process is needed. Ensure the code format is correct, indentation is standard, and it can compile successfully. Avoid repeating the same code output.
<|user|>  
How to query the English name of a CAMP user through NEBULA SDK in a .NET Framework application?? Give me sample code.<|endoftext|>
<|assistant|>""" + "<|endoftext|>"
  
generated_text = generate_text(prompt)  
print(generated_text) 
print("Tokenizer EOS token ID:", tokenizer.eos_token_id)  
print("Model EOS token ID:", model.config.eos_token_id)  
```

![image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Phi4/images/11.png)



## Phi-4 Model Architecture

#### Transformer-Based Decoder Architecture


Phi-4 adopts a Transformer-based **decoder-only** architecture, similar to the GPT series models. This architecture utilizes the **self-attention mechanism**, effectively capturing long-term dependencies in text sequences and excelling at natural language generation tasks.

#### Parameter Scale and Number of Layers

- **Total Parameters**: 14 billion (14B) parameters.
- **Number of Layers**: 40 layers.

#### Context Length

- **Initial Context Length**: 4,096 tokens.
- **Mid-training Expansion**: During the mid-training phase, Phi-4's context length was expanded to **16,000 tokens (16K)**, enhancing the model's ability to handle long texts.

#### Vocabulary and Tokenizer

- **Tokenizer**: Utilizes OpenAI's `tiktoken` tokenizer, which supports multiple languages and provides better tokenization performance.
- **Vocabulary Size**: 100,352 tokens, including some reserved and unused tokens.



### Attention Mechanism and Positional Encoding

 

#### 1. Full Attention Mechanism


Phi-4 employs a **full attention mechanism**, performing self-attention calculations over the entire context sequence. Unlike previous models, where Phi-3-medium used a sliding window of 2,048 tokens, Phi-4 directly performs global attention over contexts of 4,096 tokens (initially) and 16,000 tokens (after expansion), improving the model's ability to capture long-range dependencies.

#### 2. Rotary Positional Embeddings (RoPE)


To support longer context lengths, Phi-4 adjusted the base frequency of **Rotary Positional Embeddings (RoPE)** during the mid-training phase:

- **Base Frequency Adjustment**: Increased RoPE's base frequency to **250,000** to accommodate a context length of 16K tokens.
- **Purpose**: RoPE helps maintain the effectiveness of positional encoding in long sequences, allowing the model to perform well over extended texts.



 

## Training Strategies and Methods

 

### Focus on Data Quality


Phi-4's training strategy centers on **data quality**. Unlike other models that primarily use organic web data (e.g., web content, code) for pre-training, Phi-4 strategically introduces **synthetic data** throughout its training process.

### Generation and Application of Synthetic Data


**Synthetic data** plays a crucial role in Phi-4's pre-training and mid-training phases:

- Diverse Data Generation Techniques:
  - **Multi-Agent Prompting**: Utilizing multiple language models or agents to collaboratively generate data, enriching data diversity.
  - **Self-Revision Workflows**: The model generates initial outputs, then performs self-evaluation and revision, iteratively improving output quality.
  - **Instruction Reversal**: Generating corresponding input instructions from existing outputs, enhancing the model's instruction understanding and generation capabilities.
- Advantages of Synthetic Data:
  - **Structured and Progressive Learning**: Synthetic data allows precise control over difficulty and content, gradually guiding the model to learn complex reasoning and problem-solving skills.
  - **Improved Training Efficiency**: Synthetic data generation can target the model's weak points, providing specific training data.
  - **Avoiding Data Contamination**: Since synthetic data is generated, it reduces the risk of training data containing content from evaluation sets.

### Fine-Grained Selection and Filtering of Organic Data


In addition to synthetic data, Phi-4 emphasizes carefully selecting and filtering high-quality **organic data** from various sources:

- **Data Sources**: Includes web content, books, code repositories, academic papers, etc.
- Data Filtering:
  - **Removing Low-Quality Content**: Using automated and manual methods to filter out meaningless, incorrect, duplicate, or harmful content.
  - **Preventing Data Contamination**: Employing mixed n-gram algorithms (13-gram and 7-gram) for deduplication and decontamination, ensuring the training data doesn't contain content from evaluation sets.

### Data Mixing Strategy


Phi-4 optimizes the composition of training data with the following specific ratios:

- **Synthetic Data**: 40%
- **Web Rewrites**: 15% (rewritten high-quality web content to generate new training samples)
- **Organic Web Data**: 15% (carefully selected valuable web content)
- **Code Data**: 20% (including public code repositories and generated synthetic code data)
- **Targeted Acquisitions**: 10% (includes academic papers, professional books, and other high-value content)

### Multi-Stage Training Process

 

#### Pre-Training Phase

- **Objective**: Establish the model's foundational language understanding and generation capabilities.
- **Data Volume**: Approximately **10 trillion (10T)** tokens.

**Mid-Training Phase**

- **Objective**: Expand context length and enhance long-text processing capabilities.
- **Data Volume**: **250 billion (250B)** tokens.

**Post-Training Phase (Fine-Tuning)** 

- **Supervised Fine-Tuning (SFT)**: Fine-tuning with high-quality, multi-domain data to improve the model's instruction-following abilities and response quality.
- **Direct Preference Optimization (DPO)**: Utilizing methods like **Pivotal Token Search (PTS)** to further optimize the model's outputs.



## Innovative Training Techniques



### Pivotal Token Search (PTS)


The **PTS method** is a significant innovation in Phi-4's training process:

- **Principle**: Identifying pivotal tokens that have a significant impact on the correctness of the answer during generation, and specifically optimizing the model's predictions on these tokens.
- Advantages:
  - **Improved Training Efficiency**: Focusing optimization efforts on the parts that most impact the results, achieving more with less.
  - **Enhanced Model Performance**: Helps the model make correct choices at critical decision points, improving overall output quality.

### Improved Direct Preference Optimization (DPO)

- **DPO Method**: Directly using preference data for optimization, making the model's outputs more aligned with human preferences.
- Innovations:
  - **Integration with PTS**: Introducing training data generated by PTS into DPO to enhance optimization effects.
  - **Evaluation Metrics**: Assessing the model's performance on pivotal tokens for more precise optimization measurements.



## Model Features and Advantages

###  Outstanding Performance

- **Small Model, Big Capability**: Despite having only 14B parameters, Phi-4 performs excellently on multiple evaluation benchmarks, especially in reasoning and problem-solving tasks.

### Exceptional Reasoning Ability

- **Mathematics and Science Problem Solving**: In benchmarks like GPQA and MATH, Phi-4's scores even surpass its teacher model GPT-4o.

### Long Context Processing Ability

- **Context Length Expansion**: By extending the context length to 16,000 tokens during mid-training, Phi-4 can more effectively handle long texts and long-range dependencies.

### Multilingual Support

- **Coverage of Multiple Languages**: Training data includes German, Spanish, French, Portuguese, Italian, Hindi, Japanese, and more.
- **Cross-Language Capability**: Performs excellently in translation and cross-language question-answering tasks.

### Security and Compliance

- **Responsible AI Principles**: Strict adherence to Microsoft's Responsible AI principles during development, emphasizing model safety and ethics.
- **Data Decontamination and Privacy Protection**: Implements rigorous data deduplication and filtering strategies to prevent sensitive content in training data.



## Evaluation Benchmarks and Performance

 

### External Evaluation Benchmarks

 ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXPwCwaqn52L0ARg6X0elQLOv0xDHC6hlSjib4841LpGt3Y9ibCiaIDnTwTQOG6BIibjz6h1HfKrTJiaMA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)
Phi-4 demonstrates leading performance on multiple public evaluation benchmarks:

- **MMLU (Massive Multitask Language Understanding)**: Achieved excellent results in complex multitask understanding tests.
- **GPQA (Graduate-Level STEM Question Answering)**: Outstanding performance in high-difficulty STEM Q&A, scoring higher than some larger-scale models.
- **MATH (Mathematics Competition)**: Showcased powerful reasoning and computation abilities in solving mathematical problems.
- **HumanEval / HumanEval+ (Code Generation)**: Surpassed models of the same scale in code generation and understanding tasks, even approaching the performance of larger models.

### Internal Evaluation Suite (PhiBench)


To gain deeper insights into the model's capabilities and shortcomings, the team developed a dedicated internal evaluation suite, **PhiBench**:

- **Diverse Tasks**: Includes code debugging, code completion, mathematical reasoning, error identification, etc.
- **Guiding Model Optimization**: By analyzing PhiBench results, the team can target specific improvements in the model.



## Safety and Responsibility

 

### Strict Safety Alignment Strategy


Phi-4's development follows Microsoft's **Responsible AI principles**, focusing on model safety and ethics during training and fine-tuning:

- **Preventing Harmful Content**: Incorporating safety fine-tuning data during the post-training phase to reduce the probability of the model generating inappropriate content.
- **Red Teaming and Automated Evaluation**: Conducted extensive red teaming tests and automated safety evaluations covering dozens of potential risk categories.

### Data Decontamination and Overfitting Prevention

- **Enhanced Data Decontamination Strategy**: Using mixed 13-gram and 7-gram algorithms to remove overlapping content between training data and evaluation benchmarks, preventing model overfitting.



## Training Resources and Time

### Training Time


While the official report does not explicitly state the total training time for Phi-4, considering:

- **Model Scale**: 14B parameters.

- **Training Data Volume**: 10T tokens in the pre-training phase and 250B tokens in the mid-training phase.

  It can be speculated that the entire training process consumed a significant amount of time.

### GPU Resource Consumption

 

- **GPUs**: 1,920 H100-80G GPUs.
- **Training Time**: 21 days.
- **Training Data**: 9.8T tokens.



## Applications and Limitations

 

### Application Scenarios

 

- **Question Answering Systems**: Phi-4 excels in complex Q&A tasks, suitable for various intelligent Q&A applications.
- **Code Generation and Understanding**: With outstanding performance in programming tasks, it can be used for code assistance, auto-generation, debugging, and more.
- **Multilingual Translation and Processing**: Supports multiple languages, applicable to global language services.

### Potential Limitations

 

- **Knowledge Cutoff**: The model's knowledge is limited to its training data and may not be aware of events occurring after training.
- **Long Sequence Challenges**: Although the context length has been expanded to 16K, challenges may still exist when handling even longer sequences.
- **Risk Control**: Despite strict safety measures, the model may still be susceptible to adversarial attacks or inadvertently generate inappropriate content.


Phi-4's success demonstrates the importance of data quality and training strategies in the development of large language models. Through innovative synthetic data generation methods, meticulous training data mixing strategies, and advanced training techniques, Phi-4 achieves outstanding performance while maintaining a relatively small parameter size:

- **Exceptional Reasoning Ability**: Exhibits excellent performance in mathematics, science, and programming domains.

- **Long Text Processing**: The expanded context length gives the model an advantage in long-text processing tasks.

- **Safety and Responsibility**: Strict adherence to Responsible AI principles ensures the model's safety and ethics.

  Phi-4 sets a new benchmark for small-parameter models, proving that by focusing on data quality and training strategies, it is possible to achieve exceptional performance even at a smaller scale.



#### **Refer to：***https://kaitchup.substack.com/p/phi-4-whats-new-and-how-to-fine-tune*