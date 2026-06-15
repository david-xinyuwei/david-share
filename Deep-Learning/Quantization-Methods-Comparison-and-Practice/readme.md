# Auto-round-and-Quantization-Methods-Performance-Comparisons


> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | vLLM |


## Auto-round

*https://github.com/intel/auto-round*

AutoRound is an advanced quantization algorithm for low-bits LLM inference. It's tailored for a wide range of models. Our method adopts sign gradient descent to fine-tune rounding values and minmax values of weights in just 200 steps, which competes impressively against recent methods without introducing any additional inference overhead and keeping low tuning cost. The below image presents an overview of AutoRound. Check out our paper on [arxiv](https://arxiv.org/pdf/2309.05516v4) for more details and visit [low_bit_open_llm_leaderboard](https://huggingface.co/spaces/Intel/low_bit_open_llm_leaderboard) for more accuracy data across various models.


### Sign Gradient Descent (SignSGD)


Imagine this: You are listening to music, and the volume is a bit loud. You want to turn it down a bit, but you're not sure how much is appropriate. So you decide to adjust it a little each time and see the effect.

#### Specific Steps:

1. **Listen to the music:** First, you listen to the current volume (equivalent to calculating the current loss).
2. **Determine the direction:** If the volume is too loud, turn it down a bit; if it's too quiet, turn it up a bit (equivalent to adjusting the parameter based on the sign of the gradient).
3. **Fine-tune the volume:** Adjust the volume a little each time until you find the appropriate level (equivalent to gradually optimizing the parameters).

#### Advantages:

- **Quick adjustment:** Adjusting a little each time allows you to quickly find the appropriate volume.
- **Resource saving:** No need for complex calculations, just determine whether the volume is too high or too low.



## Quantization-Methods-Performance-Comparisons

Overall，AWQ and AutoRound (sym) are the best quantization methods. I perfer AWQ for 4-bits quantization, if you want a lower bit quantization, AutoRound (sym)  is a good choice.

### Memory Consumption

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUuIwhgMJmdKK1CAqId6R6b4urVg6DfncVqCzNsjXbzKzvUIQ1fXjd5hTIRRfOowDicQbCdqXjRnhQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Accuracy

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUuIwhgMJmdKK1CAqId6R6bOIOCKKv0X3Riay3pHlzldjTNHhvffmQjy7xAAkyr4LzjjmnuDbBOzBw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



### Inference Throughput

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUuIwhgMJmdKK1CAqId6R6bo5qK4iapJ4iaTC3MQsqJlHy4bVL6qhEuH2f3gEwlcGiapgwGwH5zzF6rA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Code during test

### symmetric quantization

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
tokenizer = AutoTokenizer.from_pretrained(model_name)

from auto_round import AutoRound

bits, group_size, sym = 4, 128, True
autoround = AutoRound(model, tokenizer, bits=bits, group_size=group_size, batch_size=2, seqlen=512, sym=sym, gradient_accumulate_steps=4, device='cuda')
autoround.quantize()
output_dir = "./AutoRound/GPTQ-sym/"
autoround.save_quantized(output_dir)
```

```
(Quantization-Methods-Performance-Comparisons) root@YOUR-VM:~# ls -al ./AutoRound/GPTQ-sym/
total 5610252
drwx------ 2 root root       4096 Aug 17 06:33 .
drwx------ 4 root root       4096 Aug 17 06:30 ..
-rw------- 1 root root       1470 Aug 17 06:33 config.json
-rw------- 1 root root        184 Aug 17 06:33 generation_config.json
-rw------- 1 root root 5735720400 Aug 17 06:33 model.safetensors
-rw------- 1 root root        485 Aug 17 06:33 quantize_config.json
-rw------- 1 root root        296 Aug 17 06:30 special_tokens_map.json
-rw------- 1 root root    9085657 Aug 17 06:30 tokenizer.json
-rw------- 1 root root      55351 Aug 17 06:30 tokenizer_config.json
```

### GPTQ

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from optimum.gptq import GPTQQuantizer
import torch
model_path = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
w = 4 #quantization to 4-bit. Change to 2, 3, or 8 to quantize with another precision

quant_path = 'Meta-Llama-3.1-8B-Instruct-gptq-'+str(w)+'bit'

# Load model and tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map="auto")
quantizer = GPTQQuantizer(bits=w, dataset="c4", model_seqlen = 2048)
quantized_model = quantizer.quantize_model(model, tokenizer)

quantized_model.save_pretrained(".//GPTQ/"+quant_path, safetensors=True)
tokenizer.save_pretrained("./GPTQ/"+quant_path)
```

