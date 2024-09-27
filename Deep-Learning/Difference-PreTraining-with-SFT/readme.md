# Difference between PreTraining with SFT

The goals of pre-training, the datasets used, and the number of GPUs required are all different. However, if we are to explain the difference from the essence of deep learning training, it is: 

** Pre-training involves randomly initializing model parameters, constructing the model, and then training it on a large amount of unlabeled data to learn general features of the corpus; whereas fine-tuning loads parameters from the pre-trained model, retains the general features learned during pre-training, and trains the model on a small amount of high-quality labeled data to enhance the model's capability and performance on specific tasks. **

The parameters mentioned above include: weights, biases, Word Embeddings, Positional Encoding, attention mechanism parameters, etc.

## More detail explaination

### Pre-Training

**Pre-Training** aims to learn the fundamental structure and semantic features of a language using large-scale unsupervised datasets (such as text corpora). Pre-training typically involves the following steps:

1. **Random Initialization of Weights**: The model's parameters, such as weights and biases, are randomly initialized at the start of pre-training.
2. **Large-Scale Dataset**: Training is conducted using a vast amount of unsupervised data.
3. **Learning General Features**: The model learns the general features of the language by optimizing a loss function (e.g., the cross-entropy loss of a language model).

#### Key Points of Pre-Training

- **Random Initialization**: All model parameters (weights, biases, etc.) are random at the beginning of pre-training.
- **Large-Scale Data**: Training is done using a large-scale unsupervised dataset.
- **General Features**: The model learns the basic structure and semantic features of the language, providing a good starting point for subsequent tasks.

### Fine-Tuning

**Fine-Tuning** aims to optimize the model's performance on a specific task using a task-specific dataset. Fine-tuning typically involves the following steps:

1. **Loading Pre-Trained Weights**: The model's weights and biases are loaded from the pre-trained model.
2. **Task-Specific Data**: Training is conducted using a dataset specific to the task.
3. **Optimizing Task Performance**: The model adjusts its parameters by optimizing a loss function to improve performance on the specific task.

#### Key Points of Fine-Tuning

- **Loading Pre-Trained Weights**: The model's parameters are loaded from the pre-trained model, retaining the general features learned during pre-training.
- **Task-Specific Data**: Training is done using a dataset specific to the task.
- **Task Optimization**: The model's parameters are further adjusted to optimize performance on the specific task.

### Summary

1. **Training Efficiency**: Pre-training usually requires substantial computational resources and time because it involves training all model parameters on a large-scale dataset. Fine-tuning is relatively efficient as it builds on the pre-trained model and only requires further optimization on task-specific data.
2. **Model Performance**: The pre-trained model has already learned general language features, allowing fine-tuning to converge faster and perform better on specific tasks. Training a task-specific model from random initialization typically requires more data and time, and its performance may not match that of the pre-training + fine-tuning approach.
3. **Application Scenarios**: Pre-trained models can serve as general-purpose base models suitable for various downstream tasks. Fine-tuning allows for quick adaptation to different task requirements without the need to train a model from scratch.


## Pre-training Code Demonstration

**Taking GPT-2 as an Example**

*https://huggingface.co/docs/transformers/v4.44.0/en/model_doc/gpt2#transformers.GPT2LMHeadModel*

*To pre-train GPT-2, we need to use the classes `GPT2LMHeadModel` and `GPT2Config`.**
```
# 创建一个新的 GPT-2 配置  
config = GPT2Config()  
  
# 从头开始初始化模型  
model = GPT2LMHeadModel(config)  
  
# 初始化 tokenizer  
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")  
tokenizer.pad_token = tokenizer.eos_token  # 设置 pad_token  
  
# 加载数据集  
dataset = load_dataset("wikitext", "wikitext-2-raw-v1")  
  
# 定义标记化函数  
def tokenize_function(examples):  
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512, return_special_tokens_mask=True)  
  
# 对数据集进行标记化  
tokenized_datasets = dataset.map(tokenize_function, batched=True, remove_columns=["text"])  
  
# 检查数据集大小  
print("Train dataset size:", len(tokenized_datasets["train"]))  
print("Validation dataset size:", len(tokenized_datasets["validation"]))  
  
# 数据整理器  
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)  
  
# 训练参数  
training_args = TrainingArguments(  
    output_dir="./results",  
    overwrite_output_dir=True,  
    num_train_epochs=5,  
    per_device_train_batch_size=64,  
    save_steps=10_000,  
    save_total_limit=2,  
    remove_unused_columns=False,  
    report_to=[],  # 确保禁用所有报告  
    learning_rate=5e-4  # 设置自定义学习率  
)  
  
# 创建 Trainer  
trainer = Trainer(  
    model=model,  
    args=training_args,  
    data_collator=data_collator,  
    train_dataset=tokenized_datasets["train"],  
    eval_dataset=tokenized_datasets["validation"]  
)  
  
# 将模型移动到 GPU（如果可用）  
if torch.cuda.is_available():  
    model.cuda()  
  
# 开始训练  
trainer.train()  
```

