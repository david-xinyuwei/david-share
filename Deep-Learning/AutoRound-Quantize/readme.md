# Quantization 72B model with AutoRound on Azure NC40ads_H100_v5

This article focuses on model quantization using Intel's open-source tool, AutoRound. In post-quantization, AutoRound's accuracy is relatively high and on par with GPTQ. 

Currently, AutoRound hasn't gained much stars on github, primarily because users are already content with AutoAWQ and AutoGPTQ and aren't seeking better alternatives. However, AutoGPTQ is actually outdated, and AutoAWQ supports only 4-bit quantization. I believe that by the end of 2025, AutoRound will become more popular, especially after its format is integrated into vLLM.

## Quantization Result

First, let's look at the test results. I used a Azure NC40ads_H100_v5 VM with a single H100 GPU, 40 CPU cores, and 320GB of host memory (not fully utilized).

Load Model

```\
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model_name = "Qwen/Qwen2.5-72B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
tokenizer = AutoTokenizer.from_pretrained(model_name)
```



CPU Utilization When Loading the Model:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVlTpOQYOKicPNz6pyHpuV8ficpSuGv3tFjOm9ga3nqq2K5A59rhJCGEKjffItFNy7EjSico8AK1ib5Hg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

4-bit Quantization

```
from auto_round import AutoRound

bits, group_size, sym = 4, 128, True

autoround = AutoRound(model, tokenizer, nsamples=128, iters=512, low_gpu_mem_usage=True, batch_size=1, graddient_accumulation_steps=8, bits=bits, group_size=group_size, sym=sym)


autoround.quantize()
output_dir = "./Qwen2.5-72B-Instruct-AutoRound-GPTQ-4bit"
autoround.save_quantized(output_dir, format='auto_gptq', inplace=True)
```

GPU Memory Utilization During Model Quantization:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVlTpOQYOKicPNz6pyHpuV8fudsKjibAY1d8PDiajficM6PZE0gt66hGAicOnFjlfib7476QHG9KzIcdsMQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The quantization action is layer by layer:

``` 
/root/anaconda3/envs/auto-round/lib/python3.11/site-packages/torch/autograd/graph.py:825: UserWarning: Flash Attention defaults to a non-deterministic algorithm. To explicitly enable determinism call torch.use_deterministic_algorithms(True, warn_only=False). (Triggered internally at ../aten/src/ATen/native/transformers/cuda/attention_backward.cu:102.)
  return Variable._execution_engine.run_backward(  # Calls into the C++ engine to run the backward pass
Quantizing model.layers.61:  76%|███████▋  | 61/80 [1:03:33<20:01, 63.23s/it]
```

```
Quantizing model.layers.79: 100%|██████████| 80/80 [1:23:37<00:00, 63.50s/it]2024-12-11 09:48:59 INFO autoround.py L340: quantization tuning time 5037.20055103302
2024-12-11 09:48:59 INFO autoround.py L356: Summary: quantized 560/561 in the model,  ['lm_head'] have not been quantized
Quantizing model.layers.79: 100%|██████████| 80/80 [1:23:37<00:00, 62.72s/it]
2024-12-11 09:48:59 INFO export.py L125: Saving quantized model to autogptq format, this may take a while...
packing lm_head: 100%|██████████| 561/561 [11:55<00:00,  1.27s/it]   
```

```
Qwen2ForCausalLM(
  (model): Qwen2Model(
    (embed_tokens): Embedding(152064, 8192)
    (layers): ModuleList(
      (0-79): 80 x Qwen2DecoderLayer(
        (self_attn): Qwen2SdpaAttention(
          (q_proj): QuantLinear()
          (k_proj): QuantLinear()
          (v_proj): QuantLinear()
          (o_proj): QuantLinear()
          (rotary_emb): Qwen2RotaryEmbedding()
        )
        (mlp): Qwen2MLP(
          (gate_proj): QuantLinear()
          (up_proj): QuantLinear()
          (down_proj): QuantLinear()
          (act_fn): SiLU()
        )
        (input_layernorm): Qwen2RMSNorm((8192,), eps=1e-06)
        (post_attention_layernorm): Qwen2RMSNorm((8192,), eps=1e-06)
      )
    )
    (norm): Qwen2RMSNorm((8192,), eps=1e-06)
    (rotary_emb): Qwen2RotaryEmbedding()
  )
  (lm_head): Linear(in_features=8192, out_features=152064, bias=False)
)
```



