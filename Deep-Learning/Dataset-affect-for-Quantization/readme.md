# The Impact of Calibration Datasets on Model Quantization

In recent years, the rapid development of Large Language Models (LLMs) has brought significant breakthroughs to the field of Natural Language Processing. However, these models typically require substantial computational resources and storage space, especially during the inference phase. This makes running high-performance LLMs a major challenge in resource-constrained environments, such as consumer-grade GPUs.  Quantization techniques, as an effective model compression method, can significantly reduce a model's storage and computational demands. By converting a model's weights and activations from high precision (e.g., 32-bit floating point) to low precision (e.g., 4-bit or 8-bit integers), we can reduce the model size while accelerating the inference process. For example, 4-bit quantization can reduce the model size by about two-thirds. 


**I. Overview of Quantization Methods**

Currently, commonly used quantization methods mainly include:

- **Post-Training Quantization (PTQ)**: Quantization is performed after the model training is completed, without the need to retrain the model.

- **Quantization-Aware Training (QAT)**: Simulates quantization operations during model training, allowing the model to adapt to the errors introduced by quantization.

  **1.1 Common Post-Training Quantization Methods**

- **GPTQ (Globally-Optimized Quantization for Transformers)**: A globally optimized quantization method for Transformer models that uses approximate second-order optimization to reduce quantization errors. GPTQ is highly dependent on the calibration dataset and may overfit the calibration data.

- **AWQ (Activation-aware Weight Quantization)**: A quantization method that considers the impact of activations on weight quantization. AWQ has less dependency on the calibration dataset, and results remain relatively stable across different calibration datasets.

- **AutoRound**: An automatic rounding quantization method proposed by Intel based on SignSGD optimization. AutoRound has even lower dependency on the calibration dataset, exhibiting higher robustness.

- **bitsandbytes (bnb) library**: Provides quantization methods that do not require calibration data. bnb maintains high accuracy even without calibration data because it uses a superior data format (NormalFloat4) compared to other methods.

  **1.2 Common Quantization-Aware Training Methods**

- **Standard Quantization-Aware Training (Standard QAT)**: Simulates quantization during training, allowing the model to gradually adapt to quantization errors. Requires the full training dataset.

- **LSQ (Learned Step Size Quantization)**: Sets the quantization step size as a learnable parameter, optimized through backpropagation.

- **DoReFa-Net**: A training method that quantizes weights, activations, and gradients to low bit widths.

------


**II. The Importance of Calibration Datasets**

In the quantization process, the calibration dataset is used to help the quantization algorithm statistically compute the distribution of weights and activations to determine quantization parameters (such as scale and zero point). Depending on the quantization method, the dependency on the calibration dataset varies.

**2.1 GPTQ's Dependency on Calibration Datasets**

GPTQ requires computing the Hessian matrix using the calibration dataset during quantization to guide the quantization of weights. However, GPTQ may overfit the calibration dataset. If the calibration dataset is too specific to a certain domain, the quantized model's performance in other domains may significantly decline. Therefore, GPTQ is not recommended to use general calibration datasets but should instead use calibration datasets that match the model's application scenario and target tasks. If you calibrate a GPTQ model based on data too specific to a particular domain, the quantized model will perform significantly worse in other domains.

**2.2 Robustness of AWQ and AutoRound**

In contrast to GPTQ, AWQ and AutoRound have less dependency on the calibration dataset.

- **AWQ**: By considering the sensitivity of activations, it reduces dependency on the calibration dataset. Experiments show that AWQ's results remain relatively stable across different calibration datasets, achieving good performance even without carefully selecting the calibration dataset.
- **AutoRound**: Exhibits higher robustness, with minimal performance differences across different calibration datasets. In non-English tasks, using a calibration dataset in the target language may bring slight performance improvements.

------


**III. Selection of Calibration Datasets**

**3.1 Default Calibration Datasets**

Quantization tools often use default calibration datasets if the user does not specify a particular dataset. For example:

- **NeelNanda/pile-10k**: A dataset containing 10,000 English text passages, extracted from the large and diverse text dataset "The Pile." Many quantization tools (such as AutoRound, AWQ) use this dataset by default.

  **3.2 Do You Need to Change the Default Calibration Dataset?**

  For **GPTQ**:

- It is recommended to use a calibration dataset that matches the model's application scenario and target tasks, rather than using a general default dataset.

