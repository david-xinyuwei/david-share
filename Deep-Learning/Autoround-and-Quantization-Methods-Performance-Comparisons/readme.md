# Auto-round-and-Quantization-Methods-Performance-Comparisons

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
(Quantization-Methods-Performance-Comparisons) root@david1a100:~# ls -al ./AutoRound/GPTQ-sym/
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
(Quantization-Methods-Performance-Comparisons) root@david1a100:~# ls -al  ./GPTQ/Meta-Llama-3.1-8B-Instruct-gptq-4bit/
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
(Quantization-Methods-Performance-Comparisons) root@david1a100:~# ls -al ./BnB/Meta-Llama-3.1-8B-Instruct-bnb-4bit
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
(Quantization-Methods-Performance-Comparisons) root@david1a100:~# ls -al ./AWQ/Meta-Llama-3.1-8B-Instruct-awq-4bit/
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
