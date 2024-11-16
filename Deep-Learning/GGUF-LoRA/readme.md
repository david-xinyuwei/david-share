# Efficiently Using GGUF Format LoRA Adapters on CPU: From Introduction to Practice

Llama.cpp has introduced a new feature: GGUF now supports LoRA loading. I tested the perplexity of the torch format merged model (Base model + LoRA Adapter) to GGUF, and it is only 3% lower than the perplexity of the base and adapter models separately to GGUF, followed by dynamic loading. I adopted the second method, converting the base model to GGUF, then quantizing it to 4-bit, and dynamically loading the 4bit base model + FP16 adapter as shown in the video. This is the inference result on the CPU. I hope it is useful.

***Please click below pictures to see my demo vedio on Yutube***:

[![GGUF-LoRA-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/OBDo2nq5rak)



## Some Key points

- GGUF is the most popular format because it's CPU-friendly. Moreover, GGUF models are easy to run and deploy as they are single files. GGUF supports most transformer architectures.

- The model shouldn't be quantized when converting to GGUF. 

- GGUF supports loading LoRA. The base model and the adapter don't need to be using the same data type.

- During GGUF conversion you can choose to convert to FP16 or a quantized format. In the subsequent steps, I will quantize the base model converted to GGUF to four bits, keep the adapter in FP16, and then dynamically load it for inference. 

  - Inference speed of the base model before quantization: approximately 10.93 tokens/sec
  - Inference speed of the base model after quantization: 34.26 tokens/sec

  

## I. Background Knowledge

### 1. What is the GGUF Format?


**GGUF** is a binary file format used for storing quantized large language models, designed to efficiently store models and accelerate the loading process. It packages everything needed for model inference (including model weights, tokenizers, configuration files, etc.) into a single file. This is extremely helpful for rapid inference in **resource-constrained environments (such as CPUs)**.

### 2. What is LoRA?


**LoRA (Low-Rank Adaptation)** is a parameter-efficient fine-tuning method. Traditional model fine-tuning requires updating and storing all the parameters of the model, which is highly resource-intensive for large models. LoRA introduces **low-rank matrices** to update the model's weights, significantly reducing the number of parameters that need to be trained and stored. This makes it possible to fine-tune large models on standard hardware.

### 3. Why Use LoRA Adapters in GGUF Format on CPUs?


Converting LoRA adapters to GGUF format and loading them together with the base model offers several advantages:

- **Efficient Storage**: GGUF format is optimized to store models more compactly.
- **Fast Loading**: Models in GGUF format can be loaded more quickly during inference, reducing startup time.
- **Resource Savings**: Inference can be performed on CPUs without the need for high-end GPUs, lowering hardware costs.
- **Fast Inference Speed**: GGUF format optimizes inference, achieving relatively fast speeds even on CPUs.

------

 

## II. How Does GGUF Format Accelerate Inference?


Before diving into practice, let's understand why the GGUF format can significantly improve inference speed.

### 1. Efficient Binary Format


GGUF uses an optimized binary storage method that allows for rapid reading and parsing of model weights. This reduces the overhead of model loading and speeds up the inference startup process.

### 2. Integrated Model File


GGUF format packages all the components required by the model (including model weights, tokenizers, configuration files, etc.) into a single file. This avoids the I/O overhead caused by loading multiple files, further enhancing loading speed.

### 3. Support for Model Quantization


GGUF format supports multiple quantization precisions (such as FP16, INT8, INT4, etc.). Through quantization, the size of model weights can be greatly reduced, lowering memory usage and computational complexity, thereby accelerating the inference process.

### 4. Optimized Memory Access


During inference, the data arrangement in GGUF format optimizes memory access patterns, reducing cache misses and memory bandwidth bottlenecks, and improving CPU computational efficiency.

### 5. Specifically Designed for CPU Inference


GGUF format is particularly suitable for running models on CPUs, such as when used with `llama.cpp`. It leverages CPU architectural features, avoiding some GPU-specific optimizations, thus achieving better performance on CPUs.

**Actual Effects:**

- Using models in GGUF format results in faster loading times and lower inference latency.
- Without high-performance GPUs, GGUF format enables us to run large language models on standard computers, achieving acceptable response speeds.
- Many developers report that when using quantized models in GGUF format (such as INT4 quantization), near real-time inference can be achieved on CPUs.

------

 

## III. Traditional Method: Merging LoRA Adapters and Converting to GGUF Format


In practice, the initial workflow for using LoRA adapters usually involves:

1. **Training LoRA Adapter**: Fine-tune the base model to obtain the LoRA adapter.
2. **Merging Adapter and Base Model**: Use tools to merge the weights of the LoRA adapter with those of the base model.
3. **Converting to GGUF Format**: Convert the merged model to GGUF format for inference.

### **Problems**


The issues with this method are:

- **Inflexibility**: Whenever there's a new LoRA adapter, you need to re-merge and convert, which is time-consuming and labor-intensive.
- **Increased Storage Usage**: Each merged model is complete, occupying a large amount of disk space.
- **Complex Operations**: Similar steps need to be repeated for each new task, hindering rapid iteration.

------

 

## IV. New Method: Separately Converting Base Model and LoRA Adapter to GGUF Format


To overcome the above problems, we can adopt a more flexible method:

1. **Convert Base Model to GGUF Format**: Convert the base model to GGUF format.
2. **Convert LoRA Adapter to GGUF Format**: Independently convert the LoRA adapter to GGUF format.
3. **Load Together During Inference**: Simultaneously load the base model and LoRA adapter during inference.

### **Advantages**

- **Flexibility**: You can freely switch between different LoRA adapters during inference without re-merging the model.
- **Storage Savings**: LoRA adapters are usually small, so the storage space they occupy is negligible.
- **Simplified Operations**: Reduces the step of merging models, lowering operational complexity.
- **Fast Inference Speed**: Leveraging the advantages of GGUF format, you can achieve good inference speeds even on CPUs.

### **Detailed Operation Steps**


Below, we will provide a detailed guide on how to implement the above process in practice.

#### **1. Convert Base Model to GGUF Format**


**Steps:**

- **Download Base Model**: Obtain the pre-trained base model from platforms like Hugging Face.

- **Use Conversion Script**: Use the `convert_hf_to_gguf.py` script provided by `llama.cpp`.

  **Sample Code:**
  
  Download gguf and compile it locally.
  
  ```
  git clone https://github.com/ggerganov/llama.cpp
  
  cd llama.cpp && GGML_CUDA=1 make && pip install -r requirements.txt
  ```
  
  **If you want to run entirely on CPU, you can replace `GGML_CUDA=1` with:**
  
  ```
  make clean  
    
  LLAMA_CUDA=0 LLAMA_CUBLAS=0 make  
  ```
  
  **After successful compilation, you need to copy `llama-cli` to `/usr/lib/bin`.**

```
# Convert base model to GGUF format  
gguf_model = './SFT_LoRA_Merged/FP16.gguf'
python llama.cpp/convert_hf_to_gguf.py ./SFT_LoRA_Merged/ --outtype f16 --outfile {gguf_model}
```

- `--outtype f16`: Specify the model's precision as FP16.

#### **2. Convert LoRA Adapter to GGUF Format**


**Steps:**

- **Train LoRA Adapter**: Use deep learning frameworks like PyTorch to perform LoRA fine-tuning on the base model.

- **Use Conversion Script**: Use the `convert_lora_to_gguf.py` script provided by `llama.cpp`.

  **Sample Code:**

```
python llama.cpp/convert_lora_to_gguf.py --outfile ./SFT_LoRA_Merged/f16_LoRA.gguf --outtype f16 ./Llama-3.2-3B-Instruct-UltraChat/
```

**Notes:**

- Ensure that the LoRA adapter and base model are compatible, i.e., based on the same architecture and version.

- The current conversion script does not support LoRA adapters that include token embeddings and language modeling heads.

#### **3. Load Base Model and LoRA Adapter Together During Inference**


**Steps:**

- **Use `llama.cpp` for Inference**: `llama.cpp` supports loading both the base model and LoRA adapter simultaneously.

  **Sample Code:**

```
# Use the inference program of llama.cpp  
root@a100vm:~/llama.cpp# llama-cli -m ../Llama-3.2-3B-Instruct/ggml-model-q4_0.gguf --lora ../SFT_LoRA_Merged/f16_LoRA.gguf -p "You are a helpful assistant, your name is XinyuWei" --threads 24 --ctx-size 1024 --batch-size 512 --ubatch-size 16
```


**Explanation:**

- `-m` specifies the path to the base model.
- `--lora` specifies the path to the LoRA adapter.

- `--threads 24`

  - **Sets** the number of CPU threads to use.
  - **Affects** CPU utilization and processing speed.
  - **Use when** you want to leverage multi-core CPUs for faster generation.

- `--ctx-size 1024`

  - **Defines** the maximum number of tokens in the context window.
  - **Affects** how much prior text the model can consider for generating responses.
  - **Use when** you need the model to maintain context over longer inputs or outputs.

- `--batch-size 512`

  - **Specifies** the maximum number of tokens processed in a single batch.
  - **Affects** throughput and memory usage.
  - **Use when** you want to optimize performance, balancing speed and resource consumption.

- `--ubatch-size 16`

  - **Determines** the size of micro-batches within the logical batch.

  - **Affects** memory usage during processing.

  - **Use when** managing limited memory resources, to prevent out-of-memory errors.

    The inference performance result:

    ```
    Please respond with your text or question
    llama_perf_sampler_print:    sampling time =      62.18 ms /   749 runs   (    0.08 ms per token, 12045.67 tokens per second)
    llama_perf_context_print:        load time =     710.04 ms
    llama_perf_context_print: prompt eval time =      86.86 ms /    14 tokens (    6.20 ms per token,   161.18 tokens per second)
    llama_perf_context_print:        eval time =   25478.82 ms /   734 runs   (   34.71 ms per token,    28.81 tokens per second)
    llama_perf_context_print:       total time =   25818.11 ms /   748 tokens
    ```

------



## V. Comparison of the Two Methods

 

### **1. Flexibility**

- **Separately Convert and Load**: You can switch LoRA adapters at any time, suitable for scenarios requiring frequent task changes.
- **Merge and Convert**: Each time you change an adapter, you need to re-merge, which is less flexible.

### **2. Storage Space**

- **Separately Convert and Load**: Only need to store one base model and multiple small LoRA adapter files.
- **Merge and Convert**: Each merged model is complete, occupying a large amount of storage space.

### **3.  Perplexity**

- According to actual measurements, the perplexity of converting a Torch-merged model to GGUF is only 3% lower than that of converting the base model and adapter separately to GGUF and then dynamically loading them. 



### **4. Inference Speed**

- The inference speed and performance are essentially the same for both methods. Since GGUF format optimizes inference speed, computations after loading into memory are efficient regardless of merging.

### **5. Applicable Scenarios**

- **Separately Convert and Load**: Suitable for LoRA adapters that do not contain token embeddings and language modeling heads, and scenarios where adapters need to be changed frequently.
- **Merge and Convert**: Suitable for LoRA adapters that contain additional modules or scenarios targeting specific tasks.

------

 

## VI. Notes and Recommendations

 

### **1. Limitations of LoRA Adapters**


The current `convert_lora_to_gguf.py` script does not support LoRA adapters that include `embed_tokens` and `lm_head` modules. If your adapter contains these modules, it is recommended to use the merge and convert method.

### **2. About QLoRA Adapters**


If your LoRA adapter is fine-tuned using the QLoRA method (i.e., fine-tuned on a quantized base model), directly converting the adapter to GGUF and loading it with a base model of different quantization configurations may lead to performance degradation. It's recommended to operate under the same quantization configuration as during fine-tuning.

### **3. Compatibility of Model and Adapter**


Ensure that your base model and LoRA adapter are based on the same model architecture and version. Incompatibility may result in inference failures or inaccurate results.

### **4. Choice of Quantization and Precision**

- **Base Model**: You can choose an appropriate quantization scheme (such as `q4_0`, `q5_1`, etc.) to reduce memory usage.
- **LoRA Adapter**: Since it is relatively small, it usually uses FP16 precision without further quantization.

### **5. Advantages of GGUF**

As mentioned earlier, GGUF format has significant advantages in inference speed. Through optimized storage methods and support for quantization, GGUF enables large language models to achieve fast and efficient inference on CPUs. This makes it possible to run complex models in resource-constrained environments. 

## VII. Practical Example


**Suppose you have a base model and multiple LoRA adapters, and you wish to perform efficient inference for different tasks on a CPU.**

**Steps:**

1. **Convert the base model to GGUF format** and store it in a fixed location.

2. **Convert all LoRA adapters separately to GGUF format**.

3. **During inference**, load the corresponding LoRA adapter according to the task without re-merging the model.

   **Advantages:**

- You only need to save one base model, saving storage space.
- You can quickly switch tasks, enhancing development and deployment efficiency.
- Thanks to the optimization of GGUF format, inference speed can meet requirements even on CPUs.



