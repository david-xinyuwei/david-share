## **Gemma 3 270M小模型能力上限检测**

### 结论

1. **模型选型上**：对于纯任务型（翻译、抽取等），270M Base > 270M Instruct，因为 Instruct 会保留安全规避和对话习惯，不利于目标任务收敛。
2. **训练轮次**：验证集 BLEU 和 Loss 在第 3 轮左右是最佳点 → 应用早停策略，避免第 4 轮开始的性能回落（过拟合）。
3. **任务方向性**：如果数据方向匹配度差（法→英），即使训练 Loss 下降，BLEU 也不会提升，提示需要换更匹配的数据集。
4. **训练动态**：Base 模型在训练集 Loss 和验证集 Loss 上同时优于 Instruct，说明它不仅记得住，还能更好泛化。
5. **工程建议**：
   - 低资源场景优先 Base 模型全量微调
   - 在监控 BLEU 变化的同时用验证集 Loss 作为早停指标
   - 数据方向和领域匹配比纯 epochs 增加更重要

| 要素         | 细节                                                         | 工程化手段（方法）                                           | 工程意义                                               |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------ |
| **问题**     | 微型模型（270M）开箱即用性能差，跨语言任务几乎不可用（BLEU≈2.23），长上下文和复杂指令跟随能力弱 | —                                                            | 小模型通用性不足、稳定性低，零样本不具备上线条件       |
| **工程目标** | 在单卡 6~12GB 显存条件下，让小模型在特定任务（英→法翻译）上达到可用精度 | —                                                            | 为边缘部署、低资源场景提供大模型替代路径               |
| **解决方案** | 针对 270M 小模型的低成本优化组合                             | ① 全量微调（包含嵌入层）<br>② 缩小领域（高一致性任务数据）<br>③ 精简模板减少 token<br>④ 一次性喂入大规模、去重数据 | 全量微调+领域聚焦+模板优化，确保小模型任务性能最大化   |
| **实施条件** | 硬件：6GB 可行，12GB 舒适<br>框架：Unsloth + AdamW-8bit<br>数据：OPUS-100、news_commentary<br>时长：RTX4090 数小时 | ⑤ AdamW-8bit 优化器<br>⑥ 梯度累积<br>⑦ BF16 精度推理         | 明确资源与参数配置，降低尝试门槛                       |
| **结果**     | BLEU 从 2.23 提升到 ≈18（可达 30）<br>base 版优于 instruct 版（避免安全层干扰）<br>推理速度快、显存低 | —                                                            | 小模型能接近大模型效果，部署成本极低                   |
| **经验结论** | 小模型零样本弱，微调后可作高可靠组件；数据多样性优于重复训练；全量微调优于高冻结率方法 | —                                                            | 为低预算工程师提供模型选型、数据策略、训练方法决策参考 |

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/SLM-limitation/images/1.png)



## Training Loss分析

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/SLM-limitation/images/2.png)

- **横轴**：Epoch（轮次）
- **纵轴**：BLEU（翻译质量，越高越好）
- **颜色含义**：
  - 红色：Base 模型（英→法）
  - 蓝色：Instruct 模型（英→法）
  - 黄色：Instruct（法→英）
  - 绿色：Base（法→英）

### 现象

1. **英→法任务**里，Base 模型（红线）BLEU 全程高于 Instruct（蓝线），并在第 3 轮达到峰值（≈11），之后略有回落；Instruct 模型峰值略低（≈9.5）。
2. **法→英任务**几乎没提升（绿线、黄线）——BLEU 全程低且在第 1 轮后反而下降，说明训练数据或任务定义对该方向支持不足。
3. 两个方向都在第 3 轮出现峰值，**第 4 轮开始出现下降** → 典型的过拟合信号（训练集拟合更好，但泛化能力变差）。

### 含义

- Base 模型在翻译任务学习速度和质量上明显优于 Instruct，这是因为 Instruct 的安全/助手调优干扰了直接翻译目标。
- 最佳训练 Epoch ≈ 3，再往后会损失效果，要早停。
- 数据和任务方向的匹配度差时（法→英）即使反复训练也无显著提高。



### Validation Loss分析

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/SLM-limitation/images/3.png)

- **横轴**：训练步数
- **纵轴**：验证集 Loss（越低越好）
- **红线 = Base 模型，蓝线 = Instruct 模型**

### 现象

1. Base 模型（红线）从头到尾验证集 Loss 都更低，并且下降更平稳。
2. Instruct 模型（蓝线）收敛到一个更高的 Loss 水平，中间波动小，但没再持续下降。
3. 训练后半程两条曲线趋于平稳 → 模型学习接近饱和。

### 含义

- Base 模型在泛化能力上确实优于 Instruct，与 BLEU 结论一致。

- Instruct 模型可能受安全指令或原有对话模式约束，对“翻译”这种单一任务无法充分优化。

  

### 效果评估

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/SLM-limitation/images/4.png)

先看图里的变化趋势

**英→法（红=Base，蓝=Instruct）**

- Epoch 0：BLEU 很低（Base ≈ 6，Instruct ≈ 2）
- Epoch 1~3：BLEU 持续提升，第 3 轮达到峰值（Base ≈ 11，Instruct ≈ 9.5）
- Epoch 4：两者 BLEU 都下降
  ✅ 说明模型在第 3 轮学到的能力最强，之后出现**过拟合**（在训练集上更准，但在测试集上泛化差了）

