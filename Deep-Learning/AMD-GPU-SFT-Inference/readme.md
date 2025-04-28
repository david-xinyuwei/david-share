# Azure AMD GPU VM相关测试



## Deepseek 671B on Azure

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X



### AMD性能测试报告

https://github.com/ROCm/MAD/tree/develop/benchmark



###  Qianwen 2.5 VL

https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/models/qwen2_5_vl.py



rocm/vllm-dev

### Megatron-LM框架训练qwen2-vl

如果使用Megatron-LM框架训练qwen2-vl的话，如果有nv的代码，只需要替换这个部分的load function：https://github.com/NVIDIA/Megatron-LM/blob/4429e8ebe21fb011529d7401c370841ce530785a/megatron/legacy/fused_kernels/__init__.py#L17 到amd的版本：https://github.com/ROCm/Megatron-LM/blob/rocm_dev/megatron/legacy/fused_kernels/__init__.py#L18 就可以了





### Llama 4 on AMD

[https://rocm.blogs.amd.com/artificial-intelligence/llama4-day-0-support/README.html#how-to-run-llama4-on-line-inference-mode-with-vllm-on-amd-instinct-gpus](https://nam06.safelinks.protection.outlook.com/?url=https%3A%2F%2Frocm.blogs.amd.com%2Fartificial-intelligence%2Fllama4-day-0-support%2FREADME.html%23how-to-run-llama4-on-line-inference-mode-with-vllm-on-amd-instinct-gpus&data=05|02|xinyuwei@microsoft.com|fdee5bf483fa48c4a98a08dd8379530d|72f988bf86f141af91ab2d7cd011db47|1|0|638811279380317136|Unknown|TWFpbGZsb3d8eyJFbXB0eU1hcGkiOnRydWUsIlYiOiIwLjAuMDAwMCIsIlAiOiJXaW4zMiIsIkFOIjoiTWFpbCIsIldUIjoyfQ%3D%3D|0|||&sdata=ZatRWnNRXgUPy1e5ehNgLC1x5ST0DAd%2FjQrTFpxuLig%3D&reserved=0)



Make sure you pull the latest image recommended there (currently rocm/vllm-dev:llama4-20250407).

Enabling V1 can also improve performance at this point. That is: VLLM_USE_V1=1





## vLLM Setup for Benchmarking Large Language Models on an NVads V710 v5-series Instance

```
#pip install num2words
```



https://github.com/dasilvajm/V710-VLLM-inference