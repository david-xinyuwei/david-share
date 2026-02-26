## The Nature and Code Implementation of Continuous Pretraining (CPT)

**一、预训练、继续预训练和微调。**

让我们来介绍一下这三个概念：预训练、继续预训练（Continued Pretraining）和微调。

- 预训练是使用随机初始化的权重从头开始训练模型的过程。这个过程通常发生在模型训练的初始阶段，目的是让模型学习到一些通用的知识和模式。最近的基础大型语言模型 (LLM) 是在数万亿个 token 上进行预训练的。预训练数据通常是从 Web 中提取的文本，不针对任何特定领域或任务。

- 继续预训练是在一个已经预训练过的模型基础上继续进行预训练的过程。这个过程通常发生在一个模型已经在一个大型的通用数据集上训练过，但是希望模型能更好地理解特定的领域或类型的数据时。从技术上讲，继续进行预训练的模型的权重不再是随机的，因为它们已经在预训练阶段得到了训练。当我们想要教预训练的 LLM 一门新语言或非常具体的领域（我们拥有数百万个 token）时，持续预训练尤其有用。您可以将其视为微调，但没有任何特定任务。

- 微调是在权重已经基于某些数据进行训练的模型上执行的。微调不一定涉及标记数据，但事实上，如今它基本上是用标记数据集执行的。微调的主要思想是利用预训练模型学习到的知识，通过细微的参数调整，使模型在新的任务上获得更好的性能。对于微调，我们需要训练示例来说明我们的目标任务。例如，对于二元分类任务，我们需要一个与标签 0 或 1 配对的标记序列。我们希望模型能够在给定标记序列的情况下学习标签。对于指令微调，我们需要提示和答案的配对。我们希望模型能够在给定提示的情况下学习答案。

   

总的来说，预训练、继续预训练和微调都是模型训练的重要步骤，它们都涉及到在大量数据上训练模型以提取有用的特征和知识。但是，它们的关注点和应用场景有所不同：预训练关注的是从大量通用数据中学习通用知识，继续预训练则关注的是在已有的预训练模型基础上，进一步学习特定领域或类型的知识，而微调则关注的是在已有的预训练模型基础上，通过细微的参数调整，使模型在新的任务上获得更好的性能。

在实践中，例如，如果我们想将基础 LLM 变成日本法律助理，那么继续对用日语撰写的法律文件中的数百万个标记进行预训练将使 LLM 在法律领域和日语方面表现得更好。

继续预训练和微调这两个概念之间的边界确实有些复杂。让我们再次回顾一下：

- 继续预训练：这是在已经预训练过的模型基础上，使用大量的未标记数据进行进一步的训练。这个过程的目标是让模型更好地理解特定的领域或类型的数据，而不是针对任何特定的任务。例如，如果我们有一个在英语互联网文本上预训练的模型，我们可能会在医学文本上进行继续预训练，以便模型能够更好地理解医学术语和概念。
- 微调：这是在已经预训练过的模型基础上，使用相对较小的标记数据集进行进一步的训练。需要注意的是，虽然可以可以使用未打标签的数据做微调，但现在做微调通常使用打标签的数据集。这个过程的目标是让模型能够执行特定的任务。例如，我们可能会在一个包含医学问题和对应答案的数据集上进行微调，以便模型能够回答医学相关的问题。



所以，边界在于：

- 数据的类型：继续预训练使用的是大量的未标记数据，而微调使用的是相对较小的标记数据。
- 目标：继续预训练的目标是让模型更好地理解特定的领域或类型的数据，而微调的目标是让模型能够执行特定的任务。



那我们回到日语训练的这个场景，看一下数据集到底是有标签还无标签的。

HuggingFaceFW/fineweb-edu

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXuKlzcwrFh9ubbjR0YrsRiarDR33nXIIZwxichlova8J15sDr0LKhAen1T7HZcanoSURHE63Hibg8hQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

让我们来分析一下图片中展示的数据集。

### 数据集字段说明

 

1. **text**:
   - **类型：** 字符串（string）
   - **描述：** 文本数据的内容，可能是从网页或其他文档中提取的段落。