```
(Quantization-Methods-Performance-Comparisons) root@YOUR-VM:~# ls -al  ./GPTQ/Meta-Llama-3.1-8B-Instruct-gptq-4bit/
total 5607624
drwx------ 2 root root       4096 Aug 17 06:54 .
drwx------ 3 root root       4096 Aug 17 06:54 ..
-rw------- 1 root root       1168 Aug 17 06:54 config.json
-rw------- 1 root root        184 Aug 17 06:54 generation_config.json
-rw------- 1 root root 4682270360 Aug 17 06:54 model-00001-of-00002.safetensors
-rw------- 1 root root 1050673280 Aug 17 06:54 model-00002-of-00002.safetensors
-rw------- 1 root root      78459 Aug 17 06:54 model.safetensors.index.json
-rw------- 1 root root        296 Aug 17 06:54 special_tokens_map.json
-rw------- 1 root root    9085657 Aug 17 06:54 tokenizer.json
-rw------- 1 root root      55351 Aug 17 06:54 tokenizer_config.json
```

### Bitsandbytes

```
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

if torch.cuda.is_bf16_supported():
  compute_dtype = torch.bfloat16
else:
  compute_dtype = torch.float16

model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
quant_path = 'Meta-Llama-3.1-8B-Instruct-bnb-4bit'
tokenizer = AutoTokenizer.from_pretrained(model_name)
bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config
)


model.save_pretrained("./BnB/"+quant_path, safetensors=True)
tokenizer.save_pretrained("./BnB/"+quant_path)
```

```
(Quantization-Methods-Performance-Comparisons) root@YOUR-VM:~# ls -al ./BnB/Meta-Llama-3.1-8B-Instruct-bnb-4bit
total 5578184
drwx------ 2 root root       4096 Aug 17 07:03 .
drwx------ 3 root root       4096 Aug 17 07:02 ..
-rw------- 1 root root       1395 Aug 17 07:03 config.json
-rw------- 1 root root        184 Aug 17 07:03 generation_config.json
-rw------- 1 root root 4652072847 Aug 17 07:03 model-00001-of-00002.safetensors
-rw------- 1 root root 1050673280 Aug 17 07:03 model-00002-of-00002.safetensors
-rw------- 1 root root     132271 Aug 17 07:03 model.safetensors.index.json
-rw------- 1 root root        296 Aug 17 07:03 special_tokens_map.json
-rw------- 1 root root    9085657 Aug 17 07:03 tokenizer.json
-rw------- 1 root root      55351 Aug 17 07:03 tokenizer_config.json
```

### AWQ

```
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_path = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
quant_path = 'Meta-Llama-3.1-8B-Instruct-awq-4bit'
quant_config = { "zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM" }

# Load model and tokenizer
model = AutoAWQForCausalLM.from_pretrained(model_path, safetensors=True, device_map='cuda')
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)

# Quantize
model.quantize(tokenizer, quant_config=quant_config)

# Save quantized model with safetensors
model.save_quantized("./AWQ/"+quant_path, safetensors=True)
tokenizer.save_pretrained("./AWQ/"+quant_path)

```

```
(Quantization-Methods-Performance-Comparisons) root@YOUR-VM:~# ls -al ./AWQ/Meta-Llama-3.1-8B-Instruct-awq-4bit/
total 5602720
drwx------ 2 root root       4096 Aug 17 07:18 .
drwx------ 3 root root       4096 Aug 17 07:18 ..
-rw------- 1 root root       1182 Aug 17 07:18 config.json
-rw------- 1 root root        184 Aug 17 07:18 generation_config.json
-rw------- 1 root root 4677265296 Aug 17 07:18 model-00001-of-00002.safetensors
-rw------- 1 root root 1050673280 Aug 17 07:18 model-00002-of-00002.safetensors
-rw------- 1 root root      63480 Aug 17 07:18 model.safetensors.index.json
-rw------- 1 root root        296 Aug 17 07:18 special_tokens_map.json
-rw------- 1 root root    9085657 Aug 17 07:18 tokenizer.json
-rw------- 1 root root      55351 Aug 17 07:18 tokenizer_config.json
```

