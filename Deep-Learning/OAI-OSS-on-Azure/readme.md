## OpenAI OSS Model on Azure 

https://openai.com/index/introducing-gpt-oss/  

The gpt-oss-120b model achieves near-parity with OpenAI o4-mini on core reasoning benchmarks, while running efficiently on **a single 80 GB GPU**. 

The gpt-oss-20b model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just **16 GB of memory**, making it ideal for on-device use cases, local inference, or rapid iteration without costly infrastructure. Both models also perform strongly on tool use, few-shot function calling, CoT reasoning (as seen in results on the Tau-Bench agentic evaluation suite) and HealthBench (even outperforming proprietary models like OpenAI o1 and GPT‑4o).

In this repo, I will show 2 models performance on Azure NC A10/H100 GPU VM, including TTFT, tokens/s etc.

## Azure A10 GPU VM

In this part of test, I only use one A10 GPU. Before load model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/1.png)

### **Ollama**

```
ollama run gpt-oss:20b
```

After I load the 20B model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/2.png)



During inference:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/3.png)



***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/SuMhR0UZyOM)





**vLLM**

The  model requires quantization for efficient inference, specifically using the new MXFP4 quantization format. To run this model  successfully, it is necessary to use a version of vLLM that supports  MXFP4 quantization. The official vLLM 0.4.x branch (corresponding to  vLLM 0.10.0) does not recognize the "mxfp4" quantization method and will throw a validation error during configuration. Therefore, you need to  install the Astral branch of vLLM (version 0.10.1+gptoss or higher),  which adds support for MXFP4. 

```
pip install --pre "vllm==0.10.1+gptoss" \
  --extra-index-url https://wheels.vllm.ai/gpt-oss/ \
  --extra-index-url https://download.pytorch.org/whl/nightly/cu118
```

```
vllm serve openai/gpt-oss-20b --gpu-memory-utilization 0.6
```

After I load the 20B model:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/OAI-OSS-on-Azure/images/2.png)