- **Reason**: GPTQ is highly dependent on the calibration dataset. Using a general dataset may lead to a decline in the model's performance in actual applications.

  For **AWQ and AutoRound**:

- Using the default calibration dataset is usually sufficient, and there's no need for special selection.

- **Reason**: These methods have less dependency on the calibration dataset. Experiments show that even when using general datasets, performance remains stable.

  **3.3 Format and Content of Calibration Datasets**

  When selecting a calibration dataset, ensure that the dataset's format and preprocessing methods are consistent with the model's training data. This consistency in data processing flows avoids performance issues caused by format differences. Additionally, the content of the calibration dataset should match the model's application scenario to ensure that the quantized model performs well in actual use.

------


**IV. Summary**

The image below contains two charts that compare the performance of GPTQ and other methods on different calibration datasets.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWic4X8iadAZcHdjIK2rNOfTomoHk2x5aicPXJ21lggiav7nibOTbbicDuNYgV6XXBq3e1zHCBjxKap3k7g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**(a) Left Chart:**

- The horizontal axis represents the number of calibration sequences (each sequence contains 2048 tokens).

- The vertical axis represents Perplexity.

- The chart shows the trend of Perplexity changes with the number of calibration sequences for GPTQ (green) and another method (orange). It can be seen that GPTQ's Perplexity decreases as the number of calibration sequences increases but requires more calibration sequences than the other method to achieve lower Perplexity. The other method can achieve low Perplexity with a very small calibration set.

  **(b) Right Table:**

- The table compares Perplexity on different calibration sets (Calib) and evaluation sets (Eval).

- GPTQ and another method are compared on two datasets: PubMed and Enron.

- The table shows that GPTQ's Perplexity changes significantly when the calibration set and evaluation set are different (e.g., using the Enron calibration set to evaluate PubMed), while the other method shows minimal changes in Perplexity when the calibration set and evaluation set differ. This indicates that the other method is more robust to calibration set distribution.

  **Summary:**

- **(a)** The other method requires a smaller calibration set to achieve lower Perplexity.

- **(b)** The other method is more robust to calibration set distribution.

------


**For GPTQ**

- Choose a calibration dataset that matches the model's application scenario to ensure that the quantized model performs well on the target tasks.

- Avoid using general default calibration datasets to prevent performance degradation.

- Ensure that the format of the calibration dataset is consistent with the training data, including data preprocessing steps, to guarantee data consistency.

  **For AWQ and AutoRound**

- Using the default calibration dataset is usually sufficient, and there's no need for special adjustments.

- When dealing with non-English tasks, if conditions allow, using a calibration dataset in the target language may bring slight performance improvements.

## AutoRound Quantization code

### Via default calibration dataset(NeelNanda/pile-10k)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Dataset-affect-for-Quantization/images/2.png)

 ```
 from transformers import AutoModelForCausalLM, AutoTokenizer
 import torch
 n = "Qwen2.5-7B-Instruct"
 model_name = "Qwen/"+n
 model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
 tokenizer = AutoTokenizer.from_pretrained(model_name)
 
 from auto_round import AutoRound
 
 bits, group_size, sym = 4, 128, False
 
 autoround = AutoRound(model, tokenizer, nsamples=512, iters=1000, low_gpu_mem_usage=True, bits=bits, group_size=group_size, sym=sym)
 
 autoround.quantize()
 output_dir = "./autoround/"
 autoround.save_quantized(output_dir+"/"+n+"_gptq", format='auto_gptq', inplace=True)
 ```

**Setting Quantization Parameters:**

- `bits = 4`: Specifies quantizing the model to a 4-bit representation.
- `group_size = 128`: Sets the group size to 128, used for group convolution or group quantization. This can better balance the model's performance and compression rate during quantization.
- `sym = False`: Specifies whether to use symmetric quantization. `False` indicates using asymmetric quantization.



1. `bits = 4`：

   - **意思**：将模型的权重值量化为 4 位表示。
   - **作用**：模型中的每个权重原本可能是 32 位或 16 位浮点数。通过将其转换为 4 位的数值表示，模型的大小会大幅减小，占用的存储空间和计算资源也会减少。
   - **影响**：模型变小、速度更快，但可能会有一定的精度损失。

2. `group_size = 128`：

   - **意思**：在量化时，将模型的权重分成大小为 128 的组进行处理。
   - **作用**：对每一组权重单独计算量化参数（例如，缩放因子和零点），这样可以更细粒度地量化模型，减少量化带来的误差。
   - **影响**：较小的组大小可以提高量化后的模型精度，但可能会增加一些计算开销。在组大小和模型性能之间取得平衡。