### Test vLLM performance on different  quantization methods

```
!pip install vllm bitsandbytes
!git clone https://github.com/vllm-project/vllm.git
%cd vllm/benchmarks/
```

```
llms = ["meta-llama/Meta-Llama-3.1-8B-Instruct",
        "kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym",
        "kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym",
        "kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit",
        "kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit",
        "ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf"
        ]

for llm in llms:
  print("------------------------------------------------------------")
  print("Inference throughput for "+llm)
  !python benchmark_throughput.py --input-len 100 --output-len 250 --max-model-len 512 --device cuda --model {llm}

print("------------------------------------------------------------")
print("Inference throughput for Meta-Llama-3.1-8B-Instruct-bnb-4bit")
!python benchmark_throughput.py --input-len 100 --output-len 250 --max-model-len 512 --device cuda --model meta-llama/Meta-Llama-3.1-8B-Instruct --enforce_eager -q bitsandbytes --load_format bitsandbytes
```

```
------------------------------------------------------------
Inference throughput for meta-llama/Meta-Llama-3.1-8B-Instruct
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='meta-llama/Meta-Llama-3.1-8B-Instruct', tokenizer='meta-llama/Meta-Llama-3.1-8B-Instruct', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
INFO 08-09 13:55:56 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='meta-llama/Meta-Llama-3.1-8B-Instruct', speculative_config=None, tokenizer='meta-llama/Meta-Llama-3.1-8B-Instruct', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.bfloat16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=None, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=meta-llama/Meta-Llama-3.1-8B-Instruct, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 13:55:57 model_runner.py:720] Starting to load model meta-llama/Meta-Llama-3.1-8B-Instruct...
INFO 08-09 13:55:58 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 4/4 [00:04<00:00,  1.14s/it]
INFO 08-09 13:56:03 model_runner.py:732] Loading model weights took 14.9888 GB
INFO 08-09 13:56:04 gpu_executor.py:102] # GPU blocks: 9930, # CPU blocks: 2048
INFO 08-09 13:56:06 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 13:56:06 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 13:56:20 model_runner.py:1225] Graph capturing finished in 14 secs.
Processed prompts: 100% 1000/1000 [01:14<00:00, 13.42it/s, est. speed input: 1341.95 toks/s, output: 3354.88 toks/s]
Throughput: 13.38 requests/s, 4681.85 tokens/s
------------------------------------------------------------
Inference throughput for kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym', tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
WARNING 08-09 13:57:44 config.py:254] gptq quantization is not fully optimized yet. The speed can be slower than non-quantized models.
INFO 08-09 13:57:44 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym', speculative_config=None, tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=gptq, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 13:57:46 model_runner.py:720] Starting to load model kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-asym...
INFO 08-09 13:57:47 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 2/2 [00:01<00:00,  1.13it/s]
INFO 08-09 13:57:49 model_runner.py:732] Loading model weights took 5.3767 GB
INFO 08-09 13:57:50 gpu_executor.py:102] # GPU blocks: 14774, # CPU blocks: 2048
INFO 08-09 13:57:52 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 13:57:52 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 13:58:07 model_runner.py:1225] Graph capturing finished in 15 secs.
Processed prompts: 100% 1000/1000 [01:30<00:00, 11.09it/s, est. speed input: 1108.60 toks/s, output: 2771.50 toks/s]
Throughput: 11.06 requests/s, 3869.90 tokens/s
------------------------------------------------------------
Inference throughput for kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym', tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
INFO 08-09 13:59:47 gptq_marlin.py:98] The model is convertible to gptq_marlin during runtime. Using gptq_marlin kernel.
INFO 08-09 13:59:47 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym', speculative_config=None, tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=gptq_marlin, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 13:59:48 model_runner.py:720] Starting to load model kaitchup/Meta-Llama-3.1-8B-Instruct-autoround-gptq-4bit-sym...
INFO 08-09 13:59:49 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 2/2 [00:01<00:00,  1.09it/s]
INFO 08-09 13:59:52 model_runner.py:732] Loading model weights took 5.3494 GB
INFO 08-09 13:59:53 gpu_executor.py:102] # GPU blocks: 14858, # CPU blocks: 2048
INFO 08-09 13:59:55 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 13:59:55 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 14:00:09 model_runner.py:1225] Graph capturing finished in 14 secs.
Processed prompts: 100% 1000/1000 [01:16<00:00, 13.10it/s, est. speed input: 1310.09 toks/s, output: 3275.21 toks/s]
Throughput: 13.06 requests/s, 4571.29 tokens/s
------------------------------------------------------------
Inference throughput for kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit', tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
INFO 08-09 14:01:35 gptq_marlin.py:98] The model is convertible to gptq_marlin during runtime. Using gptq_marlin kernel.
INFO 08-09 14:01:35 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit', speculative_config=None, tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=gptq_marlin, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 14:01:37 model_runner.py:720] Starting to load model kaitchup/Meta-Llama-3.1-8B-Instruct-gptq-4bit...
INFO 08-09 14:01:38 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 2/2 [00:01<00:00,  1.12it/s]
INFO 08-09 14:01:40 model_runner.py:732] Loading model weights took 5.3494 GB
INFO 08-09 14:01:41 gpu_executor.py:102] # GPU blocks: 14858, # CPU blocks: 2048
INFO 08-09 14:01:44 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 14:01:44 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 14:01:58 model_runner.py:1225] Graph capturing finished in 14 secs.
Processed prompts: 100% 1000/1000 [01:16<00:00, 13.08it/s, est. speed input: 1308.16 toks/s, output: 3270.41 toks/s]
Throughput: 13.04 requests/s, 4564.59 tokens/s
------------------------------------------------------------
Inference throughput for kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit', tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
INFO 08-09 14:03:24 awq_marlin.py:89] The model is convertible to awq_marlin during runtime. Using awq_marlin kernel.
INFO 08-09 14:03:24 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit', speculative_config=None, tokenizer='kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=awq_marlin, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 14:03:25 model_runner.py:720] Starting to load model kaitchup/Meta-Llama-3.1-8B-Instruct-awq-4bit...
INFO 08-09 14:03:26 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 2/2 [00:01<00:00,  1.12it/s]
INFO 08-09 14:03:29 model_runner.py:732] Loading model weights took 5.3748 GB
INFO 08-09 14:03:30 gpu_executor.py:102] # GPU blocks: 14846, # CPU blocks: 2048
INFO 08-09 14:03:33 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 14:03:33 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 14:03:47 model_runner.py:1225] Graph capturing finished in 14 secs.
Processed prompts: 100% 1000/1000 [01:17<00:00, 12.92it/s, est. speed input: 1292.34 toks/s, output: 3230.86 toks/s]
Throughput: 12.88 requests/s, 4509.58 tokens/s
------------------------------------------------------------
Inference throughput for ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf', tokenizer='ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf', quantization=None, tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=False, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='auto')
WARNING 08-09 14:05:14 config.py:254] aqlm quantization is not fully optimized yet. The speed can be slower than non-quantized models.
INFO 08-09 14:05:14 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf', speculative_config=None, tokenizer='ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.float16, max_seq_len=512, download_dir=None, load_format=LoadFormat.AUTO, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=aqlm, enforce_eager=False, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 14:05:15 model_runner.py:720] Starting to load model ISTA-DASLab/Llama-3.1-8B-Instruct-AQLM-PV-2Bit-1x16-hf...
INFO 08-09 14:05:16 weight_utils.py:225] Using model weights format ['*.safetensors']
INFO 08-09 14:05:17 weight_utils.py:269] No model.safetensors.index.json found in remote.
Loading safetensors checkpoint shards: 100% 1/1 [00:01<00:00,  1.21s/it]
INFO 08-09 14:05:19 model_runner.py:732] Loading model weights took 3.8458 GB
INFO 08-09 14:05:20 gpu_executor.py:102] # GPU blocks: 15570, # CPU blocks: 2048
INFO 08-09 14:05:22 model_runner.py:1024] Capturing the model for CUDA graphs. This may lead to unexpected consequences if the model is not static. To run the model in eager mode, set 'enforce_eager=True' or use '--enforce-eager' in the CLI.
INFO 08-09 14:05:22 model_runner.py:1028] CUDA graphs can take additional 1~3 GiB memory per GPU. If you are running out of memory, consider decreasing `gpu_memory_utilization` or enforcing eager mode. You can also reduce the `max_num_seqs` as needed to decrease memory usage.
INFO 08-09 14:05:39 model_runner.py:1225] Graph capturing finished in 17 secs.
Processed prompts: 100% 1000/1000 [02:13<00:00,  7.52it/s, est. speed input: 751.51 toks/s, output: 1878.78 toks/s]
Throughput: 7.50 requests/s, 2625.73 tokens/s
------------------------------------------------------------
Inference throughput for Meta-Llama-3.1-8B-Instruct-bnb-4bit
Namespace(backend='vllm', dataset=None, input_len=100, output_len=250, model='meta-llama/Meta-Llama-3.1-8B-Instruct', tokenizer='meta-llama/Meta-Llama-3.1-8B-Instruct', quantization='bitsandbytes', tensor_parallel_size=1, n=1, use_beam_search=False, num_prompts=1000, seed=0, hf_max_batch_size=None, trust_remote_code=False, max_model_len=512, dtype='auto', gpu_memory_utilization=0.9, enforce_eager=True, kv_cache_dtype='auto', quantization_param_path=None, device='cuda', enable_prefix_caching=False, enable_chunked_prefill=False, max_num_batched_tokens=None, download_dir=None, output_json=None, distributed_executor_backend=None, load_format='bitsandbytes')
WARNING 08-09 14:08:03 config.py:254] bitsandbytes quantization is not fully optimized yet. The speed can be slower than non-quantized models.
INFO 08-09 14:08:03 llm_engine.py:174] Initializing an LLM engine (v0.5.4) with config: model='meta-llama/Meta-Llama-3.1-8B-Instruct', speculative_config=None, tokenizer='meta-llama/Meta-Llama-3.1-8B-Instruct', skip_tokenizer_init=False, tokenizer_mode=auto, revision=None, rope_scaling=None, rope_theta=None, tokenizer_revision=None, trust_remote_code=False, dtype=torch.bfloat16, max_seq_len=512, download_dir=None, load_format=LoadFormat.BITSANDBYTES, tensor_parallel_size=1, pipeline_parallel_size=1, disable_custom_all_reduce=False, quantization=bitsandbytes, enforce_eager=True, kv_cache_dtype=auto, quantization_param_path=None, device_config=cuda, decoding_config=DecodingConfig(guided_decoding_backend='outlines'), observability_config=ObservabilityConfig(otlp_traces_endpoint=None), seed=0, served_model_name=meta-llama/Meta-Llama-3.1-8B-Instruct, use_v2_block_manager=False, enable_prefix_caching=False)
INFO 08-09 14:08:04 model_runner.py:720] Starting to load model meta-llama/Meta-Llama-3.1-8B-Instruct...
INFO 08-09 14:08:05 loader.py:871] Loading weights with BitsAndBytes quantization.  May take a while ...
INFO 08-09 14:08:06 weight_utils.py:225] Using model weights format ['*.safetensors']
Loading safetensors checkpoint shards: 100% 4/4 [00:04<00:00,  1.23s/it]
INFO 08-09 14:08:12 model_runner.py:732] Loading model weights took 5.3421 GB
INFO 08-09 14:08:13 gpu_executor.py:102] # GPU blocks: 14821, # CPU blocks: 2048
Processed prompts: 100% 1000/1000 [02:05<00:00,  7.94it/s, est. speed input: 794.24 toks/s, output: 1985.59 toks/s]
Throughput: 7.93 requests/s, 2774.51 tokens/s
```



