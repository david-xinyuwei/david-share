# Padding-Free训练详解与实战经验

随着大型语言模型（如Meta的Llama、OpenAI的GPT系列）被越来越广泛地用于生产环境和研究任务，如何有效利用昂贵的GPU资源、提升训练效率成了重要话题。目前，常用的语言模型微调（fine-tuning）批处理方式主要有三种：padding、packing和padding-free。本文将详细介绍padding-free方案在实战环境下的使用经验、详细对比数据及注意事项，帮助你深入理解并更高效地应用padding-free技术。

三种方法的大致比较如下：

| 方法            | 是否需要填充padding tokens | 是否拼合不同序列               | 是否存在跨序列污染风险 | 复杂性         |
| --------------- | -------------------------- | ------------------------------ | ---------------------- | -------------- |
| Padding（传统） | 要                         | 否                             | 否                     | 简单，但低效   |
| Packing         | 不要                       | 要（多个序列拼接起来）         | 有风险，需额外防护     | 复杂           |
| Padding-free    | 不要                       | 否（序列独立存放，但连续存储） | 无风险                 | 相对简单，高效 |

代码实现在文章最后小节

## 一、Padding

传统padding方式训练时候：

- 每一个批次里会有多个输入序列。
- 每个序列必须一样长，不够长的就在后面加特殊token补齐（padding token）。
- 比如：

```
[序列1]：A，B，C，_, _  
[序列2]：D，E，F，G，H
```

这里序列1只有3个token，不够长，后面用padding token填充（用 _ 表示），直到和序列2长度一样（5个token）。

问题：浪费时间在这些什么用也没有的padding token上。



**为什么一定要padding？为什么要强求batch中序列长度相同？**

这是因为目前主流的显卡并行计算机制要求输入数据维度是统一的：

- GPU硬件最擅长处理**统一大小的矩阵运算**。你提供给GPU的数据（tensor）长度不一致，就无法一次性加载到GPU中批量并行计算。
- 为了更好地利用GPU并行计算优势，训练过程都是**批量输入一整个batch的数据**，所有数据必须统一维度，然后把一次batch全部扔到GPU里并行计算，才能显著提速。
- 传统方法中，因为每个batch要处理多条数据，而多条数据的长度不一致，因此必须用padding统一维度，这并非人为想加入padding，而是GPU计算特点决定的。

简单总结一下：

> 『padding的存在』**不是我们真的想放padding，而是GPU并行要求我们输入维度统一，我们被迫补padding统一序列长度，而这些padding数值是虚假数据，没有实际意义，因此才说这是浪费。**



虽然padding tokens（填充标记）不会对注意力计算产生影响（因为在attention里它们是被掩盖掉而不能被其他tokens看到的），但是它们实际上占据了真实的计算和内存资源。具体来说：

- 模型运行时，输入是一个**大小固定的tensor张量**（batch_size × seq_length）。
- 如果batch内有序列较短，就需要加入padding tokens补齐到batch内最长序列长度，这样导致了额外的空间开销。
- 模型计算的时候，其实是不管你是不是padding tokens，它们都会占据一定的GPU显存和计算量，只是在attention和loss计算过程中给它们“屏蔽”掉（mask掉），结果相当于浪费了计算和内存资源。
- 举例：

例如下面一个batch中有两个句子：

```
句子A: ["今天天气很好"]
句子B: ["我"]
```

格式化成batch输入（长度一致）：

```
批次：
[
  ["今天", "天气", "很", "好"],
  ["我", "PAD", "PAD", "PAD"]
]
```

尽管三个padding token不会产生有效的attention（注意力）或者loss信号，它们依然占用了：

- 计算资源：GPU仍旧需要执行每个位置的矩阵运算（只是我们主动mask掉了结果）。
- 内存资源：显存要放下这些padding token对应的embedding、 attention计算的临时矩阵数据。

因此在计算效率和内存利用率上就出现了浪费。因此，我们才会说padding是浪费资源的。

