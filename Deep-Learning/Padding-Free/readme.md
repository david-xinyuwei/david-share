# Practical Experience of Padding-Free Training

As large language models (such as Meta's Llama and OpenAI's GPT series) become widely adopted in production and research, effectively utilizing expensive GPU resources and improving training efficiency have become crucial issues. Currently, three main batch processing strategies exist for fine-tuning language models: padding, packing, and padding-free. This article provides detailed insights, practical experience, comparative data, and important considerations about padding-free practice, helping you gain deeper understanding and efficiently apply padding-free techniques.

Here is a simplified comparison table for these three methods:

| Method       | Need padding tokens | Concatenate different sequences                   | Risk of cross-contamination   | Complexity                         |
| ------------ | ------------------- | ------------------------------------------------- | ----------------------------- | ---------------------------------- |
| Padding      | Yes                 | No                                                | No                            | Simple, but inefficient            |
| Packing      | No                  | Yes (multiple sequences merged)                   | Yes, extra precautions needed | Complex and more difficult         |
| Padding-free | No                  | No (sequences stored separately but contiguously) | No risk                       | Relatively simple, high efficiency |

Code implementation provided in the last section.

------

## 1. Padding

When training with traditional padding methods:

- Each batch contains multiple input sequences.
- Each sequence must have the same length; shorter sequences are padded with special tokens ("padding tokens").
- Example:

```
[Sequence 1]: A, B, C, _, _
[Sequence 2]: D, E, F, G, H
```



Sequence 1 only has three real tokens, so two padding tokens (`_`) are appended to match Sequence 2’s length.

Problem: wasting computational resources processing meaningless padding tokens.

### Why is padding required?

Currently, GPU parallel computation mandates batch data to have uniform tensor dimensions because:

- GPUs excel at performing parallel operations efficiently only on uniformly shaped data tensors.
- Training uses batch processing on GPU to enhance parallelism and speed. Therefore, sequences in a batch must be of unified length, forcing padding to achieve this uniformity.

In summary:

> Padding isn’t desired inherently, but required by GPU hardware’s parallelization demands—padding tokens are artificial, useless data strictly for alignment and thus considered wasteful.

Padding tokens occupy computational resources despite their mask in attention computations or loss calculations. Illustrative example:

```
Sentence A: ["today’s weather is nice"]
Sentence B: ["I"]
```



After batching:

```
Batch:
[
  ["today", "weather", "is", "nice"],
  ["I", "PAD", "PAD", "PAD"]
]
```



Although these `PAD` tokens don’t influence attention or loss directly, they still consume:

- **Computation resources:** GPUs perform operations on all positions.
- **Memory/GPU memory resources:** Storing embeddings and temporary attention matrices.

Hence, padding introduces inefficiency.

------

## 2. Packing

For packing:

- Shorter sequences are concatenated into one long sequence within each batch, utilizing batch capacity efficiently.
- Example, packing three short sequences ([3 tokens], [2 tokens], [4 tokens]) into a max-length batch of 10 tokens results in:

```
A1 A2 A3 B1 B2 C1 C2 C3 C4
```



No padding tokens required, fully utilizing computation resources.

Problems with Packing:

- Concatenation may cause unintended interaction between sequences, known as "cross-contamination."
- To avoid cross-contamination, complex mask mechanisms (like block-diagonal masking) are required, often cumbersome to implement.
- Many frameworks’ naive packing implementations may suffer from accuracy loss unless explicitly handled, suitable mostly for clearly delimited sequences (like chat templates).

### Explaining Cross-Contamination:

Suppose two training samples:

- Sample A: ["How’s Beijing’s weather?"]
- Sample B: ["Famous attractions in Shanghai?"]

Ideal training treats each sample independently:

```
[A: Beijing weather context], [B: Shanghai attractions context]
```



But packing merges them:

```
[Beijing’s weather context; Shanghai attractions context]
```



If a naive left-to-right attention is used without proper masking, sequences interact unintentionally, causing training contamination and hurting model performance (reduced generalization).

------

## 3. Padding-Free

