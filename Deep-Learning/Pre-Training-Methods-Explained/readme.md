# Pre-Training Methods Explained

This article provides a comprehensive guide to pre-training methods for large language models (LLMs), covering the fundamental concepts of pre-training vs fine-tuning, continuous pre-training (CPT), instruction pre-training with synthetic data, code demonstrations, and distributed training tools.

---

## Table of Contents

- [Part I: Pre-Training, Continuous Pre-Training, and Fine-Tuning — Core Concepts](#part-i-pre-training-continuous-pre-training-and-fine-tuning--core-concepts)
- [Part II: Pre-Training Code Demonstration (GPT-2)](#part-ii-pre-training-code-demonstration-gpt-2)
- [Part III: The Nature and Code Implementation of Continuous Pre-Training (CPT)](#part-iii-the-nature-and-code-implementation-of-continuous-pre-training-cpt)
- [Part IV: Instruction Pre-Training — Synthetic Data Approach](#part-iv-instruction-pre-training--synthetic-data-approach)
- [Part V: Fine-Tuning Methods Comparison](#part-v-fine-tuning-methods-comparison)
- [Part VI: Distributed Implementation of Training](#part-vi-distributed-implementation-of-training)

---

## Part I: Pre-Training, Continuous Pre-Training, and Fine-Tuning — Core Concepts

The goals of pre-training, the datasets used, and the number of GPUs required are all different. However, if we are to explain the difference from the essence of deep learning training, it is:

**Pre-training involves randomly initializing model parameters, constructing the model, and then training it on a large amount of unlabeled data to learn general features of the corpus; whereas fine-tuning loads parameters from the pre-trained model, retains the general features learned during pre-training, and trains the model on a small amount of high-quality labeled data to enhance the model's capability and performance on specific tasks.**

The parameters mentioned above include: weights, biases, Word Embeddings, Positional Encoding, attention mechanism parameters, etc.

### Pre-Training

**Pre-Training** aims to learn the fundamental structure and semantic features of a language using large-scale unsupervised datasets (such as text corpora). Pre-training typically involves the following steps:

1. **Random Initialization of Weights**: The model's parameters, such as weights and biases, are randomly initialized at the start of pre-training.
2. **Large-Scale Dataset**: Training is conducted using a vast amount of unsupervised data.
3. **Learning General Features**: The model learns the general features of the language by optimizing a loss function (e.g., the cross-entropy loss of a language model).

#### Key Points of Pre-Training

- **Random Initialization**: All model parameters (weights, biases, etc.) are random at the beginning of pre-training.
- **Large-Scale Data**: Training is done using a large-scale unsupervised dataset.
- **General Features**: The model learns the basic structure and semantic features of the language, providing a good starting point for subsequent tasks.

Recent foundation LLMs are pre-trained on trillions of tokens. Pre-training data is typically text extracted from the web, not targeted at any specific domain or task.

### Continuous Pre-Training (CPT)

**Continuous Pre-Training** is the process of continuing pre-training on a model that has already been pre-trained. This typically occurs when a model has already been trained on a large general dataset, but we want it to better understand a specific domain or type of data.

Technically, the weights of a continuously pre-trained model are no longer random, as they have been trained during the initial pre-training phase. CPT is especially useful when we want to teach a pre-trained LLM a new language or a very specific domain (where we have millions of tokens of domain data). You can think of it as fine-tuning, but without any specific task in mind.

For example, if we want to turn a base LLM into a Japanese legal assistant, continuously pre-training on millions of tokens from Japanese legal documents would make the LLM perform better in both the legal domain and the Japanese language. After CPT, we can fine-tune the model with a Japanese legal instruction dataset to create a chatbot specialized for that domain. This fine-tuning dataset would be relatively small. If we fine-tuned the base LLM directly on this small dataset without CPT, the model might struggle to generate Japanese text and understand legal terminology.

### Fine-Tuning

**Fine-Tuning** aims to optimize the model's performance on a specific task using a task-specific dataset. Fine-tuning typically involves the following steps:

1. **Loading Pre-Trained Weights**: The model's weights and biases are loaded from the pre-trained model.
2. **Task-Specific Data**: Training is conducted using a dataset specific to the task.
3. **Optimizing Task Performance**: The model adjusts its parameters by optimizing a loss function to improve performance on the specific task.

#### Key Points of Fine-Tuning

- **Loading Pre-Trained Weights**: The model's parameters are loaded from the pre-trained model, retaining the general features learned during pre-training.
- **Task-Specific Data**: Training is done using a dataset specific to the task.
- **Task Optimization**: The model's parameters are further adjusted to optimize performance on the specific task.

Fine-tuning does not necessarily involve labeled data, but in practice today it is basically performed with labeled datasets. For example, for a binary classification task, we need labeled sequences paired with labels (0 or 1). For instruction tuning, we need prompt-answer pairs so the model learns to generate correct answers given prompts.

### The Boundaries Between CPT and Fine-Tuning

The boundary between continuous pre-training and fine-tuning can be subtle:

| Dimension | Continuous Pre-Training | Fine-Tuning |
|-----------|------------------------|-------------|
| **Data Type** | Large amounts of unlabeled data | Relatively small labeled data |
| **Objective** | Better understanding of a specific domain or data type | Performing a specific task |
| **Weight Initialization** | Loaded from a pre-trained model | Loaded from a pre-trained model |
| **Task Specificity** | No specific task | Task-specific |

From a technical standpoint, continuous pre-training is actually a form of fine-tuning — the goal is to make the model better adapt to a specific domain. The key distinction lies in the nature of the datasets used and the training objective.

### Summary

1. **Training Efficiency**: Pre-training usually requires substantial computational resources and time because it involves training all model parameters on a large-scale dataset. Fine-tuning is relatively efficient as it builds on the pre-trained model and only requires further optimization on task-specific data.
2. **Model Performance**: The pre-trained model has already learned general language features, allowing fine-tuning to converge faster and perform better on specific tasks. Training a task-specific model from random initialization typically requires more data and time, and its performance may not match that of the pre-training + fine-tuning approach.
3. **Application Scenarios**: Pre-trained models can serve as general-purpose base models suitable for various downstream tasks. Fine-tuning allows for quick adaptation to different task requirements without the need to train a model from scratch. CPT bridges the gap when adapting to new domains or languages before task-specific fine-tuning.

---

## Part II: Pre-Training Code Demonstration (GPT-2)

*Reference: https://huggingface.co/docs/transformers/v4.44.0/en/model_doc/gpt2#transformers.GPT2LMHeadModel*

To pre-train GPT-2, we need to use the classes `GPT2LMHeadModel` and `GPT2Config`.

```python
# Create a new GPT-2 configuration
config = GPT2Config()

# Initialize the model from scratch
model = GPT2LMHeadModel(config)

# Initialize tokenizer
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token

# Load dataset
dataset = load_dataset("wikitext", "wikitext-2-raw-v1")

# Define tokenization function
def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512, return_special_tokens_mask=True)

# Tokenize the dataset
tokenized_datasets = dataset.map(tokenize_function, batched=True, remove_columns=["text"])

# Check dataset sizes
print("Train dataset size:", len(tokenized_datasets["train"]))
print("Validation dataset size:", len(tokenized_datasets["validation"]))

# Data collator
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

# Training arguments
training_args = TrainingArguments(
    output_dir="./results",
    overwrite_output_dir=True,
    num_train_epochs=5,
    per_device_train_batch_size=64,
    save_steps=10_000,
    save_total_limit=2,
    remove_unused_columns=False,
    report_to=[],
    learning_rate=5e-4
)

# Create Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    data_collator=data_collator,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"]
)

# Move model to GPU if available
if torch.cuda.is_available():
    model.cuda()

# Start training
trainer.train()
```

Since the model is small, pre-training can be done with a single H100 GPU:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXx2ibRcepjvLcJVtoKRQiaeXdYWRhDl8L5OClic6Sj6RxibicXtQaEgF0iaibbg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Training result is as following:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXx7daWmg4C8ziaIX8CCwt8rddGcLQKXYSODtEaPaDIsNTsy3h3mEuSIEg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Inference Validation

The trained model can be used for inference validation:

```python
# Load model and tokenizer
model = GPT2LMHeadModel.from_pretrained("./results/checkpoint-2870")
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

# Set pad_token
tokenizer.pad_token = tokenizer.eos_token

# Move model to GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Set model to evaluation mode
model.eval()

# Input text
input_text = "Once upon a time"

# Encode input text
inputs = tokenizer(input_text, return_tensors="pt", padding=True).to(device)

# Generate text
with torch.no_grad():
    outputs = model.generate(
        inputs.input_ids,
        attention_mask=inputs.attention_mask,
        max_length=100,
        num_return_sequences=1,
        no_repeat_ngram_size=2,
        early_stopping=True,
        temperature=0.7,
        top_p=0.9,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id
    )

# Decode generated text
generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(generated_text)
```

Inference result is as following:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXxcGkvLgsa0lxoLEjNT4VSZLya26x2xOUYia7E3CCKC2ic9Q1NXS8nOJYw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

---

## Part III: The Nature and Code Implementation of Continuous Pre-Training (CPT)

### 一、预训练、继续预训练和微调

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

### CPT Dataset Analysis: HuggingFaceFW/fineweb-edu

那我们回到日语训练的这个场景，看一下数据集到底是有标签还无标签的。

HuggingFaceFW/fineweb-edu

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXuKlzcwrFh9ubbjR0YrsRiarDR33nXIIZwxichlova8J15sDr0LKhAen1T7HZcanoSURHE63Hibg8hQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

让我们来分析一下图片中展示的数据集。

#### 数据集字段说明

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

#### 数据分析

- **数据量：** 数据集包含 1.28B 行，这意味着这是一个非常大规模的数据集。
- **字段分布：** 大多数字段的值都是均匀分布的，例如 `language` 字段中的所有记录都是 "en"，表示文本都是英文。`dump` 字段中的所有记录都是 "CC-MAIN-2013-20"，表示数据来源相同。
- **文本长度：** `text` 字段的长度从 150 到 59.3k 字符不等，显示了文本数据的多样性。
- **标记数量：** `token_count` 字段显示文本的标记数量，从 35 到 16k 不等，表示文本的长度和复杂性。
- **评分：** `language_score` 和 `score` 字段提供了对文本的评分，可能用于评估文本质量或语言识别的置信度。大多数记录的 `language_score` 在 0.86 到 0.89 之间，表示高置信度。

#### 结论

这个数据集主要包含从网页或文档中提取的文本数据，每条记录都有唯一标识符、数据来源、URL、文件路径、语言、语言置信度评分、标记数量、文本评分等信息。尽管这些字段提供了丰富的上下文信息，但它们并没有提供明确的输入-输出对，因此应被视为**未标记数据**。这些数据可以用于无监督学习任务或进一步的数据处理和分析。

### 二、继续深挖持续预训练与微调

从技术角度来看，持续预训练其实是一种微调。我们的目标是让模型更好地适应特定的领域。持续预训练和微调的主要区别在于所使用的数据集的性质和目标不同。

微调需要具体的训练示例来展示我们的目标任务。例如，在二元分类任务中，我们需要有标记序列和对应的标签（0或1）。这样模型才能在给定标记序列的情况下学会预测标签。对于指令微调，我们需要提示和答案的配对，目的是让模型在给定提示时学会生成正确的答案。

而持续预训练的目标只是让模型的权重适应新的领域，不涉及具体任务。我们只需要目标领域中的任何文本数据就可以了。比如，如果我们想把基础LLM变成一个日本法律助理，我们可以用日语法律文件中的大量标记来进行预训练，这样LLM在法律领域和日语方面的表现会更好。预训练结束后，我们可以用日语法律领域的指令数据集对模型进行微调，让它成为专门服务于该领域的聊天机器人。这个微调数据集会比较小。如果我们在没有进行持续预训练的情况下直接在这个数据集上微调基础LLM，模型可能很难生成日语并理解法律术语。

持续预训练在超参数设置上也和微调略有不同，特别是如果我们使用LoRA或QLoRA。因为我们希望模型适应新的领域或语言，所以必须更新标记嵌入和语言模型头，以确保模型能更好地模拟基础LLM预训练数据中很少见的领域内标记和术语。如果使用LoRA或QLoRA，还建议使用比平常更高的等级，即增加更多可训练参数，以确保适配器有足够的能力学习新的领域特征。

### CPT Code Implementation with Unsloth

核心代码如下：

```python
# Load a pre-quantized version of Llama 3
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
- **"embed_tokens"、"lm_head"** ：继续预训练希望模型学习新的 token 嵌入，以便更好地模拟训练数据中的特定域内术语或单词。需要完全微调 token 嵌入和语言建模头。
- **use_rslora = True** ：使用ranked stabilized LoRA。
- **dataset = load_dataset("HuggingFaceFW/fineweb-edu", "sample-10BT", split = "train[:10%]")** : 在 FineWeb-Edu 上进行预训练。我使用了 Hugging Face 发布的最小样本，但仍然非常大（10B 个 token）。
- **embedding_learning_rate = 1e-6** ：Unsloth 建议对embeddings使用较低的学习率。因为嵌入已经在数十亿个标记上进行了预训练，不需要过于积极地更新它们。

持续的预训练对于 LLM 准备在预训练期间很少见到的领域或语言中的任务非常重要。

另一方面，如果对 LLM 已经基本掌握的领域的数据进行持续的预训练，则不会产生太大影响。

此外，由于需要大量数据，持续的预训练成本可能相当高。借助 QLoRA 和 Unsloth，我们可以加快预训练速度，同时提高内存效率。

### 三、LoRA vs rsLoRA

LoRA（低秩适应）是一种微调大型语言模型（LLM）的方法，它通过向模型添加少量可训练参数，同时保持原始模型参数不变。具体来说，LoRA通过将一个大的权重矩阵分解为两个较小的权重矩阵，以更高的参数效率近似实现完全的有监督微调。在实践中，LoRA使用非常低的秩（例如4到32），这对于例如Mistral 7B或Llama 2 7B等模型来说，远低于它们的模型维度4096。

然而，LoRA的一个限制是，当适配器的秩增加时，性能并没有进一步提高。这主要是因为在非常低的适配器秩之外，LoRA的学习受到了限制。

Rank-Stabilized LoRA（rsLoRA）是一种改进的LoRA方法，它通过简单地将LoRA适配器除以其秩的平方根来纠正这个限制。这意味着，与LoRA相比，rsLoRA能够更好地利用更高的适配器秩，从而实现更好的性能。

总的来说，rsLoRA和LoRA的主要区别在于，rsLoRA通过稳定化秩来解决LoRA在高秩下的性能饱和问题，从而实现了更好的微调性能。这使得rsLoRA在某些情况下，能够比LoRA获得更好的性能。此外，rsLoRA方法现已在Hugging Face的PEFT包中可用。

*Reference: https://kaitchup.substack.com/p/continued-pre-training-llama-3-and*

---

## Part IV: Instruction Pre-Training — Synthetic Data Approach

### Concept of Instruction Pre-Training

[Instruction Pre-Training](https://huggingface.co/instruction-pretrain/instruction-synthesizer) is a new pre-training method proposed by Microsoft, which details how to generate and use synthetic instruction-response pairs to pre-train large language models (LLMs).

Traditional pre-training methods involve directly pre-training on raw corpora. In contrast, instruction pre-training enhances the raw text by generating instruction-response pairs through an instruction synthesizer. Microsoft's evaluation shows that LLMs pre-trained with instruction pre-training significantly outperform those pre-trained with standard methods across various tasks.

### Working Principle of the Instruction Synthesizer

Given raw text, the instruction synthesizer generates paired instructions and responses, which can be one-to-one or a few examples. Microsoft fine-tuned the instruction synthesizer using multiple datasets covering a wide range of tasks and domains.

### Process of Generating Instructions

Microsoft extracted 200M segments (200B tokens) of text samples from the RefinedWeb dataset. The instruction synthesizer generated instruction-response pairs from these samples, which were then re-input into the synthesizer to generate more examples. Ultimately, 200M instruction-response pairs were generated and mixed with the original samples for pre-training.

### Experimental Results

Microsoft conducted pre-training experiments on LLMs of different sizes. The results showed that models using instruction pre-training performed better on public benchmarks than those pre-trained only on raw text. They also conducted continued pre-training experiments, showing that the advantages of instruction pre-training vary by task.

### Using the Instruction Synthesizer to Generate Data

Microsoft has released the instruction synthesizer on the Hugging Face Hub and provided code examples. The article demonstrates how to use this code to generate instruction-response pairs for a financial dataset, which can be used for training or continued pre-training of models.

The current synthesizer model is based on the Mistral-7B model. The synthetic instruction-response pair method proposed by Microsoft is currently the best, outperforming previous methods like Ada-instruct. Future improvements can be made by fine-tuning larger models.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUMSkAQiczzr9ldMddDev90QewnWVvkKCUNs1dFGpdXo4Jdcw9BO6op0XicSxzjhmEFFSUxdL9Ra7ibg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Can Instruction Pre-Training Generate Labeled Data from Unlabeled Data?

Microsoft's instruction pre-training method can be used to generate labeled data from unlabeled data. Specifically, the instruction synthesizer can convert raw, unlabeled text into paired instructions and responses, thereby generating labeled data. This method can be applied to various tasks and domains, including but not limited to question answering, text classification, and named entity recognition. Below is a brief step-by-step guide on how to use the instruction synthesizer to generate labeled data:

1. **Prepare Raw Data**: Collect raw, unlabeled text data, such as financial news, social media posts, technical documents, etc.
2. **Load the Instruction Synthesizer Model**: Use the instruction synthesizer model released by Microsoft, available for download on the Hugging Face Hub. Install necessary dependencies like vLLM.
3. **Generate Instruction-Response Pairs**: Process the raw text using the instruction synthesizer model to generate paired instructions and responses. These pairs can be considered labeled data. For example, for a financial news snippet, the synthesizer might generate a question (instruction) and a corresponding answer (response), thereby labeling the snippet.
4. **Save the Generated Data**: Save the generated instruction-response pairs as a new dataset, which can be used for subsequent model training or evaluation.

### Can Instruction Pre-Training Completely Replace Manual Labeling?

While Microsoft's instruction pre-training method can generate a large number of question-answer pairs, thereby reducing the need for manual data labeling, it is still unrealistic to completely eliminate the need for manual labeling. Here are some factors to consider:

1. **Quality and Accuracy of Generated Data**: Automatically generated data may not be as accurate as manually labeled data. The generated question-answer pairs may contain errors or inaccuracies, especially when dealing with complex or ambiguous text. Therefore, manual review and correction of the generated data are still necessary.

2. **Domain-Specific Knowledge**: Some domains may require specific expertise, and automatically generated question-answer pairs may not fully capture these details. For example, texts in fields like medicine or law may require professional annotation to ensure data accuracy and reliability.

3. **Model Limitations**: Although instruction synthesizer models can generate high-quality question-answer pairs, they still have limitations. For example, the model may generate repetitive question-answer pairs or perform poorly when handling long texts. Human intervention can help identify and correct these issues.

4. **Diversity and Coverage**: Automatically generated question-answer pairs may lack diversity and coverage. Manual annotation can ensure that the dataset covers a wider range of scenarios and question types, thereby improving the model's generalization ability.

5. **Ethical and Legal Issues**: In some cases, automatically generated data may involve ethical and legal issues. For example, the generated question-answer pairs may contain sensitive information or violate privacy. Manual review can help identify and address these issues.

6. **Model Training and Evaluation**: Even if automatically generated data is used for initial training, manually labeled data is still needed for model evaluation and validation. This ensures the model's performance in the real world.

Therefore, the best practice is to combine automatic generation and manual annotation methods to obtain high-quality training data. This approach leverages the efficiency of automatic generation while ensuring data accuracy and reliability.

### Instruction Pre-Training Code Example

```bash
!pip install vllm
!git clone https://github.com/microsoft/LMOps.git
%cd LMOps/instruction_pretrain/
```

```python
from vllm import LLM, SamplingParams
from utils.read_compre import get_dataset, cook_pt_entries, run
from datasets import load_dataset
```

```python
raw_texts = load_dataset("ugursa/Yahoo-Finance-News-Sentences", split="train")
text_field = "text" # column of the dataset that contain the raw text

raw_texts = [text for text in raw_texts[text_field]]
print(f'Number of raw texts: {len(raw_texts)}')

STOP=5 # Stop after this many examples
raw_texts = raw_texts[:STOP]
max_model_len = 4096
max_new_tokens = 1000
sampling_params = SamplingParams(temperature=0, max_tokens=max_new_tokens)
llm = LLM(model="instruction-pretrain/instruction-synthesizer", max_model_len=max_model_len)
```

```python
N = len(raw_texts) # Number of raw texts
M = 2  # M-shot example

prev_examples = []
BSZ = (N+M-1)//M
for round in range(M):
    cur_raw_texts = raw_texts[round*BSZ: (round+1)*BSZ]
    # load data
    split = get_dataset(prev_examples=prev_examples,
                        cur_raw_texts=cur_raw_texts,
                        max_model_len=max_model_len,
                        max_new_tokens=max_new_tokens)
    prev_examples = run(split, llm, sampling_params)
```

```python
instruction_augmented_texts = []
for idx, entry in enumerate(prev_examples):
    texts = cook_pt_entries(read_collection=entry, random_seed=idx+1345)
    instruction_augmented_texts.extend(texts)
```

```python
for idx, text in enumerate(instruction_augmented_texts):
    print(f'## Instruction-augmented Text {idx+1}\n{text}\n')
```

In this context, M represents the number of examples generated, specifically the number of few-shot examples. More precisely, M indicates how many instruction-response pairs will be generated for each raw text segment during the pre-training process:

- **M = 2**: Each raw text segment will generate 2 instruction-response pairs. This setting is used for general pre-training from scratch, aiming to enhance the model's multitask learning capability without significantly increasing the data volume.
- **M = 3**: Each raw text segment will generate 3 instruction-response pairs. This setting is used for domain-adaptive continual pre-training, aiming to generate more examples to better adapt to specific domain requirements while maintaining a certain level of generality.

### Sample Output

```
## Instruction-augmented Text 1
China's CMOC Group, which boosted its cobalt output by 144% during the first three quarters of 2023, is now on track to become the world's biggest cobalt producer, overtaking commodity group Glencore. Curious minds, it's your turn! Answer these questions:

Problem: What is the CMOC Group?
Answer: China's CMOC Group

Problem: What did the CMOC Group increase by 144%?
Answer: its cobalt output

Problem: When did the CMOC Group increase its cobalt output by 144%?
Answer: during the first three quarters of 2023

Problem: Which company is the world's biggest cobalt producer?
Answer: Glencore

Problem: Which group is on track to become the world's biggest cobalt producer?
Answer: CMOC

## Instruction-augmented Text 2
Chinese-owned companies are aggressively expanding cobalt mining in Congo and Indonesia even while prices crash, as they bid to raise market share of the metal used in batteries for the country's electric vehicle (EV) industry. Curious minds, it's your turn! Answer these questions:

Q: What may be the reason for this expansion? ---- Available choices:
[+] They want to take over the EV industry.
[+] They can make more money that way.
[+] They own most of the cobalt mines.
[+] They need the metal for other uses.

A: They can make more money that way.

CMOC is due to lift its market share of the global mined cobalt market from 11% in 2022 to nearly 30% by 2025, said Jorge Uzcategui, an analyst at consultancy Benchmark Mineral Intelligence. Curious minds, it's your turn! Answer these questions:

Q: What may happen if CMOC does not meet it's goals? ---- Available choices:
[+] They will be put out of the company.
[+] They will be seen as incompetent.
[+] They will lose funding.
[+] They will be seen as unambitious.

A: They will be seen as incompetent.
```

### Synthetic Instructions with GPT-4o

*Refer to: https://github.com/Azure/synthetic-qa-generation.git*

---

## Part V: Fine-Tuning Methods Comparison

When we fine-tune a model, it usually refers to Supervised Fine Tuning (SFT). SFT can be divided into Parameter-Efficient Fine-Tuning (PEFT) and Full Fine Tuning. In PEFT implementations, methods like LoRA, QLoRA, and GA-LoRA are quite popular.

### Loading Models for Full Fine-Tuning

We use the `AutoModelForCausalLM.from_pretrained` class, which retrieves the parameters of the pre-trained model:

```python
model = AutoModelForCausalLM.from_pretrained(
    model_name, attn_implementation=attn_implementation, device_map={"": 0}
)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})
```

For the complete Full fine tuning code, refer to:
*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/SmolLM-Full-Fine-Tuning*

### Differences in Loading Models

1. **Full Fine-Tuning**
   - Directly load the complete model for training.
   - Use `AutoModelForCausalLM.from_pretrained` to load the model.
2. **LoRA**
   - Load the model and then use LoRA configuration for parameter-efficient fine-tuning.
   - Use `LoraConfig` from the `peft` library to configure LoRA parameters.
   - Target modules are usually specific projection layers, such as `k_proj`, `q_proj`, etc.
3. **QLoRA**
   - Based on LoRA, it combines quantization techniques (e.g., 4-bit quantization) to reduce memory usage.
   - Use `BitsAndBytesConfig` for quantization configuration.
   - Call `prepare_model_for_kbit_training` to prepare the model.

### Differences in Training Parameters

1. **Full Fine-Tuning**
   - Train all model parameters.
   - Typically requires more memory and computational resources.
   - Use standard optimizers like `adamw_torch`.

2. **LoRA**
   - Only train the low-rank matrices inserted by LoRA, keeping other parameters unchanged.
   - Faster training speed and less memory usage.
   - Use optimizers like `paged_adamw_8bit`.

3. **QLoRA**
   - Combine LoRA and quantization techniques to further reduce memory usage.
   - Suitable for fine-tuning large models in resource-constrained environments.
   - Also use the `paged_adamw_8bit` optimizer.

It should be noted that when performing LoRA or QLoRA fine-tuning, we can specify the modules to be trained, such as:

```python
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
```

For detailed information on continuous pre-training with LoRA, refer to [Part III](#part-iii-the-nature-and-code-implementation-of-continuous-pre-training-cpt) above.

---

## Part VI: Distributed Implementation of Training

There is no doubt that pre-training large language models requires multi-node and multi-GPU setups. This necessitates distributed training. Currently, the underlying distributed pre-training can be implemented by calling NCCL. Higher-level tools such as Megatron, DeepSpeed, and HF's accelerate library (which currently supports FSDP) can be used. These tools effectively implement DP/PP/TP.

### Tool Comparison

| Tool Name              | Features                                                     | Use Cases                                                    | Advantages                                                   | Disadvantages                                                | Distinctions                                                 | Underlying Implementation of Distributed Training and Fine-Tuning | Ability to Perform Inference                                 |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Megatron-DeepSpeed** | - Integrates NVIDIA's Megatron-LM and Microsoft's DeepSpeed - Supports training of ultra-large-scale models (tens of billions to trillions of parameters) - Provides advanced model parallelism and pipeline parallelism techniques | - Organizations or researchers needing to train ultra-large-scale models - Conducting distributed training on multiple GPUs or large computing clusters | - Extremely high training efficiency, fully utilizing hardware resources - Supports multiple parallel strategies, optimizing memory and computation resource usage | - Complex configuration and usage; requires deep understanding of distributed training and model parallelism - High hardware resource requirements; not suitable for resource-constrained environments | - More focused on high-performance training of ultra-large-scale models compared to other tools - Combines Megatron-LM's model parallelism and DeepSpeed's optimization techniques | - Based on PyTorch - Utilizes Megatron-LM's tensor parallelism - DeepSpeed's ZeRO optimizer for memory and computation optimization | Mainly focused on training; inference support is limited and requires users to implement it themselves |
| **Axolotl**            | - Flexible fine-tuning framework supporting multiple fine-tuning techniques - Provides a simple configuration method, simplifying data preparation and model setup | - Users wishing to quickly set up and run fine-tuning experiments - Need flexible configuration of the fine-tuning process without writing a lot of code | - High ease of use; simplifies operations through configuration files and command-line interface - Supports multiple models and fine-tuning methods; compatible with mainstream deep learning libraries | - Community support may be limited; resources for problem-solving may be scarce - Limited support for distributed training; not suitable for ultra-large-scale training | - Provides high-level encapsulation, between fully manual and highly automated - Emphasizes flexibility and ease of use in fine-tuning | - Based on Hugging Face's Transformers and PEFT library - Supports partial distributed training, mainly targeting single-machine multi-GPU environments | Supports inference; can use fine-tuned models for prediction |
| **DeepSpeed**          | - Deep learning optimization library launched by Microsoft - Provides ZeRO optimizer, significantly reducing memory footprint for large model training - Supports efficient distributed training and optimization techniques | - Researchers and engineers training large models in multi-GPU or multi-node environments - Need to optimize training efficiency and resource utilization | - Substantially reduces memory usage; supports training larger models - Provides advanced parallel and optimization strategies to improve training performance | - Complex configuration and usage; steep learning curve - Not user-friendly for novices and resource-limited users | - Focuses on optimization of distributed training rather than specific fine-tuning techniques - Deep integration with PyTorch; provides low-level performance optimization | - Based on PyTorch - Uses ZeRO optimizer and parallel strategies - Supports pipeline parallelism, tensor parallelism, etc. | Mainly focuses on training; inference support requires additional configuration and implementation |
| **Accelerate**         | - Hardware abstraction library launched by Hugging Face - Simplifies training and deployment code across different hardware configurations | - Developers needing to run the same code on various hardware environments - Wish to simplify the writing and management of distributed training code | - Masks the complexity of hardware and distributed training - Good compatibility with upper-level libraries like Transformers | - Needs to be combined with other libraries to implement specific fine-tuning techniques (e.g., LoRA) - Limited capability for complex optimization and performance tuning | - Focuses on abstraction of hardware and distributed training rather than fine-tuning methods themselves - Provides a simplified training loop interface | - Based on PyTorch's distributed functionality - Encapsulates distributed training interfaces - Needs to be used in conjunction with PEFT, Transformers, etc. | Supports inference; can be deployed and used for prediction on different devices |
| **Unsloth**            | - Designed specifically for efficient fine-tuning of large language models - Supports 4-bit quantization, significantly reducing memory and computation requirements - Integrates LoRA and other parameter-efficient fine-tuning techniques | - Fine-tuning large models in resource-constrained environments (e.g., single GPU, Colab) - Users wishing to perform fine-tuning quickly and simply without focusing on underlying details | - High memory and computational efficiency; suitable for small hardware setups - Provides high-level encapsulation, lowering the usage threshold | - Lower flexibility; may not meet special customization needs - Limited support for distributed training; unable to handle ultra-large-scale models | - Focuses on efficient fine-tuning in resource-constrained environments; provides specific optimizations like quantization - High level of encapsulation; simple to use | - Based on PyTorch and Transformers - Uses 4-bit quantization and LoRA for efficient fine-tuning - Limited distributed training support; mainly used in single GPU environments | Supports inference; can perform efficient prediction on a single GPU |

**Tool Summary:**

- **Megatron-DeepSpeed**: Suitable for organizations training ultra-large-scale models on large clusters but requires rich distributed training experience and hardware resources.
- **Axolotl**: Provides convenience for users wishing to fine-tune quickly and flexibly; suitable for small to medium-scale models and resource environments.
- **DeepSpeed**: Focuses on optimizing distributed training and large model training; requires a certain level of technical depth; suitable for users pursuing performance.
- **Accelerate**: Simplifies the writing of training code across hardware; suitable for developers needing to run models in different environments.
- **Unsloth**: Provides an efficient fine-tuning solution in resource-constrained environments; suitable for individual researchers or small teams.

### Megatron-DeepSpeed

For detailed information on pre-training using Megatron combined with DeepSpeed, refer to:
*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/Megatron%2BDeepspeed-Pretrain-GPT2*

### DeepSpeed

For an example of SFT implementation using DeepSpeed, refer to:
*https://github.com/davidsajare/david-share/tree/master/Multimodal-Models/DeepSpeed-FT-Stable-Diffusion*

### Axolotl

Currently, some open-source fine-tuning tools like Axolotl can also directly interface with DeepSpeed. For an example, refer to:
*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/Fine-tuning-with-Axolotl*

### Accelerate

When using FSDP with `accelerate`, other parallel strategies can be combined to achieve more efficient training.

1. **Data Parallelism (DP)**
   - FSDP itself is a data parallel strategy, achieved by sharding model parameters.

2. **Pipeline Parallelism (PP)**
   - The model can be divided into multiple stages, with each stage running on different devices. This requires manual partitioning of the model and managing the data flow.

3. **Tensor Parallelism (TP)**
   - The computation of a single layer is distributed across multiple devices. This requires modifications to the model's computation graph.

Combining these strategies usually requires significant customization and adjustments to the model and training scripts. `accelerate` provides some tools to simplify these processes, but specific implementations may require combining other PyTorch libraries (such as `torch.distributed`) and custom code.

For an example of FSDP with `accelerate`, refer to:
*https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Llama-3.1-Fine-Tuning-Guide*