*Refer to: https://kaitchup.substack.com/p/the-best-quantization-methods-to*

---

## AutoRound 量化 70B/72B 大模型实践

This section focuses on quantizing large 70B/72B models with AutoRound on Azure NC40ads_H100_v5 (single H100 GPU, 40 CPU cores, 320GB host memory).

### Quantization Result of Qwen-72B

Load Model:

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model_name = "Qwen/Qwen2.5-72B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
tokenizer = AutoTokenizer.from_pretrained(model_name)
```

CPU Utilization When Loading the Model:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVlTpOQYOKicPNz6pyHpuV8ficpSuGv3tFjOm9ga3nqq2K5A59rhJCGEKjffItFNy7EjSico8AK1ib5Hg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

4-bit Quantization:

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
Quantizing model.layers.61:  76%|███████▋  | 61/80 [1:03:33<20:01, 63.23s/it]
```

```
Quantizing model.layers.79: 100%|██████████| 80/80 [1:23:37<00:00, 63.50s/it]
2024-12-11 09:48:59 INFO autoround.py L340: quantization tuning time 5037.20
2024-12-11 09:48:59 INFO autoround.py L356: Summary: quantized 560/561 in the model,  ['lm_head'] have not been quantized
```

AutoRound can produce models in the same format as GPTQ, supporting TGI, vLLM, etc.

