# KV-Cache-Quantization
The memory required for inference mainly consists of three parts: loading the model, activations, and KV-cache.

Under normal circumstances, the memory occupation of activations during inference is not very large due to their sequential layer-by-layer transmission.

As for the KV-cache, its size will rapidly increase as the context seq lengthens and batch size . This is particularly prominent for systems that handle long contexts, such as RAG systems.

Reference Link: https://kaitchup.substack.com/p/kv-cache-quantization-for-memory
##  Models support
The models that support KV cache are for now as following:

- Llama (probably also Mistral but I'm not sure)

- Gemma

- RecurrentGemma

- StableLM

- DBRX

- LLM using the Cohere architecture

- OLMo

##  Test results
Hugging Face Transformers supports KV cache quantisation： pip install git+https://github.com/huggingface/transformers

It supports both HQQ quantisation and Quanto. HQQ is more accurate than Quanto, but not as efficient, and Hugging Face reports that HQQ is also much slower than Quanto.

I conducted some validation, and when inferring based on a single prompt with only a few output tokens, quantizing the KV-cache does not save much memory. However, when there are many prompts being outputted at the same time (200 prompts), the quantization of the KV-cache at that point does save a significant amount of memory. Of course, the KV-cache will to some extent reduce the speed of inference.

Let me show test result：

![image](https://github.com/davidsajare/KV-Cache-Quantization/blob/main/images/5.png)

### KV-cache quantisation with HQQ
Before tokenization and model generation:

Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After tokenization:

Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After model generation:

Allocated GPU memory: 5.32 GB
Reserved GPU memory: 29.34 GB

![image](https://github.com/davidsajare/KV-Cache-Quantization/blob/main/images/1.HQQ%20.png)
### KV-cache quantisation with quanto

Before tokenization and model generation:

Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After tokenization:

Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After model generation:

Allocated GPU memory: 5.32 GB
Reserved GPU memory: 18.94 GB
![image](https://github.com/davidsajare/KV-Cache-Quantization/blob/main/images/2%20Quanto.png)

### No KV-cache quantisation
Before tokenization and model generation:
Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After tokenization:

Allocated GPU memory: 5.31 GB
Reserved GPU memory: 5.40 GB

After model generation:

Allocated GPU memory: 5.32 GB
Reserved GPU memory: 55.99 GB
![image](https://github.com/davidsajare/KV-Cache-Quantization/blob/main/images/3%20None.png)