3. `sym = False`：

   - **意思**：选择使用**非对称量化**方式。

   - 作用：

     - **对称量化（`sym = True`）**：假设数据分布是对称的，量化范围在正负某个数值之间（例如 -A 到 +A）。
     - **非对称量化（`sym = False`）**：不假设数据是对称分布的，量化范围可以偏移（例如，从 0 到 A），更好地适应实际数据的分布。

   - **影响**：非对称量化通常可以更准确地表示实际数据，减少量化误差，提高模型的精度。

     **总结**：

- **`bits`**：决定了量化后的数值精度，值越小，模型越小，但精度可能降低。
- **`group_size`**：控制量化时权重分组的大小，影响模型压缩率和精度之间的平衡。
- **`sym`**：选择量化方式，对模型在量化后的精度有影响。

Quantization process:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Dataset-affect-for-Quantization/images/1.png)

```
2024-11-10 09:07:44 INFO utils.py L499: Using GPU device
2024-11-10 09:07:44 INFO autoround.py L219: using torch.bfloat16 for quantization tuning
2024-11-10 09:07:47,348 INFO utils.py L148: Note: NumExpr detected 24 cores but "NUMEXPR_MAX_THREADS" not set, so enforcing safe limit of 16.
2024-11-10 09:07:47,349 INFO utils.py L161: NumExpr defaulting to 16 threads.
2024-11-10 09:07:47,459 INFO config.py L54: PyTorch version 2.5.1 available.
/root/miniconda3/envs/Quantization-Methods-Performance-Comparisons/lib/python3.10/site-packages/transformers/models/qwen2/modeling_qwen2.py:163: UserWarning: Deterministic behavior was enabled with either `torch.use_deterministic_algorithms(True)` or `at::Context::setDeterministicAlgorithms(true)`, but this operation is not deterministic because it uses CuBLAS and you have CUDA >= 10.2. To enable deterministic behavior in this case, you must set an environment variable before running your PyTorch application: CUBLAS_WORKSPACE_CONFIG=:4096:8 or CUBLAS_WORKSPACE_CONFIG=:16:8. For more information, go to https://docs.nvidia.com/cuda/cublas/index.html#results-reproducibility (Triggered internally at ../aten/src/ATen/Context.cpp:208.)
  freqs = (inv_freq_expanded.float() @ position_ids_expanded.float()).transpose(1, 2)
Quantizing model.layers.0:   0%|                                                                                                                                                           | 0/28 [00:00<?, ?it/s]/root/miniconda3/envs/Quantization-Methods-Performance-Comparisons/lib/python3.10/site-packages/torch/nn/modules/linear.py:125: UserWarning: Deterministic behavior was enabled with either `torch.use_deterministic_algorithms(True)` or `at::Context::setDeterministicAlgorithms(true)`, but this operation is not deterministic because it uses CuBLAS and you have CUDA >= 10.2. To enable deterministic behavior in this case, you must set an environment variable before running your PyTorch application: CUBLAS_WORKSPACE_CONFIG=:4096:8 or CUBLAS_WORKSPACE_CONFIG=:16:8. For more information, go to https://docs.nvidia.com/cuda/cublas/index.html#results-reproducibility (Triggered internally at ../aten/src/ATen/Context.cpp:208.)
  return F.linear(input, self.weight, self.bias)
/root/miniconda3/envs/Quantization-Methods-Performance-Comparisons/lib/python3.10/site-packages/auto_round/quantizer.py:383: UserWarning: Deterministic behavior was enabled with either `torch.use_deterministic_algorithms(True)` or `at::Context::setDeterministicAlgorithms(true)`, but this operation is not deterministic because it uses CuBLAS and you have CUDA >= 10.2. To enable deterministic behavior in this case, you must set an environment variable before running your PyTorch application: CUBLAS_WORKSPACE_CONFIG=:4096:8 or CUBLAS_WORKSPACE_CONFIG=:16:8. For more information, go to https://docs.nvidia.com/cuda/cublas/index.html#results-reproducibility (Triggered internally at ../aten/src/ATen/Context.cpp:208.)
  return F.linear(x, weight_q, bias)
/root/miniconda3/envs/Quantization-Methods-Performance-Comparisons/lib/python3.10/site-packages/torch/autograd/graph.py:825: UserWarning: Deterministic behavior was enabled with either `torch.use_deterministic_algorithms(True)` or `at::Context::setDeterministicAlgorithms(true)`, but this operation is not deterministic because it uses CuBLAS and you have CUDA >= 10.2. To enable deterministic behavior in this case, you must set an environment variable before running your PyTorch application: CUBLAS_WORKSPACE_CONFIG=:4096:8 or CUBLAS_WORKSPACE_CONFIG=:16:8. For more information, go to https://docs.nvidia.com/cuda/cublas/index.html#results-reproducibility (Triggered internally at ../aten/src/ATen/Context.cpp:208.)
  return Variable._execution_engine.run_backward(  # Calls into the C++ engine to run the backward pass
/root/miniconda3/envs/Quantization-Methods-Performance-Comparisons/lib/python3.10/site-packages/torch/autograd/graph.py:825: UserWarning: Flash Attention defaults to a non-deterministic algorithm. To explicitly enable determinism call torch.use_deterministic_algorithms(True, warn_only=False). (Triggered internally at ../aten/src/ATen/native/transformers/cuda/attention_backward.cu:102.)
  return Variable._execution_engine.run_backward(  # Calls into the C++ engine to run the backward pass
Quantizing model.layers.15:  54%|█████████████████████████████████████████████████████████████████████████████▏  
```