Inference with vLLM:

```
batch_sizes = [1, 2, 4, 8, 16, 32, 64, 128]  
p = """You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe.  
Tell me about gravity."""  
  
sampling_params = SamplingParams(max_tokens=1000)  
  
loading_start = time.time()  
llm = LLM(model="/root/Qwen2.5-72B-Instruct-AutoRound-GPTQ-4bit")  
print("--- Loading time: %s seconds ---" % (time.time() - loading_start))  
  
for b in batch_sizes:  
    prompts = [p] * b  
    generation_time = time.time()  
    outputs = llm.generate(prompts, sampling_params)  
    duration = time.time() - generation_time  
    total_tokens = 0  
    for output in outputs:  
        total_tokens += len(output.prompt_token_ids) + len(output.outputs[0].token_ids)  
    print('\nBatch size: ' + str(b))  
    print("--- Speed: %s tokens/second ---" % (round(total_tokens/duration, 2)))  
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/autoround_72b_inference.png)

GPU consumption during inference:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/autoround_72b_gpu.png)

### Quantization of Llama3-70B

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model_name = "meta-llama/Llama-3.3-70B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(model_name)
```

```
from auto_round import AutoRound
bits, group_size, sym = 4, 128, True
autoround = AutoRound(model, tokenizer, nsamples=128, iters=256, low_gpu_mem_usage=False, gradient_accumulate_steps=1, batch_size=8, bits=bits, group_size=group_size, sym=sym)
autoround.quantize()
output_dir = "Llama-3.3-70B-Instruct-AutoRound-GPTQ-4bit"
autoround.save_quantized(output_dir, format='auto_gptq', inplace=True)
```