## 二、Packing

Packing方法中：

- 不是往每个序列后面补padding，而是把多个较短的序列连起来，拼成长序列以充分利用空间。
- 比如原本有3个较短的序列：

```
序列A（3 tokens）： A1，A2，A3  
序列B（2 tokens）： B1，B2  
序列C（4 tokens）： C1，C2，C3，C4
```

假如每个batch最大token数量是10，那么packing就把它们拼成一个序列：

```
A1 A2 A3 B1 B2 C1 C2 C3 C4
```

这样，我们完全不用padding token，充分利用了batch空间，计算没浪费了。

但Packing也有问题：

- 由于序列们拼在了一起，原本不相关的句子之间可能会互相干扰，这种情况叫作“跨序列污染（cross-contamination）”。
- 要防止跨序列污染，必须专门设置“屏蔽掩码(mask)”（比如block-diagonal masking），但多数框架不专门这么做，因为这样做很麻烦，复杂度高而且实现难度较大。
- 因此很多现成框架简单做的Packing方案可能会导致性能下降，且更适合那些明确带分界标记的序列，比如chat模板形式。

**跨序列污染**

跨序列污染（cross-contamination）通常指的是在对语言模型进行训练时，模型错误地从一个序列（或一个训练样本）的信息“泄露”到了另一个序列，导致模型可能产生错误的学习或不恰当的输出。

换个更好的方式来说明：

假设我们在训练一个语言模型，原本我们希望：

- 训练样本A就是：“北京的天气怎么样？”
- 训练样本B是：“上海有哪些著名景点？”

理想情况下，模型在训练时只使用各自序列内部的信息：

```
样本A：[北京 的 天气 怎么样]       <--- 只内部互相关注
样本B：[上海 有 哪些 著名 景点]     <--- 只内部互相关注
```

但是在Packing策略中，我们为了提高计算利用率，可能会把多个训练样本拼接到一起，比如拼成：

```
[北京 的 天气 怎么样 上海 有 哪些 著名 景点]
```

如果使用传统的attention mask（注意力掩码，一种控制模型如何允许信息流动的方式）是左往右全开的，例如每个词可以关注前面所有词，那么紧随其后的“上海 有 哪些...”的token可能会看到并考虑到前面的“北京的天气怎么样”的信息。这意味着“上海景点”这个问题在训练过程中可能不小心借用了“北京天气”的上下文信息。

这样一来，原本相互独立的两个训练样本（例如两个互不相关的问题）之间就出现了信息的混合，即为“跨序列污染”。



**跨序列污染带来的问题**

跨序列污染会导致训练过程存在误导：

1. 模型可能学会依赖前面其他样本的信息，模型的泛化能力变差。
2. 当模型用于实际应用时，输入的单个样本就是独立的。这时可能导致模型无法正确预测，其表现比预期差。
3. 如果训练样本之间内容特别不相关（比如前一个问题是天气，后一个问题是美食推荐），模型在训练中获得的信号就变得混乱，会损害模型学习到的语义结构。

## 三、Padding-free

Padding-free是最近提出的一种策略，它：

- 也像Packing一样，把所有序列紧密压缩进连续空间，没有padding。
- 但和Packing重要的区别是：
  - Padding-free并不会把多个不同的序列拼接成一个长序列，而是把多个序列压平成一维tensor，但同时很明确地记录每个序列的边界信息（例如用了cu_seqlens这个特殊数组记录每个序列从哪里到哪里）。
  - Padding-free利用一种特殊的高效attention机制（如FlashAttention 2），让模型在计算attention时自动知道每一个序列从哪儿到哪儿，天然避免序列之间互相“看到”，天然避免了跨序列污染（不需要人为单独做复杂的attention_mask）。

也就是说：

- Packing是简单粗暴地把短的序列串在一起变成长序列，但可能需要复杂的方法去防止跨序列干扰，稍微复杂麻烦些。
- Padding-free则是新的机制，天然就防止了不同序列之间的相互影响，每个序列独立且完全隔离，简单干净一些。



