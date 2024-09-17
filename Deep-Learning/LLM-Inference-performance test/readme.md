# LLM Inference performance test

GuideLLM (*https://github.com/neuralmagic/guidellm*) can test the inference performance of various models under TGI and vLLM. We can test with different hyper parameters on various GPU hardware to identify performance bottlenecks in the environment.

Based on the tool's parameters, I have created a reference table for the performance requirements of different LLM scenarios and their corresponding parameter settings.

| Scenario                  | TTFT Goal | Throughput Goal      | Example Test  Parameter Settings                             |
| ------------------------- | --------- | -------------------- | ------------------------------------------------------------ |
| Chat Application          | <  200 ms | -                    | --rate-type  constant --rate 2.37                            |
| Summary Application       | -         | >  4.06 req/sec      | --rate-type  throughput                                      |
| High Concurrency          | <  200 ms | >  4.06 req/sec      | --rate-type  sweep --rate 10 --rate 20 --rate 30             |
| Low Latency               | <  100 ms | -                    | --rate-type  synchronous                                     |
| Load Testing              | -         | Maximize  Throughput | --rate-type  throughput --max-requests 1000                  |
| Real-time Response        | <  50 ms  | -                    | --rate-type  constant --rate 5                               |
| Data Generation Emulation | -         | -                    | --data-type  emulated --data "prompt_tokens=128,generated_tokens=128" |
| File Data Benchmarking    | -         | -                    | --data-type  file --data "data.txt"                          |
| Variability Testing       | -         | -                    | --rate-type  poisson --rate 10 --rate 20 --rate 30           |

Follow *https://github.com/neuralmagic/guidellm* to prepare env.

## Meta-Llama-3.1-8B-Instruct-quantized.w4a16 with vLLM on A100

Open 2 terminal:

```
vllm serve "neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
```

```
guidellm \
  --target "http://localhost:8000/v1" \
  --model "neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

Results are as following

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2Sd1Vf6AWBwX0BQnXiba5HLezmdVPCfajP6K6UjDV9BMAqS64U4DT9h2Kg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2SdibPkae4mV5wQOzoaziaMLRh9Tb2xqSXZPYDyKf0BFq8wCPIrgUibtIyLQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2Sd6IA80u8ib0TIgtpWhhnXPRe6RzwDe1Az0JC1rIKovKiaMw2FerCBwr7Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2SdsicXq3nqZTagf5uWGW3kVm34BJN5BAWlGqdZgS8AvsmrsPZogz0IGKg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## microsoft/Phi-3.5-mini-instruct with vLLM on A100

Test microsoft/Phi-3.5-mini-instruct on vLLM：

Open 2 terminal:

```
vllm serve "microsoft/Phi-3.5-mini-instruct" &
```

```
guidellm \
  --target "http://localhost:8000/v1" \
  --model "microsoft/Phi-3.5-mini-instruct" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2Sd8QfK9HicibQGWOZPEZ3NBGMJMoribvClaSZSSZibR508AmlA14HbxvznOg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2SdRxQnFhvDIr4kto8GaX5TicKB7SibrEJU0BRiac59KhiafD8Kc4JjbUGlsQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2Sdn9M1w2edyDiareXsa55bPHSa3COgvroH2ehuPEhLJmxOibqldbBTiapAQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVDOHr5U1iaZpHkGUhpHh2SdseM8AWebMF8heysLSkDV9H992D43cU9aHF6tn7UEULfAOWibYoUIhTw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## microsoft/Phi-3.5-mini-instruct with TGI on A100

Open 2 terminal:

```
docker run --gpus 1 -ti --shm-size 1g --ipc=host --rm -p 8080:80 \
  -e MODEL_ID=microsoft/Phi-3.5-mini-instruct \
  -e NUM_SHARD=1 \
  -e MAX_INPUT_TOKENS=4096 \
  -e MAX_TOTAL_TOKENS=6000 \
  -e HF_TOKEN=$(cat ~/.cache/huggingface/token) \
  ghcr.io/huggingface/text-generation-inference:2.2.0
```

```
guidellm \
  --target "http://localhost:8080/v1" \
  --model "microsoft/Phi-3.5-mini-instruct" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTjQ1hAyzPBYtWaxdLJ6oWqM7uOVMmuAaand3wZzQgoAP77QPL5pMeGg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Performance test result:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTCvWno9roBb5VmUnCtwNsiaFrayE9GqJdhIYc9bAybjoBRjUutgF2wog/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTTvBScj6T7sTcB2CIdOZfYibltqDdQ8QsSSwpSYtia5xpQVZAj2xTMXVg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTfpBPeRSAA6QKk7EIFSbKWJSTtS2uMlIDXufjXdRpns0F0I9ZMACP2w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTibicZcNj1CkWlibjwxIAia5Io5osWBeMmLu6Z8uxbDnALTQEJ0q7kaXJ5A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

##  microsoft/Phi-3.5-mini-instruct with vLLM on H100

```
# vllm serve "microsoft/Phi-3.5-mini-instruct"  &
```

```
guidellm \
  --target "http://localhost:8000/v1" \
  --model "microsoft/Phi-3.5-mini-instruct" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

Resource Utilization During Stress Testing:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT9pyT4H3cCWEnIYfibfox7DkDibzbJxHlabkhNFK1UxxibdPXvWEiabt9Ew/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT8H8f5FlpxGAryTBOl7SN28TMib51UEB8OSFDDHoI9E3AicWohEco5kqg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTzbYYx8qYQBNkrFeePDic0XDyfa6mhEwkpj0icSI8NcB5Ueib27MibhfIMg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTwsY5wn2RCan1Qvj90J3c5Y6mNslIz3bL3Gy9d59XypXT7LaicPEoB1w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT23OFZV7NAHUS7ochuyFkstYY1Aeia2L5Q1H5P9QxKrZYm53Kes4JA4A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## microsoft/Phi-3.5-mini-instruct with vLLM on H100(20% Mem usage)

```
# vllm serve "microsoft/Phi-3.5-mini-instruct" --gpu-memory-utilization 0.2 --max-model-len 8192 &
```

```
guidellm \
  --target "http://localhost:8000/v1" \
  --model "microsoft/Phi-3.5-mini-instruct" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

Resource Utilization During Stress Testing:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT32CJojDHePxCrwh6A6wibKqBZUtJfJ1bAKD08zsWXFa04p1DFJ3NMMw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTicxP04eKbGG630aLBrL6AXl0yXMrajwNz7mcRdTwRJLWFATWdNoWfqw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcTqHD6jpUNRf7aQ2LFK9qZEJqQwiaHZv5vTXVwnibTxJiaNX0ZgTD7J93Ow/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT4MfmJib6QPU17T03gABlJnNDQmKOsDZBsnfYiccRWyTWh2z6QgN7PTMQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVgYe83BBuZRVeGk65Y0qcT1eyyDA7r9ItCNc2JhhzDsE6fSkXhrVeic9YTicN87C0xHGRGUNeGwFIA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## microsoft/Phi-3.5-mini-instruct with vLLM on H100(40% Mem usage)

```
vllm serve "microsoft/Phi-3.5-mini-instruct" --gpu-memory-utilization 0.4 --max-model-len 8192 &
```

```
guidellm \
  --target "http://localhost:8000/v1" \
  --model "microsoft/Phi-3.5-mini-instruct" \
  --data-type emulated \
  --data "prompt_tokens=512,generated_tokens=128"
```

Resource Utilization During Stress Testing:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRqa8ZBBDsLVNyfZ3rI0BXESa6IjQtHwMcGcFySHQPUx4KApGceFQPDeDOqIhsDTYJrTumYuibFtg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRqa8ZBBDsLVNyfZ3rI0BXSDNgciaZvSttdJ5a60qRA2ufqrJz48CZmeU2wzZ5OxeArEK7PKb5AIw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRqa8ZBBDsLVNyfZ3rI0BXebU33bLF6FapTLP4Ujc5E5K87qpxOotos2icEtgtP93t8WqhcoxAuUQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRqa8ZBBDsLVNyfZ3rI0BXbPt5fmFyW2MzXBviaALHU07IKZPhpHcvnt9pZSmu5jYAWCqqA5WRcIw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRqa8ZBBDsLVNyfZ3rI0BXSCvcwwFUSMdgziabqftdRse9AGOw8C3tWyic1dtEznc53uVdqRSiaTxEw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

It can be seen that vLLM  consumes lots of video memory and relies heavily on it. 
