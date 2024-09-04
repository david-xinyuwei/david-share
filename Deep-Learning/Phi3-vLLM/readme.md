# Phi3 on vLLM

The code supporting Phi3 in vLLM has now been merged into the main branch:
https://github.com/vllm-project/vllm
Phi-3 (microsoft/Phi-3-mini-4k-instruct, microsoft/Phi-3-mini-128k-instruct, etc.)

## Phi3 on vLLM

Since Phi-3 is still relatively new, installing vLLM via conda using `pip install vllm` does not work yet (running the code will result in an error saying vLLM cannot be found). You need to build from source.
https://docs.vllm.ai/en/latest/getting_started/installation.html

```
$git clonehttps://github.com/vllm-project/vllm.git
$ cd vllm
$ # export VLLM_INSTALL_PUNICA_KERNELS=1 # optionally build for multi-LoRA capability
$ pipinstall-e.# This may take 5-10 minutes.
```

Next we compare the speed of HF transformer and vLLM against Phi-3 inference.

HF：4.5s

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXcZyEZQcBx03pDlfGtJTYzLBUQVMk74vYZF0ayBppzdZadJ6ARrQ0UMka0Ld5eicWwwicIdUTHjwvA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

vLLM：0.7s

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXcZyEZQcBx03pDlfGtJTYzXZnKeJKXFy1PMD5CNzJbfRcsDVnUhS3N8EfGXllPNmXFV0TcmzbHcg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

As expected, vLLM is still significantly faster.

It should be noted that when loading models with vLLM (flash_attention_2), it will reserve enough KV cache; otherwise, it will throw an error:

```
ValueError: The model's max seq len (131072) is larger than the maximum number of tokens that can be stored in KV cache (24400). Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine.  
```

Setting Lazy Load and `gpu_memory_utilization` is ineffective.

Therefore, if you want to save GPU memory, you should either use Phi-3 4K or set `max_sequence_length` when loading Phi-3 128K. Otherwise, the KV cache will occupy a large amount of GPU memory during model loading, negating the benefits of a smaller model.

Additionally, during testing, it was found that the inference speed of GGUF is already comparable to vLLM. Therefore, for edge inference, GGUF is a more practical approach. You can use the Phi-3 Mini GGUF q4 model published on HF without needing to use vLLM or further quantization.

## Test code

HF code:

```

import torch  
from transformers import AutoModelForCausalLM, AutoTokenizer  
import time  

# 设置随机种子以确保结果的可重复性  
torch.random.manual_seed(0)  

# 开始计时  
start_time = time.time()  

# 加载模型  
model = AutoModelForCausalLM.from_pretrained(  
    "microsoft/Phi-3-mini-128k-instruct",  
    device_map="cuda",  
    torch_dtype="auto",  
    trust_remote_code=True,  
)  

# 加载分词器  
tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-128k-instruct")  

# 结束计时  
loading_time = time.time() - start_time  
print(f"Model and tokenizer loading time: {loading_time} seconds")
```

```

from transformers import pipeline  

# 创建文本生成管道  
pipe = pipeline(  
    "text-generation",  
    model=model,  
    tokenizer=tokenizer,  
)  

# 定义输入提示  
prompts = [  
    "1+2+3+4+...+99+100=?",  
#    "The capital of France is",  
#    "The future of AI is",  
#    "The best movie of all time is",
]  

# 推理参数  
generation_args = {  
    "max_new_tokens": 500,  
    "return_full_text": False,  
    "temperature": 0.0,  
    "do_sample": False,  
}  

# 执行推理并计时  
total_length = 0  
total_duration = 0.0  
for prompt in prompts:  
    start_time = time.time()  
    output = pipe(  
        [{"role": "system", "content": "You are a helpful assistant. Please generate a response."},  
         {"role": "user", "content": prompt}],  
        **generation_args  
    )  
    duration = time.time() - start_time  
    total_duration += duration  
    generated_text = output[0]['generated_text']  
    total_length += len(tokenizer.tokenize(generated_text))  
    tok_sec_prompt = round(len(tokenizer.tokenize(generated_text)) / duration, 3)  
    print(f"Prompt --- {tok_sec_prompt} tokens/seconds ---")  
    print(generated_text)  

# 计算平均速度  
tok_sec = round(total_length / total_duration, 3)  
print(f"Average --- {tok_sec} tokens/seconds ---")
```

vLLM code:

```

!export VLLM_USE_MODELSCOPE=True
!export TOKENIZERS_PARALLELISM=False
!export CUDA_MODULE_LOADING=LAZY
from vllm import LLM, SamplingParams
prompts = [  
   #"1+2+3+4+...+99+100=?",  
    "Who is the current president of United States?",
    "Hello, my name is",  
    "The capital of France is",  
    "The future of AI is",  
]  


sampling_params = SamplingParams(temperature=1, top_p=0.95, max_tokens=2000,)  
#llm = LLM(model="microsoft/Phi-3-mini-4k-instruct",trust_remote_code=True,gpu_memory_utilization=0.3,max_sequence_length=8192)
outputs = llm.generate(prompts, sampling_params)


# Print the outputs.
for output in outputs:
    prompt = output.prompt
    generated_text = output.outputs[0].text
    print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")
```

