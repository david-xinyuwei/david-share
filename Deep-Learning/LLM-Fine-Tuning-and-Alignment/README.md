# LLM Fine-Tuning and Alignment: A Complete Guide

This article is a comprehensive technical guide to LLM fine-tuning and alignment, covering SFT hyperparameter tuning; comparison of various fine-tuning methods (SFT/ReFT/RLHF/DPO/PPO/RLAIF/TPO); LoRA/QLoRA/GaLore mechanisms; DPO theory and practice; detailed PPO architecture; and the end-to-end workflow for large-model DPO distributed training (DeepSpeed ZeRO-3 / FSDP).

> *This guide consolidates content from multiple previously separate articles into a single coherent resource.*

## Table of Contents

- [Part 1: SFT Hyperparameter Tuning Best Practices](#part-1-sft-hyperparameter-tuning-best-practices)
- [Part 2: A Panoramic Comparison of Various Fine-Tuning Methods](#part-2-a-panoramic-comparison-of-various-fine-tuning-methods)
- [Part 3: The Essential Difference Between Reinforcement Learning and Fine-Tuning](#part-3-the-essential-difference-between-reinforcement-learning-and-fine-tuning)
- [Part 4: Comparison Table of Seven Fine-Tuning Techniques](#part-4-comparison-table-of-seven-fine-tuning-techniques)
- [Part 5: LoRA/QLoRA Fine-Tuning Mechanisms and GaLore Full Fine-Tuning](#part-5-loraqlorafine-tuning-mechanisms-and-galore-full-fine-tuning)
- [Part 6: In-Depth DPO Theory and Alignment Practice](#part-6-in-depth-dpo-theory-and-alignment-practice)
- [Part 7: DPO Fine-Tuning Code and Training Results Analysis](#part-7-dpo-fine-tuning-code-and-training-results-analysis)
- [Part 8: Large Model DPO Distributed Training (DeepSpeed & FSDP)](#part-8-large-model-dpo-distributed-training-deepspeed--fsdp)

## Running on Azure

All experiments in this project were conducted on **Azure GPU VMs**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | DeepSpeed, FSDP, LoRA/PEFT |

---
# Part 1: SFT hyperparameter tuning best practices

> *Originally from LLM-Fine-Tuning-Best-Practices*


The hyperparameters for LLM fine-tuning are roughly as follows; in this article, we explain these parameters.

```
training_arguments = TrainingArguments(
        output_dir="./results",
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=2,
        optim="adamw_8bit",
        logging_steps=50,
        learning_rate=1e-4,
        evaluation_strategy="steps",
        do_eval=True,
        eval_steps=50,
        save_steps=100,
        fp16= not torch.cuda.is_bf16_supported(),
        bf16= torch.cuda.is_bf16_supported(),
        num_train_epochs=3,
        weight_decay=0.0,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        gradient_checkpointing=True,
）
```

**I. Batch sizebatch size**

Let’s discuss the batch size setting. In model training, batch size refers to the number of samples used in each training step. We split the dataset into multiple batches and update the model weights once after processing each batch—that is, after completing one training step. Choosing an appropriate batch size is a key consideration in the training process; it directly affects both the convergence speed and the quality of training.

In general, smaller batch sizes provide a regularization effect and reduce generalization error on new data, which can make the model more stable. However, this may slow down training and increase the risk of getting stuck in local minima. Larger batch sizes can leverage hardware optimizations—such as the GPU’s parallel processing capabilities—to accelerate training, but they require more memory and may yield less precise gradient estimates. Here, the “gradient” can be seen as an indicator arrow pointing toward the direction in which the model’s error increases most rapidly. During training, our goal is to minimize error. To do this, we examine the gradient to determine the direction we don’t want the model to go, then adjust the model to move in the opposite direction, thereby reducing error.

In practice, you can keep increasing the batch size until you encounter an out-of-memory error on the GPU, indicating the GPU can no longer handle a larger batch. This gives us the maximum batch size suitable for our hardware.

In TrainingArguments, you can set the batch size with the following parameters:

```
[...]
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
[...]
```

The first controls the training batch size; the second controls the evaluation batch size. For evaluation, it only affects evaluation speed. Typically, we use the same batch size for both evaluation and training. GPUs are optimized for specific batch sizes. For example, avoid using odd numbers; setting a batch size of 9 or 13 may lead to slower fine-tuning than a batch size of 8.

We trained TinyLlama for 1 epoch with batch sizes of 1, 2, 4, and 8.


First we show the learning curves, then discuss the results.

For batch size 1:

![images](images/ext_01.png)

For batch size 2:

![images](images/ext_02.png)

For batch size 4:

![images](images/ext_03.png)

For batch size 8:

![images](images/ext_04.png)

Comparison:

![images](images/ext_05.png)



Batch size has a significant impact on both training quality and efficiency. Larger batches can improve model performance and accelerate the training process, but you must also account for total training time, including additional time to run validation steps. When using small batches, reduce the frequency of validation steps accordingly to keep total training time down.


Experiments show that good loss can be achieved even with a batch size of 32. However, this increases memory usage, and in some cases—for example, on GPUs with 16 GB of memory—it’s impractical to reach such batch sizes without techniques like gradient accumulation. Therefore, rather than blindly pursuing larger batches, you should factor in hardware constraints and determine the optimal batch size through experimentation. This ensures training is both efficient and practical within available resources.


## II. Maximum Sequence Length, Padding, Truncating

In batching, training samples need to be padded to ensure all samples within a batch have the same shape or size, which is a basic requirement for machine learning models that process data in parallel. This is especially important for sequence tasks such as language generation. When preparing batches, shorter sequences are padded by adding some inconsequential values so that their length matches the longest sequence in the batch. Padding can be applied to the front of the sequence (left padding), the end (right padding), or sometimes both, depending on the model design and task requirements. Note that not all techniques support padding on arbitrary sides. For example, when using the FlashAttention technique, left padding is required. To better control batch size, it’s recommended to set a maximum sequence length. For example, if we set this maximum length to 1,024 tokens, then each sample in the batch will be processed to exactly 1,024 tokens. If a sample originally has only 512 tokens, 512 padding tokens will be appended. Conversely, if a sample exceeds 1,024 tokens, the excess will be truncated. This approach not only ensures consistency during processing but also helps optimize memory usage, thereby improving training efficiency.


Consider an example. We want to put these two sentences into one batch:

```
prompt1 = "You are not a chatbot."
prompt2 = "You are not."

prompt_test1 = [prompt1, prompt1]
prompt_test2 = [prompt1, prompt2]
```

I created two batches of prompts. The first contains the same sequence twice, so the two sequences have the same length.

If we tokenize prompt_test1 with the Llama 2 tokenizer

```
input = tokenizer(prompt_test1, return_tensors="pt");
print(input)
```

It produces tensors of input IDs (the IDs of the tokens) and attention mask:It yields tensors of input IDs (the IDs of the tokens) and attention mask:

```
{
    'input_ids': tensor([[    1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    1,   887,   526,   451,   263, 13563,  7451, 29889]]),
    'attention_mask': tensor([[1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1]])
}
```

However, if we try to tokenize prompt_test2:

```
input = tokenizer(prompt_test2, return_tensors="pt");
print(input)
```

It will produce this error:

*ValueError: Unable to create tensor, you should probably activate truncation and/or padding with 'padding=True' and 'truncation=True' to have batched tensors with the same length. Perhaps your features (`input_ids` in this case) have excessive nesting (inputs type `list` where type `int` is expected)*

This error message clearly indicates that we need to apply padding and truncation to the samples. Given that our samples are short, we set the tokenizer’s maximum length to 20. I chose a left-padding strategy and decided to use the “UNK” (unknown) token as the padding token. With this setup, all input lengths are consistent during both training and inference, making processing more efficient. At the same time, using the UNK token for padding can make the model more robust when handling unknown or rare inputs.

```
tokenizer.padding_side = "left"
tokenizer.pad_token = tokenizer.unk_token
input = tokenizer(prompts, padding='max_length', max_length=20, return_tensors="pt");
print(input)
```

It yields:

```
{
    'input_ids': tensor([
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     0,     0,     0,     1,   887,   526,   451, 29889]]), 
    'attention_mask': tensor([
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]])
}
```

Now many “0”s appear at the beginning (left side) of the sequences; these represent the padding token IDs. During training, to ensure these padding tokens do not interfere with learning, they are marked as “0” in the attention mask, indicating they will be ignored. You can see that the maximum sequence length decisively affects the batch shape. For example, if the batch size is 12 and the maximum sequence length is 1,024, then the batch shape is 12×1,024, containing a total of 12,288 tokens. If the maximum sequence length is set to 512, the batch’s total token count is halved.

Ideally, the maximum length should match the longest sequence in the training examples. If GPU memory is limited, this length can be reduced accordingly. Typically, values above 4,096 are uncommon except for RAG applications and summarization tasks; for most language generation tasks, the minimum recommended length is 512. This strikes a balance between model effectiveness and avoiding unnecessary memory consumption.

## III. Epochs and Steps

After processing a batch of data, the model updates its weights; this is called a training step. For example, if a dataset has 1,000 examples and the batch size is 100, then one complete pass over the dataset requires 10 such training steps (1,000 divided by 100 equals 10). Each step involves a forward pass (data through the model), loss computation (the discrepancy between predictions and ground truth), and weight updates via backpropagation to try to reduce the loss. When every example in the dataset has been processed exactly once by the model, one training cycle—an epoch—is completed. Therefore, the number of steps per epoch depends on the dataset size and batch size. Continuing the example, if the dataset has 1,000 examples and the batch size is 100, then one epoch requires 10 steps. Training for multiple epochs means the model sees the same data multiple times, with the expectation that it adjusts its weights for more accurate predictions; the model may learn and improve with each epoch.

```
[...]
        num_train_epochs=3,
[...]
```

oror

```
[...]
        max_steps=1000,
[...]
```

When num_train_epochs is set, max_steps is overridden. In this configuration, training will run for 3 epochs, meaning the model will see all training data in full three times.

Suppose we train TinyLlama on openassistant-guanaco, with a total of 9,846 steps and a batch size of 8; one epoch will contain about 1,231 training steps. If we train for just one epoch on this dataset, the model typically learns useful information. However, continuing for more epochs may lead to overfitting—becoming overly tuned to the training data and potentially hurting performance on new data. If we examine training after two epochs on this dataset, we can observe signs of such overfitting.

![images](images/ext_06.png)


Even without observing validation loss, you can notice the training loss decreasing unusually fast. As discussed in the next section, this can be effectively mitigated by adjusting the learning rate and adopting an appropriate warmup ratio. Such adjustments help the model learn more smoothly, avoid overfitting, and maintain generalization to unseen data.

## IV. Gradient Accumulation Steps

Gradient accumulation simulates large-batch training by splitting data into smaller micro-batches. Instead of updating model weights after each micro-batch, it accumulates gradients over a specified number of steps. A weight update only occurs once the accumulated gradients correspond to the target larger batch size. For example, if the target batch size is 1,024 but the device can only process 256 samples per step, you can accumulate the gradients from four steps of 256 samples each to simulate one update with a batch of 1,024 samples.

This method balances the need for large batches under limited memory, enabling more stable gradient estimates and potentially faster convergence. For instance, in TrainingArguments, if per_device_train_batch_size is set to 4 and gradient_accumulation_steps is set to 2, the effective total batch size is 8 (4 times 2), equivalent to setting per_device_train_batch_size to 8 with gradient_accumulation_steps of 1. This technique does not affect the model’s intrinsic performance; rather, it is an effective way to optimize resource usage during training.

```
[...]
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
[...]
```
## V. Gradient Checkpointing

In standard training, all intermediate activations are kept in memory to compute gradients during backpropagation. However, given the memory limits of most hardware (e.g., GPUs), this quickly becomes impractical for very deep networks. Gradient checkpointing addresses this by saving activations only at selected layers in the network. For layers whose activations are not saved, they are recomputed during backpropagation when gradients are needed.

This trade-off between compute and memory means that while gradient checkpointing can greatly reduce the memory required for training, it may increase compute time due to the need to recompute some activations. It is a strategy to balance efficiency and resources, particularly suitable when resources are limited and the model is deep and large.

This is configured in TrainingArguments as follows:

```
[...]
        gradient_checkpointing=True,
[...]
```

Or

```
model.gradient_checkpointing_enable()
```

## VI. Learning Rate

The learning rate is a key hyperparameter that determines how the model updates its weights during training. It affects the step size the model takes in parameter space to minimize the loss function. A properly set learning rate ensures that the model improves predictive performance efficiently without overshooting or stalling before reaching optimality.

For large language models (LLMs), selecting an appropriate learning rate is especially important due to their large number of parameters and complex data patterns. If the learning rate is too high, the model may rapidly converge to a suboptimal solution or oscillate when searching for the optimum. Conversely, if the learning rate is too low, convergence can be slow or even completely stall.

In practice, determining a suitable learning rate often requires empirical tuning—trying several fine-tuning runs with different learning rates. For LLMs, a reasonable range is typically between 1e-6 and 1e-3. For example, you can try values such as 1e-3, 5e-4, 1e-4, 5e-5, 1e-5, 5e-6, and 1e-6. You do not need to exhaustively try all of them; generally, it is recommended to search around 1e-4. For instance, if you find that 5e-5 performs better than 1e-5, even smaller values like 5e-6 and 1e-6 are unlikely to yield better results. This way, you can more efficiently pinpoint a learning rate that optimizes model performance.

Set the learning rate in TrainingArguments as follows:

```
[...]
        learning_rate=1-e4,
[...]
```

## VII. Learning Rate Scheduler

The purpose of a learning rate scheduler is to adjust the learning rate during training according to a predefined schedule. This helps avoid getting trapped in local minima early in training or skipping over minima when approaching the optimum. For large language models (LLMs), the most common type is a scheduler with a warmup phase. Such schedulers start from a low learning rate and gradually ramp up to the target value after several epochs or steps. This strategy is particularly useful when fine-tuning from large-scale pretrained models, as it helps prevent large early weight updates that can harm stability. In most scenarios, I recommend a linear scheduler with warmup, as it is at least as effective as other types, as demonstrated in the paper “When, Why, and How Much? Refining Adaptive Learning Rate Scheduling.” After warmup, the linear scheduler gradually reduces the learning rate, which helps the model converge more stably in the later stages of training.

This is configured in TrainingArguments as follows:

```
[...]
        lr_scheduler_type="linear",
[...]
```

## VIII. Warmup Steps and Warmup Ratio

Warmup steps refer to the initial phase of training during which the learning rate increases from a lower starting value to a predefined target according to the learning rate schedule. For example, if 1,000 warmup steps are set, the learning rate starts low and increases step by step, reaching the target at step 1,000. After that point, the learning rate may be adjusted according to another schedule, such as remaining constant or decaying proportionally.

Warmup ratio is not a fixed number of steps, but the proportion of the total training steps used for warmup. For instance, if the entire training is scheduled for 10,000 steps and the warmup ratio is set to 0.1, then 10% of the steps—the first 1,000—will be used to warm up the learning rate. This ratio helps scale the warmup duration with the overall training length, ensuring an appropriate warmup proportion regardless of the total training duration.

Using a warmup ratio is generally more common than setting a fixed number of warmup steps. If you set a fixed number, you must know in advance how many steps training will run. In practice, if we fix warmup steps to 2,000 but only train for 1,900 steps, the model will never reach the target learning rate. A warmup ratio of 0.1 is a good starting point. Exploring a more suitable warmup ratio may help improve model performance.

Set the warmup ratio in TrainingArguments as follows:

```
[...]
        warmup_ratio=0.1,
[...]
```

## IX. Weight Decay

Weight decay is a technique that encourages the model to maintain smaller weight values, thereby regularizing the model to avoid excessive complexity. It is implemented by adding the squared sum of the weights multiplied by a regularization parameter to the loss function. The effect is to gently push weights toward zero, helping the model avoid over-reliance on any single input feature, which would typically manifest as a large weight for that feature.

The regularization parameter controls the strength of weight decay: a value of zero means no regularization, while larger values impose stronger penalties on larger weights. By default, the weight decay is often set to 0, meaning no penalties on weights initially.

If you observe signs of overfitting during fine-tuning—for example, the training loss decreases rapidly while validation loss increases—consider adjusting the weight decay value. Otherwise, if the model trains well, you can keep weight decay at 0 to allow the training process to proceed naturally.

Set weight decay in TrainingArguments as follows:

```
[...]
        weight_decay=0.0,
[...]
```

## X. Optimizer

The optimizer guides the training process by minimizing error or improving accuracy during fine-tuning. Among many optimizers, AdamW (a variant of Adam) is currently the most widely used. Additionally, AdaFactor is an interesting option that is more memory-efficient.

Adam, or Adaptive Moment Estimation, maintains two moving averages for each parameter: one of the gradients (first moment, indicating the direction and velocity of updates) and one of the squared gradients (second moment, indicating the magnitude of updates). As a result, Adam has relatively high memory consumption. These moving averages help adapt the learning rate for each parameter.

AdamW is a variant of Adam that applies weight decay. It decouples weight decay from the optimization step by applying weight decay directly to the parameters rather than mixing it with gradient updates, which promotes better regularization. AdamW often yields more stable training and better model performance.

AdaFactor is another optimizer designed to reduce memory usage and improve training efficiency by factorizing the second-moment estimates used in Adam. Unlike Adam and AdamW, AdaFactor can work without explicit learning rate scheduling, making it a practical choice for large-scale and resource-constrained training environments.

In terms of memory efficiency, AdaFactor is a good alternative to AdamW. However, we now have a memory-efficient implementation of AdamW, namely 8-bit quantized AdamW. The AdamW states can even be paged out to CPU RAM to further reduce GPU memory usage. Moreover, while AdamW adds two states per model parameter for fine-grained updates, this is not an issue when using parameter-efficient fine-tuning (PEFT) methods like LoRA, since only a small number of parameters are trainable. Combining 8-bit paged AdamW with LoRA can significantly reduce total memory consumption, making AdamW suitable for more constrained environments.

Set the optimizer in TrainingArguments as follows:

```
[...]
        optim="adamw_8bit",
[...]
```

For better models, I recommend setting it to the non-quantized "adamw_torch". If you run out of memory, try "adamw_8bit". Then, as a last resort, try "paged_adamw_8bit". It will be slower than 8-bit AdamW but will further reduce memory usage.

## XI. Float16 and Bfloat16

Traditionally, machine learning models are trained with the float32 data type, where each parameter occupies 4 bytes (32 bits) of memory. For a model with 7 billion (7B) parameters, using float32 alone requires at least a GPU with 28 GB of memory (7 times 4 equals 28). For larger models, this memory requirement becomes prohibitive. As a result, half-precision training has become popular, using float16 or bfloat16 to halve memory usage. The main difference between float16 and bfloat16 lies in how bits are allocated between exponent and mantissa. bfloat16 is designed to handle a wider numeric range without significantly sacrificing computational precision, giving it an advantage for fast and memory-efficient deep learning operations. Although bfloat16 is generally superior in performance, it is only supported on Ampere or newer GPUs. If your GPU supports bfloat16, prefer it. If not, choose float16; however, if you encounter overflow issues during training (e.g., loss suddenly becomes 0.0 or NaN), you may need to fall back to float32. You can automatically set these parameters based on your hardware, configured as follows: [Assuming the original provides specific code or configuration steps].

```
        fp16= not torch.cuda.is_bf16_supported(),
        bf16= torch.cuda.is_bf16_supported(),
```

## XII. Evaluation and Save Steps

Evaluation is a key part of the training process in which the model is periodically assessed on unseen data. This is crucial for ensuring the model is not overfitting the training data. If training loss decreases but validation loss remains unchanged or increases, it usually indicates overfitting.

Depending on the task and model size, evaluation can be resource-intensive. If the total number of training steps is X, it is recommended to evaluate at least every X/10 steps to monitor progress and performance.

The "save_steps" parameter determines how frequently the model is saved, i.e., how often checkpoints are created. Checkpoints are intermediate but fully functional model versions. Saving checkpoints is important because they allow you to resume training if issues arise. Sometimes, these intermediate checkpoints may even outperform the final model.

It is recommended to set save_steps to a multiple of eval_steps so that every saved checkpoint has been evaluated on the validation data. This helps ensure the validity of saved model states and facilitates comprehensive assessment of model performance throughout training.

You can set them in TrainingArguments as follows:

```
[...]
        evaluation_strategy="steps",
        do_eval=True,
        eval_steps=50,
        save_steps=100,
[...]
```

Note that model checkpoints can occupy substantial disk space. When using parameter-efficient fine-tuning (PEFT) methods such as LoRA, checkpoints mainly contain the adapter parameters. Typically, such checkpoints do not exceed 500 MB. However, if the training runs for 1,000 steps and save_steps is set to 50, the accumulated checkpoints will take roughly 10 GB due to frequent saving.

In such cases, while checkpoints are critical to enable resuming training from interruptions, you also need to manage disk space. Therefore, choose a suitable save_steps value in your training setup that both ensures timely saving for recovery and respects storage constraints, especially when disk space is limited.

---

## Appendix: Fine-tuning Base LLMs vs Instruct Version

> *Originally from LLM-Fine-Tuning-Best-Practices*

In the application of large language models (LLMs), fine-tuning is a critical step. Fine-tuning allows the model to better adapt to specific tasks or datasets. However, with the development of LLMs, two main versions have emerged: base LLMs and instruct LLMs. This article will explore the differences between these two versions and discuss which version should be chosen for fine-tuning in practical applications.

![images](images/ext_07.png)

## What are Base LLMs and Instruct LLMs?

### Base LLMs

Base LLMs are models pre-trained on a large amount of text data, with the training objective of predicting the next token. These models do not have specific format constraints and can generate highly diverse text. However, base LLMs may not directly answer user prompts and may repeat or deviate from the topic during generation.

### Instruct LLMs

Instruct LLMs are fine-tuned versions of base LLMs, processed through a complex pipeline to better respond to user instructions. These models undergo several post-training stages, including supervised fine-tuning (SFT), reinforcement learning with human feedback (RLHF), and direct preference optimization (DPO). They are capable of generating answers that align more closely with human preferences and are commonly used in chat applications.

## Differences Between Fine-Tuning Base LLMs and Instruct LLMs

 

### Fine-Tuning Base LLMs

When fine-tuning base LLMs, the model updates its weights based on new data, gradually adapting to new tasks or datasets. Since base LLMs do not have specific format constraints, they can more quickly learn new features and styles.

### Fine-Tuning Instruct LLMs

Instruct LLMs have already undergone a complex post-training process and have specific formats and system instructions. Fine-tuning instruct LLMs may introduce conflicts with the original system instructions and templates, leading to unexpected results. Additionally, instruct LLMs may partially lose their original safety and preference alignment capabilities during fine-tuning.

## Why Fine-Tuning Instruct LLMs is Not Recommended

- **Disruption of Original Training**: Fine-tuning instruct LLMs can partially undo the results of their original SFT and DPO training, causing the model to generate answers that no longer fully align with human preferences.

- **System Instruction Conflicts**: Fine-tuning instruct LLMs introduces new system instructions that may conflict with the original instructions, leading to inconsistent results.

- **Safety Issues**: Instruct LLMs undergo safety training, and fine-tuning may disrupt these safety constraints, resulting in the generation of unsafe content.

  In most cases, fine-tuning base LLMs is preferable to fine-tuning instruct LLMs. Base LLMs do not have specific format constraints and can more quickly adapt to new data and tasks. For applications requiring specific formats and safety, instruct LLMs can be considered, but potential conflicts and inconsistencies should be noted.
  
## SFT code

### Base Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_QLoRA_right/",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512,
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()

```
### Instruct Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_Instruct_QLoRA_right/",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512,
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```
---

# Part 2: A Panoramic Comparison of Various Fine-Tuning Methods

> *Originally from Comparison-of-Various-Fine-Tuning-Methods*


This article compares the following fine-tuning techniques: SFT, ReFT, RHLF, RLAIF, DPO, PPO, TPO.

## Relationships among the techniques

If we take a simplified view of a complex topic, the relationships between these techniques are roughly as follows:

**ReFT (Reinforced Fine-Tuning):**

- **Components**: ReFT = SFT + PPO
- **Process**: Based on supervised fine-tuning (SFT), apply PPO (Proximal Policy Optimization) for reinforcement learning.
- **Evaluation method**: Typically evaluated by an **automated program**, with reward signals coming from the program’s assessment of model outputs.

**RLHF (Reinforcement Learning from Human Feedback):**

![images](images/ext_08.png)

- **Components**: RLHF = SFT + PPO + human feedback
- **Process**: Based on SFT, apply PPO for reinforcement learning, with reward signals derived from **human feedback**.
- **Evaluation method**: Humans evaluate model outputs, or a **reward model** trained from human feedback is used for evaluation.

##### DPO method (Direct Preference Optimization):

- **Components**: DPO method = SFT + **reference model** + DPO
- **Process**: On top of SFT, a **reference model** is introduced (typically the initial SFT model with parameters frozen), and the DPO method uses the reference model and human preference data to directly optimize model parameters.
- **Evaluation method**: Using **human preference data and a reference model**, construct a loss function that directly optimizes model parameters so that the model is more inclined to generate outputs preferred by humans.

**RLAIF (Reinforcement Learning from AI Feedback):**

![images](images/ext_09.png)

- **Components**: RLAIF = SFT + PPO + AI feedback
- **Process**: Based on SFT, apply PPO for reinforcement learning, with reward signals coming from **feedback of an AI model**.
- **Evaluation method**: An auxiliary AI model (possibly a reward model) evaluates the model’s outputs and provides reward signals.


**TPO (Thought Preference Optimization):**

- **Components**: TPO = SFT + Thought Generation + DPO
- **Process**: Based on SFT, introduce **thought generation**, where the model produces an internal chain of thought before emitting the final answer. Then, use the DPO method to directly optimize the model, with preference data sourced from **an AI discriminator’s feedback**.
- **Evaluation method**: Use an **AI discriminator** to evaluate the **answer portion** of the model’s output and form preference pairs (preferred vs. non-preferred). Based on these preference pairs, apply DPO to optimize model parameters and improve performance.



**Explanation:**

- ReFT (Reinforced Fine-Tuning) applies the PPO algorithm for reinforcement learning on top of an SFT model, with rewards derived from automated comparison of the model’s output against reference answers.

- RLHF (Reinforcement Learning from Human Feedback) applies the PPO algorithm on top of SFT, with reward signals coming from human evaluations of model output.

- The DPO method (Direct Preference Optimization) applies the DPO algorithm on top of SFT to directly optimize model parameters toward human preferences, without using traditional RL algorithms like PPO.

- RLAIF (Reinforcement Learning from AI Feedback) is similar to RLHF, but replaces human feedback with AI model feedback, applying PPO for reinforcement learning.




ReFT, RLHF, DPO, and RLAIF are all built on top of supervised fine-tuning (SFT) to further optimize the model for better performance, but they differ in optimization strategies and feedback sources.

1. **ReFT (Reinforced Fine-Tuning)**: This is a combination of SFT and PPO (Proximal Policy Optimization). In the first stage, the model is trained via SFT on labeled data to establish fundamental language understanding and generation capabilities. In the second stage, PPO is introduced to perform reinforcement learning optimization. The model’s outputs are evaluated by automated programs according to predefined rules or standards, producing reward signals. The model updates its parameters using PPO in response to these rewards to produce better outputs. A hallmark of ReFT is automated evaluation with no human in the loop, suitable for tasks with clear, objective metrics, such as mathematical problem solving.

2. **RLHF (Reinforcement Learning from Human Feedback)**: Built on SFT and combined with PPO, but with reward signals sourced from human feedback. Specifically, humans evaluate model outputs, identify better answers, or provide preference comparisons. These human feedback signals can be used directly to guide optimization or to train a reward model that subsequently evaluates model outputs. The advantage of RLHF is the incorporation of human subjective judgment, making outputs more aligned with human preferences, suitable for tasks requiring complex evaluation and subjective judgment.

3. **DPO (Direct Preference Optimization) method:** Unlike the previous two, DPO does not use RL algorithms (such as PPO); instead, it uses a supervised learning approach to directly optimize the model. After SFT (supervised fine-tuning), a **reference model** is introduced (typically the initial SFT model with parameters frozen), and using human preference data together with the reference model, a loss function is constructed to fine-tune the model. Specifically:

   - **Collect human preference data**: Gather human preference data over model outputs, such as labeling the preferred answer among multiple candidates to form preference pairs (chosen vs. non-chosen responses).

   - **Introduce a reference model**: The reference model provides a stable probabilistic baseline to compare against the current model’s output probabilities, preventing excessive drift from the pretrained language distribution during optimization.

   - **Construct the loss function**: Design a loss that uses the log probabilities from the current model and the reference model for preferred and non-preferred responses, encouraging the model to generate outputs preferred by humans. The loss typically includes log-probability differences and regularization terms to ensure training stability.

   - **Directly optimize model parameters**: Minimize this loss to directly adjust model parameters, making the model more inclined to produce outputs preferred by humans.

     DPO avoids the trial-and-error process of reinforcement learning, making training more stable and efficient. It is well-suited to scenarios with abundant human preference data. **Meanwhile, the introduction of a reference model helps maintain generation quality stability and prevents the model from drifting too far from the pretrained distribution.**

   ## DPO in Azure OpenAI

   Currently AOAI supports DPO:

   *https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/fine-tuning?tabs=azure-openai%2Cturbo%2Cpython-new&pivots=programming-language-studio#direct-preference-optimization-dpo-preview*

   ```
   {  
     "input": {  
       "messages": {"role": "system", "content": ...},  
       "tools": [...],  
       "parallel_tool_calls": true  
     },  
     "preferred_output": [{"role": "assistant", "content": ...}],  
     "non_preferred_output": [{"role": "assistant", "content": ...}]  
   }  
   ```

   Jsonal format:

   ```
   {{"input": {"messages": [{"role": "system", "content": "You are a chatbot assistant. Given a user question with multiple choice answers, provide the correct answer."}, {"role": "user", "content": "Question: Janette conducts an investigation to see which foods make her feel more fatigued. She eats one of four different foods each day at the same time for four days and then records how she feels. She asks her friend Carmen to do the same investigation to see if she gets similar results. Which would make the investigation most difficult to replicate? Answer choices: A: measuring the amount of fatigue, B: making sure the same foods are eaten, C: recording observations in the same chart, D: making sure the foods are at the same temperature"}]}, "preferred_output": [{"role": "assistant", "content": "A: Measuring The Amount Of Fatigue"}], "non_preferred_output": [{"role": "assistant", "content": "D: making sure the foods are at the same temperature"}]}
   }
   ```

   

4. **RLAIF (Reinforcement Learning from AI Feedback)**: This combines SFT, PPO, and AI feedback. After SFT, PPO is used for reinforcement learning, but the reward signals come not from humans, but from an auxiliary AI model (e.g., a reward model). The AI model evaluates the main model’s outputs and provides reward signals. This approach reduces the cost of human evaluation but depends on the quality of the auxiliary AI model.

**Summary:**

Among the four methods, ReFT, RLHF, and RLAIF use PPO as the reinforcement learning algorithm, with the difference being the source of reward signals: ReFT uses automated program evaluation, RLHF uses human feedback, and RLAIF uses AI model feedback. Only the DPO method uses a supervised learning approach, not PPO or other RL algorithms, directly leveraging human preference data to optimize the model.



**So, what is the significance of DPO?**

Reinforcement learning methods (such as PPO) require the model to explore in an environment and learn through trial and error to obtain reward signals. This process is complex, training can be unstable, and hyperparameter tuning is challenging. In contrast, supervised approaches are more direct and efficient: using human-provided preference data to tell the model what constitutes good output, constructing a loss, and adjusting parameters accordingly. This avoids the complexity of RL, making training more stable and efficient, especially suitable when large amounts of human preference data are available.

For example, an RL-trained model is like groping forward in the dark, requiring repeated trial and error; the supervised DPO approach is like being handed a map that tells you the correct route. With supervised learning, you can reach the goal faster.

Basis for choosing a method: If the task has clear, objective evaluation criteria, ReFT is appropriate, with automated programs assessing model outputs. If you want outputs that better align with human subjective preferences and have abundant human feedback data, choose RLHF or DPO. RLHF uses RL algorithms that require model–environment interaction and lead to complex training; DPO uses supervised learning and is simpler and more efficient to train. If human feedback is costly, consider RLAIF, using an auxiliary AI model to provide feedback signals.



---
# Part 3: The essential difference between Reinforcement Learning and fine-tuning

> *Originally from Comparison-of-Various-Fine-Tuning-Methods*


## Differences between Reinforcement Learning methods and supervised fine-tuning methods

**I. Reinforcement Learning**

Basic framework of Reinforcement Learning

Reinforcement Learning (RL) is a process in which an agent interacts with an environment. The agent’s objective is to learn a policy that maximizes cumulative reward through interaction with the environment.

 

![images](images/ext_10.png)

#### **1. Key components**

##### **(1) State space (S)**

- **Definition**: The set of all possible states the environment can be in.
- **Notation**: At time step t, the environment’s state is denoted as **s_t**.

##### **(2) Action space (A)**

- **Definition**: The set of all possible actions the agent can take.
- **Notation**: At time step t, the agent’s action is denoted as **a_t**.

##### **(3) Policy (π)**

- **Definition**: A mapping from states to actions that determines which action the agent chooses in each state.
- **Notation**:
  - **Deterministic policy**: a_t = π(s_t), i.e., in state s_t, it always chooses the same action.
  - **Stochastic policy**: actions are sampled from a probability distribution, a_t ~ π(a | s_t).

##### **(4) Reward function (R)**

- **Definition**: Specifies the immediate reward obtained after taking an action in a given state.
- **Notation**: R(s_t, a_t) denotes the reward after taking action a_t in state s_t.

##### **(5) State transition probability (P)**

- **Definition**: Describes the probability that the environment transitions to the next state after the agent takes an action in the current state.
- **Notation**: P(s_{t+1} | s_t, a_t) denotes the probability of transitioning to state s_{t+1} after taking action a_t in state s_t.

##### **(6) Discount factor (γ)**

- **Definition**: Balances the importance of immediate rewards versus future rewards, with 0 ≤ γ ≤ 1.
- **Characteristics**:
  - When γ is close to 0, the focus is on immediate rewards.
  - When γ is close to 1, the focus is on long-term cumulative rewards.

##### **(7) Value function**

- **State-value function (V^π(s))**:

  - **Definition**: Under policy π, the expected cumulative reward starting from state s.

  - **Notation**:

    ```
    V^π(s) = E_π [ R(s_t, a_t) + γ * V^π(s_{t+1}) | s_t = s ]
    ```

- **Action-value function (Q^π(s, a))**:

  - **Definition**: Under policy π, the expected cumulative reward after taking action a in state s.

  - **Notation**:

    ```
    Q^π(s, a) = E_π [ R(s, a) + γ * Q^π(s_{t+1}, a_{t+1}) ]
    ```

#### **2. Example**


**Example: Self-driving car**

- **Environment**: A simple 2D road grid; the car needs to reach the goal from the start.
- **State (s_t)**: The car’s current position coordinates, e.g., (x, y).
- **Action (a_t)**: Possible movement directions, e.g., up, down, left, right.
- **Policy (π)**: The rules that determine which direction to move at each position.
- **Reward function (R)**:
  - **Reaching the goal**: reward +100.
  - **Each step**: penalty -1 (encourages reaching the goal quickly).
  - **Hitting an obstacle**: penalty -50.
- **State transition probability (P)**: In a deterministic environment, taking an action deterministically leads to the corresponding new position. If randomness is introduced—for instance, a nonzero probability of slipping to another cell due to a slippery road surface—then P(s_{t+1} | s_t, a_t) is used to describe such probabilities.
- **Discount factor (γ)**: Set to 0.9 so the car cares about immediate rewards (avoiding unnecessary moves) while also valuing the large final reward for reaching the goal.



#### **3. Objective of Reinforcement Learning**

- **Goal**: Learn an optimal policy π* such that the agent’s expected cumulative reward in the environment is maximized.

- **Mathematical formulation**:

  ```
  π* = arg max_π E_π [ ∑_{t=0}^∞ γ^t * R(s_t, a_t) ]
  ```

  where E_π denotes the expectation over all possible state and action sequences under policy π.



#### **4. Summary of key RL elements**

- **State (s_t)**: Perception of the environment; where the agent currently is.
- **Action (a_t)**: The set of actions the agent can execute.
- **Policy (π)**: Rules guiding the agent’s action selection.
- **Reward signal (R)**: Immediate feedback evaluating the quality of the agent’s actions.
- **Discount factor (γ)**: Balances immediate and future rewards.
- **Value functions (V^π(s), Q^π(s, a))**: Evaluate policy quality and guide policy improvement.
- **Learning algorithms**: Methods to update the policy and value functions, e.g., Q-learning, SARSA, policy gradient methods, Actor-Critic, etc.



#### **5. Summary**


In Reinforcement Learning, the agent continuously interacts with the environment and adjusts its policy based on reward signals, aiming to find the optimal policy that maximizes cumulative reward. Key components include:

- **State space (S)\**and\**Action space (A)**

- **Policy (π)**

- **Reward function (R)**

- **Discount factor (γ)**

- **Value functions (V^π(s), Q^π(s, a))**

- **Learning algorithms**

  

**II. Reward function and reward model**

Reinforcement Learning does require reward signals to guide the agent to learn an optimal policy that maximizes cumulative reward. However, it is important to clarify that while RL requires a reward signal, it does not necessarily need to be obtained via a reward model. The reward signal can be provided directly by a predefined reward function or obtained via a reward model, depending on the specific task and environment.

**Differences between reward function and reward model**

**1. Reward function (Reward Function)**

- **Definition**: An explicitly hand-crafted set of rules or formulas that directly compute the immediate reward based on the agent’s state and action.

- **Characteristics**:

  - **Clear rules**: Explicitly specify rewards or penalties in given situations.
  - **Direct computation**: No training or learning is required; rewards are computed directly from state and action.
  - **High interpretability**: Easy to understand and explain since the rules are human-designed.

- **Applicable scenarios**: Tasks with clear, objective, and easily quantifiable evaluation criteria.

- **Example**:

  In the earlier self-driving car example, we defined the following reward function:

  This reward function is explicitly designed by humans; the agent can directly compute the reward for each action from it.

  - **Reaching the goal**: reward **+100**.
  - **Each move**: penalty **-1**, encouraging the shortest path.
  - **Hitting an obstacle**: penalty **-50**, discouraging dangerous behavior.

**2. Reward model (Reward Model)**

- **Definition**: A model trained via machine learning to predict or evaluate the reward of the agent’s behavior or outputs.

- **Characteristics**:

  - **Data-driven**: Trained on large volumes of human feedback data.
  - **Handles complex evaluation**: Can capture complex, subjective evaluation criteria; suitable when it is hard to handcraft a reward function.
  - **Requires training**: The model’s parameters are learned to accurately predict rewards.

- **Applicable scenarios**: Tasks with complex, subjective, and hard-to-quantify evaluation criteria.

- **Example**:

  In training dialogue generation models such as ChatGPT, it is difficult to hand-design an explicit reward function to evaluate response quality. Therefore, we:

  - **Collect human feedback data**: Humans rate or compare model-generated responses.
  - **Train a reward model**: Using this data to train a model that predicts response quality scores.
  - **Apply it in Reinforcement Learning**: During training, after the model generates a response, the reward model evaluates it and provides a reward signal to guide optimization.

**Summary**

- **Reinforcement Learning must have a reward signal**, which is the key driving force for the agent’s learning.
- **The source of the reward signal** can be:
  - **Reward function**: Hand-designed; suitable for tasks with clear evaluation criteria.
  - **Reward model**: Trained; suitable for tasks with complex, subjective evaluation criteria.
- **Whether a reward model is needed depends on the specific task requirements**:
  - **Simple tasks with clear rules**: A reward function suffices.
  - **Complex, subjective tasks**: A reward model is needed to capture human evaluation standards.



Therefore, Reinforcement Learning definitely requires a reward signal but does not necessarily have to use a reward model. **In many traditional RL applications, hand-designed reward functions are already effective. However, in certain complex domains—especially tasks involving human subjective evaluation—a reward model becomes necessary.
**III. Direct Preference Optimization (DPO)**

Direct Preference Optimization (DPO) is a method that directly optimizes a policy using human preference data, aiming to align the model’s behavior more closely with human expectations. Compared with traditional reinforcement learning, DPO does not require training a separate reward model; instead, it directly uses human preferences to guide model optimization. 

 

**1. Key Components**

**(1) Policy Model**

- Definition: The model to be optimized, which determines the action taken by the agent at each state.
- Representation: The policy model is denoted as πₜθ, where θ denotes the model parameters.

**(2) Human Preference Data**

- Definition: Feedback reflecting human preferences over model behavior, typically in the form of pairwise comparisons.
- Representation: Given the same input, the model generates two different outputs, called A and B. Human evaluators choose the output they prefer.

**(3) Reference Policy**

- Definition: The initial, unoptimized policy model used to stabilize the new policy’s behavior during training.
- Role: Prevents the policy model from deviating too far from the initial behavior during optimization, maintaining model stability.

**(4) Loss Function**

- Definition: A loss function constructed from human preference data to optimize the policy model’s parameters.
- Objective: Maximize the probability that the policy model generates outputs selected by human preference.

**2. Example**

Example: Optimizing a car’s navigation policy via DPO

Background:

- Environment: A two-dimensional grid world where an intelligent car needs to reach the destination from the starting point, possibly encountering obstacles along the way.

- State (s_t): The car’s current position coordinates (x, y).

- Action (a_t): The car’s possible movement directions: up, down, left, right.

- Objective: Not only to have the car reach the destination via the shortest path, but also to align with human preferences for the route, such as avoiding specific areas (e.g., danger zones) or passing through scenic routes.

  **Steps**:

**(1) Initial Policy Model**

- Setup: The car has an initial policy model π₀, which may be generated based on a shortest-path algorithm.
- Issue: This policy might lead the car through dangerous areas or miss scenic routes, which does not align with human preferences.

**(2) Collect Human Preference Data**

- Generate candidate paths:
  - Given a start and end point, the policy model π₀ generates different travel paths.
- Human evaluators perform comparisons:
  - Safety: Avoid dangerous regions.
  - Aesthetics: Pass through scenic places.
  - Efficiency: Moderately short path length.
  - For each pair of candidate paths A and B, human evaluators choose the path they prefer based on their own preferences.
  - Preference factors may include:

**(3) Build the Dataset**

- Data format: [(start, end), path A, path B, human preference]
- Example:
  - Start: coordinates (0, 0)
  - End: coordinates (5, 5)
  - Path A: Passes through a dangerous area but is the shortest path.
  - Path B: Slightly longer, but avoids dangerous areas and passes through scenic spots.
  - Human preference: Choose path B.

**(4) Define the Loss Function**

- Objective: Optimize the policy model πₜθ to make it more inclined to generate paths preferred by humans.

- Loss function design:

  - If humans prefer path B but the policy model is more inclined to path A, then Δ > 0, the loss will be larger, prompting the model to adjust its parameters.

  - By minimizing the loss function, the policy model becomes more inclined to generate human-preferred paths.

  - Δ = s_θ(A) - s_θ(B), representing the difference in preference scores assigned by the policy model to paths A and B.

  - s_θ(X) is the score computed by the policy model for path X (e.g., the log-probability of the path).

  - σ(Δ) is the Sigmoid function, mapping the difference to the interval (0, 1).

  - For each preference datum:

    ```
    L(θ) = -log(σ(Δ))
    ```

    Where:

  - Intuition:

#### **(5) Incorporate the Reference Policy**

- Reference policy π₀: The initial policy model.

- Regularization term: Prevents the policy model from deviating too far from the initial policy, maintaining reasonable paths.

  ```
  R(θ) = KL(πₜθ || π₀)
  ```

  Where:

  - KL denotes Kullback-Leibler divergence, measuring the difference between the policy model and the reference policy.

- Total loss function:

  ```
  L_total(θ) = L(θ) + λ * R(θ)
  ```

  - λ is a hyperparameter that balances the loss and the regularization term, controlling how far the model deviates from the initial policy.

#### **(6) Optimize the Policy Model**

 

- Minimize the total loss L_total(θ) to update the policy model parameters θ.
- Iterative training: Repeat the above process until the model’s performance on validation data meets expectations.

#### **(7) Results**

- Optimized policy model πₜθ:
  - More inclined to plan routes that align with human preferences.
  - When encountering similar navigation problems, it can automatically choose routes that are both safe and scenic.

**3. Advantages of DPO**

- Direct use of human preference data: No need to train an additional reward model, reducing complexity.
- Stable training: Introducing a reference policy prevents overfitting and maintains reasonable behavior.
- Higher efficiency: Compared to traditional reinforcement learning methods, DPO’s training process is simpler and less resource-intensive.
- Strong applicability: Suitable for tasks that need to adjust policies based on human preferences.

**4. Summary**

- DPO is an effective policy optimization method that directly uses human preference data to optimize an agent’s policy, making its behavior better aligned with human expectations.
- In the car navigation example, the DPO approach helps the agent learn how to plan routes that are both safe and scenic, improving user experience.
- Key ideas:
  - Construct a loss function using human preference data to directly optimize the policy model.
  - Introduce a reference policy as regularization to ensure model stability.

**IV. Techniques adopted by various training/fine-tuning methods**

1. **SFT (Supervised Fine-Tuning，有监督微调)**

   - Whether it belongs to reinforcement learning: It is not reinforcement learning.

   - Category: Supervised learning.

   - Explanation:

     SFT is supervised fine-tuning of a pre-trained model (such as a large language model). It uses labeled data (input-output pairs) to train the model, improving performance on specific tasks. The model directly learns the mapping between inputs and desired outputs, without involving reinforcement learning concepts.



2. **ReFT (Reinforced Fine-Tuning，强化微调)**

- Whether it belongs to reinforcement learning: It is reinforcement learning.

- **Use a reward function or a reward model: \**use\** a reward function**.

- Explanation:

  ReFT builds on SFT and uses reinforcement learning algorithms (such as PPO) to further optimize the model. In ReFT, the reward signal is typically computed via an explicit reward function, for example, based on the match between the model’s output and the ground-truth answer. The model adjusts its parameters using reinforcement learning algorithms according to the immediate reward signal provided by the reward function, to improve performance. This approach is suitable for tasks with clear evaluation criteria, such as solving math problems.



3. **RLHF (Reinforcement Learning from Human Feedback，基于人类反馈的强化学习)**

- Whether it belongs to reinforcement learning: It is reinforcement learning.

- **Use a reward function or a reward model: \**use\** a reward model**.

- Explanation:

  RLHF combines SFT and reinforcement learning. After SFT, the model learns about the quality of its outputs by collecting human feedback. Humans rate or rank the model’s outputs, and this feedback is used to train a reward model. The reward model can predict human preferences or satisfaction with different outputs. During the reinforcement learning phase, the model uses the reward signal provided by the reward model and optimizes its policy with algorithms such as PPO, so that its outputs better align with human expectations.



4. **RLAIF (Reinforcement Learning from AI Feedback，基于AI反馈的强化学习)**

- Whether it belongs to reinforcement learning: It is reinforcement learning.

- **Use a reward function or a reward model: \**use\** a reward model**.

- Explanation:

  RLAIF is similar to RLHF, but the difference lies in the source of the reward signal. RLAIF uses a pre-trained AI model (rather than humans) to evaluate the main model’s outputs and provide reward signals. This AI model serves as a reward model, guiding the main model’s optimization by predicting output quality or conformity. This approach reduces dependence on human feedback, but its effectiveness depends on the quality of the AI feedback model.



5. **DPO (Direct Preference Optimization，直接偏好优化)**

- Whether it belongs to reinforcement learning: It is not reinforcement learning.
- Category: Supervised learning, directly optimizes model parameters.

- **Explanation:**

  The DPO method does not use reinforcement learning algorithms; instead, it directly leverages human preference data for supervised learning. After collecting human preferences on model outputs, it constructs a loss function that encourages the model to generate outputs favored by humans. By minimizing this loss function, it directly optimizes model parameters. This approach avoids the complexity of reinforcement learning, yields a more stable training process, and is suitable for scenarios with abundant human preference data.



6. **PPO（Proximal Policy Optimization，近端策略优化）**

- Whether it belongs to reinforcement learning: It belongs to reinforcement learning.

- **Use reward function or reward model：\**Depends on the application scenario, can use\**reward function** or **reward model**。

- **Explanation:**

  PPO is a reinforcement learning algorithm used to update the policy network. By constraining the magnitude of policy updates, it ensures training stability and efficiency. PPO itself is an algorithmic tool commonly used in models that require reinforcement learning, such as ReFT and RLHF. It can be optimized based on different reward signals:

  - **Using a reward function:** When the reward signal comes from explicit computation (such as correctness comparison in ReFT), PPO uses a reward function.
  - Using a reward model: When the reward signal comes from a trained reward model (such as the human feedback model in RLHF), PPO uses a reward model.



## Introduction to ReFT

### OpenAI's ReFT

监督式微调 (SFT) involves taking a pre-trained model and adapting it using supervised learning techniques with additional data. In practice, SFT works best when the goal is to align the model’s outputs or format with a specific dataset or to ensure the model follows certain instructions.

Although supervised fine-tuning and reinforced fine-tuning both rely on labeled data, they use it differently. In SFT, labeled data directly drives the model updates. The model treats it as the target output and adjusts its parameters to reduce the discrepancy between its predicted output and the known correct answer.

In RFT, the model’s exposure to labels is indirect because they are primarily used to create reward signals rather than direct targets. This is why less labeled data is needed in RFT—the model seeks patterns to produce the outputs we want rather than directly producing our outputs, which guarantees a stronger *generalization tendency*.

We summarize the differences with this table:

| Feature                | Supervised Fine-Tuning (SFT)                          | Reinforced Fine-Tuning (RFT)                                   |
| ---------------------- | ------------------------------------------------------ | --------------------------------------------------------------- |
| **Core idea**          | Train the model directly on labeled data to match desired outputs. | Use a “grader” to provide rewards for generating desired outputs. |
| **Use of labels**      | Directly as targets for the model to imitate.          | Indirectly used to create reward signals for the model.         |
| **Data efficiency**    | Requires more labeled data.                            | May require fewer labeled data due to generalization.           |
| **Human involvement**  | Only in initial data labeling.                         | Only in designing the “grader” function.                        |
| **Generalization**     | May overfit the training data, limiting generalization. | Higher generalization potential due to focus on patterns and rewards. |
| **Alignment with human preferences** | Limited, as it relies entirely on imitating labeled data. | Better alignment if the “grader” accurately reflects human preferences. |
| **Examples**           | Fine-tuning a language model to generate specific text formats (e.g., poetry or code). | Training a language model to generate creative content, judged by a “grader” for originality and coherence. |

Training data examples are as follows; in training, the answers are not directly included in the training set.

![images](images/3.png)

During training, the model may or may not include the correct answer:

![images](images/4.png)

Create jsonal files for the training set and validation set:

![images](images/5.png)

![images](images/6.png)

Construct the reward function:

![images](images/7.png)

![images](images/8.png)

This JSON file (grader.json) defines the configuration of a scoring system. Specifically, this configuration file defines how to score an object. Let’s parse the file line by line:

1. `"type": "object-grader"`：

   - This line defines the grader type as “object-grader,” indicating this is a grader used for scoring objects.

2. `"property_graders": { ... }`：

   - This field defines specific rules for scoring object properties. In this example, there are specific scoring rules for the property “genes.”

3. `"genes": { "type": "inverse-rank-grader" }`：

   - This defines the grader type for the “genes” property as “inverse-rank-grader.” “Inverse-rank-grader” typically means the score is based on inverse ranking.
   - An inverse-rank grader usually works by computing scores based on an element’s position in a list. The earlier the position, the higher the score. For example, the first-ranked element may score 1, the second 0.5, the third 0.33, etc.

4. `"calculate_output": "genes"`：

   - This line defines how the grader’s final output is computed, which is based on the “genes” property.

     

     Summary:
     This JSON configuration file defines a scoring system that uses an “inverse-rank-grader” to score the object’s “genes” property, and computes the final output based on this score. Specifically, the “inverse-rank-grader” calculates scores according to the position of elements in the “genes” list, where earlier positions get higher scores.

     Combined with the previously mentioned score (0.7), one can infer the scoring mechanism may be based on inverse ranking in the “inverse-rank-grader.” For example, if “FOXE3” ranks high in the list (e.g., first or second), it might receive a higher score. The exact scoring rules depend on the implementation details of the “inverse-rank-grader.”

Set training hyperparameters:

![images](images/9.png)

Training results:

![images](images/10.png)

![images](images/11.png)

![images](images/12.png)

### ByteDance's ReFT

First, see the flowchart from the ReFT paper:

![images](images/ext_11.png)

As shown above, ReFT combines Supervised Fine-Tuning (SFT) and Reinforced Fine-Tuning (ReFT). Below is a detailed explanation of each part in the figure:

1. **Supervised Fine-Tuning (SFT):**

   - **Model:** The initial model is trained on the training data for multiple SFT epochs. The training data contains questions (x), chain-of-thought (CoT, e), and answers (y).
   - **SFT Epochs:** The model is trained for multiple epochs on the training data to learn how to generate the correct answer (y) from the question (x) and chain-of-thought (e).
   - **Models at different stages:** The figure shows changes in the model’s “expressions” after different training stages, indicating the model gradually improves.

2. **Reinforced Fine-Tuning (ReFT):**

   - **Warm-up phase:** Before entering reinforcement learning, the model is warmed up via SFT.
   - **Question:** The model receives an input question (x).
   - **On-Policy Sampling:** The model generates a chain-of-thought and answer (e', y') under the current policy.
   - **Golden Reward:** Compare the generated answer (y') with the correct answer (y) to provide a reward signal. If the answer is correct, give a positive reward (√); otherwise, a negative reward (×).
   - **Reinforcement Learning:** Use the reward signal to adjust the model parameters to improve performance on the same data.

3. **Final Policy:**

   - After SFT and ReFT training, the model forms the final policy and can answer questions more accurately.

     The legend illustrates an example of a question (x), chain-of-thought (e), and answer (y) on the GSM8K dataset. The training data is iterated over multiple SFT epochs, and ReFT is used with warm-up from SFT, followed by reinforcement learning on the same data.

## TPO Workflow

First, look at the Thought Preference Optimization (TPO) process:

![images](images/ext_12.png)

- The TPO method consists of three main components:
  1. SFT (Supervised Fine-Tuning): provides the model foundation.
  2. Thought Generation: enables the model to perform internal reasoning before answering.
  3. DPO (Direct Preference Optimization): directly optimizes model parameters using preference pairs generated by an AI judge model.
- Innovations of TPO:
  - Introduces thought generation to enhance the model’s reasoning and planning abilities.
  - Uses feedback from AI judge models, reducing reliance on human preference data.
  - Uses the DPO method to simplify the training pipeline and improve training efficiency.



**TPO = SFT + Thought Generation（Thought Generation）+ DPO（Preference Optimization）**

It is important to note that the DPO method (Direct Preference Optimization) typically uses human preference data directly and introduces a reference model. In traditional applications, DPO relies on human preference feedback on model outputs and constructs a loss function via a reference model to directly optimize model parameters. However, the TPO method (Thought Preference Optimization) extends DPO to use preference data generated by AI models, enabling training with preference optimization even in the absence of human preference data. It is crucial to emphasize that for DPO, the combination of the reference model and preference data is key. Regardless of whether the preference data comes from humans or AI models, DPO constructs the loss function using the reference model and preference data to directly optimize the model, without involving reinforcement learning algorithms. 
**A concrete explanation of the TPO method is as follows:**

**1. SFT (Supervised Fine-Tuning):**

- **Seed Model:** TPO starts with a pre-trained model that has already undergone SFT (e.g., Llama-3-8B-Instruct).

  **2. Thought Generation:**

- **Introducing a thought process:** Before generating the final answer, the model is guided by specific prompts to produce an internal thought process (Thought).

- **Separation of thought and answer:** The generated output is divided into a thought part and an answer part, with the thought part hidden from the end user.

  **3. DPO (Direct Preference Optimization):**

- **Introduction of a reference model:** Use the SFT-trained model as the reference model, with parameters frozen.

- **Source of preference data:** Preference pairs come from evaluations of model outputs by an AI judge model rather than traditional human preference data.

- **AI judge models:**

  - **Self-Taught Evaluator (STE):** Based on a large language model (e.g., Llama-3-70B-Instruct), used to compare two answers and output a preference.
  - **ArmoRM:** A reward model that directly scores a single answer.

    **Optimization process:**

- **Generate candidate outputs:** For each input instruction, the model generates multiple candidates containing both thought and answer.
- **Evaluate the answer part:** Feed the answer part into the AI judge model for scoring or pairwise preference comparison.
- **Construct preference pairs:** Based on evaluation results, select the best and worst answers to form preference pairs (Chosen and Rejected).
- **Optimize with DPO:** Use these preference pairs together with the reference model to construct a loss via DPO and directly optimize model parameters.

## Essential Differences Between PPO and DPO

### 1. The essence of reinforcement learning


Reinforcement learning is like training a puppy to perform actions.

For example:

- Training a puppy: When the puppy performs the correct action (e.g., sit, shake), we give it a treat as a reward; when it does it wrong, we don’t reward it.

- Goal: After many training rounds, the puppy learns that doing the right action earns rewards, so it becomes more willing to do what we want.

  In machine learning:

- Interaction between model and environment: The model (analogous to the puppy) interacts within an environment and, based on the current state, chooses an action.
- **Receive rewards or penalties**: The environment provides a reward based on the model’s actions (the reward can be positive or negative).

- **Optimization objective**: The model’s goal is to learn a policy that maximizes cumulative reward over long-term interactions with the environment.

  **In simple terms:**

- **Reinforcement learning = trial-and-error learning + reward mechanism**

- By continually trying different actions, the model learns which behaviors can obtain more reward.

  **For example:**

- A robot in a game: Imagine a robot searching for an exit in a maze.

  - **Reach the exit**: reward +10 points.
  - **Hit a wall**: reward -1 point.
  - **Other cases**: reward 0 points.

- Action selection:

  - At each step, the robot chooses to move up, down, left, or right (action) based on its current position (state).

- Model objective:

  - Learn an optimal path to quickly find the exit and achieve the highest cumulative reward.

### 2. The essence of Direct Preference Optimization (DPO) on preference data

**Direct Preference Optimization (DPO)** is a method that directly uses preference data and a reference model to optimize the model.

**For example:**

- **The model generates two answers**: For the same question, the current model (Policy Model) produces answer A and answer B.

- **Obtain preference feedback**: We ask human evaluators or an auxiliary AI model to tell us which answer is better.

  - For example, a human evaluator says: “Answer A is better than answer B.”

- **Introduce a reference model**:

  - **Reference model**: Typically the initial model after Supervised Fine-Tuning (SFT), whose parameters remain fixed during DPO training.
  - **Role**: Provide a stable probabilistic baseline, preventing the current model from drifting away from the pretraining language distribution during optimization.

- **Construct the loss function**:

  - **Using the current model and the reference model**, compute the log probabilities of the two answers.
  - **Loss function**: Design a loss that makes the current model more inclined to generate the human-preferred answer while constraining the magnitude of updates to keep training stable.

- **Directly optimize the model**:

  - By minimizing the loss, directly adjust the current model’s parameters so that it is more inclined to produce the preferred answer A.

    **Difference from reinforcement learning:**

- **No need for a complex reward function**: DPO does not require designing a numeric reward function or an interaction mechanism with an environment; it only needs preference comparisons and the reference model’s probabilistic baseline.

- **No environment interaction required**: DPO directly uses existing preference data and the reference model for optimization, without ongoing model-environment interaction, and without immediate reward signals.

  **In simple terms:**

- **DPO = directly adjust model parameters using preference comparisons and the reference model**

- Based on which outputs are preferred, and leveraging the reference model’s probability information, the model directly optimizes itself to favor outputs more aligned with human preferences.

  **For example:**

- **Training a chatbot**:

  1. **The model generates two answers**: For a user’s question, the current model produces two candidate answers.

     - **Answer 1**: “Okay, I will help you look up the relevant information.”
     - **Answer 2**: “I don’t know, go check it yourself.”

  2. **Collect preference data**: Human evaluators compare the two answers and pick the better one.

     - The human evaluator prefers **Answer 1** because it is more polite and has a better service attitude.

  3. **Introduce a reference model**:

     - Use the SFT-trained initial model as the reference model, with its parameters fixed.

  4. **Construct the loss function**:

     - Compute the log probabilities assigned by the **current model** and the **reference model** to **Answer 1** and **Answer 2**.
     - Design the loss to encourage the current model to increase the probability of the preferred answer (Answer 1) and decrease that of the non-preferred answer (Answer 2), while using the reference model’s information to stabilize training.

  5. **Directly optimize the model**:

     - Minimize the loss to update the current model’s parameters so it becomes more inclined to produce content like **Answer 1**.

       **Summary:**

- **The DPO method** combines **human preference data** and a **reference model** to directly optimize model parameters within a supervised learning framework.

- The **reference model** provides a stable baseline to prevent the model from deviating too far from the pretraining language distribution, ensuring training stability and output quality.

- **Differences from reinforcement learning**:

  - DPO does not involve interaction with an environment or immediate reward signals, avoiding the complexity and instability of reinforcement learning.
  - DPO’s optimization process is more direct and stable, making it suitable for scenarios with abundant preference data.

### **3. About the “interaction” in DPO**


In the description of DPO, the model needs to generate multiple answers, and then human evaluators or an auxiliary AI discriminator model provides preference feedback (**Note: In the DPO part of TPO, preference data may come from an AI model**). This seems to also involve some interaction. So, doesn’t DPO also have interaction?

**Indeed, DPO involves “interaction” between the model and human evaluators or an AI discriminator model, because preference data must be collected. However, this interaction is fundamentally different from the interaction in reinforcement learning.**

#### **1. “Interaction” in DPO**

- Interaction in the data collection stage:
  - In DPO, the model generates multiple candidate outputs (such as answers) for each input.
  - **Human evaluators or an AI discriminator model** label preferences among these candidates, forming preference pairs (preferred and non-preferred responses).
  - **Characteristics**: This interaction is one-off and offline, used to build the training dataset. After data collection is complete, the process proceeds to the model training stage.
- Optimization during the training phase:
  - Once preference data collection is complete, the model is trained on these preference pairs, **together with the reference model**, using supervised learning to directly optimize the model parameters.
  - **No further interaction with human evaluators or the environment is required during training**, and the reference model’s parameters remain fixed during training.

#### **2. Interaction in reinforcement learning**



- Continuous environment interaction:
  - In reinforcement learning (e.g., PPO), the model must continuously and dynamically interact with the environment during training.
  - The model selects actions based on the current state; the environment returns a new state and a reward signal; the model updates its policy based on this information.
- Complexity of the training process:
  - Reinforcement learning training is online and iterative; the model must continually learn via trial and error to find the optimal policy.
  - It involves complex concepts such as **state, action, reward, value function, and policy updates**.

#### **3. Differences between the two**

- The nature and phase of interaction differ:

  - **DPO** interaction occurs in the pre-training data collection stage; it is **static and offline**. During training, the model only needs to use the collected preference data and the reference model for optimization.
  - **Reinforcement learning** interaction occurs during training; it is **dynamic and online**. The model must continuously interact with the environment to obtain immediate reward signals.

- Different training methods:

  - **DPO** uses supervised learning, together with a **reference model**, to build a loss from preference pairs and directly optimize model parameters.
  - **Reinforcement learning** requires methods such as policy gradients or value functions, updating the policy based on reward signals from the environment, typically using RL algorithms (e.g., PPO).

- Complexity and stability:

  - **DPO** training is relatively simple and stable because it is based on supervised learning; the introduction of a reference model further stabilizes training.
- **Reinforcement learning** training is more complex and may be unstable, requiring careful tuning of hyperparameters and training strategies.

#### **4. An example**


**Example of DPO:**

- **Step 1: Data collection**

  - The model generates two answers:

    - **Answer 1**: “Okay, I will help you look up the relevant information.”
  - **Answer 2**: “I don’t know, go check it yourself.”
    
  - **Human evaluators or an AI discriminator model** compare the two answers and prefer **Answer 1**.

- **Step 2: Model optimization**

  - **Introduce a reference model**: Use an SFT-trained model as the **reference model**, keeping its parameters fixed.
  - Construct the loss:
    - Use the **current model** and the **reference model** to compute the log probabilities for **Answer 1** and **Answer 2**.
    - Based on the preference data, design the loss to encourage the current model to increase the probability of the preferred answer (Answer 1) and decrease that of the non-preferred answer (Answer 2).
  - **Optimize the model**: By minimizing the loss, directly adjust the current model’s parameters so that it becomes more inclined to produce the preferred output.

- **Characteristics**:

  - **Data collection and model training are separate**.

  - **No interaction with human evaluators or the environment is required during training**, and the reference model provides a stable baseline in training.

    **Example of reinforcement learning:**

- **The model continuously interacts with the environment**:

  - During training, the model continuously interacts with the environment, chooses actions, observes feedback, and receives immediate rewards.
  - For example, **training a game AI**, the model must continually try different actions in the game environment and update its policy based on the score (reward).

- **Characteristics**:

  - **The training process requires continuous, online interaction**.
  - **The model’s behavior affects subsequent states and rewards**, making training more complex and requiring handling of environmental uncertainty.

#### **5. Summary**

- **Direct Preference Optimization (DPO)**:
  - **Interaction occurs during data collection**, which is offline and static. After preference data collection is complete, the training process no longer needs interaction.
  - **Supervised learning is used during training**, together with a reference model, to directly optimize the model using preference data.
  - **The training process is simple and stable**, with no environment interaction, and the introduction of a reference model ensures training stability.
- **Reinforcement learning**:
  - **Interaction occurs during training**, which is online and dynamic. The model must continuously interact with the environment to obtain immediate reward signals.
  - **Through continuous interaction with the environment**, the model updates its policy based on reward signals and must handle environmental uncertainty.
  - **The training process is complex**, potentially unstable, and requires careful tuning of training strategies and hyperparameters.



---
# Part 4: Comparison table of seven fine-tuning techniques

> *Originally from Comparison-of-Various-Fine-Tuning-Methods*


## Comparison of several techniques

| **Comparison dimension** | **SFT (Supervised Fine-Tuning)**           | **ReFT (Reinforced Fine-Tuning)**                           | **RLHF (Reinforcement Learning from Human Feedback)**       | **DPO (Direct Preference Optimization)**                     | **PPO (Proximal Policy Optimization)**            | **RLAIF (Reinforcement Learning from AI Feedback)**          | **TPO (Thought Preference Optimization)**                    |
| -------------- | ------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **Concept**    | Supervised fine-tuning of a pre-trained model using labeled data | On top of SFT, combines a **reference model** and uses automated evaluation and DPO to directly optimize the model | On top of SFT, combines human feedback and PPO for reinforcement learning | Uses human preference data and a **reference model** to directly optimize model parameters, avoiding RL complexity | A reinforcement learning algorithm that limits policy update magnitude to maintain training stability | On top of SFT, uses feedback from an AI model, combined with PPO for reinforcement learning | The model performs internal thinking before answering; combines a **reference model** and preference data to optimize parameters |
| **Implementation method** | Collect labeled data and minimize the loss between model outputs and target outputs | After SFT, sample model outputs and use automated evaluation or preference data; combined with a **reference model**, apply DPO to directly optimize | After SFT, collect human feedback, train a reward model, and use PPO to optimize the policy | Collect human preference data and, with a **reference model**, build a loss function to directly optimize model parameters | Interact with the environment, compute the advantage function, and use a clipped objective to optimize the policy | After SFT, use an auxiliary AI model for evaluation, train a reward model, and optimize with PPO | Use prompting to guide the model to generate thoughts and answers; use a **reference model** and preference data, and optimize with DPO |
| **Data requirements** | Large amounts of high-quality labeled data | Labeled data + automated evaluation programs or preference data + **reference model** | Labeled data + large amounts of human feedback + reward model | Large amounts of human preference data + **reference model** | Data generated through environment interaction | Labeled data + auxiliary AI model + reward model | Input data + discriminator model + **reference model** |
| **Human involvement** | High, requires human-labeled data | Low, no additional human feedback needed (if preference data comes from automated evaluation) | High, requires extensive human feedback | High, requires human preference data | Task-dependent; generally no human involvement | Low, no human feedback; relies on AI models | Low, no human chain-of-thought annotations; preference data can come from AI models |
| **Reference model** | **No** | **Yes**, uses a reference model to stabilize training | **No** | **Yes, a key component** | **No** | **Yes**, used for stabilizing training and comparison | **Yes, a key component** |
| **Thinking process** | No | No | No | No | No | No | **Yes**, the model generates thoughts before answering |
| **Reward mechanism** | Based on a loss function that minimizes the difference between predicted and target outputs | Use automated evaluation or preference data and **construct a loss with a reference model** for direct optimization | Outputs are evaluated by a reward model trained from human feedback and rewarded accordingly | Build a loss from human preference data and a **reference model** to directly optimize parameters | Rewards provided by the environment; compute advantages to guide policy updates | Auxiliary AI model evaluates outputs; train a reward model and provide rewards | Evaluate answer quality; **construct a loss with a reference model** to optimize parameters |
| **Training complexity** | Low | Medium; needs to integrate a reference model and preference data for optimization; training is stable | High; multi-stage training requiring human feedback and reinforcement learning | Medium; avoids RL complexity and is training-stable | Medium; requires hyperparameter tuning; training is stable | Medium; requires auxiliary AI model, reward model, and reinforcement learning | High; multiple iterative trainings optimizing thoughts and answers; must consider the reference model and preference data |
| **Advantages** | Simple, direct, easy to implement | Stable training; directly optimizes the objective; suitable for tasks with automated evaluation | Outputs better align with human expectations; improved safety and naturalness | Stable training; directly optimizes the objective; efficient; avoids RL complexity | High training stability; high sample efficiency | Reduces human feedback cost and scales training | Improves performance on complex tasks; no human thought data needed; applicable to multi-task settings |
| **Disadvantages** | High data demand; limited generalization | Dependent on the quality of automated evaluation or preference data; careful reference model selection required | High human labor cost; complex training; requires multi-stage process | Depends on preference data quality and reference model design | Complex hyperparameter tuning; lower sample efficiency | Depends on auxiliary model quality; may introduce bias | High training complexity; discriminator model quality has large impact; thought process may be uncontrollable |
| **Applicable scenarios** | Tasks with abundant labeled data | Tasks with clear evaluation criteria that can be automatically computed or have preference data | Tasks requiring high-quality outputs emphasizing human values and subjective evaluation | Tasks with abundant human preference data needing simplified training pipelines | Reinforcement learning tasks requiring environment interaction | Tasks where human feedback is unavailable but reliable AI model evaluation exists | Complex tasks, multi-step reasoning, and tasks lacking human chain-of-thought annotations |

**ReFT (Reinforced Fine-Tuning):**

- **Composition**: ReFT = SFT + **reference model** + DPO
- **Process**: On top of supervised fine-tuning (SFT), introduce a **reference model** (usually the SFT-initialized model with frozen parameters), and use DPO (Direct Preference Optimization), combined with automated evaluation or preference data, to directly optimize model parameters.
- **Evaluation approach**: Typically evaluates model outputs via **automated programs or preference data**; uses the **reference model** and evaluation results to construct a loss function for direct optimization.


**RLHF (Reinforcement Learning from Human Feedback):**

- **Composition**: RLHF = SFT + PPO + human feedback
- **Process**: On top of SFT, use PPO (Proximal Policy Optimization) for reinforcement learning, **introducing a reward model** whose reward signals come from **human feedback**. The model interacts with the environment and updates its policy using the reward signals.
- **Evaluation approach**: Humans rate model outputs to build preference data and train a **reward model**. During RL, the reward model evaluates outputs to provide reward signals that guide optimization.


**DPO (Direct Preference Optimization):**

- **Composition**: DPO = SFT + **reference model** + DPO
- **Process**: On top of SFT, introduce a **reference model** (parameters frozen) and use DPO with **human preference data** and the reference model to directly optimize model parameters.
- **Evaluation approach**: Use human preference data combined with the **reference model** to construct a loss that directly optimizes parameters, biasing the model toward outputs preferred by humans.


**RLAIF (Reinforcement Learning from AI Feedback):**

- **Composition**: RLAIF = SFT + PPO + **AI feedback** + reward model
- **Process**: On top of SFT, use PPO for reinforcement learning, **introducing a reward model** whose reward signals come from **AI model feedback**. The model interacts with the environment and updates its policy using AI-evaluated reward signals.
- **Evaluation approach**: An auxiliary AI model evaluates outputs to generate preference data and train a **reward model**. During RL, the reward model evaluates outputs, provides reward signals, and guides optimization.


**TPO (Thought Preference Optimization):**

- **Composition**: TPO = SFT + Thought Generation + **reference model** + DPO
- **Process**: On top of SFT, introduce **Thought Generation**, i.e., the model generates an internal thinking process before producing the answer. Then, use DPO combined with a **reference model** to directly optimize parameters; preference data comes from **AI discriminator feedback**.
- **Evaluation approach**: Use an **AI discriminator** to evaluate the **answer part** of the model output and form preference pairs (preferred vs. dispreferred). Combined with the **reference model**, use DPO to construct a loss and directly optimize parameters to improve performance.


---
# Part 5: LoRA/QLoRA Fine-tuning Mechanisms and GaLore Full Fine-tuning

> *Originally from Comparison-of-Various-Fine-Tuning-Methods*


## LoRA/QLoRA Fine-tuning Mechanisms and Adapter Merge Strategies

### Principle of LoRA

The core idea of LoRA (Low-Rank Adaptation) is to add a low-rank increment BA to the pretrained weights W, rather than directly modifying all parameters.

QLoRA further optimizes on this basis—first quantizing the large pretrained model to lower precision (typically 4-bit), then training a very small set of adapter parameters on top of it, thereby enabling effective fine-tuning while significantly reducing VRAM usage.

Key components include:

1. Pretrained Weights: the original pretrained model weights W; QLoRA quantizes these pretrained weights to 4-bit, drastically shrinking the model size and reducing memory footprint.

2. Adapter parameters (A and B): two small matrices A and B used in LoRA/QLoRA, stored and trained in 16-bit. The adapter parameter size is much smaller than the full model weights; during training, gradients and optimizer states are kept only for this small subset. At the start of training, B is initialized as a zero matrix and A is randomly initialized.

3. Forward pass: h = W x + B A x; the model output includes the contribution from the original pretrained weights W plus the incremental term obtained by multiplying the adapter BA with the input x.

4. Merged weights: during inference, W and BA can be merged into a new weight matrix W_merged for computation.

![images](images/qlora_perf_1.png)

### Mathematical example of low-rank matrix representation

Use a 4×4 small matrix to illustrate LoRA's low-rank update principle:

**Original weights** W (4×4):
```
W = [[1, 2, 3, 4],
     [2, 3, 4, 5],
     [3, 4, 5, 6],
     [4, 5, 6, 7]]
```

Choose r=2 (low rank), then B is (4×2) and A is (2×4):
```
B = [[0.1, 0.2],    A = [[2.0, 0.0, 0.0, 1.5],
     [0.0, 0.3],         [0.0, 1.0, 2.0, 1.0]]
     [0.1, 0.1],
     [0.0, 0.2]]
```

The result BA is a 4×4 matrix (with rank no greater than 2):
```
BA = [[0.2, 0.1, 0.4, 0.3],
      [0.0, 0.3, 0.6, 0.3],
      [0.2, 0.1, 0.4, 0.3],
      [0.0, 0.2, 0.4, 0.2]]
```

After fine-tuning, the weights are W_merged = W + BA, correcting the original weights via the product of two small matrices. When r is much smaller than d, the parameter counts of B and A are far less than d×d, saving substantial training cost and storage.

### Adapter merge strategies and the impact of quantization on accuracy

![images](images/qlora_perf_2.png)

Below are four different adapter deployment strategies and their comparative effects:

| Strategy | Method | Perplexity (PPL) | Notes |
|------|------|:-----------:|------|
| **Do not merge Adapter** | Base model 4-bit + Adapter 16-bit | **3.55** | Best performance; requires managing separate adapter files |
| **Merge then AWQ quantization** | Merge → 16-bit → AWQ 4-bit | 3.88 | Simple deployment; slightly worse performance |
| **Merge without quantization** | Merge → keep 16-bit | 3.60 | Requires 16-bit memory; comparable to not merging |
| **Merge then BnB quantization** | Merge → bitsandbytes 4-bit | 4.33 | **Not recommended**; regresses to pre-finetuning level |

**Conclusion**:
- For best performance → base model 4-bit + unmerged adapter (16-bit)
- For simpler deployment → merge then quantize to 4-bit with AWQ/AutoRound
- If memory is ample → merge and run inference in 16-bit
- **Avoid** merging then quantizing with bitsandbytes 4-bit

## GaLore Full Fine-tuning Experiments

GaLore (Gradient Low-Rank) supports full fine-tuning, i.e., updating all model parameters. Unlike parameter-efficient fine-tuning (PEFT) methods such as LoRA, GaLore uses a novel low-rank projection of gradients to enable full fine-tuning of large models under memory constraints.

![images](images/ext_13.png)

GaLore performance comparison:

![images](images/ext_14.png)

GaLore introduces additional hyperparameters: rank r, scale factor α, and subspace change frequency T.

### GaLore optimizer options

| Optimizer | VRAM requirement (Mistral 7B, BS=8) | Notes |
|--------|:---------------------------:|------|
| galore_adamw | Higher | Standard GaLore, float32 parameters |
| galore_adamw_8bit | ~35 GB (rank=512), ~30 GB (rank=128) | 8-bit quantized optimizer |
| galore_adamw_8bit_layerwise | ~22.5 GB | Layer-wise updates; can run on 24 GB consumer GPUs |

### Experimental logs

Below are full fine-tuning runs of Mistral-7B on a single H100 (trainable parameters = 7,241,732,096), using the openassistant-guanaco dataset.

**Experiment 1**: BS=128, lr=1e-5, optim=galore_adamw_8bit_layerwise, rank=512

![images](images/ext_15.png)

![images](images/ext_16.png)

![images](images/ext_17.png)

![images](images/ext_18.png)

Judging from the loss curve, the training is suboptimal.

**Experiment 2**: BS=64, lr=2e-5, optim=galore_adamw_8bit_layerwise, rank=512

Double the learning rate and halve the BS:

![images](images/ext_19.png)

![images](images/ext_20.png)

![images](images/ext_21.png)

Some improvement, but still suboptimal.

**Experiment 3**: BS=128, lr=1e-5, optim=galore_adamw_8bit, rank=512

After switching to the galore_adamw_8bit (non-layerwise) optimizer, GPU memory utilization is higher:

![images](images/ext_22.png)

![images](images/ext_23.png)

Training performs much better than before; results are satisfactory.

![images](images/ext_24.png)

**Experiment 4**: BS=128, lr=1e-5, optim=galore_adamw_8bit, rank=1024

Keep BS=128 and the galore_adamw_8bit optimizer, increase rank from 512 to 1024:

![images](images/ext_25.png)

During training, GPU memory usage spikes to 87 GB, but there is no OOM, highlighting the benefit of large VRAM:

![images](images/ext_26.png)

Examining the training results, it is better than Experiment 3; the loss drops directly to 0.825400 at step 50 and decreases to 0.71 at step 100:

![images](images/ext_27.png)

The above shows that while the training loss decreases as expected, the validation loss rises, indicating overfitting.

**Experiment 5**: BS=128, lr=1e-6, optim=galore_adamw, rank=1024, weight_decay=0.05, warmup_ratio=0.2

To address the overfitting in Experiment 4, lower the learning rate and increase weight_decay and warmup_ratio:

![images](images/ext_28.png)

Looking at the training results, the overfitting issue is resolved:

![images](images/ext_29.png)

### Summary of GaLore experiments

| Experiment | BS | LR | Optimizer | Rank | Result |
|:----:|:--:|:--:|--------|:----:|------|
| 1 | 128 | 1e-5 | galore_adamw_8bit_layerwise | 512 | Suboptimal |
| 2 | 64 | 2e-5 | galore_adamw_8bit_layerwise | 512 | Slightly better but suboptimal |
| 3 | 128 | 1e-5 | galore_adamw_8bit | 512 | **Ideal** |
| 4 | 128 | 1e-5 | galore_adamw_8bit | 1024 | Better, but overfitting |
| 5 | 128 | 1e-6 | galore_adamw | 1024 | **Best** (addresses overfitting) |

Key findings:
- `galore_adamw_8bit` outperforms `galore_adamw_8bit_layerwise`
- Higher rank (1024 vs 512) yields better results
- Overfitting can be mitigated by lowering the learning rate and increasing weight_decay and warmup_ratio



---
# Part 6: In-depth DPO Theory and Alignment Practice

> *Originally from LLM-Alignment-DPO-PPO-CPO*


## 6.1 Interpreting DPO and PPO: Best Practices for Learning from Preference Feedback

***Refer to ：Unpacking DPO and PPO: Disentangling Best Practices for Learning from Preference Feedback***

![images](images/6.png)

This paper again confirms that PPO significantly outperforms DPO. Notably, the original DPO paper claimed that in the context of reinforcement learning with human feedback (RLHF), DPO is better than PPO. However, after extensive practical tests, community feedback, and follow-up research, it has become clear that this is not the case.

In short, the study finds that synthetic, diverse datasets and detailed aspect-level preference information are most effective for training from preference data. Moreover, the quality of preference annotations matters more than the quality of the generated responses themselves. Across a variety of datasets, PPO generally outperforms DPO. Increasing the reward model size for PPO and adding more training data can significantly improve the reward model’s performance on direct evaluation, but these gains are mainly task-specific (e.g., GSM) rather than improvements to overall model performance. In addition, incorporating unlabeled prompts that closely match the test environment can improve domain-specific performance, such as math tasks, but has limited impact on broader metrics.

DPO’s operational cost is significantly lower than PPO because it does not require a reward model. Its simpler objective makes optimization easier and convergence faster. For general post-training tasks and budget-constrained AI projects, DPO remains a stronger alternative than more complex reinforcement learning methods such as PPO or GRPO.

### Detailed Explanation of PPO

 In the PPO training architecture, the four main models（Policy Model, Reference Model, Reward Model, Value Model）each play different roles, briefly described below:

![images](images/7.png)

1. Policy Model（policy model）
   • This is the "generative model" or "policy" we actually want to train and update; given an input（q）, it outputs some action (such as the next text tokens).
   • PPO’s objective is to enable this model to produce a better policy when given an environment (e.g., dialogue context or prompt).
2. Reference Model（reference model）
   • Typically a "frozen" reference policy used to compare the current Policy’s output distribution during training.
   • The Reference Model is used to compute the KL divergence: PPO penalizes (or constrains) large deviations between the new policy and the reference policy to avoid distribution collapse or drift during training.
3. Reward Model（reward model）
   • This model scores the Policy Model’s outputs, providing an "external" or "alignment" reward signal.
   • For example, in dialogue scenarios, the Reward Model may combine human feedback and task completion signals to assign preference scores to outputs.
   • In RLHF (reinforcement learning from human feedback), the Reward Model is typically trained on human-labeled data to measure answer quality, feasibility, politeness, etc.
4. Value Model（value function model）
   • Used to approximate the "value" of the current state (the expected long-term cumulative reward); it is the "critic" in PPO.
   • During training, the Value Model outputs a value estimate v, which helps compute the advantage and guides the Policy Model’s update.
   • In practice, GAE (Generalized Advantage Estimation) is often used to stabilize advantage estimation and reduce variance.

In summary, these four models work together:
• Policy Model is responsible for producing actions（outputs）,
• Reward is provided by the Reward Model,
• Value Model estimates the value function to support advantage computation,
• Reference Model is used to constrain the difference between the new and old policies during training（KL divergence）,
thus enabling iterative optimization of the generative policy via PPO while maintaining stability and controllability.



The outputs of these four models do not flow in a single linear chain "one feeds the next"; instead, they "each produce their outputs in parallel" and are finally combined in the PPO loss to guide parameter updates. You can think of it as "all models look at the same sample (state + response), compute their own results, and then aggregate into one big formula." Concretely:

1. The Policy Model first produces a response
   • Given an input (e.g., "7×8=?", state s), the Policy Model generates an action (response) "56".
   • This response (action) is then fed to the models below for their respective computations.

2) The reference model(Reference Model) computes KL
   • Given the same "state s + action a", the Reference Model computes the probability under the reference policy p_ref(a|s),
   while the Policy Model has its own probability p_new(a|s).
   • The KL or ratio = p_new / p_ref is recorded for the "policy constraint" component in PPO (KL penalty).
   • But it does not pass a "score" to the Reward Model or Value Model; it only computes a distributional comparison in its own dimension.

3) The reward model(Reward Model) scores the current response
   • The reward model only cares: "Is the response just output by the Policy good or not?"
   • Given the response "56", it assigns a score r, for example r=1.0 (correct).
   • This step also does not feed the "score" directly into the Value Model; instead, this r will be used later in the loss.

4) The value model(Value Model) estimates the value of the state
   • The Value Model takes "state s" (and possibly action a or prior context) as input and outputs a "predicted long-term return" v(s).
   • It does not directly take "reward r" as input, because its task is to "predict" how much reward will be obtained in the future (while r is the ground truth).
   • Once an episode is complete, we know the "true reward r" and the "value of the next state v(s')", enabling us to update the Value Model by comparing "v(s)" with "r + γ·v(s')".

5) The training script (or the PPO algorithm) aggregates the above results to construct the loss function
   • At the code level, we typically do the following:

1. Use the Policy Model to output action a;
2. Obtain the KL difference (or ratio) from the Reference Model;
3. Get the immediate reward r from the Reward Model;
4. Get the current value estimate v(s) and the next state's v(s') from the Value Model;
5. Compute the advantage A = r + γ·v(s') - v(s);
6. Assemble the PPO objective, which includes the "advantage × policy probability ratio" term, the KL penalty, and the value regression loss, etc.
   • Only then are all pieces of information "merged" into the same big loss to run backpropagation once, updating the parameters of the Policy Model and Value Model（the Reference is like a frozen teacher, and the Reward Model may also be an offline-trained scorer that is not updated）.



6. What is recorded in training outputs?
   • Typically the following (averaged over batches or reported every N steps):
   – Policy loss (the policy-gradient part of the loss)
   – Value loss (MSE of value prediction, etc.)
   – KL divergence (between new and old policy, or relative to the reference model)
   – Average reward (the average reward obtained by the Policy’s responses at this point)
   – Advantage mean (the average of the advantage)
   – and possibly the total loss
   You can also log, as needed: learning rate, gradient norm, GPU utilization, etc., to monitor training.

   

   **Summary**

   It may look like "a later model doesn’t use the previous model’s outputs" because they are not connected like an assembly line where "one model’s output is fed directly as the next model’s input"; rather, they are more like "four judges" each giving a score (or judgment) on the same sample from their own perspective:
   • Policy: provides the action (response)
   • Reference: computes the discrepancy relative to the reference policy
   • Reward: gives the score for the current response quality
   • Value: predicts long-term value

Finally, these signals are "jointly integrated" by our training logic (PPO), forming the loss and updating parameters. It is not truly "serial input-output", but a "parallel outputs → integrated effect" paradigm.



### Abstract

Learning from preference feedback has become a key approach for modern large language models (LMs) to improve generation quality and performance across tasks. Simply put, "preference feedback" typically has humans (or simulated systems) compare two different model outputs and choose which one they prefer, thereby guiding the model toward better responses.

However, in current practice, the sources of preference data, the choice of learning algorithms, and the evaluation protocols differ widely, making it difficult to identify which parts matter most to final performance. This work decomposes the "preference learning" pipeline into four core components:

1. Preference data (source and quality),

2. Learning algorithm (PPO, DPO, etc.),

3. Reward model,

4. Policy training prompts.

   We analyze them systematically and find that all components affect the final performance, but to different degrees:
   • Preference data quality is most critical; good data yields substantial gains.
   • Next is the choice of learning algorithm, especially PPO versus DPO.
   • Then comes having a more robust reward model.
   • Finally, if you care about a single domain, adding more targeted prompts during policy training can help that domain, but it brings limited gains on broad multi-task performance.

   In our experiments:
   • When focusing on math tasks, **PPO outperforms DPO by up to 2.5 percentage points; it also leads by 1.2 points on general tasks.**
   • High-quality preference data brings up to **8% performance improvements in instruction following and truthfulness**.
   • Even scaling the reward model from small/medium to larger sizes yields significant**（up to 5%）improvement,** in math tasks, but offers little help on other general tasks.

We open-sourced all training and evaluation code, as well as the corresponding models and datasets. Overall, high-quality preference data, appropriate algorithms and reward models, combined with suitable prompts, are the recipe for better downstream performance in "preference learning".

**Terminology**
• "Preference feedback": Suppose we give a model the same question and have it generate two different answers, A and B. A human annotator compares them and deems A better. The model thus "learns" that A’s style or approach is preferable and is fine-tuned in that direction.
• "Instruction following" and "truthfulness": If the system specifies "first list the solution steps, then give the final answer," a model with strong instruction following and truthfulness will provide correct and complete reasoning and avoid unfounded fabrication.


### Introduction

In modern large language model (LM) development pipelines, an additional stage—**learning from preference feedback (sometimes called RLHF, reinforcement learning from human feedback)—is often added before deployment.** Prior work has shown that this stage can significantly enhance models, including substantial improvements in instruction following, code generation, math problem solving, and summarization.

However, due to wide variation in datasets, algorithms, and evaluation practices across studies, it is difficult to determine "which component is the main driver of quality and efficiency gains." In particular, when comparing the two most common preference learning algorithms—PPO (Proximal Policy Optimization) and DPO (Direct Preference Optimization)—practitioners often wonder: What are their pros and cons? How should one choose?

Both PPO and DPO are trained on preference data, but their processes differ:
• DPO: performs offline optimization directly on preference data (prompt, chosen response, rejected response).
• PPO: first trains a "reward model," then uses it online to score the policy model’s outputs and update the policy via reinforcement learning.

![images](images/1.png)

Therefore, we decompose this preference learning pipeline into four parts:
1）Preference data
2）Learning algorithm
3）Reward model
4）Policy training prompts (the set of prompts used for online generation and scoring during training).

If we take the same trained (Supervised Fine-Tuned) model and vary any one of the above components, what happens to downstream performance? In our experiments, each component indeed has an effect, but their importance and impact differ.

### Setup

This section first briefly introduces the concepts and principles of PPO and DPO, then describes our experimental and evaluation procedures. It presents a structured comparison between PPO and DPO.  

![images](images/2.png)

**PPO and DPO（PPO and DPO）**
(1) PPO
In preference learning, PPO is often considered an "online" reinforcement learning approach:
• First train a "reward model" Rψ(x, y), which outputs a score representing quality given (x, y).
• During policy training, for each prompt x, we generate a response y with the current policy πθ, score it with the reward model, update the policy based on the scores, and add a KL penalty to the loss to prevent the policy from deviating too far from the initial reference policy πref.

(2) DPO
In contrast, DPO is an "offline" method:
• It does not dynamically sample new responses during training;
• Nor does it require maintaining a value network or reward model during policy training.
• The core idea of DPO is to optimize directly on existing (prompt, chosen, rejected) data.

**Experimental and Evaluation Setup（Experimental and Evaluation Setup）**

We base our study on the publicly released TÜLU 2 13B model series. The evaluation covers the following capabilities:
• MMLU: evaluates factuality.
• GSM8k, Big Bench Hard: evaluates reasoning ability.
• TruthfulQA: evaluates the truthfulness and correctness of responses.
• HumanEval+, MBPP+: evaluates coding ability.
• ToxiGen, XSTest: evaluates safety.
• AlpacaEval 1 & 2, IFEval: evaluates instruction following.


### Exploration Based on Preference Feedback

Here we expand along four aspects: (1) preference data; (2) learning algorithms; (3) reward models; (4) policy training prompts.  

**Preference Data（Preference Data）**

We collected 14 representative preference datasets, trained with DPO on each, and then evaluated downstream performance. Main findings include:
• Large improvements to "instruction following" and "truthfulness", but little help for "factual knowledge".
• "Synthetic + multi-aspect annotation" often works best.
• Some Arena data is relatively poor in safety.

**Learning Algorithms: DPO and PPO**
![images](images/3.png)
Under the conditions of identical preference data and model size (13B):
• PPO is overall slightly better than DPO, with an advantage of about 0.7 points.
• In reasoning, coding, and safety, PPO delivers more pronounced gains.
• For tasks requiring larger exploration spaces such as math and coding, PPO’s online generation and scoring mechanism has an advantage.

**Reward Models**

• Larger scale (70B) or more training data can indeed make the reward function more precise.
• But in aggregate multi-task settings, only math metrics show the most significant improvement.

**Policy Training Prompts**

![images](images/4.png)

• Targeted prompts can substantially improve a single domain (e.g., Math: 46% → 62%).
• But mixed prompts offer limited improvements to overall multi-task performance.


### A "Recipe" Based on Preference Feedback (A Recipe)

Combining the above analysis, recommended best practices:

![images](images/5.png)

- Preference data: Use high-quality synthetic preference data (e.g., UltraFeedback).
- Learning algorithm: In most scenarios, PPO generally outperforms DPO.
- Reward model: If compute and resources are available, opt for a larger reward model.
- Policy training prompts: If you only need extreme gains in a single domain, intensify the prompt distribution for that domain.


### Related Work

(1) Learning from preference feedback: Early studies often framed it as reinforcement learning; PPO is one of the most commonly used practical methods. This work systematically examines the combined impacts across multiple dimensions including data, algorithms, reward models, and policy prompts.

(2) Recent parallel research: Xu et al. focus on DPO’s unstable performance and PPO’s greater robustness; Tajwar et al. stress the importance of online sampling and explicit gradient updates on negative samples.


### Conclusion

This study systematically investigates the four core components of preference learning. The order of influence is:
- Preference data quality first determines the achievable ceiling,
- The learning algorithm (PPO vs. DPO) delivers a higher potential ceiling,
- Larger reward models can significantly benefit specific tasks,
- Policy training prompts deliver large gains only in specialized domains.

Overall, with a stronger reward model and effective online sampling, PPO training can better leverage high-quality preference data to further improve model performance.

---


## 6.2 DPO Deep Dive and Practice

### Bias Issues in RLHF, RLAIF, and DPO

RLHF (Reinforcement Learning with Human Feedback) and RLAIF (Reinforcement Learning with AI Feedback) are two methods used to fine-tune large language models (LLMs). Their primary difference lies in the source of feedback: RLHF relies on human-provided feedback, while RLAIF uses feedback generated by another LLM.

The advantage of RLHF is that it can train AI systems to handle use cases such as content moderation, where humans have better judgment than AI regarding language that constitutes hate speech, bullying, and other undesirable behaviors.

RLHF relies on human-provided feedback, which can introduce some challenges:

1. Cost and scalability: For use cases that require feedback involving domain-specific knowledge and skill sets, the process can become expensive and time-consuming. Therefore, RLHF may face difficulties at scale.
2. Consistency of feedback: Human feedback can be influenced by individual bias and subjectivity, which may affect training consistency and quality.

RLAIF attempts to address these issues by using another large language model (LLM) to generate feedback. This approach can significantly reduce the cost of obtaining feedback and improve feedback consistency. However, it also has its own challenges, such as potentially replicating and amplifying the biases and errors of the original model. This is why RLAIF and RLHF are often used together to leverage the strengths of both.

Comparison of bias sources across the three methods:

- DPO bias primarily comes from the AI model used to generate feedback. If that model has biases in its training data, those biases may be transferred to the fine-tuned model.
- RLAIF bias also primarily comes from the AI model used to generate feedback. If that model has biases in its training data, those biases may be transferred to the fine-tuned model.
- RLHF bias mainly comes from humans providing feedback. If the annotators have certain biases, those biases may be reflected in the model.

Overall, all three methods require careful handling of bias. This typically involves measures during data collection and model training, such as using diverse data sources, conducting fairness and bias audits, and, where possible, using transparent and interpretable models. This is also an active research area, where researchers are seeking better ways to understand and reduce AI bias.



### In-depth Analysis of the Reference Model in DPO

**https://huggingface.co/docs/trl/dpo_trainer**

DPO (Direct Preference Optimization) training requires two models:

1. Reference Model: A model fine-tuned with SFT on an instruct dataset.
2. Base Model: The model we aim to train using DPO.

![images](images/ext_30.png)

Differences between the Reference Model and the Base Model:

1. Reference Model:
   - Trained via supervised fine-tuning (SFT) on an instruct dataset, representing basic understanding and execution capabilities for specific tasks.
   - Serves as a baseline in DPO to compare and evaluate outputs generated by other models.
   - In some cases, it can be used as the initialization for subsequent DPO training, although this is not required.

2. Base Model:
   - The model we want to optimize via DPO; it may be untrained or already partially trained on some tasks.
   - Trained directly on human feedback during DPO to learn to produce outputs more aligned with human preferences.
   - Through DPO training, the base model gradually learns to emulate outputs rated as high quality by humans.

In DPO, the reference model primarily serves as a comparison baseline, whereas the base model is the actual optimization target. DPO simplifies optimization into a classification-style problem, allowing the base model to learn directly from human preferences without relying on complex reward functions or reinforcement learning algorithms.

Specific roles of the reference model:

1. Implicit reward computation: The reference model is used to compute the so-called implicit reward. In DPO training, we do not directly train a reward model to output reward values; instead, we use the reference model to estimate the probabilities of preferred and rejected answers and compute implicit rewards based on these probabilities. These implicit rewards guide the base model to favor “good” outputs.
2. Basis for the loss function: The implicit reward difference (i.e., the difference in probabilities assigned by the reference and base models to the chosen vs. rejected answers) forms the basis of the loss. This loss is maximized in DPO to increase the probability of generating preferred answers.
3. Providing stability: The reference model acts as a fixed point during training, providing stability and helping prevent the base model from drifting too far. As a constant, it makes training more stable and predictable.
4. Architectural consistency: DPO requires the reference and base models to share the same architecture. This ensures comparable probability outputs on the same inputs when computing implicit rewards.
5. Simplifying the training process: Compared to traditional RL methods, DPO simplifies training by using a reference model, avoiding the need to design complex reward and value models and reducing training complexity.
6. Role of the beta parameter: In DPO training, beta is a temperature parameter used to scale implicit reward differences. It controls how strongly optimization depends on the reference model’s behavior. A smaller beta gives the base model more freedom and less dependence on the reference.

Overall, the reference model provides a stable comparative baseline in DPO, giving the base model a clear direction during optimization and simplifying the process via implicit rewards. This makes DPO an efficient method for optimizing language models, especially when working with preference data.



### Why Choose DPO Instead of Direct SFT Fine-tuning?

Using an SFT Mistral as the reference model to train another Mistral model may sound redundant, but in the context of DPO it has specific purposes and justification.

The core of DPO is to directly optimize the model to produce outputs aligned with human preferences, typically by contrasting human-labeled “preferred” and “non-preferred” outputs. DPO’s goal is to train a model that systematically produces high-quality outputs.

In this process, the SFT Mistral model, as the reference model, primarily provides a performance baseline. It represents the capability level before training on specific preferences. The Mistral model used in DPO is then further optimized atop this baseline to generate outputs aligned with human preferences.

Why not continue fine-tuning the SFT model directly instead of using DPO? Reasons include:

1. Specific optimization objective: DPO optimizes a specific objective—outputs consistent with human preferences. This is not merely improving general performance but teaching the model to make decisions within a human feedback framework.
2. Simplification via a classification-style framing: DPO turns a complex RL problem into a relatively straightforward classification-style problem, making training more direct and efficient.
3. Avoiding reward model instability: Traditional RLHF requires training a reward model to guide learning, which can be unstable. DPO avoids this by directly leveraging human feedback.
4. Computational efficiency: DPO is often more efficient than traditional RLHF because it avoids training and maintaining multiple models, reducing compute requirements.
5. High-quality initialization: An SFT model provides a strong starting point with good task performance. DPO then further improves preference alignment rather than training from scratch.

In short, while SFT models are often strong enough, DPO offers a way to fine-tune using direct human preferences, enabling further optimization for specific application scenarios. This preference-based fine-tuning can better align outputs with human evaluators’ expectations while improving adaptability and generalization.



### Application Scenarios for DPO

Although DPO relies on a classification-style framework (distinguishing higher- vs. lower-quality outputs per human preference), it is not limited to traditional classification tasks. DPO is designed to solve optimization for generative tasks in language models.

In DPO, “classification” does not mean assigning instances to predefined labels; it means identifying and optimizing outputs so they match direct human preferences, typically defined via pairwise comparisons of response quality rather than fixed classes.

DPO is particularly suitable for:

1. Text generation: For tasks such as chatbots, article or poetry generation, DPO helps models learn to produce more natural, engaging, or style-conformant text.
2. Content recommendation: DPO can optimize recommendation algorithms to more accurately reflect user preferences.
3. Interactive applications: For applications that dynamically generate responses based on user input, DPO helps models better understand user intent and preferences.
4. Personalized services: DPO can be used for personalization, such as custom news summaries or product suggestions, enabling the model to learn individual user preferences.

While DPO borrows techniques from classification, its goal is to improve performance on generative tasks so the model produces outputs highly aligned with human preferences. This distinguishes it from traditional classification, making DPO a strategy tailored to generation rather than merely a classification method.



### Core DPO Code Reference

Below, using the Mistral 7B model as an example, we show the full DPO training pipeline.

**Dataset Preparation**

The reference model for training and the base model for DPO training use different datasets:

```python
dataset_train_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft")
dataset_test_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="test_sft[:5%]")

dataset_train_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="train_prefs")
dataset_test_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="test_prefs[:5%]")
```

Illustration of the two datasets:

![images](images/ext_31.png)

![images](images/ext_32.png)

**Model Loading and Adapter Configuration**

The DPO reference model is a Mistral 7B previously trained via supervised fine-tuning (SFT) on a specific dataset. The reference model is used to initialize an adapter, which is then used for DPO training.

```python
model = PeftModel.from_pretrained(model, "kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", is_trainable=True, adapter_name="DPO")  
model.load_adapter("kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", adapter_name="reference")
```

Here, model is the base model, i.e., the one to be trained with DPO. The load_adapter method loads an adapter named "reference," which was trained during SFT using Mistral 7B on the ultrachat dataset. In DPO training, this "reference" adapter serves as a comparison baseline to help assess whether generated outputs align with human preferences.

In DPO, the reference model serves as the standard against which the trained model’s outputs are compared. During training, the system computes the log-probability differences between the reference model’s outputs and the trained model’s outputs, and multiplies them by a coefficient (beta). This difference guides the DPO training process so that the trained model produces more preferred responses.

**Key Considerations When Choosing a Reference Model:**

1. Similarity: Identical or similar model architectures ensure that differences between the base and reference models’ outputs mainly come from weights rather than architectural differences.
2. Consistency: Using the same architecture ensures comparability of generated outputs, which is critical for evaluating and improving performance during training.
3. Simplified training: If the reference and base models share the same architecture, the training process can be simplified by sharing components, helping reduce memory and compute costs.
4. **Adapter technology**: In some implementations, adapter techniques are used to fine-tune the model. In this case, the adapters between the reference model and the base model can be shared, reducing resource requirements.

**Step 1: SFT training for the reference model** (using HuggingFaceH4/ultrachat_200k)

![images](images/ext_33.png)

![images](images/ext_34.png)

![images](images/ext_35.png)

Resource consumption during fine-tuning:

![images](images/ext_36.png)

**Step 2: DPO training for the base model** (using the model after SFT as the reference model)

![images](images/ext_37.png)

![images](images/ext_38.png)

![images](images/ext_39.png)

![images](images/ext_40.png)

**Resource overhead during DPO training**

bs=4:

![images](images/ext_41.png)

bs=16：

![images](images/ext_42.png)

bs=32：

![images](images/ext_43.png)

![images](images/ext_44.png)

![images](images/ext_45.png)

**Interpretation of DPO training metrics**

Meanings of the metrics recorded in the training logs:

1. **Step**：Training step index; each number represents one training batch completed by the model.
2. **Training Loss**：Training loss; a smaller value indicates better performance on the training set.
3. **Validation Loss**：Validation loss computed on a held-out dataset (the validation set) to assess generalization.
4. **Rewards/chosen**：Reward value corresponding to the chosen output (i.e., the human-preferred output).
5. **Rewards/rejected**：Reward value corresponding to the rejected output (i.e., the non-preferred output).
6. **Rewards/accuracies**：Reward accuracy, indicating how accurately the model distinguishes human-preferred from non-preferred outputs.
7. **Rewards/margins**：Reward margin, i.e., the reward gap between chosen and rejected outputs; larger values indicate better performance in distinguishing preferred outputs.
8. **Logps/rejected** 和 **Logps/chosen**：Log probability values corresponding to the rejected and chosen outputs, respectively, commonly used for numerical stability when handling probabilities.
9. **Logits/rejected** 和 **Logits/chosen**：Values before the output of the model’s final linear layer, i.e., logits—values after the last linear transformation but before applying an activation function.

### SimPO and CPO practice

在本项目的 Jupyter Notebook 中，还包含了使用 SimPO（Simple Preference Optimization）和 CPO（Contrastive Preference Optimization）对 Llama 3 进行内存高效对齐训练的完整代码示例，详见 `Memory_efficient_LLM_Alignment_with_SimPO_Example_with_Llama_3_and_Comparison_with_CPO.ipynb`。


---
# Part 7: DPO fine-tuning code and training results analysis

> *Originally from Comparison-of-Various-Fine-Tuning-Methods*


## DPO fine-tuning code

Define the model to be fine-tuned

```
model_name = "mistralai/Mistral-7B-v0.1"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = 'left' #Left is necessary for FlashAttention

#Better to use bf16 if supported (Ampere GPUs or more recent)
#If bf16 is supported, the GPU is also recent enough to support FlashAttention
if torch.cuda.is_bf16_supported():
  compute_dtype = torch.bfloat16
  attn_implementation = 'flash_attention_2'
else:
  compute_dtype = torch.float16
  attn_implementation = 'sdpa'
```

Load the dataset:

```
dataset = load_dataset("UltraFeedback-prompt-chosen-rejected")
```

Inspect the first entry of the dataset; in the dataset, the `chosen` and `rejected` labels can be used to train the model to understand what constitutes a good response and a poor response, thereby improving the output quality.

![images](images/1.png)

```
bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, torch_dtype=compute_dtype, attn_implementation=attn_implementation
)
model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})
#Configure the pad token in the model
model.config.pad_token_id = tokenizer.pad_token_id
```

The main purpose of the following code is:

1. Load a pretrained model and attach two “plugins” (we call them “adapters”):
   - The first adapter is called "DPO", and it is trainable, i.e., it will be updated and improved during training.
   - The second adapter is called "reference", and it is frozen and not trained, serving as a control reference.

```
model = PeftModel.from_pretrained(model, "kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", is_trainable=True, adapter_name="DPO")
model.load_adapter("kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", adapter_name="reference")
```

Next, set the hyperparameters for DPO training. `DPOConfig` is a class specifically used to configure the parameters of the Direct Preference Optimization (DPO) training process.

```
training_arguments = DPOConfig(
        output_dir="./results",
        evaluation_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=8,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_steps=20,
        logging_steps=20,
        learning_rate=5e-7,
        eval_steps=20,
        max_steps=100,
        warmup_steps=20,
        lr_scheduler_type="linear",
        report_to='none'  
)
```

```
trainer = DPOTrainer(
    model,
    args=training_arguments,
    beta=0.1,
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    train_dataset=dataset['train'],
    eval_dataset=dataset['test'],
    tokenizer=tokenizer,
)

trainer.train()
```

View the training results:

![images](images/2.png)

## Interpreting DPO training results

When using DPO (Direct Preference Optimization) for model training, we involve two models:


Policy model: This is the model we want to optimize; its parameters are updated during training.

Reference model: This is a fixed model whose parameters remain unchanged during training, used for reference and regularization.

Training objective: the policy should, given a Prompt (input), prefer to generate the Chosen (higher-preference response) and avoid generating the Rejected (lower-preference response).

Key steps and metrics during training

#### Training data

Each training sample contains:

- Prompt (input): the question or instruction the model needs to answer.
- Chosen (ideal response): the correct answer we want the model to produce.
- Rejected (undesired response): the answer we want the model to avoid producing.

#### Model evaluation

For each sample, we compute the following:

- The policy model’s evaluation of Prompt + Chosen.
- The policy model’s evaluation of Prompt + Rejected.
- The reference model’s evaluation of Prompt + Chosen and Prompt + Rejected (used to compute the regularization term).

#### Reward computation

Reward function: used to assess the quality of the policy model’s outputs for Chosen and Rejected, assigning numerical scores (rewards).

- Reward calculation:
  - Rewards/chosen: the reward for the policy model on the chosen response.
  - Rewards/rejected: the reward for the policy model on the rejected response.

#### Loss computation

Main components of the loss:

- Preference loss: encourages the model to assign higher reward to the chosen response and lower reward to the rejected response.

- Regularization term: uses the reference model to constrain the policy from drifting too far from the original language model distribution.

  Loss function (simplified, in plain text):

```
损失 = -（训练模型对 Chosen 的奖励 - 训练模型对 Rejected 的奖励） + β * （训练模型与参考模型的差异）  
```

Here, β is a hyperparameter controlling the weight of the regularization term.



### Explaining the training process and metrics via an example

 #### Example training data


Prompt:

```
翻译以下英文句子为中文： "The quick brown fox jumps over the lazy dog."  
```


Chosen (ideal response):

```
"敏捷的棕色狐狸跳过了懒狗。"  
```


Rejected (undesired response):

```
"我不知道如何翻译这个句子。"  
```

 **Step 1: Model evaluation**

(a) Policy model evaluation of chosen and rejected
Compute log probabilities (Logps):

- Logps/chosen: the sum of log probabilities assigned by the policy model to the chosen response. For example, suppose it is -50.

- Logps/rejected: the sum of log probabilities assigned by the policy model to the rejected response. For example, suppose it is -70.

  (b) Reference model output
  The reference model also evaluates chosen and rejected to compute log probabilities (used for the regularization term). But these values do not appear directly in the training results.

**Step 2: Reward computation**

(a) Compute rewards

- Rewards/chosen:
  ```
  Rewards/chosen = 训练模型对 Chosen 的对数概率 - β * （训练模型与参考模型在 Chosen 上的差异）  
  ```

  For example, suppose the difference between the training model and the reference model on Chosen is 5, and β is 0.1, then:

  ```
  Rewards/chosen = -50 - 0.1 * 5 = -50.5  
  ```

 

- Rewards/rejected：

  ```
  Rewards/rejected = 训练模型对 Rejected 的对数概率 - β * （训练模型与参考模型在 Rejected 上的差异）  
  ```

  For example, if the difference is 3, then:

  ```
  Rewards/rejected = -70 - 0.1 * 3 = -70.3  
  ```


(b) Compute reward margin (Rewards/margins)

```
Rewards/margins = Rewards/chosen - Rewards/rejected  
```

Substitute the values:

```
Rewards/margins = (-50.5) - (-70.3) = 19.8  
```

 

**Step 3: Compute the loss**

```
损失 = -（Rewards/chosen - Rewards/rejected） = -（-50.5 - (-70.3)） = -19.8  
```

The model updates its parameters based on this loss value with the goal of minimizing the loss, i.e., maximizing the reward margin.



**Step 4: Compute other metrics**

- Rewards/accuracies (reward accuracy)
  If Rewards/chosen > Rewards/rejected, it counts as a correct decision. In our example, -50.5 > -70.3, so this is a correct decision.
- Logits/chosen and Logits/rejected
  Logits are the raw outputs before computing log probabilities (Logps). These values reflect the model’s unnormalized confidence for each token.



### Role of the reference model

 

- Regularization: The reference model helps compute the regularization term, constraining the training model from deviating too far from the original language model distribution.
- Compute differences: By comparing the outputs of the training and reference models on Chosen and Rejected, adjust the reward values.
- Implicit influence: Although the reference model’s outputs do not appear directly in the training results, it plays a key role in the loss computation and thereby affects the training model’s updates.

### Metrics in the training results


Now, we summarize the metrics in the training results and how they are produced:

- Rewards/chosen: Computed from the training model’s assessment of the Chosen response, taking into account the reference model’s influence (via the regularization term).
- Rewards/rejected: Computed from the training model’s assessment of the Rejected response, likewise considering the reference model’s influence.
- Rewards/accuracies: The proportion of cases where the model correctly distinguishes Chosen from Rejected.
- Rewards/margins: The difference between Rewards/chosen and Rewards/rejected, reflecting the model’s ability to discriminate preferences.
- Logps/chosen and Logps/rejected: The sum of log probabilities of the training model on Chosen and Rejected.
- Logits/chosen and Logits/rejected: The unnormalized outputs of the training model when generating Chosen and Rejected.

### Summary

- Role of the reference model: Although the reference model’s outputs do not appear directly in the training metrics, it indirectly influences the training model’s updates via the regularization term in the loss function.
- How the metrics are produced: The training metrics mainly reflect the training model’s performance and are computed by evaluating Chosen and Rejected.
- Training objective: By minimizing the loss function, the training model is encouraged to generate Chosen responses and avoid Rejected responses, while preserving its language capabilities.

## Regularization and Generalization in DPO fine-tuning

### Regularization


Simply put, regularization is a way to prevent overfitting.


Overfitting refers to a model performing very well on training data but poorly on new (unseen) data. This happens because the model “memorizes” details and noise in the training data rather than learning the underlying general patterns.


Regularization is a technique to address overfitting. Its role is: during training, constrain certain properties of the model to prevent it from becoming overly complex, thereby enabling good performance on new data.


Analogy: Imagine you are learning to recognize apples and oranges. An overfit model might memorize specific features of each apple and orange in the training set, such as a small spot on this apple or a leaf on that orange. A regularized model would focus on general features of apples and oranges, like shape and color, rather than overemphasizing idiosyncratic details in the training data.

#### Application in model training

- Limit model complexity: Regularization constrains model parameters so the model does not become overly complex. For example, in neural networks you can constrain weights to prevent them from becoming too large.
- Prevent excessively large parameters: If parameters (e.g., weights) become too large, the model may overfit to details in the training data. Regularization adds a penalty term to the loss, encouraging parameters to remain small.

In the training above

- Role of the reference model: In DPO (Direct Preference Optimization) training, the reference model is used for regularization.

- Why regularization is needed:

  - Balance: We want the model to learn user preferences without losing its original language generation ability.
  - Prevent excessive drift: If we only focus on making the model more inclined to produce “correct” responses, it may over-adjust, degrading language quality.

- Regularization methods

  ：

  - Use a reference model: Add a term to the loss to measure the divergence between the training model and the reference model (e.g., KL divergence).
  - Effect: This difference serves as regularization to prevent the model from drifting too far from the reference model’s behavior, preserving fluency and diversity.

### Generalization


We have actually provided examples in the training data of “how to answer” and “how not to answer,” namely Chosen and Rejected responses. But merely providing correct answers and having the model imitate them is not enough; we want the model to understand why a response is good or bad, so it can make correct decisions in new situations.

1. Limitations of imitation learning

   - Direct imitation can lead to overfitting:
     If the model only mechanically memorizes correct answers from the training data, it may fail to respond well to new questions or slightly varied inputs.
   - Lack of discriminative ability:
     The model may not know why one answer is good and another is bad, so it may fail to distinguish correctly in novel situations.

2. Why introduce bad responses

   - Make model preferences explicit:
     By providing Rejected (bad responses), we tell the model which answers are undesirable.
   - Contrastive learning:
     By contrasting Chosen with Rejected, the model learns to distinguish good from bad responses. This helps the model learn which features are desirable and which are not.

3. Improve the model’s generalization

   - Make correct decisions in new scenarios:
     We want the model not only to memorize correct answers but also to generate high-quality responses to a variety of new questions based on learned preferences.
   - Understand underlying principles:
     By contrasting good and bad responses, the model can learn deeper patterns and regularities, rather than merely memorizing answers.

4. Prevent bias and harmful behavior

   - Address safety and ethical issues:
     By clearly labeling responses that should not be generated, the model can avoid producing harmful, biased, or inappropriate content.
   - Reinforce proper behavior:
     Teach the model what to avoid and what to encourage, improving reliability.

5. An example

   - Risks of providing only correct answers:
     If we only give the model a question and the correct answer, for example:

     ```
     问题：请解释牛顿的第一定律。  
     回答：物体在没有受到外力作用时，会保持静止或匀速直线运动状态。  
     ```

     The model may only produce the correct answer when it encounters exactly the same question.

   - Add a bad response for contrast:
     We then provide a bad response:

     ```
     不良回答：我不知道牛顿的第一定律是什么。  
     ```

     Through contrast, the model can learn:

     - A good response should be an accurate and complete explanation of the question.
     - A bad response fails to answer the question or provides incorrect information.

     In this way, when the model faces similar but different questions, it can still give correct responses:
     For example, when encountering “Please explain Newton’s second law,” the model can infer it should provide an explanation of that law rather than say “I don’t know.”

#### Summary

- Regularization:
  A method to prevent overfitting and ensure good performance on new data. In your training, the reference model is used for regularization to prevent the training model from deviating too far from the original language model distribution, preserving language quality and consistency.
- Training method design:
  By providing Chosen and Rejected responses, the model learns to distinguish good from bad answers. This contrastive learning approach enables the model to understand differences in response quality, so it can generate high-quality responses in new situations. Simply having the model imitate correct answers may lead to poor generalization and an inability to make correct judgments in novel contexts.


---
# Part 8: Large Model DPO Distributed Training (DeepSpeed & FSDP)

> *Originally from DPO-DeepSpeed-FSDP*


**Direct Preference Optimization (DPO)** is currently one of the popular methods for aligning large language models (LLMs) with human preferences. With parameter-efficient fine-tuning techniques like **LoRA** and **QLoRA**, we can perform DPO training on models with 8 billion parameters (such as Llama 3.1 8B and Qwen2.5 7B) on a single GPU, though the training sequences might be shorter. However, for larger models, like 72B, multiple GPUs are required. 

 

### Technical Points

For example, suppose we want to perform DPO training on a 70 billion-parameter model on a machine with 8 H100 GPUs (totaling 640 GB of VRAM). We need to consider the following points:

- **Policy Model**: The model we want to train, which occupies about 140 GB of VRAM.

- **Reference Model**: DPO requires a reference model, usually with the same architecture as the policy model, also occupying about 140 GB of VRAM.

  Thus, just the model parameters alone consume 280 GB of VRAM, approximately 43.75% of the total VRAM. In addition, there are optimizer states. For example, using the AdamW optimizer, each parameter has two additional state variables. If these state variables are stored in 16-bit precision, they will take up an extra 280 GB of VRAM. Adding it all up, we've used 560 GB of VRAM, leaving only 80 GB. This remaining VRAM is needed to store activations and gradients. Without special methods, it's unlikely to train on a single machine.


## Distributed training technology 

To address the above challenges, we could use PyTorch's **Fully Sharded Data Parallel (FSDP)** technology, combined with parameter-efficient fine-tuning methods like LoRA and QLoRA. 

**FSDP is similar to DeepSpeed's ZeRO technology.** **Accelerate** is a library from Hugging Face (HF).  FSDP is a distributed training technique that shards the model's parameters, optimizer states, and gradients, distributing them across multiple devices (such as GPUs). During the forward and backward passes, only the required parameter shards are loaded into memory and released after computation. This greatly reduces memory requirements.  Of course, when training even larger models, **DeepSpeed** can be used. DeepSpeed requires a large amount of memory to store full-precision model parameters. 

In my repo, I used both DeepSpeed ZeRO-3 technology and FSDP technology, and the training results were the same. I will showcase the scripts and configuration files for both training methods. 

 ![images](images/ext_46.png)

In the following DeepSpeed and Accelerate FSDP training, I use an adapter from HF:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# ls -al ./SFT_LoRA/
total 838112
drwxr-xr-x  5 root root      4096 Dec 19 06:49 .
drwx------ 48 root root      4096 Dec 19 11:24 ..
drwxr-xr-x  9 root root      4096 Dec 19 06:49 .git
-rw-r--r--  1 root root      2345 Dec 19 06:48 .gitattributes
-rw-r--r--  1 root root       264 Dec 19 06:48 README.md
-rw-r--r--  1 root root       728 Dec 19 06:48 adapter_config.json
-rw-r--r--  1 root root 842289128 Dec 19 06:49 adapter_model.safetensors
-rw-r--r--  1 root root       605 Dec 19 06:48 added_tokens.json
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-10
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-5
-rw-r--r--  1 root root   1671853 Dec 19 06:48 merges.txt
-rw-r--r--  1 root root       499 Dec 19 06:48 special_tokens_map.json
-rw-r--r--  1 root root  11421896 Dec 19 06:48 tokenizer.json
-rw-r--r--  1 root root      7306 Dec 19 06:48 tokenizer_config.json
-rw-r--r--  1 root root      5496 Dec 19 06:48 training_args.bin
-rw-r--r--  1 root root   2776833 Dec 19 06:48 vocab.json

(Multi-GPU-DPO-Training) root@YOUR-VM:~/SFT_LoRA# cat adapter_config.json
{
  "alpha_pattern": {},
  "auto_mapping": null,
  "base_model_name_or_path": "Qwen/Qwen2.5-72B-Instruct",
  "bias": "none",
  "fan_in_fan_out": false,
  "inference_mode": true,
  "init_lora_weights": true,
  "layer_replication": null,
  "layers_pattern": null,
  "layers_to_transform": null,
  "loftq_config": {},
  "lora_alpha": 16,
  "lora_dropout": 0.05,
  "megatron_config": null,
  "megatron_core": "megatron.core",
  "modules_to_save": null,
  "peft_type": "LORA",
  "r": 16,
  "rank_pattern": {},
  "revision": null,
  "target_modules": [
    "up_proj",
    "q_proj",
    "k_proj",
    "down_proj",
    "gate_proj",
    "v_proj",
    "o_proj"
  ],
  "task_type": "CAUSAL_LM",
  "use_dora": false,
  "use_rslora": false
```



## DeepSpeed Training

Deepspeed Configuration file:

```
# cat deepspeed_config.json
{  
  "zero_optimization": {  
    "stage": 3,  
    "overlap_comm": true,  
    "contiguous_gradients": true,  
    "reduce_bucket_size": 104857600,  
    "stage3_prefetch_bucket_size": 104857600,  
    "stage3_param_persistence_threshold": 1048576  
  },  
  "bf16": {  
    "enabled": true  
  },  
  "train_micro_batch_size_per_gpu": 1,  
  "gradient_accumulation_steps": 16,  
  "steps_per_print": 10,  
  "wall_clock_breakdown": false  
}  
```

Training code:

```
#cat fsdp+QLoRA_deepspeed.py
import torch  
import os  
import multiprocessing  
from datasets import load_dataset  
from peft import PeftModel  
from transformers import (  
    AutoModelForCausalLM,  
    AutoTokenizer,  
    BitsAndBytesConfig,  
    set_seed  
)  
from trl import DPOTrainer, DPOConfig  
  
set_seed(1234)  
  
model_name = "Qwen/Qwen2.5-72B-Instruct"  
sft_adapter = "./SFT_LoRA/"  # 一个使用 SFT 微调的 LoRA 适配器  
  
compute_dtype = torch.bfloat16  
  
# 如果在使用 FlashAttention 时遇到问题，可以改用 'sdpa'  
attn_implementation = 'flash_attention_2'  
  
# 如果内存不足，可以修改以下三个训练参数  
bs = 1        # 每个设备的批大小（训练和验证）  
gas = 16      # 梯度累积步骤数  
mseqlen = 512 # 最大序列长度  
  
lr = 1e-5     # 学习率  
QLoRA = True  # 是否量化基模型  
  
output_dir = "/workspace/DPO_LoRA"  
  
# 初始化 Tokenizer  
tokenizer = AutoTokenizer.from_pretrained(model_name)  
tokenizer.pad_token = "<|image_pad|>"  
tokenizer.pad_token_id = 151655  
tokenizer.padding_side = 'right'  # 对于 Qwen2.5，左右 padding 都可以  
  
# 加载并处理数据集  
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)  
ds_train = ds['train']  
ds_test = ds['test']  
  
def process(row):  
    # 第一个消息是提示  
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)  
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token  
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token  
    row["prompt"] = prompt_messages  
    row["chosen"] = chosen_messages  
    row["rejected"] = rejected_messages  
    return row  
  
ds_train = ds_train.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
ds_test = ds_test.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
if QLoRA:  
    bnb_config = BitsAndBytesConfig(  
        load_in_4bit=True,  
        bnb_4bit_quant_type="nf4",  
        bnb_4bit_compute_dtype=compute_dtype,  
        bnb_4bit_use_double_quant=True,  
        bnb_4bit_quant_storage=compute_dtype,  
    )  
  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        quantization_config=bnb_config,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
    # 冻结基模型的参数  
    for name, param in model.named_parameters():  
        param.requires_grad = False  
  
    # 让输入嵌入支持梯度  
    def make_inputs_require_grad(module, input, output):  
        output.requires_grad_(True)  
  
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)  
else:  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': True})  
  
# 加载 LoRA 适配器  
model = PeftModel.from_pretrained(  
    model,  
    sft_adapter,  
    is_trainable=True,  
    adapter_name="DPO"  
)  
model.load_adapter(sft_adapter, adapter_name="reference")  
  
# 将模型移动到设备上  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
  
training_arguments = DPOConfig(  
    output_dir=output_dir,  
    eval_strategy="steps",  
    do_eval=True,  
    optim="adamw_torch",  
    per_device_train_batch_size=bs,  
    gradient_accumulation_steps=gas,  
    per_device_eval_batch_size=bs,  
    log_level="debug",  
    save_strategy="steps",  
    save_steps=5,  
    logging_steps=2,  
    learning_rate=lr,  
    bf16=True,  
    beta=0.1,  
    eval_steps=2,  
    max_steps=10,  
    warmup_ratio=0.1,  
    lr_scheduler_type="linear",  
    max_length=mseqlen,  
    max_prompt_length=512,  
    dataset_num_proc=multiprocessing.cpu_count(),  
    model_adapter_name="DPO",  
    ref_adapter_name="reference",  
    deepspeed="deepspeed_config.json",  # 指定 DeepSpeed 配置文件  
)  
  
trainer = DPOTrainer(  
    model=model,  
    args=training_arguments,  
    train_dataset=ds_train,  
    eval_dataset=ds_test,  
    tokenizer=tokenizer,  
)  
  
# 开始训练  
trainer.train()  
  
# 保存模型  
trainer.save_model(output_dir)  
```
Launch training 

```
(dpo) root@h1002gpu:~# deepspeed fsdp+QLoRA_deepspeed.py
```

```
{'loss': 0.6914, 'grad_norm': 3.3615094645372428, 'learning_rate': 8.888888888888888e-06, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': -536.0, 'logps/rejected': -532.0, 'logits/chosen': 0.1, 'logits/rejected': 0.0, 'epoch': 0.0}
 20%|████████████████████████████▊   
```

![images](images/1.png)

## Accelerate FSDP training

 Configuration file:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 2
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
```



Training code:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 1
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat fsdp+QLoRA.py
import torch
import os
import multiprocessing
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from peft.utils.other import fsdp_auto_wrap_policy
from accelerate import Accelerator, FullyShardedDataParallelPlugin
from trl import DPOTrainer, DPOConfig

# Set seed for reproducibility
set_seed(1234)

# Configure FSDP Plugin
fsdp_plugin = FullyShardedDataParallelPlugin(
    sharding_strategy="FULL_SHARD",
    backward_prefetch="BACKWARD_PRE",
    forward_prefetch=False,
    cpu_offload=False,
    use_orig_params=True,  # Set use_orig_params to True
    auto_wrap_policy="TRANSFORMER_BASED_WRAP",
    mixed_precision_policy={
        "param_dtype": torch.float16,
        "reduce_dtype": torch.float16,
        "buffer_dtype": torch.float16,
    },
)

# Initialize accelerator with fsdp_plugin
accelerator = Accelerator(
    mixed_precision="no",
    fsdp_plugin=fsdp_plugin,
    log_with=None,
)

# Model and training configuration
model_name = "Qwen/Qwen2.5-72B-Instruct"
sft_adapter = "./SFT_LoRA/"  # Path to your LoRA adapter fine-tuned with SFT

compute_dtype = torch.float16  # Use torch.float16 for consistency

# If you have troubles with FlashAttention, use 'standard' or 'triton' instead
attn_implementation = 'eager'

# Modify the following training arguments if you run out of memory
bs = 1  # Batch size per device
gas = 1  # Gradient accumulation steps
mseqlen = 32  # Maximum sequence length

lr = 1e-6  # Learning rate
QLoRA = True  # Quantize the base model
lora_alpha = 16
lora_dropout = 0.0
lora_r = 4

output_dir = "/workspace/DPO_LoRA"

# Tokenizer setup
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = "<|image_pad|>"
tokenizer.pad_token_id = 151655
tokenizer.padding_side = 'right'  # Adjust as needed

# Load and process the dataset
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)
ds_train = ds['train']
ds_test = ds['test']

def process(row):
    # The first message is the prompt
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token
    row["prompt"] = prompt_messages
    row["chosen"] = chosen_messages
    row["rejected"] = rejected_messages
    return row

ds_train = ds_train.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)
ds_test = ds_test.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)

# Model loading and preparation
if QLoRA:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage=compute_dtype,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
    for name, param in model.named_parameters():
        param.requires_grad = False

    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)

    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
else:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )

# Load the LoRA adapter
model = PeftModel.from_pretrained(model, sft_adapter, is_trainable=True, adapter_name="DPO")
model.load_adapter(sft_adapter, adapter_name="reference")

# Ensure all model parameters are in torch.float16
model.to(torch.float16)

# Ensure all model parameters are on the correct device
model.to(accelerator.device)

# Training arguments
training_arguments = DPOConfig(
    output_dir=output_dir,
    eval_strategy="steps",
    do_eval=True,
    optim="adamw_hf",  # Use the PyTorch fused optimizer
    per_device_train_batch_size=bs,
    gradient_accumulation_steps=gas,
    per_device_eval_batch_size=bs,
    log_level="debug",
    save_strategy="steps",
    save_steps=5,
    logging_steps=2,
    learning_rate=lr,
    bf16=True,
    fp16=False,
    beta=0.1,
    eval_steps=2,
    max_steps=10,
    warmup_ratio=0.1,
    lr_scheduler_type="linear",
    max_length=mseqlen,
    max_prompt_length=512,
    dataset_num_proc=multiprocessing.cpu_count(),
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    report_to="none",
    max_grad_norm=1.0,
)

# Initialize the DPOTrainer
trainer = DPOTrainer(
    model=model,
    args=training_arguments,
    train_dataset=ds_train,
    eval_dataset=ds_test,
    processing_class=tokenizer,
)