2. **id**:
   - **类型：** 字符串（string）
   - **描述：** 唯一标识符（UUID），用于唯一标识每条记录。
3. **dump**:
   - **类型：** 类别（classes）
   - **描述：** 数据来源的类别。在这个数据集中，所有记录都来自 "CC-MAIN-2013-20"。
4. **url**:
   - **类型：** 字符串（string）
   - **描述：** 数据来源的URL，指向原始网页。
5. **file_path**:
   - **类型：** 字符串（string）
   - **描述：** 文件路径，指向数据存储的位置。
6. **language**:
   - **类型：** 类别（classes）
   - **描述：** 文本的语言。在这个数据集中，所有记录都是英文（"en"）。
7. **language_score**:
   - **类型：** 浮点数（float64）
   - **描述：** 语言识别的置信度分数，表示文本被识别为某种语言的置信度。
8. **token_count**:
   - **类型：** 整数（int64）
   - **描述：** 文本的标记（token）数量，表示文本中单词或符号的数量。
9. **score**:
   - **类型：** 浮点数（float64）
   - **描述：** 评分，可能是对文本质量或相关性的评分。
10. **int_score**:
    - **类型：** 整数（int64）
    - **描述：** 整数评分，可能是对文本质量或相关性的另一个评分标准。

### 数据分析

 

- **数据量：** 数据集包含 1.28B 行，这意味着这是一个非常大规模的数据集。
- **字段分布：** 大多数字段的值都是均匀分布的，例如 `language` 字段中的所有记录都是 "en"，表示文本都是英文。`dump` 字段中的所有记录都是 "CC-MAIN-2013-20"，表示数据来源相同。
- **文本长度：** `text` 字段的长度从 150 到 59.3k 字符不等，显示了文本数据的多样性。
- **标记数量：** `token_count` 字段显示文本的标记数量，从 35 到 16k 不等，表示文本的长度和复杂性。
- **评分：** `language_score` 和 `score` 字段提供了对文本的评分，可能用于评估文本质量或语言识别的置信度。大多数记录的 `language_score` 在 0.86 到 0.89 之间，表示高置信度。

### 结论

 
这个数据集主要包含从网页或文档中提取的文本数据，每条记录都有唯一标识符、数据来源、URL、文件路径、语言、语言置信度评分、标记数量、文本评分等信息。尽管这些字段提供了丰富的上下文信息，但它们并没有提供明确的输入-输出对，因此应被视为**未标记数据**。这些数据可以用于无监督学习任务或进一步的数据处理和分析。



**二、继续深挖持续预训练与微调**

从技术角度来看，持续预训练其实是一种微调。我们的目标是让模型更好地适应特定的领域。持续预训练和微调的主要区别在于所使用的数据集的性质和目标不同。

微调需要具体的训练示例来展示我们的目标任务。例如，在二元分类任务中，我们需要有标记序列和对应的标签（0或1）。这样模型才能在给定标记序列的情况下学会预测标签。对于指令微调，我们需要提示和答案的配对，目的是让模型在给定提示时学会生成正确的答案。

而持续预训练的目标只是让模型的权重适应新的领域，不涉及具体任务。我们只需要目标领域中的任何文本数据就可以了。比如，如果我们想把基础LLM变成一个日本法律助理，我们可以用日语法律文件中的大量标记来进行预训练，这样LLM在法律领域和日语方面的表现会更好。预训练结束后，我们可以用日语法律领域的指令数据集对模型进行微调，让它成为专门服务于该领域的聊天机器人。这个微调数据集会比较小。如果我们在没有进行持续预训练的情况下直接在这个数据集上微调基础LLM，模型可能很难生成日语并理解法律术语。



持续预训练在超参数设置上也和微调略有不同，特别是如果我们使用LoRA或QLoRA。因为我们希望模型适应新的领域或语言，所以必须更新标记嵌入和语言模型头，以确保模型能更好地模拟基础LLM预训练数据中很少见的领域内标记和术语。如果使用LoRA或QLoRA，还建议使用比平常更高的等级，即增加更多可训练参数，以确保适配器有足够的能力学习新的领域特征。



核心代码如下：