```
(auto-round) root@h100vm:~# ls -al ./Qwen2.5-72B-Instruct-AutoRound-GPTQ-4bit
total 40533644
drwxr-xr-x  2 root root       4096 Dec 10 16:50 .
drwx------ 47 root root       4096 Dec 10 16:37 ..
-rw-r--r--  1 root root        605 Dec 11 09:48 added_tokens.json
-rw-r--r--  1 root root       1376 Dec 11 10:00 config.json
-rw-r--r--  1 root root        243 Dec 11 10:00 generation_config.json
-rw-r--r--  1 root root    1671853 Dec 11 09:48 merges.txt
-rw-r--r--  1 root root 4977604760 Dec 11 10:00 model-00001-of-00009.safetensors
-rw-r--r--  1 root root 4893894648 Dec 11 10:01 model-00002-of-00009.safetensors
-rw-r--r--  1 root root 4984871048 Dec 11 10:01 model-00003-of-00009.safetensors
-rw-r--r--  1 root root 4976067496 Dec 11 10:02 model-00004-of-00009.safetensors
-rw-r--r--  1 root root 4893776280 Dec 11 10:02 model-00005-of-00009.safetensors
-rw-r--r--  1 root root 4893894800 Dec 11 10:02 model-00006-of-00009.safetensors
-rw-r--r--  1 root root 4893894808 Dec 11 10:03 model-00007-of-00009.safetensors
-rw-r--r--  1 root root 4484842920 Dec 11 10:03 model-00008-of-00009.safetensors
-rw-r--r--  1 root root 2491416704 Dec 11 10:03 model-00009-of-00009.safetensors
-rw-r--r--  1 root root     215614 Dec 11 10:04 model.safetensors.index.json
-rw-r--r--  1 root root        569 Dec 11 10:04 quantize_config.json
-rw-r--r--  1 root root        613 Dec 11 09:48 special_tokens_map.json
-rw-r--r--  1 root root   11421896 Dec 11 09:48 tokenizer.json
-rw-r--r--  1 root root       7336 Dec 11 09:48 tokenizer_config.json
-rw-r--r--  1 root root    2776833 Dec 11 09:48 vocab.json
(auto-round) root@h100vm:~#
```



AutoRound can produce models in the same format as GPTQ, support TGI, vLLM, etc.

Inference with vLLM

```

batch_sizes = [1, 2, 4, 8, 16, 32, 64, 128]  
p = """You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.  
  
If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.  
  
Tell me about gravity."""  
  
sampling_params = SamplingParams(max_tokens=1000)  
  
loading_start = time.time()  
llm = LLM(model="/root/Qwen2.5-72B-Instruct-AutoRound-GPTQ-4bit")  
print("--- Loading time: %s seconds ---" % (time.time() - loading_start))  
  
for b in batch_sizes:  
    prompts = [p] * b  # 创建包含 b 个相同提示的列表  
  
    generation_time = time.time()  
    outputs = llm.generate(prompts, sampling_params)  
    duration = time.time() - generation_time  
    total_tokens = 0  
    for output in outputs:  
        total_tokens += len(output.prompt_token_ids) + len(output.outputs[0].token_ids)  
    print('\nBatch size: ' + str(b))  
    print("--- Speed: %s tokens/second ---" % (round(total_tokens/duration, 2)))  
```



## Understanding AutoRound Literally

"AutoRound" is composed of two English words:

- **Auto**: An abbreviation of "Automatic," meaning automatic.

- **Round**: In mathematics and computer science, it refers to the rounding or truncation operation, i.e., converting numbers from high precision (more decimal places) to low precision (fewer decimal places) or integers.

  Therefore, "AutoRound" can be understood as "Automatic Rounding" or "Automatic Truncation." In the context of model quantization and deep learning, this name represents the main function of the tool:

  Automatically rounding the model's high-precision parameters to low-precision representations; that is, automatically converting the high-precision weights in a model (such as 32-bit floating-point numbers) to low-precision numerical formats (such as 4-bit, 2-bit), thereby achieving model compression and acceleration.

  AutoRound uses an automated approach to intelligently round model parameters, combining optimization algorithms to reduce model size and computational resources while preserving the model's performance and accuracy as much as possible.


Next, let's go into more detail.

### How Does AutoRound Quantize Models?

AutoRound is an intelligent model quantization tool. Its main features and advantages are:

**No Need for Calibration Dataset:**

- **No Additional Dataset Required**: AutoRound can quantize models without relying on a calibration dataset. This means you can perform quantization even if you don't have a special calibration dataset.
- **Internal Mechanism**: AutoRound leverages the model's own structure and parameter distribution to automatically optimize and minimize the accuracy loss caused by quantization as much as possible.

#### Intelligent Optimization Strategy

- **Automatic Rounding Optimization**: AutoRound uses advanced optimization algorithms to intelligently decide how to quantize each parameter during the quantization process, minimizing quantization errors.
- **Global Consideration**: Unlike traditional layer-wise or channel-wise quantization, AutoRound optimizes the quantization scheme on a global scale to achieve better overall results.

#### Low Memory Footprint:

- **Efficient Memory Management**: When quantizing large models, AutoRound provides a `low_gpu_mem_usage` parameter, which can shift some computations to the CPU to reduce GPU memory usage.
- **Suitable for Consumer-grade Hardware**: This allows for quantization of large models (e.g., models with 70B parameters) even on graphics cards with relatively small memory (such as RTX 3090, RTX 4090).

