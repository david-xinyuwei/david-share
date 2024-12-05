# Use Unsloth to fine-tune VLM

In this article, I will introduce the challenges of fine-tuning VLM and how to use Unsloth to fine-tune VLM. I will provide the fine-tuning code and results. 

**Note:**

 The free version of Unsloth only supports single GPU operation. If you need multi-GPU support, you will need to upgrade Unsloth to the Pro version or the Enterprise version.

## Understanding the Challenges of Fine-tuning Visual Language Models

1. **Model Parameter Size**

   Taking Qwen2-VL 7B as an example, it adds an image encoder to the base Qwen2 7B model. Although this adds approximately 670 million parameters (increasing from 7.62 billion to 8.29 billion), compared to the overall model size, this is not the main issue.

2. **Sequence Length of Image Tokens**

   The real challenge lies in the fact that the image encoder converts images into a large number of image tokens, which significantly increases the sequence length and, in turn, consumes a large amount of memory. For example, processing an image of size 200x300 pixels may generate about 235 image tokens, while a larger image (such as 2667x1786 pixels) may produce close to 2000 image tokens.

   The increase in sequence length significantly boosts memory requirements. This is why, when fine-tuning VLMs, a large amount of memory is needed even if the model parameters have not increased substantially.

   

   ## Methods to Optimize Memory Usage

   ### Controlling the Input Image Size

   To reduce memory consumption, the maximum size of input images should be limited. It is generally recommended to keep the longest side of the image within 768 pixels or 1024 pixels. For GPUs with 12 GB of memory, it is advisable to set the maximum size to 768 pixels.

   Below is a code example for preprocessing images:

   This code adjusts the image size to a controllable range and converts the data into a conversation format for subsequent processing.

   

   ### Using Unsloth to Optimize the Fine-tuning Process

   Unsloth is a toolkit designed to optimize memory usage and accelerate the fine-tuning process. By using Unsloth, we can save a significant amount of memory.

   ### The Essence of Unsloth in Saving Memory

   Unsloth saves memory fundamentally by optimizing memory usage during the model fine-tuning process, enabling large Visual Language Models (VLMs) to be fine-tuned even on hardware with limited resources. This is achieved mainly through the following methods:

1. **Optimized Gradient Checkpointing**

   - **Efficient Implementation for Long Sequences**: Unsloth provides a specially optimized gradient checkpointing functionality, particularly suitable for models dealing with long sequence data, such as the large number of image tokens in VLMs.
   - **Reducing Memory Consumption**: By selectively saving intermediate activations during the forward pass and recomputing parts of the forward process during the backward pass, the number of activations that need to be stored is reduced, significantly lowering memory usage.

2. **Parameter-Efficient Fine-Tuning (PEFT)**

   - **Using LoRA Technology**: Unsloth integrates the LoRA (Low-Rank Adaptation) fine-tuning method, adding low-rank adapters to specific weight matrices in the model instead of fine-tuning all the model's parameters.
   - **Reducing the Number of Trainable Parameters**: LoRA significantly reduces the number of parameters that need to be updated and stored, decreasing the memory occupation of optimizer states and gradients.

3. **Flexible Modular Fine-Tuning Configuration**

   - **Selective Fine-tuning of Model Components**: Unsloth allows users to selectively fine-tune different parts of the model according to task requirements, such as the vision encoder, language model layers, attention modules, and MLP modules.
   - **Reducing Unnecessary Computation and Memory Overhead**: By fine-tuning only the necessary parts, it avoids the additional memory consumption that would be brought by fine-tuning the entire model.

4. **Support for Low-Precision Training and Quantization**

   - **4-bit and 8-bit Quantization**: Unsloth supports loading models using 4-bit or 8-bit precision (`load_in_4bit=True`), which significantly reduces the memory occupation of model weights.
   - **Low-Precision Storage of Optimizer States**: Using specialized optimizers (such as `paged_adamw_8bit`), optimizer states are stored in 8-bit precision, further reducing memory usage.

5. **Efficient Data Processing and Preprocessing**

   - **Control the Scale of Input Data**: By adjusting the size of input images during data preprocessing, the maximum side length of images is limited to prevent the generation of overly long image token sequences, avoiding exceeding memory limits.
   - **Optimized Data Collator**: Unsloth provides an efficient data collator for visual data, reducing memory overhead during data loading and processing.

6. **Optimization Specific to Model Architectures**

   - **Optimized for VLMs**: Unsloth has been adapted and optimized for different VLM architectures (such as Qwen2-VL, Llama 3.2 Vision, Pixtral), ensuring optimal memory efficiency on these models.

     In summary, Unsloth saves memory through the following core strategies:

- **Optimizing the Computation Process**: Reducing the number of intermediate activations and gradients that need to be stored.

- **Reducing Data Precision and Model Size**: Utilizing quantization techniques to reduce the memory occupation of model weights and optimizer states.

- **Flexible Selection of Model Components to Fine-Tune**: Fine-tuning only task-relevant parts to reduce unnecessary computation and memory usage.