**Padding-free的实现机制**

- Padding-free 本质上并没有真的把多个序列强行补成同一长度，而是将多个长短不一的序列**打平**（展平成一维数组），然后用一个**额外的长度标记数组（cu_seqlens）**记录每个序列的边界位置。
- 当配合FlashAttention等先进attention算法时，这种attention算法天然支持『长度可变』的序列输入，并且自动处理好每条序列的内部关注关系。
- 因此它既能收获GPU大规模并行计算的优势，又避免了padding token额外占资源的浪费问题，可谓是“鱼和熊掌兼得”。



**padding-free需要需要的注意力机制**

我们前面讨论到：

- 传统注意力（如Transformer原始实现）在GPU上通常处理固定shape的tensor。
- padding-free方式把序列们展平成一个连续的一维向量（称为flattened contiguous tensor），并用额外的序列起止位置标记（即`cu_seqlens`）来记录每个序列的边界位置。
- 传统普通的注意力实现不知道如何根据`cu_seqlens`进行变长序列的划分和attention计算。

因此 padding-free 需要 **支持变长序列的特殊attention机制** 来做到这一点。



**FlashAttention在padding-free中的作用**

简单来说，FlashAttention 做了下面这几件事：

1. **原生支持不规则序列长度**：
   FlashAttention天然支持传入一个展平成连续的一维张量的token序列，同时配合序列长度信息（cu_seqlens），就能“自动”识别出哪些token属于哪个序列。
2. **自动处理序列边界 isolation**：
   它利用cu_seqlens这个辅助信息，自动处理好序列间的边界，使attention只会发生在各个序列自己内部，从根本上避免跨序列的污染。
3. **更高效的计算和内存利用**：
   由于没有padding浪费，也不需要额外的attention mask，它的计算量和内存占用都更小、更高效。



**padding-free的attention计算示意：**

假设我们有两个序列，以cu_seqlens = [0, 4, 9]标记：

```
tokens：[北京, 的, 天气, 怎么样, 上海, 有, 哪些, 著名, 景点]
序列A: tokens[0:4] 北京 的 天气 怎么样
序列B: tokens[4:9] 上海 有 哪些 著名 景点
```



FlashAttention通过cu_seqlens会自动划分成：

- Attention内关系1（序列A内部之间）：
  北京、的、天气、怎么样互相看到 ；
  不会看到上海及之后的token 。
- Attention内关系2（序列B内部之间）：
  上海、有、哪些、著名、景点互相看到 ；
  不会看到序列A的信息 。

而普通的传统attention实现本身无法做到上述事情（不认识 cu_seqlens 标记），因此padding-free依赖于FlashAttention这类专门为其设计的机制、或者其他类似的高效变长序列支持机制。

**目前padding-free实践中普遍用到的：**

- Hugging Face的TRL训练框架提供padding-free支持，底层采用FlashAttention。
- NVIDIA提供高优化的FlashAttention kernel来支持padding-free。
- 你当前阅读的文章里作者也明确提到TRL配合FlashAttention使用了这个padding-free策略。

## 

## 四、padding-free发挥优势的场景

**当batch size大于1时，padding-free 才能体现它的性能优势**

在padding-free场景下，每个batch的数据是通过连续flatten（打平）方式连接，并使用特殊技术（cu_seqlens、FlashAttention）区分各个样本的边界的。因此：

- 当 **batch size = 1** 时，每个batch中实际上就只有**一个样本**：

  - 此时无需进行padding（每批次单一序列，不存在序列间padding需求）。
  - padding-free的机制（即通过cu_seqlens划分序列边界、减少padding浪费）根本发挥不出来优势（因为本来就不需要padding了）。

  **结论：batch size 为 1时，实际上 padding-free 与传统 padding 表现无区别。**

