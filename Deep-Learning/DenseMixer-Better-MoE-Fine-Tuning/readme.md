## DenseMixer: Better MoE Fine-Tuning

DenseMixer 是一种面向 MoE（Mixture-of-Experts）模型的训练增强插件。它在保持推理 Top-K 稀疏前向的同时，通过直通估计器（STE）和敏感度信号，让路由器从 **所有专家** 获得梯度反馈，从而减少梯度偏置、提升专家利用率与训练稳定性。   兼容全参微调、LoRA、QLoRA，零侵入集成，工程落地简单。



DenseMixer母亲啊支持的模型如下：

| 类别                    | 代表模型 / 架构                                              | 说明与注意事项                                               |
| ----------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **开箱即用（已验证）**  | **Qwen 系列**<br>Qwen3‑30B‑A3B<br>Qwen1.5‑MoE‑A2.7B<br>Qwen2.5‑MoE 各规格<br><br>**GPT‑OSS 系列**<br>gpt‑oss‑120B<br>gpt‑oss‑20B<br><br>**其他已测结构**<br>Mixtral<br>Switch Transformer<br>GLaM | HuggingFace Transformers 官方/社区已验证支持，采用标准 Top‑K 硬路由实现。DenseMixer 可直接：<br>`densemixer setup` + `export DENSEMIXER_ENABLED=1` |
| **可预期适配**          | DeepSpeed‑MoE<br>Tutel‑MoE<br>自定义 Experts（符合 HF Router + Top‑K API） | 架构与已验证模型类似，只要硬路由是在标准 `forward` 中实现，即可直接加载 DenseMixer |
| **可能需要自定义 Hook** | 非标准 Router Pipeline<br>完全软路由（Soft routing）<br>特殊梯度裁剪或重参数化的 MoE 架构 | 如果路由选择逻辑未在标准 API 暴露，或不是硬 Top‑K 路由，则需在注册 DenseMixer 时手动 Hook；对于纯软路由，DenseMixer 优势较小 |

### DenseMixer 只对硬 Top‑K 稀疏路由有意义

- 硬路由：未选中专家梯度恒为 0 → 会导致路由器训练有偏，专家使用极不均衡
- 软路由：所有专家都能接到梯度，本质上没有“没被训练”的专家 → DenseMixer 就没有改进空间
- 混合路由：如果未激活专家权重太小，梯度仍接近 0，也可能从 DenseMixer 得到改善；但效果取决于权重大小

| 类型     | 选择规则                   | 激活专家数 | 未选中专家前向 | 未选中专家梯度 | 算力开销   | DenseMixer 价值 |
| -------- | -------------------------- | ---------- | -------------- | -------------- | ---------- | --------------- |
| 硬 Top‑K | 选 K 个最高分专家          | K≪N        | 跳过           | 0              | 低         | 高              |
| 硬 Top‑1 | 选 1 个最高分专家          | 1          | 跳过           | 0              | 极低       | 高              |
| 软路由   | 所有专家按概率分布加权     | N          | 参与           | 有梯度         | 高         | 无              |
| 混合路由 | Top‑K 权重大，其他权重很小 | N          | 参与           | 弱梯度         | 中等       | 中              |
| 随机路由 | 按概率随机选专家           | 任意       | 取决于策略     | 取决于策略     | 取决于策略 | 中等/高         |

### 确认一个模型的MoE类型

```
"num_local_experts": 32,        // 一共有 32 个本地专家
"num_experts_per_tok": 4,       // 每个 token 只激活 4 个专家
"experts_per_token": 4,         // 也是同样的意思
```

- **num_local_experts = 32** → 这个 MoE 模型一共有 32 个专家（Expert），每个专家是一个独立的前馈子网络（FFN）。
- **num_experts_per_tok = 4** & **experts_per_token = 4** → 对于每个 token，路由器会计算每个专家的打分，然后**只选择分数最高的 4 个专家**来执行 forward。
- 没被选中的 28 个专家在这一 token 的前向计算中完全跳过，梯度也是 0（这就是硬路由的特点）。
- 从实现角度，这里是典型的 **硬 Top‑K 稀疏**：
  1. 前向：`torch.topk` 选择 K=4 专家
  2. 其他专家不执行运算
  3. 反向梯度仅流向激活专家
  4. Router 更新依赖这 K 个激活专家的梯度（这会导致梯度 **偏置**、专家使用不均衡 → DenseMixer 就是来解决这个问题的）

### 对 DenseMixer 的意义