```

#I load a pre-quantized version of Llama 3, llama-3-8b-bnb-4bit. You can also load the standard version. The only difference is that llama-3-8b-bnb-4bit is faster to download
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)


model = FastLanguageModel.get_peft_model(
    model,
    r = 128,
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",
                      "embed_tokens", "lm_head",], # Add for continual pretraining
    lora_alpha = 32,
    lora_dropout = 0, # Supports any, but = 0 is optimized
    bias = "none",    # Supports any, but = "none" is optimized
    use_gradient_checkpointing = "unsloth", # True or "unsloth" for very long context
    random_state = 3407,
    use_rslora = True,
)


dataset = load_dataset("HuggingFaceFW/fineweb-edu", "sample-10BT", split = "train[:10%]",)

trainer = UnslothTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 8,

    args = UnslothTrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 8,
        warmup_ratio = 0.1,
        max_steps = 2000,

        # Select a 2 to 10x smaller learning rate for the embedding matrices!
        learning_rate = 5e-6,
        embedding_learning_rate = 1e-6,

        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 10,
        save_steps = 100,
        save_total_limit = 10,
        optim = "adamw_8bit",
        weight_decay = 0.00,
        lr_scheduler_type = "cosine",
        seed = 3407,
        output_dir = "./Llama-3-8B-fineweb-edu-r128a32wd0lstcosinelr5e06-10BT",
    ),
)

trainer_stats = trainer.train()

```

上面的代码中，与标准 QLoRA 微调的区别大致如下：

- **r=128** ：我们希望为模型提供足够的容量来学习新知识。可训练的参数越多越好。这就是为什么对于持续的预训练，最好使用高rank，即高于常用于 LoRA 微调的rank。
- **“embed_tokens”、“lm_head”** ：继续预训练希望模型学习新的 token 嵌入，以便更好地模拟训练数据中的特定域内术语或单词。需要完全微调 token 嵌入和语言建模头。
- **use_rslora = True** ：使用ranked stabilized LoRA。
- **dataset = load_dataset("HuggingFaceFW/fineweb-edu", "sample-10BT", split = "train[:10%]")** : 在 FineWeb-Edu 上进行预训练。我使用了 Hugging Face 发布的最小样本，但仍然非常大（10B 个 token）。
- **embedding_learning_rate = 1e-6** ：Unsloth 建议对embeddings使用较低的学习率。因为嵌入已经在数十亿个标记上进行了预训练，不需要过于积极地更新它们。



持续的预训练对于 LLM 准备在预训练期间很少见到的领域或语言中的任务非常重要。

另一方面，如果对 LLM 已经基本掌握的领域的数据进行持续的预训练，则不会产生太大影响。

此外，由于需要大量数据，持续的预训练成本可能相当高。借助 QLoRA 和 Unsloth，我们可以加快预训练速度，同时提高内存效率。

**三、LoRA与rsLoRA的区别**

LoRA（低秩适应）是一种微调大型语言模型（LLM）的方法，它通过向模型添加少量可训练参数，同时保持原始模型参数不变。具体来说，LoRA通过将一个大的权重矩阵分解为两个较小的权重矩阵，以更高的参数效率近似实现完全的有监督微调。在实践中，LoRA使用非常低的秩（例如4到32），这对于例如Mistral 7B或Llama 2 7B等模型来说，远低于它们的模型维度4096。

然而，LoRA的一个限制是，当适配器的秩增加时，性能并没有进一步提高。这主要是因为在非常低的适配器秩之外，LoRA的学习受到了限制。

Rank-Stabilized LoRA（rsLoRA）是一种改进的LoRA方法，它通过简单地将LoRA适配器除以其秩的平方根来纠正这个限制。这意味着，与LoRA相比，rsLoRA能够更好地利用更高的适配器秩，从而实现更好的性能。

总的来说，rsLoRA和LoRA的主要区别在于，rsLoRA通过稳定化秩来解决LoRA在高秩下的性能饱和问题，从而实现了更好的微调性能。这使得rsLoRA在某些情况下，能够比LoRA获得更好的性能。此外，rsLoRA方法现已在Hugging Face的PEFT包中可用。

参考链接：https://kaitchup.substack.com/p/continued-pre-training-llama-3-and