## What is Automatic Rounding Optimization

Automatic Rounding Optimization is the core technology of AutoRound. It treats the model quantization process as an optimization problem, using mathematical methods to globally find the optimal parameter rounding scheme. In this process, AutoRound doesn't just independently round each parameter but considers the overall impact of all parameters on the model's performance, intelligently deciding how each parameter should be quantized.

**Traditional Quantization vs. AutoRound's Automatic Rounding Optimization**

**Traditional Quantization Methods:**

- **Point-wise Rounding**: Independently round or truncate each weight, converting floating-point numbers to low-precision representations individually.

- **Local Optimality**: Each weight's quantization is based on its own value, without considering its role in the entire model.

- **Accumulated Quantization Error**: Since the relationships between parameters are not considered, quantization errors may accumulate in the model, leading to significant performance degradation.

  **AutoRound's Automatic Rounding Optimization:**

- **Global Optimization**: Treats the quantization of the entire model as a holistic optimization problem, aiming to minimize the error in the model's outputs after quantization.

- **Consideration of Parameter Importance**: Analyzes the impact of parameters on the model's output, giving priority to protecting parameters critical to performance.

- **Intelligent Rounding Decisions**: Based on optimization results, intelligently decides which parameters should be rounded up or down, and even allows different parameters to have different quantization strategies.

## Working Principle of AutoRound's Automatic Rounding Optimization 

### 1. Treating Quantization as an Optimization Problem

- **Objective Function**: AutoRound aims to minimize the output difference between the quantized model and the original model, i.e., minimizing the quantization error.
- **Constraints**: Quantize model parameters under certain bit widths (e.g., 4-bit, 2-bit) and quantization schemes (e.g., symmetric quantization, asymmetric quantization).

### 2. Using Optimization Algorithms to Solve

- **Continuous Relaxation**: Since quantized parameters are discrete (e.g., can only take specific quantization levels), direct optimization is difficult. AutoRound converts the discrete quantization problem into a continuous optimization problem, making optimization algorithms applicable.
- **Gradient Descent Method**: Using the model's gradient information, AutoRound can compute the impact of the quantization error of each parameter on the model's output.
- **Integer Programming**: In some cases, AutoRound transforms the quantization problem into an integer programming problem, finding the optimal quantization scheme by solving integer variables.

### 3. Intelligent Decision of Quantization Method for Each Parameter

- Parameter Importance Analysis:
  - **Sensitivity Evaluation**: Assess the impact of each parameter on the model's output. Parameters that significantly affect the model's output are considered "important" to model performance.
  - **Prioritizing Key Parameters**: For highly important parameters, more precise quantization schemes may be used during quantization, or excessive rounding may be avoided.
- Dynamic Quantization Strategy:
  - **Non-uniform Quantization**: Unlike traditional methods that treat all parameters equally, AutoRound can use different quantization steps or strategies for different parameters.
  - **Adaptive Rounding**: Based on optimization results, intelligently decide whether each parameter should be rounded up or down to minimize the overall quantization error.

### 4. Iterative Optimization

- **Multiple Iterations**: Through multiple iterative optimizations, continuously adjust the quantization scheme of parameters to gradually approach the optimal solution.

- **Error Feedback**: In each iteration, use the difference between the output of the quantized model and the original model to feed back into the optimization process, guiding the next rounding decision.

  

## Illustration of Automatic Rounding Optimization with Examples 

**Hypothetical Scenario:**

- **Model Parameters**: Suppose we have a set of model parameters: [2.3, -1.7, 0.5, -0.2].

- **Quantization Bit Width**: We want to quantize the parameters to a 2-bit representation, which means parameters can only take a limited number of values (e.g., -2, -1, 0, 1).

  **Traditional Quantization Method:**

- Independent Rounding:

  - 2.3 → 2
  - -1.7 → -2
  - 0.5 → 1
  - -0.2 → 0

- **Issue**: This method doesn't consider the relationships between parameters or their impact on the model's output, which may lead to performance degradation.

  **AutoRound's Automatic Rounding Optimization:**

- **Global Consideration**: AutoRound calculates the impact of different quantization values for each parameter on the model's output.

- Optimization Decisions:

  - **2.3**: It's a positive number, close to 2 or 3. Through calculation, it's found that quantizing to 3 is more beneficial to model performance, so 3 is chosen.
  - **-1.7**: Although close to -2, quantizing to -1 may result in a smaller overall error, so -1 is chosen.
  - **0.5**: Quantize to 0 or 1; through calculation, the value more beneficial to the model is chosen.
  - **-0.2**: Close to 0, may be directly quantized to 0.

- Final Quantization Results:

  - 2.3 → 3
  - -1.7 → -1
  - 0.5 → 1
  - -0.2 → 0

- **Effect**: Through intelligent decisions, the overall error may be smaller than simple rounding, and the model's performance degradation is less.

