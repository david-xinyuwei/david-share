# Deep-Speed-Inference
**Refer：**
https://github.com/microsoft/DeepSpeed-MII

https://medium.com/towards-data-science/deepspeed-deep-dive-model-implementations-for-inference-mii-b02aa5d5e7f7

## Deep Learning architecture
从下往上的深度学习堆栈如下图所示：

```
  +---------------------+  
  |      Model          |  <-- Model layers (e.g., Phi3-Vision)  
  +---------------------+  
            |  
            v  
  +---------------------+  
  |  DeepSpeed/vLLM     |  <-- Specific frameworks (e.g. vLLM for optimising the Transformer)  
  +---------------------+  
            |  
            v  
  +---------------------+  
  |   Transformer       |  <-- Specific neural network architectures (e.g. Transformer)  
  +---------------------+  
            |  
            v  
  +---------------------+  
  |      PyTorch        |  <-- Deep learning frameworks  
  +---------------------+  
            |  
            v  
  +---------------------+  
  |      Python         |  <-- programming language  
  +---------------------+  
            |  
            v  
  +---------------------+  
  |       CUDA/ROCm     |  <-- Underlying computational acceleration library  
  +---------------------+  
```

## Is DeepSpeed Zero available for use in inference?
DeepSpeed的ZeRO优化是主要用于训练阶段的，而不是推理阶段。在推理阶段，模型已经被训练好了，我们主要关注的是如何更快、更高效地进行推理，而不需要再进行模型的优化。因此，ZeRO优化在推理阶段通常是不需要的，也不会被使用。

如果你需要在推理阶段进行优化，可以使用其他适用于推理的优化技术，如混合精度（FP16）和内核注入。

ZeRO（Zero Redundancy Optimizer）是DeepSpeed的一个特性，它的主要目标是减少训练大型模型时的内存占用。ZeRO通过在多个设备间分割模型参数、优化器状态和梯度来实现这一目标。这就是你提到的ZeRO的三个阶段：P_os（只对优化器状态进行分区）、P_os+g（对优化器状态和梯度进行分区）和P_os+g+p（对优化器状态、梯度和参数进行分区）。

然而，在推理（或称为预测）阶段，我们通常不需要优化器或梯度，因为模型已经被训练好了，我们只需要用它来生成预测。因此，ZeRO的优化在推理阶段并不适用。

此外，推理阶段的主要关注点通常是如何更快、更高效地进行预测，而不是如何减少内存占用。因此，我们在推理阶段通常会使用其他的优化技术，如模型量化（减少模型大小和计算复杂性）和模型融合（合并模型的操作以减少计算时间）等。


DeepSpeed提供了一些推理优化技术，主要包括以下几个方面12：

具有自适应并行性的多GPU推理：优化延迟是推理系统的重要目标。使用模型并行（MP），可以拆分模型并使用多个GPU进行并行计算以减少延迟，但这可能会影响吞吐量。
专为推理优化的CUDA内核：为了实现高计算效率，DeepSpeed推理通过运算符融合为Transformer blocks提供定制化的推理内核，同时考虑了多GPU的模型并行性。
灵活的量化支持：为了进一步降低大规模模型的推理成本，DeepSpeed创建了量化工具包，支持灵活的量化感知训练和用于量化推理的高性能内核。

## DeepSpeed-MII
MII 是 DeepSpeed 设计的开源 Python 库，旨在实现强大模型推理的民主化，重点关注高吞吐量、低延迟和成本效益。MII 的功能包括blocked KV-caching、continuous batching、Dynamic SplitFuse、 tensor parallelism和and high-performance CUDA kernels，以支持 LLM（如 Llama-2-70B、Mixtral (MoE) 8x7B 和 Phi-2）的快速高吞吐量文本生成。


![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Deep-Speed-ZeRO-Policy/images/memoryintraining.webp)

```
# create pipeline
pipe = pipeline("text-generation",
                model="mistralai/Mistral-7B-Instruct-v0.3",
                device=0,
                torch_dtype=torch.float16)

# prompt
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.3")
start_text = "Once upon a time"
tokens_start_text = len(tokenizer(start_text, return_tensors="pt").input_ids[0])

new_tokens = 2000

# generate text (500 new tokens)
t0 = time.time()
result = pipe(start_text, max_new_tokens=new_tokens)
t1 = time.time()
```


## 推理速度对比
首先使用HF Transformers pipeline
```
# 设置输入文本、模型、最大令牌数  
input_text = "Once upon a time"  
model = "mistralai/Mistral-7B-Instruct-v0.3"  
new_tokens = 2000  
  
# 加载tokenizer和pipeline  
tokenizer = AutoTokenizer.from_pretrained(model)  
pipe = pipeline("text-generation", model=model, device=0)  
```
我们查看执行结果：
image

接下来使用DeepSpeed推理.
# 使用 DeepSpeed 初始化模型  
pipe.model = deepspeed.init_inference(  
    pipe.model,  
    mp_size=1,  
    dtype=torch.half,  
    replace_method='auto',  
    replace_with_kernel_inject=True  
)  
```

我们看到DeepSpeed的速度没有明显提升

使用DeepSpeed MII推理：

```
conda activate dsmii;cd dsmii
pip install git+https://github.com/huggingface/transformers
pip install --upgrade torch torchvision torchaudio deepspeed
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export CXX=/usr/bin/g++
export CUDA_HOME=/usr
export PATH=$CUDA_HOME/bin:$PATH
#sudo apt-get install libaio-dev  
(dsmii) root@h100vm:~/DeepSpeed-MII# git clone https://github.com/NVIDIA/cutlass.git
Cloning into 'cutlass'...
remote: Enumerating objects: 26714, done.
remote: Counting objects: 100% (25/25), done.
remote: Compressing objects: 100% (23/23), done.
remote: Total 26714 (delta 5), reused 10 (delta 0), pack-reused 26689
Receiving objects: 100% (26714/26714), 42.66 MiB | 64.52 MiB/s, done.
Resolving deltas: 100% (20054/20054), done.
(dsmii) root@h100vm:~/DeepSpeed-MII# pwd
/root/DeepSpeed-MII
(dsmii) root@h100vm:~/DeepSpeed-MII# export CUTLASS_PATH=/root/DeepSpeed-MII/cutlass
(dsmii) root@h100vm:~/DeepSpeed-MII#
deepspeed --num_gpus 1 3.py


ImportError: cannot import name 'Conversation' from 'transformers' (/opt/miniconda/envs/dsmii/lib/python3.10/site-packages/transformers/__init__.py)
```