- 当**batch size > 1** 时，每个batch内至少包含两个以上的序列：

  - 若这些序列长度不一致，传统padding会补齐到统一最大长度，浪费计算资源。
  - 而padding-free不需要pad，每次batch中不同序列紧密堆叠，节省padding token占据的资源和计算开销。因此，这时候padding-free的效率优势就能体现出来。



比如有两个样本，假设最大长度为 8：

- 样本A长度=3个字
- 样本B长度=7个字

**① 如果batch size = 1：**

每个batch单独处理一个样本，就不存在padding问题：

| 批次 | 数据   | padding情况 | 浪费条件 | padding-free是否更好？ |
| ---- | ------ | ----------- | -------- | ---------------------- |
| 1    | A(3字) | 无须padding | 无浪费   | ❌ padding-free无优势   |
| 2    | B(7字) | 无须padding | 无浪费   | ❌ padding-free无优势   |

此时padding-free根本没比传统padding好（事实上传统padding在单样本batch时也无需真正加padding）。

**② 如果batch size = 2：**

两个样本同时放入一个batch：

- 传统padding：

  - 必须补padding把两个样本对齐长度至7（最长序列B的长度）：

  ```
  A: [X, X, X, PAD, PAD, PAD, PAD]
  B: [Y, Y, Y, Y,   Y,   Y,   Y ]
  ```

  

  有4个 PAD token浪费GPU资源。

- padding-free：

  - 不用pad直接压平成一维tensor：

  ```
  [X, X, X, Y, Y, Y, Y, Y, Y, Y]
  ```

  

  节省了padding空间，无浪费。

此时padding-free真正体现优势了，**因此batch size>1时padding-free才真正有价值**。



**针对VLM的模型的场景**

| 分类                      | 场景举例或特征                                               | 建议                             | 适用程度 |
| ------------------------- | ------------------------------------------------------------ | -------------------------------- | -------- |
| 适合padding-free的VLM场景 | - 视觉问答(VQA)：不定长文本输入，大batch时padding明显浪费；<br>- 多轮跨模态对话：不定长文本输入，padding浪费巨大；<br>- 图像描述任务：大量长短不一的文本输入，需要避免padding。 | 推荐考虑padding-free方案         | 较为适合 |
| 不太适用的场景            | - 图像分类任务：无文本或只有短固定长度文本，无明显padding浪费；<br>- 图像配固定短文本的任务：padding-free优势不显著。 | padding-free意义不大，需慎重考虑 | 较不适合 |

视觉语言模型（VLM）有个非常关键的特点：

**输入通常包含文本序列 + 图像数据（图像通常是经过视觉编码器编码成图像特征序列）**。

因此，VLM模型的真实数据结构通常如下：

- 【文本】：长度可变的tokens

  ```
  [token1, token2, ..., tokenN.TEXT]
  ```

- 【图像】：长度固定的patches tokens序列（如ViT处理后的图像patches embeddings）

  ```
  [img_patch1, img_patch2, ..., img_patchN.IMAGE]
  ```

典型VLM输入可能类似这样：

```
[ [image tokens...] + [text tokens...] ]
```

也就是说，**「图像」部分通常不是变长的序列，而是固定长度的向量序列**。（例如，ViT类视觉编码器通常将图片分割成固定数量patches，比如16x16的分割块，不同图片输进模型时长度是一样的。）

此时，padding-free所解决的“每个batch序列长短不一导致padding浪费”的问题，可能就不像纯文本时那么明显了——因为你的**图像部分是固定尺寸的**：

- VLM的batch输入图像部分通常长度固定，根本无需padding。

- padding-free在图像序列处理上的优势不明显（本质上用padding-free或padding都一样）。

  

虽然VLM图像端无优势，但文本端可能是『不定长的序列』：

- 有些VLM任务（如视觉问答VQA、图像说明Caption任务）的文本端序列本身就长度不定（问题长短、答案长短都不一）。
- 此时，如果你设置了较大batch size，对文本端确实可能造成大量padding浪费。
- 利用padding-free可以在『文本端』节约显存和计算资源，使整体训练效率提升。



## 五、代码实现

