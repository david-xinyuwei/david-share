# Phi-3.5-Vision-and-Pixtral-vLLM



### 1. Pixtral VS Microsoft's Phi-3.5-Vision?


Pixtral and Phi-3.5 Vision are both highly powerful Visual Language Models (VLMs), but they each have their own strengths in certain areas. Below is a detailed comparison of the two:

#### 1.1 Pixtral

**Advantages:**

- **High-Resolution Image Processing:** Pixtral can handle high-resolution images, making it suitable for tasks requiring detailed image analysis.

- **Multi-Task Capability:** Excels in tasks such as image description, Optical Character Recognition (OCR), and Visual Question Answering (VQA).

- **Rich Image Tagging:** Uses a large number of image tags to encode images, capturing more image details.

  **Disadvantages:**

- **High Memory Requirement:** Due to the use of numerous image tags, Pixtral requires more GPU memory when processing high-resolution images.

#### 1.2 Phi-3.5 Vision

**Advantages:**

- **Efficient Image Encoding:** Uses fewer image tags to encode images, making memory usage more efficient.

- **Multi-Modal Input Processing:** Can handle multi-modal inputs that include both text and images, suitable for various application scenarios.

- **Optimized Model Architecture:** Improved attention mechanisms and memory management make it perform better in handling long sequences and large images.

  **Disadvantages:**

- **Image Detail Capture:** May not be as detailed as Pixtral in some high-resolution image tasks due to the use of fewer image tags.

## Specific Application Scenarios

- **High-Resolution Image Analysis:** If your application requires handling high-resolution images and capturing details, Pixtral may be more suitable.

- **Memory-Constrained Environments:** If your application has strict memory usage limitations, Phi-3.5 Vision would be a better choice.

  In some benchmark tests, Phi-3.5 Vision excels in single-image understanding and reasoning, particularly in multi-frame image understanding and reasoning tasks. Pixtral, on the other hand, has advantages in handling high-resolution images and multi-task capabilities.

  Overall, the choice of model depends on your specific needs and application scenarios. If you need to handle high-resolution images and capture more details, Pixtral is a good choice. If you need to efficiently process multi-modal inputs in a memory-constrained environment, Phi-3.5 Vision would be more suitable.

## Technical Implementation Differences

Pixtral and Phi-3.5 Vision are two types of VLMs that perform well in handling prompts containing both text and images. Pixtral uses a large number of tags to encode images, leading to increased memory requirements, while Phi-3.5 Vision adopts a more efficient image encoding scheme, significantly reducing the number of tags used.

The reason Phi-3.5 Vision can use fewer tags to encode images is mainly due to its adoption of a more efficient image encoding technology, ViT-L (https://arxiv.org/pdf/2404.14219). Here are some key points:

1. Larger Image Blocks:

   - Phi-3.5 Vision divides images into larger blocks. For example, if Pixtral divides an image into 16x16 pixel blocks, Phi-3.5 Vision might divide it into 32x32 pixel blocks. This way, each image tag represents more pixels, thus reducing the number of tags needed.

2. Efficient Encoding Algorithms:

   - Phi-3.5 Vision may use more efficient encoding algorithms that can reduce the number of tags while maintaining the integrity of the image information. These algorithms might include more advanced compression techniques and smarter feature extraction methods.

3. Optimized Model Architecture:

   - The model architecture of Phi-3.5 Vision might be optimized to better handle and understand fewer image tags. This optimization could include improved attention mechanisms and more efficient memory management.

4. Multi-Modal Data Processing:

   - Phi-3.5 Vision might also use multi-modal data processing techniques to more closely integrate image and text information, thereby reducing the reliance on a single type of tag.

     These technical improvements enable Phi-3.5 Vision to maintain high performance while significantly reducing memory usage and computational resource requirements.

## Inference code

### Pixtral

```
model_name = "mistralai/Pixtral-12B-2409"

sampling_params = SamplingParams(max_tokens=512)

llm = LLM(model=model_name, tokenizer_mode="mistral", enable_chunked_prefill=False, max_model_len=5000)

prompt = "Describe this image in one sentence."
image_url = "https://images.unsplash.com/photo-1601139677490-2b3144da51a4?q=80&w=2667&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
messages = [
    {
        "role": "user",
        "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}]
    },
]

outputs = llm.chat(messages, sampling_params=sampling_params)

print(outputs[0].outputs[0].text)![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi-3.5-Vision-and-Pixtral-vLLM/images/1.png)
```

Images which is for inferencing:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi-3.5-Vision-and-Pixtral-vLLM/images/1.png)

Inference speed:

```
Processed prompts: 100%|███████████| 1/1 [00:00<00:00,  3.53it/s, est. speed input: 980.30 toks/s, output: 84.93 toks/s]
```

Inference result:

```
The image depicts a busy Times Square in New York City during the night with numerous people walking and sitting, surrounded by bright advertisements, and tall buildings in the background.
```

### vLLM

```
model_path = "microsoft/Phi-3.5-vision-instruct"


llm = LLM(
    model=model_path,
    trust_remote_code=True,
    max_model_len=5000,
)

image = Image.open("street.jpg")

# single-image prompt
prompt = "<|user|>\n<|image_1|>\nDescribe this image in one sentence.<|end|>\n<|assistant|>\n"
sampling_params = SamplingParams(max_tokens=512)

outputs = llm.generate(
    {
        "prompt": prompt,
        "multi_modal_data": {
            "image": image
        },
    },sampling_params=sampling_params)

print(outputs[0].outputs[0].text)
```

Inference speed:

```
Processed prompts: 100%|██████████| 1/1 [00:00<00:00,  1.82it/s, est. speed input: 1412.22 toks/s, output: 56.56 toks/s]
```

Inference result:

```
A densely packed urban street scene at twilight with brightly lit billboards and neon signs, where many people are gathered.
```

We could see that Phi-3.5-Vision is faster, Pixtral has more detailed inference result.