# Start training
```

Launch training 

```
 accelerate launch --config_file config_fsdp.yaml fsdp+QLoRA.py
```

```
***** Running training *****
  Num examples = 43,802
  Num Epochs = 1
  Instantaneous batch size per device = 1
  Total train batch size (w. parallel, distributed & accumulation) = 1
  Gradient Accumulation steps = 1
  Total optimization steps = 10
  Number of trainable parameters = 210,534,400
{'loss': 0.6931, 'grad_norm': 0.0, 'learning_rate': 8.888888888888888e-07, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': 0.0, 'logps/rejected': 0.0, 'logits/chosen': 0.1, 'logits/rejected': nan, 'epoch': 0.0}
 20%|████████████████████████████▊                                                                                                                   | 2/10 [00:07<00:26,  3.37s/it]The following columns in the evaluation set don't have a corresponding argument in `FullyShardedDataParallel.forward` and have been ignored: source, prompt, question, rejected, chosen. If source, prompt, question, rejected, chosen are not expected by `FullyShardedDataParallel.forward`,  you can safely ignore this message.

```



## Training result analyze

In DPO training, the model is provided with a set of conversations, each containing the same "prompt" or "question", along with corresponding "chosen" and "rejected" replies. The model needs to learn to distinguish between these replies and prefer generating high-quality "chosen" responses.

### Training data and results

The training data includes:

- **Source**: Airoboros

- **Chosen Reply**: Contains multiple rounds of dialogue

- **Rejected Reply**: Contains multiple rounds of dialogue

- **Prompt**: A descriptive text

- **Question**: The same text as the prompt

  Sometimes in the data, the "prompt" and "question" may be identical, which can serve as the starting point for the conversation in certain training settings.

  ![images](images/ext_47.png)

  Training results are as following:

  ![images](images/ext_48.png)

Next, I will combine the training data to roughly introduce the DPO training process and results.

### DPO training process and results explanation


**Core Objective of DPO**

- **Objective:** Directly optimize the model parameters to reflect human preferences without the need for a separate reward model. DPO uses human preference data to adjust the model directly, making its generated responses more aligned with human expectations.

- **Introducing the Reference Model:** To prevent the model from **deviating from its original language capabilities** during optimization, DPO introduces a **reference model** (usually a copy of the initial model with fixed parameters) as a **regularization term**.

  **Role of the Reference Model:**

  - **Maintaining Language Capabilities:** The reference model provides a baseline of the model before adjustment. By comparing with the reference model, the trained model can learn human preferences while avoiding overfitting and deviation from its original abilities, ensuring that its language understanding and generation capabilities remain intact. This helps prevent the model from prioritizing human preferences at the expense of core language skills like grammatical correctness and factual accuracy.



#### Training Data

- **Prompt:** User input, for example: "Please explain the phase changes of water."

- **Chosen Reply:** Responses evaluated by humans as high-quality, fully answering the question, and meeting expectations. These replies are typically **accurate**, **complete**, **relevant**, and **fluent**, satisfying user needs.

- **Rejected Reply:** Responses evaluated by humans as lower quality, not adequately answering the question, or not meeting expectations. These replies may lack **accuracy**, contain **incomplete information**, be **irrelevant** to the prompt, or be **less fluent**.

  **Human Evaluation Criteria:**

- **Accuracy:** Is the content of the reply correct and free from misleading information?

- **Completeness:** Does the reply fully answer the user's question?

- **Relevance:** Is the reply closely related to the user's prompt?

- **Fluency:** Is the reply grammatically correct and clearly expressed?

  **Example:**

- **Prompt:** "Please explain the phase changes of water."

- **Chosen Reply:**

  ```
  Water exists in three states: solid, liquid, and gas. Through changes in temperature and pressure, water can transition between these states. For example, ice (solid) melts into water (liquid) when heated, and water vaporizes into steam (gas) upon further heating.  
  ```

  - **Evaluation Reasoning:** The reply accurately explains the process of water's phase changes, provides complete information, is highly relevant to the prompt, and is fluent.

- **Rejected Reply:**

  ```
  Water is a very common substance found everywhere in daily life.  
  ```

  - **Evaluation Reasoning:** The reply does not address the question about the phase changes of water; the information is incomplete, and the relevance is insufficient.



#### Training Process

**Step 1: Calculate Log Probabilities**

 
**For the trained model (parameters θ):**

- **Log probability of the chosen reply:**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**For the reference model (fixed parameters):**

- **Log probability of the chosen reply:**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

**Step 2: Calculate Preference Differences**

 

- **Preference difference for the chosen reply:**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **Preference difference for the rejected reply:**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

**Step 3: Construct the Loss Function**

 

- **Loss function:**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  Where β is the temperature hyperparameter controlling sensitivity to preference differences.

- **Objective:** Minimize the loss function loss to make the model more inclined to generate the "chosen" reply over the "rejected" reply.

#### Training Process Example


**Assumed Values (for Illustration):**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **Calculate Preference Differences:**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **Calculate the Loss Function (assuming β = 1):**

1. **Calculate the numerator:**
   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **Calculate the denominator:**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **Calculate the loss:**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**Result Analysis:**

- **The loss value is relatively small (approximately 0.127), indicating that the model tends to prefer the "chosen" reply.**
- **Optimize Model Parameters:**
  - Through backpropagation, minimize the loss function **loss** to further enhance the model's preference for the "chosen" reply.



#### Explanation of Training Log Fields

 
Based on the DPO training process, here's a detailed explanation of each field in the training log and their importance in evaluating training effectiveness:

**Example Training Log:**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### 1. `loss`

- **Meaning:**
  - Represents the loss value at the current training step, measuring the model's ability to distinguish between the "chosen" and "rejected" replies.
- **Importance:**
  - **Core Indicator:** The primary metric to evaluate training effectiveness.
  - **Training Goal:** Minimizing **loss** indicates successful learning toward preferring the "chosen" reply.
- **Indicator Trend:**
  - **Initial Stage:** `loss` is typically higher (around `0.6931`), indicating no preference.
  - **During Training:** Should decrease over time, showing the model is learning to prefer the "chosen" reply.

#### 2. `grad_norm`

- **Meaning:**
  - Represents the gradient norm of the model parameters, indicating the overall magnitude of parameter updates.
- **Importance:**
  - **Learning Intensity:** Reflects how much the model is adjusting its parameters.
  - **Training Stability:** Helps detect issues like vanishing or exploding gradients.
- **Indicator Trend:**
  - **Normal Range:** Should be within a reasonable range (e.g., `0.01` to `1`).
  - Abnormal Situations:
    - **Too Small:** Near zero may indicate lack of learning.
    - **Too Large:** May require gradient clipping to prevent instability.

#### 3. `learning_rate`

- **Meaning:**
  - Controls the step size in parameter updates during training.
- **Importance:**
  - **Convergence Speed and Stability:** Affects how quickly and smoothly the model learns.
- **Adjustment Strategy:**
  - **Slow Loss Decrease:** Consider increasing the learning rate.
  - **Unstable Training:** If loss fluctuates, decreasing the learning rate might help.

#### 4. `rewards/chosen` and `rewards/rejected`

- **Meaning:**
  - `rewards/chosen`: Reward value for the "chosen" reply (`Δ_chosen`).
  - `rewards/rejected`: Reward value for the "rejected" reply (`Δ_rejected`).
- **Importance:**
  - **Model Preference:** Indicates the model's inclination towards each reply.
- **Indicator Trend:**
  - **Initial Stage:** Both may be around `0.0` (no preference).
  - During Training:
    - `rewards/chosen` should increase.
    - `rewards/rejected` should decrease.

#### 5. `rewards/accuracies`

- **Meaning:**
  - The proportion of times the model correctly prefers the "chosen" reply.
- **Importance:**
  - **Performance Measure:** Directly evaluates preference learning.
- **Indicator Trend:**
  - **Initial Stage:** Around `0.5` (random guess).
  - **During Training:** Should approach `1.0`, indicating improved preference accuracy.

#### 6. `rewards/margins`

- **Meaning:**

  - The difference between `rewards/chosen` and `rewards/rejected`.

  ```
  rewards/margins = rewards/chosen - rewards/rejected  
  ```

- **Importance:**
  - **Discrimination Ability:** Larger margins indicate better distinction between replies.
- **Indicator Trend:**
  - Should increase during training.

#### 7. `logps/chosen` and `logps/rejected`

- **Meaning:**
  - Total log probabilities of generating the "chosen" and "rejected" replies.
- **Importance:**
  - **Probability Basis:** Used in calculating preference differences and rewards.
- **Indicator Trend:**
  - **Increasing `logps/chosen`** indicates higher probability for the "chosen" reply.
  - **Stable or decreasing `logps/rejected`** shows reduced preference for the "rejected" reply.

#### 8. `logits/chosen` and `logits/rejected`

- **Meaning:**
  - Raw output scores from the final layer before applying softmax, for both replies.
- **Importance:**
  - **Probability Calculation:** Used to compute probabilities for each token, affecting log probabilities.
- **Indicator Trend:**
  - **Ensure Valid Values:** Avoid `nan` or `inf` values.
  - **Monitor Changes:** Changes in logits reflect learning progress.

#### 9. `epoch`

- **Meaning:**
  - Indicates the current training epoch or iteration over the training dataset.
- **Importance:**
  - **Training Progress:** Helps track how far along the training is.
- **Indicator Trend:**
  - As `epoch` increases, expect improvements in other metrics.

#### Summary 

- **Adjust Training Strategies Based on Indicators:**

  - **Slow Loss Decrease:** Increase learning rate or check data quality.
  - **Gradient Issues:** If `grad_norm` is abnormal, inspect gradient computations or adjust optimizer settings.
  - **Low Preference Accuracy:** Enhance data quality or quantity.
  - **Small Reward Margins:** Adjust the temperature parameter β to influence sensitivity.

- **Emphasize the Importance of the Reference Model:**

  - **Maintaining Language Capabilities:** Ensures the model doesn't overfit human preferences at the cost of language understanding and generation skills.
  - **Balancing Objectives:** Optimizes for human preference while retaining overall model performance.

- **Continuous Monitoring and Adjustment:**

  - **Regular Evaluation:** Use a validation set to assess performance and prevent overfitting.

  - **Dynamic Adjustment:** Modify training strategies based on log indicators to optimize the model.

    By understanding DPO's core concepts, training processes, and how to interpret key training metrics, you can effectively train a model that aligns with human preferences while maintaining strong language capabilities.



### DPO training process and results explanation in Chinese

- **Objective:** Directly optimize model parameters to reflect human preferences without a separate reward model. DPO leverages human preference data to directly adjust the model, making its generated replies better aligned with human expectations.

- **Introduce a reference model:** To prevent the model from **deviating from its original language capabilities** during optimization, DPO introduces a **reference model** (usually a copy of the initial model with frozen parameters) as a **regularization term**.

  **Role of the reference model:**

  - **Preserve language capabilities:** The reference model provides the baseline of the model before adjustment. By comparing with the reference model, the trained model can learn human preferences while avoiding overfitting and deviating from its original capabilities, ensuring its language understanding and generation abilities are not impaired. This helps prevent the model from neglecting language capabilities—such as grammatical correctness and knowledge accuracy—in pursuit of human preference alignment.

**Training data**

- **Prompt（Prompt）：** User input, for example: “Please explain the phase changes of water.”

- **Chosen reply（Chosen Reply）：** A response evaluated by humans as high quality, fully answering the question and meeting expectations. Such replies are typically **accurate**, **complete**, **relevant**, and **fluent** in language, satisfying user needs.

- **Rejected reply（Rejected Reply）：** A response evaluated by humans as lower quality, failing to sufficiently answer the question, or not meeting expectations. Such replies may have **insufficient accuracy**, **incomplete information**, be **unrelated to the prompt**, or be **non-fluent**.

  

  **Human evaluation criteria：**
- **Accuracy（Accuracy）：** Whether the response content is correct and non-misleading.

- **Completeness（Completeness）：** Whether the response fully answers the user's question.

- **Relevance（Relevance）：** Whether the response is closely related to the user's prompt.

- **Fluency（Fluency）：** Whether the response is linguistically smooth and clearly expressed.

  

  **Example:**

- **Prompt：**“Please explain the phase changes of water.”

- **Chosen response：**

  ```
  水有三种物态：固态、液态和气态。通过温度和压力的变化，水可以在这三种物态之间转换。例如，冰（固态）受热会融化成水（液态），水加热会变成水蒸气（气态）。  
  ```

  - **Evaluation rationale：** The response explains the process of water’s phase changes with high **accuracy**, the information is **complete**, **highly relevant** to the prompt, and the language is **fluent**.

- **Rejected response：**

  ```
  水是一种非常常见的物质，生活中到处都有。  
  ```

  - **Evaluation rationale：** The response does not address the question about phase changes, the information is **incomplete**, and **insufficiently relevant**.



#### **Training process**

#### **Step 1: Compute log probabilities**

 
**For the model being trained (parameters θ):**

- **Log probability of the chosen response:**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **Log probability of the rejected response:**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**For the reference model (parameters fixed):**

- **Log probability of the chosen response:**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **Log probability of the rejected response:**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

#### **Step 2: Compute preference deltas**

 

- **Preference delta for the chosen response:**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **Preference delta for the rejected response:**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

#### **Step 3: Construct the loss function**

 

- **Loss function form:**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  Here, **β** is the temperature hyperparameter that controls sensitivity to preference differences.

- **Objective:** Minimize the **loss** so that the model is more inclined to generate the “chosen” response rather than the “rejected” response.



### **Training process example**

 
**Assumed values (for illustration):**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **Compute preference deltas:**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **Compute the loss (assume β = 1):**

1. **Compute the numerator:**

   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **Compute the denominator:**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **Compute the loss:**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**Result analysis:**

- **The loss is relatively small (≈ 0.127), indicating the model tends to prefer the “chosen” response.**
- **Optimize model parameters:**
  - Through backpropagation, minimize the **loss** to further strengthen the model’s preference for the “chosen” response. 

### **Explanation of training log fields**

 
In conjunction with the above DPO training process, below is a detailed explanation of each field in the training logs and their importance in evaluating training effectiveness. We also illustrate the trends of these metrics using examples from actual training.

**Training log example:**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### **1. `loss`**

- **Meaning:**
  - **Loss value**, measuring the model’s ability at the current training step to distinguish between the “chosen” and “rejected” responses.
- **Importance:**
  - **Core metric:** The primary basis for evaluating training effectiveness.
  - **Training objective:** Minimize **loss**, indicating the model more successfully prefers the “chosen” response.
- **Metric trend:**
  - **Initial phase:** `loss` is typically higher, e.g., around `0.6931`, corresponding to no preference between the two responses.
  - **During training:** As training progresses, `loss` should gradually decrease, indicating the model is learning to prefer the “chosen” response.

#### **2. `grad_norm`**

- **Meaning:**
  - **Gradient norm**, representing the overall magnitude of parameter updates.
- **Importance:**
  - **Learning intensity:** Reflects how strongly the model is learning at the current step.
  - **Training stability:** Monitors gradient magnitude to prevent vanishing or explosion.
- **Metric trend:**
  - **Normal range:** `grad_norm` should remain within a reasonable range, e.g., `0.01` to `1`.
  - **Abnormal cases:**
    - **Too small (near 0):** May indicate the model is not learning.
    - **Too large:** Consider gradient clipping to prevent gradient explosion.
#### **3. `learning_rate`**

- **Meaning:**
  - The learning rate, which controls the step size of model parameter updates.
- **Importance:**
  - **Convergence speed and stability:** Determines the model’s learning speed and the stability of training.
- **Metric adjustment strategy:**
  - **Based on training outcomes:** If `loss` decreases slowly, you can appropriately increase the learning rate; if the loss oscillates or increases, you may need to reduce the learning rate.
- **Example:**
  - **Initial learning rate:** Commonly set to `1e-5`.
  - **Adjustment strategy:** Dynamically adjust the learning rate based on training performance.

#### **4. `rewards/chosen` and `rewards/rejected`**

- **Meaning:**
  - `rewards/chosen`: The reward value for the “chosen” response, i.e., the preference difference `Δ_chosen`.
  - `rewards/rejected`: The reward value for the “rejected” response, i.e., the preference difference `Δ_rejected`.
- **Importance:**
  - **Model inclination:** Reflects the degree of the model’s preference between the two responses.
- **Metric trend:**
  - **Initial stage:** Both may be close to `0.0`, indicating no clear preference.
  - **During training:**
    - **`rewards/chosen` should gradually increase**, indicating the model’s inclination toward the “chosen” response strengthens.
    - **`rewards/rejected` should gradually decrease**, indicating the model’s inclination toward the “rejected” response weakens.

#### **5. `rewards/accuracies`**

 **Meaning:**

- - **Preference accuracy**, the proportion of times the model correctly prefers the “chosen” response.
- **Importance:**
  - **Performance measurement:** Directly evaluates whether the model successfully prefers higher-quality responses.
- **Metric trend:**
  - **Initial stage:** May be close to `0.5`, equivalent to random choice.
  - **During training:** Should gradually improve, approaching `1.0`, indicating the model increasingly prefers the “chosen” response correctly.

#### **6. `rewards/margins`**

- **Meaning:**

  - **Reward margin**, i.e., the difference between `rewards/chosen` and `rewards/rejected`.

  - **Formula:**

    ```
    rewards/margins = rewards/chosen - rewards/rejected  
    ```

- **Importance:**
  - **Discriminative ability:** The larger the gap, the higher the model’s ability to distinguish between the two responses.
- **Metric trend:**
  - **Initial stage:** May be close to `0.0`.
  - **During training:** Should gradually increase, indicating the model better distinguishes and prefers the “chosen” response.

#### **7. `logps/chosen` and `logps/rejected`**

- **Meaning:**
  - `logps/chosen`: The total log probability of generating the “chosen” response.
  - `logps/rejected`: The total log probability of generating the “rejected” response.
- **Importance:**
  - **Probabilistic basis:** Used to compute preference differences and reward values.
- **Metric trend:**
  - **During training:**
    - **`logps/chosen` should gradually increase (value tends toward 0)**, indicating the generation probability for the “chosen” response increases.
    - **`logps/rejected` may remain unchanged or decrease**, indicating the generation probability for the “rejected” response decreases.

#### **8. `logits/chosen` and `logits/rejected`**

- **Meaning:**
  - **Raw output scores**, the unnormalized scores at the model’s final layer for the two responses (typically a vector).
- **Importance:**
  - **Probability computation:** `logits` are used to compute the probability distribution for each token, thereby computing log probabilities.
- **Metric trend:**
  - **Normal values:** Ensure `logits` have no anomalies (e.g., `nan` or `inf`).

#### **9. `epoch`**

- **Meaning:**
  - **Training epochs**, the number of times the model traverses the entire training dataset.
- **Importance:**
  - **Training progress:** Understand the current stage of training.
- **Metric trend:**
  - **As `epoch` increases:** You should observe improvements in various performance metrics.



### **Summary**

- **Adjust training strategy based on metrics:**
  - **Loss decreases slowly:** You can appropriately increase the learning rate or check data quality.
  - **Gradient anomalies:** If `grad_norm` is abnormal, check gradient computation or adjust optimizer parameters.
  - **Low preference accuracy:** Increase the amount of training data or improve data quality.
  - **Small reward margin:** Adjust the temperature parameter β to affect the model’s sensitivity to preference differences.
- **Emphasize the importance of the reference model:**
  - **Maintain language capabilities:** The reference model ensures the model being trained does not become overly biased toward human preferences at the expense of its original knowledge and linguistic expression capabilities.
  - **Balance optimization objectives:** While optimizing for human preferences, maintain the model’s overall performance.
- **Continuous monitoring and adjustment:**
  - **Regular evaluation:** Use a validation set to assess model performance and prevent overfitting.
  - **Dynamic adjustment:** Adjust training strategies in a timely manner based on metrics in the training logs to optimize the model.