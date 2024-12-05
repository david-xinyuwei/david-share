# Use Unsloth to fine-tune VLM

In this article, I will introduce the challenges of fine-tuning VLM and how to use Unsloth to fine-tune VLM. I will provide the fine-tuning code and results. 

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

Load Model with Unsloth

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