### AutoRound 参数详解

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bits` | 4 | Quantize parameters to 4 bits |
| `group_size` | 128 | Every 128 parameters form a group |
| `sym` | True/False | Symmetric vs asymmetric quantization |
| `nsamples` | 128/512 | Number of calibration samples |
| `iters` | 256/512/1000 | Optimization iterations |
| `low_gpu_mem_usage` | True/False | Offload computation to CPU |

**Impact of `group_size`**:
- Small (128): Better accuracy, captures local features, more storage overhead
- Large (1024): Less storage, potentially lower accuracy

**Impact of `sym`**:
- Symmetric (`True`): Simpler computation, works well for symmetrically distributed parameters
- Asymmetric (`False`): Better for asymmetrically distributed parameters, higher accuracy

### AutoRound 自动舍入优化原理

"AutoRound" = "Automatic Rounding" — automatically converting high-precision weights (e.g., 32-bit float) to low-precision representations (e.g., 4-bit, 2-bit) while preserving model performance.

**Traditional Quantization vs. AutoRound:**

| Aspect | Traditional | AutoRound |
|--------|------------|-----------|
| Rounding | Independent per weight | Global optimization |
| Scope | Local optimality per weight | Considers impact on model output |
| Error | Accumulated quantization error | Minimized overall error |
| Strategy | Uniform for all parameters | Adaptive per parameter importance |

**Working Principle:**

1. **Treats Quantization as an Optimization Problem**: Minimizes output difference between quantized and original model
2. **Continuous Relaxation**: Converts discrete quantization into continuous optimization problem
3. **Parameter Importance Analysis**: Evaluates sensitivity of each parameter on model output
4. **Iterative Optimization**: Multiple iterations to gradually approach optimal solution

**Example** — Quantizing parameters `[2.3, -1.7, 0.5, -0.2]` to 2-bit:

| Parameter | Traditional (simple round) | AutoRound (global optimization) |
|-----------|---------------------------|--------------------------------|
| 2.3 | → 2 | → 3 (better for overall model) |
| -1.7 | → -2 | → -1 (smaller overall error) |
| 0.5 | → 1 | → 1 or 0 (optimized choice) |
| -0.2 | → 0 | → 0 |

Through intelligent decisions, AutoRound achieves smaller overall error and less performance degradation.

---

## 校准数据集对模型量化的影响

The calibration dataset is used to help quantization algorithms compute the distribution of weights and activations to determine quantization parameters (scale and zero point).

### 各量化方法对校准数据集的依赖程度

| Method | Calibration Dependency | Recommendation |
|--------|----------------------|----------------|
| **GPTQ** | High — may overfit calibration data | Use task-specific calibration dataset |
| **AWQ** | Low — stable across different calibration sets | Default dataset usually sufficient |
| **AutoRound** | Lowest — highest robustness | Default dataset sufficient; target-language data may help for non-English tasks |
| **bitsandbytes** | None — no calibration needed | No calibration required; uses NormalFloat4 format |

### GPTQ 的校准数据集依赖性

GPTQ requires computing the Hessian matrix using calibration data. If the calibration dataset is too domain-specific, the quantized model's performance in other domains may decline significantly. Therefore, GPTQ should use calibration datasets matching the model's application scenario.

### AWQ 与 AutoRound 的鲁棒性

- **AWQ**: By considering activation sensitivity, it reduces calibration dependency. Results remain stable across different calibration datasets.
- **AutoRound**: Exhibits the highest robustness with minimal performance differences across different calibration datasets.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWic4X8iadAZcHdjIK2rNOfTomoHk2x5aicPXJ21lggiav7nibOTbbicDuNYgV6XXBq3e1zHCBjxKap3k7g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### AutoRound 使用默认校准数据集量化

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/dataset_quant_default_calib.png)

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

Quantization process:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/dataset_quant_process.png)

### AutoRound 使用自定义校准数据集量化

```
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
n = "Qwen2.5-7B"
model_name = "Qwen/"+n
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(model_name)