- **Efficient Data Preprocessing and Processing**: Controlling the scale of input data and optimizing the data loading process.

  Therefore, Unsloth's core advantage lies in a combination of multiple optimizations, enabling effective fine-tuning of large Visual Language Models even on hardware environments with limited memory.



## Training Code

**Load Model with Unsloth**

```
from unsloth import FastVisionModel # FastLanguageModel for LLMs
import torch
from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Qwen2-VL-7B-Instruct",
    load_in_4bit = True, # Use 4bit to reduce memory use. False for 16bit LoRA.
    use_gradient_checkpointing = "unsloth", # True or "unsloth" for long context
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/1.png)

Set models to be trained

```
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers     = True, # False if not finetuning vision layers
    finetune_language_layers   = True, # False if not finetuning language layers
    finetune_attention_modules = True, # False if not finetuning attention layers
    finetune_mlp_modules       = True, # False if not finetuning MLP layers

    r = 16,           # The larger, the higher the accuracy, but might overfit
    lora_alpha = 16,  # Recommended alpha == r at least
    lora_dropout = 0,
    bias = "none",
    random_state = 3407,
)
```

Training dataset

```
dataset_train = load_dataset("HuggingFaceM4/DocumentVQA", split = "train[:1000]")
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/2.png)

Let us have a look at one example.

Prompt:

what is the date mentioned in this letter?

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/3.jpg)

Answer:

 [ "1/8/93" ]



**Data process:**

```
max_size_img = 768


instruction = "You are an expert in document analysis. Answer the questions on the provided document.\n\n"
def convert_to_conversation(sample):
    width, height = sample["image"].size
    #resize the image
    if width >= max_size_img or height > max_size_img:
      if width > height:
          sample["image"] = sample["image"].resize((max_size_img, int(max_size_img*height/width)))
      else:
          sample["image"] = sample["image"].resize((int(max_size_img*width/height), max_size_img))

    conversation = [
        { "role": "user",
          "content" : [
            {"type" : "text",  "text"  : instruction+sample['question']},
            {"type" : "image", "image" : sample["image"]} ]
        },
        { "role" : "assistant",
          "content" : [
            {"type" : "text",  "text"  : sample["answers"][0]} ]
        },
    ]
    return { "messages" : conversation }
```

Training code:

```
training_args = SFTConfig(
        per_device_train_batch_size = 8,
        gradient_accumulation_steps = 16,
        warmup_ratio = 0.1,
        max_steps = 200,
        # num_train_epochs = 1, # Uncomment this line to train on the full dataset
        learning_rate = 1e-4,
        bf16 = True,
        logging_steps = 25,
        save_steps = 100,
        save_total_limit = 2,
        optim = "paged_adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs/",
        report_to = "none",

        # Unsloth mentionned that we MUST put the below items for vision finetuning:
        remove_unused_columns = False,
        dataset_text_field = "",
        dataset_kwargs = {"skip_prepare_dataset": True},
        dataset_num_proc = 4,
        max_seq_length = 1024,
    )
```

```
FastVisionModel.for_training(model) # Enable for training!
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    data_collator = UnslothVisionDataCollator(model, tokenizer), # Must use!
    train_dataset = new_dataset_train,
    args = training_args
)
```

```
trainer_stats = trainer.train()
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/4.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/5.png)

 Inference

```
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-7B-Instruct", torch_dtype=torch.bfloat16, device_map="auto",attn_implementation="flash_attention_2"
)

adapter_path = "outputs/checkpoint-200/"
model = PeftModel.from_pretrained(model, adapter_path)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")


dataset_test = load_dataset("HuggingFaceM4/DocumentVQA", split = "validation[:10]")

from PIL import Image

max_size_img = 768


instruction = "You are an expert in document analysis. Answer the questions on the provided document.\n\n"
def convert_to_conversation(sample):
    width, height = sample["image"].size
    #resize the image
    if width >= max_size_img or height > max_size_img:
      if width > height:
          sample["image"] = sample["image"].resize((max_size_img, int(max_size_img*height/width)))
      else:
          sample["image"] = sample["image"].resize((int(max_size_img*width/height), max_size_img))

    conversation = [
        { "role": "user",
          "content" : [
            {"type" : "text",  "text"  : instruction+sample['question']},
            {"type" : "image", "image" : sample["image"]} ]
        }
    ]
    return { "messages" : conversation }

processed_dataset = [convert_to_conversation(sample) for sample in dataset_test]
messages = processed_dataset[0]["messages"]

# Preparation for inference
text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)

image_inputs, video_inputs = process_vision_info(messages)
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
inputs = inputs.to("cuda")

# Inference: Generation of the output
generated_ids = model.generate(**inputs, max_new_tokens=128)
generated_ids_trimmed = [
    out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]
output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
)
print(output_text)

```

```
dataset_test[0]["image"]																										
```

```
print(dataset_test[0]["question"])
print(dataset_test[0]["answers"])
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Use-Unsloth-to-fine-tune-VLM/5.png)

What is name of university? 

['university of california', 'University of California', 'university of california, san diego']