- GPT‑OSS‑20B 完全符合 DenseMixer 的适用条件（硬 Top‑K 稀疏路由 MoE）
- DenseMixer 在这里能：
  1. 保持前向推理时只运行 4 个专家（推理速度不变）
  2. 在训练/微调时，为剩下 28 个未激活专家计算 **no_grad 前向** + **敏感度信号**
  3. 用 STE（直通估计器）让路由器从所有 32 个专家接收梯度信号，改善路由稳定性和专家利用率

#### 总结表

| 配置项                                                | 意义                | 对 DenseMixer                           |
| ----------------------------------------------------- | ------------------- | --------------------------------------- |
| `"num_local_experts": 32`                             | 总专家数            | N=32                                    |
| `"num_experts_per_tok": 4` / `"experts_per_token": 4` | 每 token 激活专家数 | K=4（稀疏度高）                         |
| 路由逻辑                                              | 硬选择 Top‑K 专家   | DenseMixer 可介入反向，补充未选专家信号 |
| 适用性                                                | 硬 Top‑K 稀疏路由   | **完全适用**                            |

------

✅ 结论：**gpt-oss-20b** 这个模型 100% 是 **硬 Top‑K 稀疏路由**，DenseMixer 完全能用，并且理论上在它这种 N=32, K=4 的高稀疏度结构中效果会更明显。

### **背景**

#### **传统 MoE 训练的问题**：

- Router 仅在 Top‑K 激活专家中回传梯度，未激活专家梯度恒为 0。 
- 导致 Router 学到的信息有偏，高方差更新，容量利用不足。
- 激活集变化时性能容易震荡。

#### **DenseMixer 的解决方案**：

- 前向依旧 Top‑K 激活，保证推理效率。

- 反向时：  

​		为未激活专家执行一次 no_grad 前向，估计它们对降低 loss 的潜在贡献（敏感度信号）。  

​		用直通估计器 STE，让路由梯度透明化，将这些敏感度信号反馈到 Router 更新。 

- 支持归一化与非归一化路由的稳定反向规则。

#### **核心区别对比**

传统MoE训练和DenseMixer训练的形象对比如下图：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/DenseMixer-Better-MoE-Fine-Tuning/images/1.png)

分开来看两种训练模式的步骤。

传统MoE训练:

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/DenseMixer-Better-MoE-Fine-Tuning/images/2.png)

DenseMixer训练：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/DenseMixer-Better-MoE-Fine-Tuning/images/3.png)

完整的DenseMixer训练流程图：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/DenseMixer-Better-MoE-Fine-Tuning/images/4.png)

### 训练示例代码

```
pip install --upgrade densemixer peft trl datasets transformers bitsandbytes accelerate
densemixer setup
export DENSEMIXER_ENABLED=1
```

训练代码run_densemixer_qlora.py ：

```
import torch, os, multiprocessing
from datasets import load_dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed
)
from trl import SFTTrainer, SFTConfig

set_seed(1234) #Useful only for reproducibility

compute_dtype = torch.bfloat16
attn_implementation = 'flash_attention_2'
model_name = "Qwen/Qwen3-30B-A3B-Base"
batch_size = 1
gradient_accumulation_steps = 16
output_dir = "./QLoRA_DenseMoE/"

#Since this is a large dataset, we take only a subsample of the dataset for this tutorial
ds_train = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft[:10000]")
ds_test = load_dataset("HuggingFaceH4/ultrachat_200k", split="test_sft[:1000]")

ds_train = ds_train.remove_columns(["prompt"])
ds_test = ds_test.remove_columns(["prompt"])

tokenizer = AutoTokenizer.from_pretrained(model_name)


from transformers import Qwen3MoeForCausalLM
bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = Qwen3MoeForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})
print(model) #checking that the model is quantized


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'gate', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)

# I disabled evaluation to speed up training
training_arguments = SFTConfig(
      output_dir=output_dir,
      #eval_strategy="steps",
      #do_eval=True,
      optim="paged_adamw_8bit",
      per_device_train_batch_size=batch_size,
      gradient_accumulation_steps=gradient_accumulation_steps,
      #per_device_eval_batch_size=batch_size,
      log_level="debug",
      save_strategy="epoch",
      logging_steps=5,
      learning_rate=2e-5,
      bf16 = True,
      #eval_steps=5,
      max_steps=100,
      lr_scheduler_type="linear",
      dataset_text_field="text",
      max_length=1024,
      report_to="none"
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds_train,
        #eval_dataset=ds_test,
        peft_config=peft_config,
        processing_class=tokenizer,
        args=training_arguments,
)


trainer.train()

```

对照试验：

```
export DENSEMIXER_ENABLED=0
python run_densemixer_qlora.py
```