from auto_round import AutoRound
bits, group_size, sym, dataset = 4, 128, False, "wikipedia-20220301-fr-sample-10k"
autoround = AutoRound(model, tokenizer, nsamples=512, iters=1000, dataset=dataset, bits=bits, group_size=group_size, sym=sym)
autoround.quantize()
output_dir = "./autoround/"
autoround.save_quantized(output_dir+"/"+n+"_wikipedia-20220301-fr_gptq", format='auto_gptq', inplace=True)
```

### AWQ 使用自定义校准数据集量化

```
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

n = "Qwen2.5-7B"
model_path = "Qwen/"+n
quant_path = 'Qwen2.5-7B-wikipedia-20220301-fr-AWQ'
quant_config = { "zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM" }

model = AutoAWQForCausalLM.from_pretrained(model_path, low_cpu_mem_usage=True, use_cache=False, device_map="cuda")
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model.quantize(tokenizer, quant_config=quant_config, calib_data="kaitchup/wikipedia-20220301-fr-sample-10k")
model.save_quantized(quant_path)
tokenizer.save_pretrained(quant_path)
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/dataset_quant_awq.png)

AWQ inference:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Quantization-Methods-Comparison-and-Practice/images/dataset_quant_awq_inference.png)



## Reproducing the Results

### Prerequisites

- Python 3.10+
- CUDA-compatible GPU (recommended)

### Setup

```bash
git clone <this-repo-url>
cd <repo-name>
```