### Via customer dataset

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
n = "Qwen2.5-7B"
model_name = "Qwen/"+n
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(model_name)

from auto_round import AutoRound

bits, group_size, sym, dataset = 4, 128, False, "wikipedia-20220301-fr-sample-10k"

autoround = AutoRound(model, tokenizer, nsamples=512, iters=1000,  dataset= dataset, bits=bits, group_size=group_size, sym=sym)

autoround.quantize()
output_dir = "./autoround/"
autoround.save_quantized(output_dir+"/"+n+"_wikipedia-20220301-fr_gptq", format='auto_gptq', inplace=True)
```

## AWQ Quantization code

```
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

n = "Qwen2.5-7B"
model_path = "Qwen/"+n
quant_path = 'Qwen2.5-7B-wikipedia-20220301-fr-AWQ'
quant_config = { "zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM",  }

# Load model
model = AutoAWQForCausalLM.from_pretrained(
    model_path, low_cpu_mem_usage=True, use_cache=False, device_map="cuda"
)
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

# Quantize
model.quantize(tokenizer, quant_config=quant_config, calib_data = "kaitchup/wikipedia-20220301-fr-sample-10k")

# Save quantized model
model.save_quantized(quant_path)
tokenizer.save_pretrained(quant_path)

print(f'Model is quantized and saved at "{quant_path}"')
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Dataset-affect-for-Quantization/images/5.png)

Inference code:

```
import os    
from transformers import AutoTokenizer    
from vllm import LLM, SamplingParams    
  
# 设置模型和 tokenizer 的路径    
model_path = "/root/Qwen2.5-7B-wikipedia-20220301-fr-AWQ"    
  
# 准备输入提示    
prompt = "你好，能为我介绍一下人工智能的发展历史吗？"    
  
# 创建多个提示，以实现并发执行    
num_prompts = 500  # 您可以根据需要调整并发的数量  
prompts = [prompt] * num_prompts  # 重复相同的提示  
  
# 设置采样参数    
sampling_params = SamplingParams(    
    max_tokens=20480,  # 生成的最大 token 数    
    temperature=0.7,  # 温度    
    top_p=0.95,       # nucleus 采样    
)    
  
# 创建 LLM 对象，加载本地模型    
llm = LLM(    
    model=model_path,    
    quantization="awq",  # 指定使用 AWQ 量化模型    
)    
  
# 执行推理，传入多个提示，实现并发生成    
outputs = llm.generate(prompts, sampling_params)    
  
# 处理并打印生成的文本    
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)    
  
total_tokens = 0  # 用于统计总的输出 token 数量  
  
for idx, output in enumerate(outputs):    
    generated_text = output.outputs[0].text    
  
    print(f"生成的文本（提示 {idx + 1}）：")    
    print(generated_text)    
  
    # 计算输出的 token 数量    
    output_tokens = tokenizer.encode(generated_text)    
    num_output_tokens = len(output_tokens)    
  
    print(f"\n输出的 token 数量：{num_output_tokens}\n")    
  
    total_tokens += num_output_tokens    
  
print(f"总输出的 token 数量：{total_tokens}")    
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Dataset-affect-for-Quantization/images/4.png)

