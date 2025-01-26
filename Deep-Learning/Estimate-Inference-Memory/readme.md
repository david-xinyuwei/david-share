# Estimating Memory Need in AI model Inference

The formula for total memory during inference is as follows:

Total Memory = Model Parameter Memory + Activation Memory + KV Cache Memory + Buffer Memory

If you are interested in the specific calculations, you can refer to previous articles on our WeChat official account, such as the link below. However, here I would recommend using tools for a rough evaluation. 

*https://mp.weixin.qq.com/s/UBtT1dsoE1FSPINVtMBv_Q?token=1958363107&lang=zh_CN*



***Please click below pictures to see my demo video on Youtube***:
[![Estimating-memory-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/nYATNXRr4tA)

## How to use the tool

On Linux:

Install need package:

```
#pip install transformers
#pip install torch
```

Run  estimatememory.pyc in *https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Estimate-Inference-Memory*

Note: The result of the tool is very reply on the parameters.

```
(EstimatingMemoryInference) root@davidgpt:~# python python-estimating.py 

######################################################################
#                                                                    #
#              Model Memory Consumption Calculator V1.0              #
#         https://github.com/xinyuwei-david/david-share.git          #
#                                                                    #
######################################################################

Note: Ensure that your environment has internet access to Hugging Face and that you have set your Hugging Face API token.

Enter the model name from Hugging Face: microsoft/phi-4

Loading model configuration...
/root/anaconda3/envs/EstimatingMemoryInference/lib/python3.11/site-packages/transformers/models/auto/configuration_auto.py:1039: FutureWarning: The `use_auth_token` argument is deprecated and will be removed in v5 of Transformers. Please use `token` instead.
  warnings.warn(

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
Use FlashAttention? [Y/n] (Default Y): N
Use KV Cache? [Y/n] (Default Y): N

--- Memory Consumption Results ---
Memory consumption of the model: 29.4 GB
Memory consumption of vanilla inference: 91.27 GB
Memory consumption of inference with GQA: 26.26 GB

Total Memory consumption (given the selected configuration): 55.66 GB
```

When I use a H100 VM to do actual inference test, the result is:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Estimate-Inference-Memory/images/3.png)

The accuracy of the tool's calculated values was 99.7%.