------

**法→英（绿=Base，黄=Instruct）**

- Epoch 0：BLEU 有个初始值（黄线甚至接近 8）
- Epoch 1 开始：BLEU 直接大幅下降，并且后续几轮一直下滑 ❌ 原因：
  - 训练数据是 **News-Commentary EN→FR**，因此模型接受到的是“英语→法语”映射数据
  - 对 “法语→英语” 没有直接监督训练，反而学到的权重更新损害了原本的法→英能力 → **灾难性遗忘（catastrophic forgetting）**

------

为什么会出现 “有的任务 BLEU 高了，有的低了”

1. **数据方向不匹配**
   - 英→法任务是训练目标 → 权重更新直接优化了它 → BLEU 上升
   - 法→英是非训练方向 → 权重更新不断覆盖原本的参数 → BLEU 下降
2. **过拟合效应**
   - 英→法在 Epoch 3 后开始掉分 → 虽然训练 Loss 会继续下降，但模型在验证集 BLEU 开始下滑
   - 原因是模型开始记住训练数据的细节，而不是学习可泛化的翻译规律
3. **模型容量限制（270M 小模型）**
   - 小模型参数有限，无法同时在两个方向保留高水平性能
   - 在单一方向训练时，会偏向牺牲另一个方向的表现来“腾出容量”
4. **初始 BLEU 高的那条黄线（法→英 Instruct）为什么骤降**
   - 可能原本依赖于广泛的多语言知识（预训练阶段获得）
   - 但微调阶段用大量单方向数据训练，破坏了这种知识平衡 → 灾难性遗忘的典型信号

------

工程意义

- 如果你只在一个翻译方向微调，**要接受另一个方向性能下降的风险**
- 如果想双向都好，需要用双向数据（英→法 + 法→英）联合训练
- BLEU 在训练过程中不仅用于“看涨”，也可以用于**发现性能损失和过拟合拐点**
- 最佳停训点通常在 **验证集 BLEU 峰值出现的 epoch**（这里是第 3 轮）



### 示例代码

```
pip install unsloth
```

```
from unsloth import FastLanguageModel
import torch, multiprocessing
from datasets import load_dataset
from peft import LoraConfig
from transformers import set_seed, AutoTokenizer,DataCollatorForSeq2Seq

from trl import SFTTrainer, SFTConfig

set_seed(42)

iso_language = dict()
iso_language["en"] = "English"
iso_language["de"] = "German"
iso_language["es"] = "Spanish"
iso_language["fr"] = "French"
iso_language["it"] = "Italian"


def FT(model_name, pair):

    compute_dtype = torch.bfloat16

    bs = 16 #Batch size per device (training and validation), bs = 1 *can* be faster
    gas = 4 #Gradient accumulation steps
    mseqlen = 4096 #Maximum sequence length; reduce if you run out of memory

    lr = 5e-5

    output_dir = "./SFT-OPUS/"

   model, tokenizer = FastLanguageModel.from_pretrained(
      model_name = model_name,
      fix_tokenizer=False,
      max_seq_length = mseqlen,
      dtype = compute_dtype,
      load_in_4bit=False,
      full_finetuning=True
    )


    languages = pair.split("-")
    src_lang = languages[0]
    tgt_lang = languages[1]


    ds = load_dataset("Helsinki-NLP/opus-100", pair, split="train").train_test_split(test_size=0.01)
    ds_train = ds["train"]
    ds_test = ds["test"]
    def process(row):

      source = row['translation'][src_lang]
      target = row['translation'][tgt_lang]

      row["text"] = "<start>You are a professional translator that translates messages from "+iso_language[src_lang]+" to "+iso_language[tgt_lang]+".<user>"+source+"<translator>"+target+tokenizer.eos_token
      return row

    ds_train = ds_train.map(
      process,
      num_proc= 10,
      load_from_cache_file=False,
    )
    print(ds_train[0]['text'])


    ds_test = ds_test.map(
      process,
      num_proc= 10,
      load_from_cache_file=False,
    )
    print(ds_test[0]['text'])



    from unsloth import UnslothTrainer, UnslothTrainingArguments

    training_arguments = UnslothTrainingArguments(
          output_dir=output_dir,
          optim="adamw_8bit",
          per_device_train_batch_size=bs,
          gradient_accumulation_steps=gas,
          log_level="debug",
          save_strategy="steps",
          save_steps=6000,
          logging_steps=25,
          learning_rate = lr,
          bf16 = True,
          num_train_epochs=1,
          warmup_ratio=0.03,
          report_to = "none",
          lr_scheduler_type="linear",
          max_length=mseqlen,
          dataset_text_field='text',
          dataset_num_proc=10,
          #do_eval=True,
          #per_device_eval_batch_size=bs,
          #eval_steps=100,
          #eval_strategy="steps",
    )

    trainer = UnslothTrainer(
      model = model,
      train_dataset=ds_train,
      #eval_dataset=ds_test,
      processing_class=tokenizer,
      args = training_arguments
    )



    trainer_ = trainer.train()

```

```
FT("google/gemma-3-270m", "en-fr")
```

