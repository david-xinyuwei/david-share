## OpenAI OSS Model on Azure 

https://openai.com/index/introducing-gpt-oss/  

The gpt-oss-120b model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The gpt-oss-20b model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

In this repo, I will show 2 models performance on Azure NC A10/H100 GPU VM, including TTFT, tokens/s etc.

## Azure A10 GPU VM

In GPT-OSS's inference logic, a sink token has been introduced. The sink token requires FlashAttention-3 for efficient execution  (FlashAttention-2 does not have the corresponding kernel), but FA3 is  better supported on Hopper, while there are issues on Ampere. Therefore, if you are using an A10, you can use the Ollama method or transformers. Ollama is the simplest. The Ollama version uses MXFP4 quantization. If  you don't do quantization and directly use HF transformers with BF16  inference, the A10's memory is insufficient.



In this part of test, I only use one A10 GPU on ollama. Before load model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/1.png)

### **Ollama**

```
ollama run gpt-oss:20b
```

After I load the 20B model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/2.png)

**During inference:**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/3.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/SuMhR0UZyOM)

The approximate performance during inference with Ollama is:

```
 TTFT < 1s
 Throughput: 45~55 tokens/s
```



## Azure H100 GPU VM

