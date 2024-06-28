我们如何在本地安全地运行私有的LLMs呢？开源模型为此提供了可能的解决方案。本文将介绍七种方法。

1. **Hugging Face的transformers**

   这是一个Python库，可以简化本地运行LLM的过程。

Transformers的优点：

- 自动模型下载
- 提供代码片段
- 非常适合实验和学习

Transformers的缺点：

- 需要对ML和NLP有深入了解
- 需要编码和配置技能

**2.Llama.cpp：**

特点：Llama.cpp是一个基于C++的推理引擎，专门为Apple Silicon优化，可以运行Meta的Llama2模型。它针对GPU和CPU都做了推理优化。

优点：性能高于基于Python的解决方案，支持在适度的硬件上运行大型模型，如Llama 7B，并提供绑定，可以用其他语言构建AI应用程序，同时通过Llama.cpp运行推理。

缺点：模型支持有限，需要构建工具。

使用场景：当你需要在自己的硬件上运行大型模型，或者需要用其他语言构建AI应用程序时，可以选择使用Llama.cpp。

**3.Llamafile：**

特点：Llamafile由Mozilla开发，基于C++开发,它使用了llama.cpp，这是一个C++库，提供了运行自托管大型语言模型（LLMs）所需的各种功能。通过llama.cpp，开发人员可以轻松地创建、加载和运行LLM模型，而无需担心底层环境的复杂性。此外，Llamafile还提供了一个简洁的API接口，使得开发人员可以更加方便地与LLM进行交互，从而实现各种复杂的应用场景.

优点：与Llama.cpp相同的速度优势，你可以构建一个嵌入模型的单个可执行文件。

缺点：项目仍处于早期阶段，不是所有模型都支持，只支持Llama.cpp支持的模型。

使用场景：当你需要创建一个嵌入模型的单个可执行文件，或者需要一个便携性强的工具时，可以选择使用Llamafile。

**4.Ollama：**

特点：Ollama是Llama.cpp和Llamafile的一个更加用户友好的替代品。你下载一个可执行文件，它会在你的机器上安装一个服务。安装完成后，你打开一个终端并运行。

优点：易于安装和使用，可以运行llama和vicuña模型，运行速度非常快。

缺点：提供有限的模型库，自己管理模型，你不能重用自己的模型，无法调整选项来运行LLM，暂时没有Windows版本。

使用场景：当你需要一个易于安装和使用的工具，或者需要运行llama和vicuña模型时，可以选择使用Ollama。

目前微软Phi-3以上四种本地运行模式都支持。详见：