###  训练效率对比（packing vs padding vs padding-free）

| 方法         | 已处理steps | 总steps | 已用时长 | 预计剩余时长 | 速度（it/s） | epoch完成比例 |
| ------------ | ----------- | ------- | -------- | ------------ | ------------ | ------------- |
| packing      | 3           | 129     | 1分55秒  | 4小时2分20秒 | 0.01         | 0.02/1 ≈ 2%   |
| padding      | 3           | 235     | 1分18秒  | 5小时4分0秒  | 0.01         | 0.01/1 ≈ 1%   |
| padding-free | 30          | 235     | 22分41秒 | 2小时46分7秒 | 0.02         | 0.12/1 ≈ 12%  |

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
set_seed(1234)

compute_dtype = torch.bfloat16
attn_implementation = 'flash_attention_2'

def fine_tune(batch_method):
  model_name = "meta-llama/Llama-3.1-8B"
  tokenizer = AutoTokenizer.from_pretrained(model_name)
  tokenizer.pad_token = "<|finetune_right_pad_id|>"
  tokenizer.pad_token_id = 128004
  tokenizer.padding_side = 'right'

  ds_train = load_dataset("allenai/tulu-3-sft-mixture", split="train[:120000]")

  # Apply the chat template from TULU's tokenizer
  tokenizer_name_chat_template = "allenai/Llama-3.1-Tulu-3-8B"
  tokenizer_chat = AutoTokenizer.from_pretrained(tokenizer_name_chat_template)
  def process(row):
      row["text"] = tokenizer_chat.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
      return row

  ds_train = ds_train.map(
      process,
      num_proc= multiprocessing.cpu_count(),
      load_from_cache_file=False,
  )

  print(ds_train[0]['text'])

  ds_train = ds_train.remove_columns(["messages"])

  model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map={"": 0}, torch_dtype=compute_dtype, attn_implementation=attn_implementation
  )
  model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})


  peft_config = LoraConfig(
          lora_alpha=16,
          lora_dropout=0.05,
          r=16,
          bias="none",
          task_type="CAUSAL_LM",
          target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"],
          modules_to_save = ["embed_tokens", "lm_head"]
  )


  if batch_method == "padding_free":
    packing = False
    padding_free = True
    output_dir = "./sft_padding_free/"
  elif batch_method == "packing":
    packing = True
    padding_free = False
    output_dir = "./sft_packing/"
  else:
    packing = False
    padding_free = False
    output_dir = "./sft_padding/"



  training_arguments = SFTConfig(
          output_dir=output_dir,
          optim="paged_adamw_8bit",
          per_device_train_batch_size=4,
          gradient_accumulation_steps=32,
          
          log_level="debug",
          save_strategy="epoch",
          logging_steps=25,
          learning_rate=1e-4,
          bf16 = True,
          num_train_epochs=1,
          warmup_ratio=0.01,
          lr_scheduler_type="linear",
          dataset_text_field="text",
          max_seq_length=1024,
          packing=packing,
          padding_free=padding_free,
          report_to="none"
  )

  trainer = SFTTrainer(
          model=model,
          train_dataset=ds_train,
          peft_config=peft_config,
          processing_class=tokenizer,
          args=training_arguments,
  )

  #--code by Unsloth: https://colab.research.google.com/drive/1Ys44kVvmeZtnICzWz0xgpRnrIOjZAuxp?usp=sharing#scrollTo=pCqnaKmlO1U9

  gpu_stats = torch.cuda.get_device_properties(0)
  start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
  max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
  print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
  print(f"{start_gpu_memory} GB of memory reserved.")

  trainer_ = trainer.train()


  used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
  used_memory_for_trainer= round(used_memory - start_gpu_memory, 3)
  used_percentage = round(used_memory         /max_memory*100, 3)
  trainer_percentage = round(used_memory_for_trainer/max_memory*100, 3)
  print(f"{trainer_.metrics['train_runtime']} seconds used for training.")
  print(f"{round(trainer_.metrics['train_runtime']/60, 2)} minutes used for training.")
  print(f"Peak reserved memory = {used_memory} GB.")
  print(f"Peak reserved memory for training = {used_memory_for_trainer} GB.")
  print(f"Peak reserved memory % of max memory = {used_percentage} %.")
  print(f"Peak reserved memory for training % of max memory = {trainer_percentage} %.")
  print("-----")
  #----
