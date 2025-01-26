# Estimating Memory Need in AI model Inference

The formula for total memory during inference is as follows:

Total Memory = Model Parameter Memory + Activation Memory + KV Cache Memory + Buffer Memory

If you are interested in the specific calculations, you can refer to previous articles on our WeChat official account, such as the link below. However, here I would recommend using tools for a rough evaluation. 

*https://mp.weixin.qq.com/s/UBtT1dsoE1FSPINVtMBv_Q?token=1958363107&lang=zh_CN*



***Please click below pictures to see my demo video on Yutube***:
[![Estimating-memory-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://www.youtube.com/watch?v=el7edql4Xug)

## How to use the tool

On Linux:

Install need package:

```
#pip install transformers
#pip install torch
```

Run  estimatememory.pyc in https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Estimate-Inference-Memory

```
(EstimatingMemoryInference) root@davidgpt:~# python  estimatememory.pyc 

######################################################################
#                                                                    #
#              Model Memory Consumption Calculator V1.0              #
#         https://github.com/xinyuwei-david/david-share.git          #
#                                                                    #
######################################################################

Note: Ensure that your environment has internet access to Hugging Face and that you have set your Hugging Face API token.

Enter the model name from Hugging Face: microsoft/phi-4

Loading model configuration...

--- Model Parameters ---
Model Name: microsoft/phi-4
Number of Hidden Layers (L): 40
Hidden Size (h): 5120
Number of Attention Heads (a): 40
Number of Key-Value Heads (g): 10
The model uses Grouped Query Attention (GQA).

--- Adjustable Parameters ---
Number of parameters in the model (n) (in billions) (**Please enter this manually**): 14.7
Bitwidth of the model's parameters (p) (in bits) [Default 16]: 
Sequence length (s) (**Please enter this manually**): 16384
Batch size (b) (**Please enter this manually**) [Default 1]: 1
Use FlashAttention? [Y/n] (Default Y): Y
Use KV Cache? [Y/n] (Default Y): Y

--- Memory Consumption Results ---
Memory consumption of the model: 29.4 GB
Memory consumption of vanilla inference: 91.27 GB
Memory consumption of inference with GQA: 26.26 GB
Memory consumption of inference with FlashAttention: 5.39 GB
Memory consumption of the KV cache (with GQA): 1.34 GB

Total Memory consumption (given the selected configuration): 36.13 GB
```