[Phi-3量化模型：SLM系列2](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663557136&idx=1&sn=cbaa6da80ca8bf16c1dbe978993b89a5&chksm=81d5ef68b6a2667e1b5aee2ca63f49f8856bf7965f28efd6459f230ca8fa938e21dddd529917&scene=21#wechat_redirect)

**5：vLLM**

vLLM是一个高吞吐量和内存高效的大型语言模型(LLMs)推理和服务引擎。它的目标是为每个人提供简便、快捷、经济的LLM服务。

优点

- 高效的服务吞吐量：vLLM可以快速处理大量的并发请求。
- 支持模型种类多。
- 内存高效：vLLM使用了一种名为PagedAttention的技术，可以高效地管理注意力键和值的内存。

缺点

- 你需要确保你的设备有GPU，CUDA或者RoCm.

vLLM会提供对Phi-3的支持，目前代码在集成中。

对Phi-2的支持的验证详见：

[语言模型小型化尝试-PyTorch学习系列36](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663554006&idx=1&sn=928bf267838f377a3996f8f3673ed995&chksm=81d5dcaeb6a255b823ca162c234bc5c0a06b61cbb08efb26770976ffdecc50bc6e2e9d7fa62b&scene=21#wechat_redirect)

**6.TGI（Text Generation Inference）**

TGI（Text Generation Inference）是HuggingFace推出的大模型推理部署框架。它支持主流大模型和主流大模型量化方案，并且联用Rust和Python来达到服务效率和业务灵活性的平衡。TGI实现了许多特性，例如：

- 简单的启动LLM

- 使用Flash Attention和Paged Attention进行推理的优化的transformers代码

- 使用bitsandbytes GPT-Q EETQ AWQ Safetensors进行量化

  

Text Generation Inference（TGI）和Transformer模型的推理方式有一些区别，主要体现在以下几个方面：

- 并行计算：TGI和Transformer都支持并行计算，但TGI更进一步，它使用了Rust和Python联用的方式，实现了服务效率和业务灵活性的平衡。这使得TGI在处理大型语言模型时，能够更有效地利用计算资源，提高推理效率。
- 优化技巧：TGI引入了一些优化技巧，如continuous batching、Flash Attention和Paged Attention等，这些技巧可以进一步提高推理的效率和性能1。而传统的Transformer模型可能没有这些优化技巧。
- 模型支持：TGI支持部署GPTQ模型服务，这使得我们可以在单卡上部署拥有continuous batching功能的，更大的模型。而传统的Transformer模型可能没有这样的支持。

然而，虽然TGI在某些方面可能比传统的Transformer推理更优秀，但这并不意味着我们就不需要使用Transformer的推理了。因为在某些情况下，例如当我们需要处理的任务或数据与TGI的优化技巧不匹配时，使用传统的Transformer推理可能会更合适。目前测试效果TGI的推理速度不如vLLM。

TGI推理支持容器方式运行：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVp5dLMGUbjuqocs4fNO7KvIf9Oha23p0LfibiapQJd35pGdTRDtUQoSQpUInXBibPor3zfbnMKvPuJQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**7.Deepspeed**

DeepSpeed支持本地推理。DeepSpeed是微软推出的一个开源深度学习优化库，它通过系统优化和压缩的方法，深度优化硬件设备、操作系统、框架等方面，并采用模型压缩和数据压缩技术，以提升大规模模型推理和训练的效率。

DeepSpeed-Inference是DeepSpeed框架在推理方面的扩展，专门针对大语言模型设计。它通过模型并行、张量并行和流水线并行等技术，提高了推理性能并降低了延迟。

详细内容参见：

[DeepSpeed-Chat微调模型：deepspeed训练系列-1](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663556001&idx=1&sn=fe5eb356c84ff1be36b26e06342dd146&chksm=81d5e4d9b6a26dcf2e0c81fb4ba066cca04d4521a2441c9aca708e88ae7a8ba45614e0393e0b&scene=21#wechat_redirect)



**推理框架的选择（选择之前先确认要使用的模型是否支持这种推理框架）：**

DeepSpeed：如果你的任务需要高性能的推理，那么DeepSpeed可能是一个好选择。DeepSpeed提供了一系列优化技术，如ZeRO（零冗余优化器），3D并行（数据并行、模型并行和流水线并行的结合），1比特Adam等，这些技术可以显著提升大模型训练和推理的效率。

ollama：如果你需要一个易于使用的工具，那么ollama可能更适合你。ollama的主要优点在于其易用性，用户可以通过简单的命令行界面运行模型。

Llamafile：如果你需要创建一个嵌入模型的单个可执行文件，那么Llamafile可能是一个好选择。Llamafile以其便携性和创建单文件可执行文件的能力而闻名。

TGI (Text Generation Inference)：如果你的任务需要在多种硬件环境下进行高效推理，那么TGI可能是一个好选择。TGI提供了一系列优化技术，如模型并行、张量并行和流水线并行等，这些技术可以显著提升大模型推理的效率。

Transformer：如果你的任务需要处理复杂的自然语言处理任务，如机器翻译、文本生成等，那么使用基于Transformer的模型可能是一个好选择。Transformer模型具有强大的表示能力，可以捕获文本中的长距离依赖关系。

vLLM：如果你的任务需要处理大规模的自然语言处理任务，如文本分类、情感分析等，那么使用vLLM可能是一个好选择。vLLM是一个大规模的预训练模型，可以在各种自然语言处理任务上实现优秀的性能