```

**packing的效果：**

```
fine_tune("packing")
```

```
Using auto half precision backend
No label_names provided for model class `PeftModelForCausalLM`. Since `PeftModel` hides base models input arguments, if label_names is not given, label_names can't be set automatically within `Trainer`. Note that empty label_names list will be used instead.
Currently training with a batch size of: 4
skipped Embedding(128256, 4096): 501.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped Embedding(128256, 4096): 1002.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped: 1002.0M params
***** Running training *****
  Num examples = 65,934
  Num Epochs = 1
  Instantaneous batch size per device = 4
  Total train batch size (w. parallel, distributed & accumulation) = 512
  Gradient Accumulation steps = 128
  Total optimization steps = 129
  Number of trainable parameters = 1,092,616,192
GPU = NVIDIA H100 NVL. Max memory = 93.115 GB.
17.074 GB of memory reserved.
`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`.
```

需要的时间： [ 3/129 01:55 < 4:02:20, 0.01 it/s, Epoch 0.02/1]

padding的效果：

```
fine_tune("padding")
```

```
Using auto half precision backend
No label_names provided for model class `PeftModelForCausalLM`. Since `PeftModel` hides base models input arguments, if label_names is not given, label_names can't be set automatically within `Trainer`. Note that empty label_names list will be used instead.
Currently training with a batch size of: 4
The following columns in the Training set don't have a corresponding argument in `PeftModelForCausalLM.forward` and have been ignored: source, text, id. If source, text, id are not expected by `PeftModelForCausalLM.forward`,  you can safely ignore this message.
skipped Embedding(128256, 4096): 501.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped Embedding(128256, 4096): 1002.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped: 1002.0M params
***** Running training *****
  Num examples = 120,000
  Num Epochs = 1
  Instantaneous batch size per device = 4
  Total train batch size (w. parallel, distributed & accumulation) = 512
  Gradient Accumulation steps = 128
  Total optimization steps = 235
  Number of trainable parameters = 1,092,616,192
GPU = NVIDIA H100 NVL. Max memory = 93.115 GB.
17.074 GB of memory reserved.
`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`.
```

需要的时间：[ 3/235 01:18 < 5:04:00, 0.01 it/s, Epoch 0.01/1]

**padding_free的效果：**

```
fine_tune("padding_free")
```

```
Using auto half precision backend
No label_names provided for model class `PeftModelForCausalLM`. Since `PeftModel` hides base models input arguments, if label_names is not given, label_names can't be set automatically within `Trainer`. Note that empty label_names list will be used instead.
Currently training with a batch size of: 4
The following columns in the Training set don't have a corresponding argument in `PeftModelForCausalLM.forward` and have been ignored: text, source, id. If text, source, id are not expected by `PeftModelForCausalLM.forward`,  you can safely ignore this message.
skipped Embedding(128256, 4096): 501.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped Embedding(128256, 4096): 1002.0M params
bitsandbytes: will optimize Embedding(128256, 4096) in fp32
skipped: 1002.0M params
***** Running training *****
  Num examples = 120,000
  Num Epochs = 1
  Instantaneous batch size per device = 4
  Total train batch size (w. parallel, distributed & accumulation) = 512
  Gradient Accumulation steps = 128
  Total optimization steps = 235
  Number of trainable parameters = 1,092,616,192
GPU = NVIDIA H100 NVL. Max memory = 93.115 GB.
17.074 GB of memory reserved.
`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`.
```

需要的时间： [ 30/235 22:41 < 2:46:07, 0.02 it/s, Epoch 0.12/1]