Since the model is small, pre-training can be done with a single H100 GPU:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXx2ibRcepjvLcJVtoKRQiaeXdYWRhDl8L5OClic6Sj6RxibicXtQaEgF0iaibbg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Training resule is as following:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXx7daWmg4C8ziaIX8CCwt8rddGcLQKXYSODtEaPaDIsNTsy3h3mEuSIEg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The trained model can be used for inference validation.
```
# 加载模型和tokenizer  
model = GPT2LMHeadModel.from_pretrained("./results/checkpoint-2870")  
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")  
  
# 设置pad_token  
tokenizer.pad_token = tokenizer.eos_token  
  
# 将模型移动到GPU（如果可用）  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
  
# 设置模型为评估模式  
model.eval()  
  
# 输入文本  
input_text = "Once upon a time"  
  
# 编码输入文本  
inputs = tokenizer(input_text, return_tensors="pt", padding=True).to(device)  
  
# 生成文本  
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
  
# 解码生成的文本  
generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)  
print(generated_text)  
```
Inference resule is as following:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW6dQWwELzZygpch9cW1IXxcGkvLgsa0lxoLEjNT4VSZLya26x2xOUYia7E3CCKC2ic9Q1NXS8nOJYw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Fine-tuning Code Demonstration

When we fine-tune a model, it usually refers to Supervised Fine Tuning (SFT). SFT can be divided into Parameter-Efficient Fine-Tuning (PEFT) and Full Fine Tuning.In PEFT implementations, methods like LoRA, QLoRA, and GA-LoRA are quite popular.

Let's first look at how to load a model for Full Fine Tuning. We use the `AutoModelForCausalLM.from_pretrained` class, which retrieves the parameters of the pre-trained model.

```
 model = AutoModelForCausalLM.from_pretrained(
          model_name, attn_implementation=attn_implementation, device_map={"": 0}
)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})
```

For the complete Full fine tuning code, refer to the repository:

*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/SmolLM-Full-Fine-Tuning*

Next, let's look at the differences in code implementation for fine-tuning, LoRA, and QLoRA. In terms of loading models and training parameters, Full Fine-Tuning, LoRA, and QLoRA have the following differences:

### Difference in Loading Models

1. Full Fine-Tuning
   - Directly load the complete model for training.
   - Use `AutoModelForCausalLM.from_pretrained` to load the model.
2. LoRA
   - Load the model and then use LoRA configuration for parameter-efficient fine-tuning.
   - Use `LoraConfig` from the `peft` library to configure LoRA parameters.
   - Target modules are usually specific projection layers, such as `k_proj`, `q_proj`, etc.
3. QLoRA
   - Based on LoRA, it combines quantization techniques (e.g., 4-bit quantization) to reduce memory usage.
   - Use `BitsAndBytesConfig` for quantization configuration.
   - Call `prepare_model_for_kbit_training` to prepare the model.

### Difference in Training Parameters

 

1. Full Fine-Tuning

   - Train all model parameters.
   - Typically requires more memory and computational resources.
   - Use standard optimizers like `adamw_torch`.

2. LoRA

   - Only train the low-rank matrices inserted by LoRA, keeping other parameters unchanged.
   - Faster training speed and less memory usage.
   - Use optimizers like `paged_adamw_8bit`.

3. QLoRA

   - Combine LoRA and quantization techniques to further reduce memory usage.

   - Suitable for fine-tuning large models in resource-constrained environments.

   - Also use the `paged_adamw_8bit` optimizer.

     It should be noted that when performing LoRA or QLoRA fine-tuning, we can specify the modules to be trained, such as:

```
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

For detailed information, refer to：

*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/Continue-Pre-training*

## Distributed Implementation of Training

There is no doubt that pre-training large language models requires multi-node and multi-GPU setups. This necessitates distributed training. Currently, the underlying distributed pre-training can be implemented by calling NCCL. Higher-level tools such as Megatron, DeepSpeed, and HF's accelerate library (which currently supports FSDP) can be used. These tools effectively implement DP/PP/TP. 

### Tool comparison

Let's compare main Training/SFT tool in a table:

| Tool Name              | Features                                                     | Use Cases                                                    | Advantages                                                   | Disadvantages                                                | Distinctions                                                 | Underlying Implementation of Distributed Training and Fine-Tuning | Ability to Perform Inference                                 |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Megatron-DeepSpeed** | - Integrates NVIDIA's Megatron-LM and Microsoft's DeepSpeed - Supports training of ultra-large-scale models (tens of billions to trillions of parameters) - Provides advanced model parallelism and pipeline parallelism techniques | - Organizations or researchers needing to train ultra-large-scale models - Conducting distributed training on multiple GPUs or large computing clusters | - Extremely high training efficiency, fully utilizing hardware resources - Supports multiple parallel strategies, optimizing memory and computation resource usage | - Complex configuration and usage; requires deep understanding of distributed training and model parallelism - High hardware resource requirements; not suitable for resource-constrained environments | - More focused on high-performance training of ultra-large-scale models compared to other tools - Combines Megatron-LM's model parallelism and DeepSpeed's optimization techniques | - Based on PyTorch - Utilizes Megatron-LM's tensor parallelism - DeepSpeed's ZeRO optimizer for memory and computation optimization | Mainly focused on training; inference support is limited and requires users to implement it themselves |
| **Axolotl**            | - Flexible fine-tuning framework supporting multiple fine-tuning techniques - Provides a simple configuration method, simplifying data preparation and model setup | - Users wishing to quickly set up and run fine-tuning experiments - Need flexible configuration of the fine-tuning process without writing a lot of code | - High ease of use; simplifies operations through configuration files and command-line interface - Supports multiple models and fine-tuning methods; compatible with mainstream deep learning libraries | - Community support may be limited; resources for problem-solving may be scarce - Limited support for distributed training; not suitable for ultra-large-scale training | - Provides high-level encapsulation, between fully manual and highly automated - Emphasizes flexibility and ease of use in fine-tuning | - Based on Hugging Face's Transformers and PEFT library - Supports partial distributed training, mainly targeting single-machine multi-GPU environments | Supports inference; can use fine-tuned models for prediction |
| **DeepSpeed**          | - Deep learning optimization library launched by Microsoft - Provides ZeRO optimizer, significantly reducing memory footprint for large model training - Supports efficient distributed training and optimization techniques | - Researchers and engineers training large models in multi-GPU or multi-node environments - Need to optimize training efficiency and resource utilization | - Substantially reduces memory usage; supports training larger models - Provides advanced parallel and optimization strategies to improve training performance | - Complex configuration and usage; steep learning curve - Not user-friendly for novices and resource-limited users | - Focuses on optimization of distributed training rather than specific fine-tuning techniques - Deep integration with PyTorch; provides low-level performance optimization | - Based on PyTorch - Uses ZeRO optimizer and parallel strategies - Supports pipeline parallelism, tensor parallelism, etc. | Mainly focuses on training; inference support requires additional configuration and implementation |
| **Accelerate**         | - Hardware abstraction library launched by Hugging Face - Simplifies training and deployment code across different hardware configurations | - Developers needing to run the same code on various hardware environments - Wish to simplify the writing and management of distributed training code | - Masks the complexity of hardware and distributed training - Good compatibility with upper-level libraries like Transformers | - Needs to be combined with other libraries to implement specific fine-tuning techniques (e.g., LoRA) - Limited capability for complex optimization and performance tuning | - Focuses on abstraction of hardware and distributed training rather than fine-tuning methods themselves - Provides a simplified training loop interface | - Based on PyTorch's distributed functionality - Encapsulates distributed training interfaces - Needs to be used in conjunction with PEFT, Transformers, etc. | Supports inference; can be deployed and used for prediction on different devices |
| **Unsloth**            | - Designed specifically for efficient fine-tuning of large language models - Supports 4-bit quantization, significantly reducing memory and computation requirements - Integrates LoRA and other parameter-efficient fine-tuning techniques | - Fine-tuning large models in resource-constrained environments (e.g., single GPU, Colab) - Users wishing to perform fine-tuning quickly and simply without focusing on underlying details | - High memory and computational efficiency; suitable for small hardware setups - Provides high-level encapsulation, lowering the usage threshold | - Lower flexibility; may not meet special customization needs - Limited support for distributed training; unable to handle ultra-large-scale models | - Focuses on efficient fine-tuning in resource-constrained environments; provides specific optimizations like quantization - High level of encapsulation; simple to use | - Based on PyTorch and Transformers - Uses 4-bit quantization and LoRA for efficient fine-tuning - Limited distributed training support; mainly used in single GPU environments | Supports inference; can perform efficient prediction on a single GPU |
|                        |                                                              |                                                              |                                                              |                                                              |                                                              |                                                              |                                                              |

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

1. Data Parallelism (DP)

   - FSDP itself is a data parallel strategy, achieved by sharding model parameters.

2. Pipeline Parallelism (PP)

   - The model can be divided into multiple stages, with each stage running on different devices. This requires manual partitioning of the model and managing the data flow.

3. Tensor Parallelism (TP)

   - The computation of a single layer is distributed across multiple devices. This requires modifications to the model's computation graph.

     Combining these strategies usually requires significant customization and adjustments to the model and training scripts. `accelerate` provides some tools to simplify these processes, but specific implementations may require combining other PyTorch libraries (such as `torch.distributed`) and custom code.

For an example of FSDP with `accelerate`, refer to:

*https://github.com/davidsajare/david-share/tree/master/Deep-Learning/Llama-3.1-70B-FSDP-Fine-Tuning*