Padding-free is a newer strategy recently proposed. Like packing, it tightly compresses sequences without any padding. The main difference from packing is padding-free explicitly tracks sequence boundaries using auxiliary arrays (e.g., `cu_seqlens`) alongside efficient attention algorithms (like FlashAttention 2). This completely avoids cross-contamination.

- Packing merges individual sequences into one long sequence. It requires additional complex masking against contamination.
- Padding-free flattens sequences continuously but separately while preserving clear boundaries automatically handled by advanced attention mechanisms.

### Padding-free Key Mechanism:

- Flatten variable-length sequences into one continuous tensor.
- Record exact boundary indices with a separate array (`cu_seqlens`).
- Advanced attention mechanism, like FlashAttention, naturally supports variable-length handling using `cu_seqlens`, enabling GPU parallelization efficiency and avoiding wasteful computations on padding tokens.

### FlashAttention Role in Padding-free:

- **Native support for variable lengths:** Accepts continuously flattened tensors with `cu_seqlens`.
- **Isolation of sequence boundaries:** Automatically prevents cross-contamination.
- **Higher efficiency:** No padding overhead and reduced memory requirements by avoiding traditional attention masks.

### Illustration of Padding-free Attention Computation:

Given two sequences with `cu_seqlens = [0, 4, 9]`:

```
tokens：[Beijing, weather, how, Shanghai, famous, attractions, etc.]
Seq A: tokens[0:4], Seq B: tokens[4:9]
```



FlashAttention automatically ensures internal attention within each sequence only, preventing cross-contamination entirely.

**Currently widespread padding-free examples:**

- Hugging Face’s TRL framework provides padding-free support based on FlashAttention.
- NVIDIA optimized kernels support FlashAttention/padding-free.
- This current work explicitly highlights this practice using TRL+FlashAttention combination.

------

## 4. Scenarios Where Padding-free Shines:

Padding-free advantages only manifest clearly when batch size exceeds one:

- **Batch size = 1:** No padding needed anyway, padding-free provides no benefits.
- **Batch size > 1:** Variable lengths across sequences cause heavy padding overhead, eliminated entirely by padding-free.
- **Larger GPU memory capacity and speed**：batches per device are faster to process with higher memory bandwidth. TFlops on H100 and H200 are same, but memory speed is much higher on H200 than that on H100.

For Visual-Language Models (VLMs), applicability notably depends on textual modality:

| Type              | Example scenarios                                            | Recommendations                          | Suitability     |
| ----------------- | ------------------------------------------------------------ | ---------------------------------------- | --------------- |
| Suitable for VLMs | VQA tasks, dialogues, image captions (varying length texts, padding wastes resources). | Recommended padding-free                 | Highly suitable |
| Less suitable     | Image classification tasks or short fixed-length text scenarios (negligible padding waste). | Padding-free not useful, not recommended | Less suitable   |

VLM trains with fixed-length visual features and variable-length textual input, so padding-free notably reduces GPU waste when dealing with variable-length textual modality.

------

## 5. Code Implementation & Efficiency comparison

### Efficiency comparison (packing vs padding vs padding-free):

| Method       | Completed steps | Total steps | Used time | Est. remaining | Speed (it/s) | Epoch completion % |
| ------------ | --------------- | ----------- | --------- | -------------- | ------------ | ------------------ |
| packing      | 3               | 129         | 1m55s     | 4h2m20s        | 0.01         | ~2%                |
| padding      | 3               | 235         | 1m18s     | 5h4m00s        | 0.01         | ~1%                |
| padding-free | 30              | 235         | 22m41s    | 2h46m7s        | 0.02         | ~12%               |

Padding-free clearly shows faster training speed than padding/packing.

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

**packing：**

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

 [ 3/129 01:55 < 4:02:20, 0.01 it/s, Epoch 0.02/1]

**padding:**

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

[ 3/235 01:18 < 5:04:00, 0.01 it/s, Epoch 0.01/1]

**padding_free：**

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

 [ 30/235 22:41 < 2:46:07, 0.02 it/s, Epoch 0.12/1]

**Summary:**
Padding-free training leverages advanced GPU capabilities, significantly reducing computation overhead from padding. When batch size > 1 and captures variable-length textual inputs, padding-free is highly recommended for efficiency and resource-saving.
