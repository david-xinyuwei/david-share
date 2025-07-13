# 从零开始实现llama3

本文旨在全面解析并从零开始实现 LLaMA 3 模型。通过结合理论讲解与实践代码示例，带你深入理解 LLaMA 3 的模型架构、核心原理及关键实现细节。

无论你是机器学习初学者，还是深度学习爱好者，都可以在本文中找到详细且易于上手的指导内容。

项目源码已开源，欢迎克隆并动手练习：

```
git clone https://github.com/naklecha/llama3-from-scratch.git
```

接下来，我们将一步步拆解 LLaMA 3 模型，从基础参数、数据处理，到多头注意力机制及全模型推理流程，完整复现其设计与实现。



### Llama3的整体架构

下图展示了 LLaMA 3 模型的整体架构示意。作为一个大型基于 Transformer 的语言模型，LLaMA 3 由多个核心模块组成，包括输入嵌入层、多个堆叠的 Transformer Block 以及输出预测层。每个 Transformer Block 内部包含多头自注意力机制和前馈神经网络，协同作用实现强大的语言理解与生成能力。

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Implementing-llama3-from-scratch/images/1.png)

**Llama3的模型参数：**

接下来，让我们详细查看 LLaMA 3 各关键参数的实际数值。透过这些参数，我们能够更好地理解模型的规模、复杂度及其运作机制。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPPyxLcZngK2DiajQPl7p2e8bYJJSNfKjX681XPcX6kiap2YB3IibQFYe6A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[1] 上下文窗口（context-window）**
在实例化LlaMa类时，变量max_seq_len定义了context-window。类中还有其他参数，但这个参数与transformer模型的关系最为直接。这里的max_seq_len是8K。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPzOa7a8YtTv6DG6icXSiae85xq5SrKravlx2meaRxEhUQhNjyB9HYOyJQ/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)


**[2] 词汇量（Vocabulary-size）和注意力层（Attention Layers）**
接下来是Transformer类，它定义了词汇量和层数。这里的词汇量是指模型能够识别和处理的单词（和tokens）集。Attention layers指的是模型中使用的transformer block（attention和feed-forward layers的组合）。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPc8RF5licIGNYdLrQ0g9r9SceAyxiacc25ib5qfDa2TMkKP5eE4vWKBh3A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)


根据这些数字，LlaMa 3的词汇量为128K，这是相当大的。此外，它有32个transformer block。

**[3] 特征维度（Feature-dimension）和注意力头（Attention-Heads）**
特征维度和attention-heads被引入到Self-Attention模块中。Feature dimension指的是嵌入空间中tokens的向量大小（特征维度是指输入数据或嵌入向量的维度大小），而attention-heads包括驱动transformers中self-attention机制的QK-module。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPtsQsgg3VZ8xP1umlZqVZVDbabMq05BuPiaZPTD511kHvoTJGAeHzH2A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[4] 隐藏维度（Hidden Dimensions）**
隐藏维度是指在前馈神经网络（Feed Forward）中，隐藏层的维度大小。前馈神经网络通常包含一个或多个隐藏层，这些隐藏层的维度决定了网络的容量和复杂度。在Transformer模型中，前馈神经网络的隐藏层维度通常是特征维度的某个倍数，以增加模型的表示能力。LLama3中，隐藏维度是特征维度的1.3倍。需要注意的是，隐藏层和隐藏维度是两个概念。

更多的隐藏层数量允许网络在将它们投射回较小的输出维度之前，内部创建和操纵更丰富的表示。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPgftUOgFE3slpwAp5hItAzhibqCNnDSic22Jxh3YQuXaXxwr0Sxzoeiafg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[5] 将上述参数组合成Transformer**
第一个矩阵是输入特征矩阵，通过Attention layer处理生成Attention Weighted features。在这幅图像中，输入特征矩阵只有5 x 3的大小，但在真实的Llama 3模型中，它增长到了8K x 4096，这是巨大的。

接下来是Feed-Forward Network中的隐藏层，增长到5325，然后在最后一层回落到4096。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPgS1JCcK6xhOhnqU66pNXxXCET6XEtIn6IFMeGBgnLHy9QK3mGeaQiaw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[6] Transformer block的多层**
LlaMa 3结合了上述32个transformer block，输出从一个block传递到下一个block，直到达到最后一个。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPQRa1cicqXxhnzZesxGpPobIX7Qq1TGu5icTq3QKvPIENWcLxEcehtakw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[7] 把所有这些放在一起**
一旦我们启动了所有上述部分，就是时候把它们整合在一起，看看它们是如何产生LlaMa效果的。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPLzibicmYGtmUC8IcmlJBO4CGa9A14VnF1oQVtqTLPAD18GgY1YMhKrfg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

###  LLaMA 3 模型中数据流转的核心流程

**步骤1：输入矩阵**

首先，我们拥有一个输入矩阵，其大小为：
8K（上下文窗口大小，代表最多可以输入8000个token） × 128K（词汇表大小，代表模型识别的不同符号或词的总数）。
矩阵的每一行代表一个token的向量表示，经过词嵌入层映射后，从原始的稀疏表示变成了固定维度的连续向量，用于后续模型的处理。

**步骤2：特征降维**

经过嵌入处理后，这个低维矩阵会被转换成一个特征向量，大小为4096。也就是说，每个token由一个长度为4096的向量表示。这是LLaMA 3模型设计的“特征维度（feature dimension）”。

**升维与降维的目的**

- **升维（将输入映射到更高维空间）**：通过提升到更高的维数，模型能够学习到更复杂的特征关系，有助于捕获非线性特征、改善模型的表达能力。例如，将低维特征升到4096，是为了让模型有更丰富的表达能力。
- **降维（将高维特征压缩）**：减少特征空间中的冗余信息，有助于减少模型的过拟合、提升运算效率，以及增强模型的泛化能力。降维是对特征的“提炼”，用最少的参数拟合实用的模式。

总结：在神经网络中，升维和降维通常结合使用，先用升维探索数据内在结构，再用降维提取关键特征。这一策略帮助模型既具备强能力，又不过度复杂。

**步骤3：Transformer的处理流程**

- 经过特征后，输入进入Transformer结构 ：
  - 先由 **Attention Layer** 横向处理：侧重于不同特征之间的交互关系。
  - 再由 **Feed-Forward Network (FFN)** 层纵向处理：提升每个特征向量的表达能力。

**步骤4：堆叠多层Transformer**

- 这个流程会重复执行32次（表示模型有32个Transformer Block），每一层都会基于上一层输出进行进一步处理。
- 最终，得到的矩阵特征和输入时的特征维度一致（4096），实现了深层次的特征融合。

**步骤5：输出还原到原词空间**

- 最后，这个矩阵被映射回词汇表大小（128K），以便模型能输出下一步要生成的词或符号。
- 这个映射是真实生成文本的基础。

#### 术语总结

1. **max_seq_len（最大序列长度）**
   表示模型一次最多能处理多少个tokens。
   比如：在LLaMA 3-8B模型中，这个值是8000，代表最多考虑8千个单词或符号，支持长文本理解。
2. **Vocabulary-size（词汇表大小）**
   代表模型认识的不同符号（词、标点、特殊字符）总数。
   以128,256为例，意味着模型有128,256个不同输入“单元”。
3. **Attention Layers（注意力层）**
   关键模块，学习输入中哪些信息更重要，从而理解句子关系。
   在LLaMA 3中，一共包含32层，每层含多头自注意力机制。
4. **Transformer Block（变压器模块）**
   一个完整处理单元，包含一个自注意力子层和一个前馈网络子层。模型由多个这些模块堆叠组成。
5. **Feature-dimension（特征维度）**
   指每个token被映射成的向量长度（如4096），折射出模型捕获信息的容量。
6. **Attention-Heads（注意力头）**
   每个Attention层中的子空间，个数为32。通过分多头，模型可以从不同角度分析输入的关系。
7. **Hidden Dimensions（隐藏层维度）**
   在前馈网络中隐藏层神经元的个数，例：5325。较大隐藏层旨在增强模型容量。

**关系总结**

- 一个Attention层中的多头（Heads）数量为32，每个头处理128维的子空间，以多视角捕捉关系。
- 逐层堆叠的32个Transformer块，共同逐步提炼出深层次的表达。



## 模型加载与文本预处理

在理解模型架构和参数基础上，下一步是实际使用模型进行数据处理。这包括如何加载词表，进行文本编码，以及如何加载模型的权重。

### **读取模型文件**



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDWq3cUFHcGLTqNZyGibr7kGXicpiaqCVtLU1jXqXaHFFcQgtTqKlmwzSYg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

加载模型文件后，我们可以查看其中存储的参数或权重。以下展示的是模型文件中包含的前20个参数名称，用于了解模型的具体组成结构。

```
model = torch.load("Meta-Llama-3-8B/consolidated.00.pth")
print(json.dumps(list(model.keys())[:20], indent=4))
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDm8K80nAiaH3iaSLjseMZWBwy3btkT2rgYanlWXOn7cTCjIZK7u5jWroQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. **`tok_embeddings.weight`**：表示模型中的词嵌入层权重。该层负责将输入的单词（或者更一般的令牌token）转换成固定维度的向量表示，这是大多数自然语言处理模型的第一步。
2. **`layers.0.attention...` 和 `layers.1.attention...`**：这些参数对应模型多个层中的注意力模块。每个注意力模块包含四个核心权重矩阵——查询（`wq`）、键（`wk`）、值（`wv`）和输出（`wo`）。这四个矩阵共同构成Transformer模型的核心机制，负责捕捉输入序列中不同token之间的相关性。
3. **`layers.0.feed_forward...` 和 `layers.1.feed_forward...`**：这些参数表示每个层中前馈神经网络（Feed-Forward Network，FFN）的权重。通常，FFN由两个线性层和一个非线性激活函数组成，`w1`、`w2`、`w3`可能指代这些线性层的不同权重矩阵。
4. **`layers.0.attention_norm.weight` 和 `layers.1.attention_norm.weight`**：表示每个注意力模块后面的归一化层权重，通常为Layer Normalization，用于稳定训练过程。
5. **`layers.0.ffn_norm.weight` 和 `layers.1.ffn_norm.weight`**：表示前馈网络后续的归一化层权重，功能同样是提升训练的稳定性和模型表现。

综上所述，以上参数涵盖了LLaMA 3中一个完整Transformer Block的主要组成部分。



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRhJ7lib0q1qrnjeXgFwZtpDUbkCSDQChWqTW97ECQM5NLoRSKmD2M82w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

总体来看，上面结果揭示了基于 Transformer 架构的深度学习模型的核心组成部分。此类模型广泛应用于自然语言处理任务，包括文本分类、机器翻译和问答系统等。模型的每一层结构基本一致，均包含注意力机制、前馈网络和归一化层，这样的设计有助于模型有效捕捉输入序列中的复杂特征。

### 查看 LLaMA 3 模型的参数配置

```
import json

with open("Meta-Llama-3-8B/params.json", "r") as f:
    config = json.load(f)

print(config)
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDrNrD9wDLcrBc80VibiaDIhCB07evn5fMSj7icEIcGJJrZIlkz7vFQCFJg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. 运行结果示例如下：
   - **dim**: 4096
     模型的隐藏层维度或特征维度，即每个token被表示成4096维的向量。
   - **n_layers**: 32
     Transformer层数，表示模型深度。
   - **n_heads**: 32
     注意力头的个数，多头机制使模型可以并行捕捉多方面的信息。
   - **n_kv_heads**: 8
     用于键（Key）和值（Value）的多头数量，LLaMA中常用的减少计算的优化设计。
   - **vocab_size**: 128256
     词汇表大小，代表模型可识别的单词或符号总数。
   - **multiple_of**: 1024
     模型参数维度通常设置为1024的倍数，保证硬件和算法的效率。
   - **ffn_dim_multiplier**: 1.3
     前馈网络隐藏层大小相对于特征维度的放大倍数。
   - **norm_eps**: 1e-5
     归一化层中防止除零的小常数，增强数值稳定性。
   - **rope_theta**: 500000.0
     RoPE（旋转位置编码）相关参数，控制位置信息编码方式。



### **将Text转化为Token**

在自然语言处理模型中，文本数据需要经过分词器（Tokenizer）转换为模型能够处理的数字序列（即 tokens）。这些 tokens 是模型输入的基础，它们将文本映射成数字ID，便于后续的嵌入计算和模型处理。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDUBSbb8Ss1ynwSr363SkibxtDHgvQJ6iab8YlEzGn3ulWpfau02kTbpeQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)



下面通过代码示例，演示如何利用前面加载的 tokenizer，将一段文本转化为对应的 token 序列，并验证tokenizer的正确性：

```
prompt = "the answer to the ultimate question of life, the universe, and everything is "
tokens = [128000] + tokenizer.encode(prompt)
print(tokens)
tokens = torch.tensor(tokens)
prompt_split_as_tokens = [tokenizer.decode([token.item()]) for token in tokens]
print(prompt_split_as_tokens)
```

```
[128000, 1820, 4320, 311, 279, 17139, 3488, 315, 2324, 11, 279, 15861, 11, 323, 4395, 374, 220]
['<|begin_of_text|>', 'the', ' answer', ' to', ' the', ' ultimate', ' question', ' of', ' life', ',', ' the', ' universe', ',', ' and', ' everything', ' is', ' ']
```



到目前为止，我们处理的17个令牌（形状为 [17×1] 的序列）已经被转换为对应的嵌入向量，形成了一个形状为 [17×4096] 的张量。也就是说，每个令牌被映射成一个长度为4096的向量，总共有17个这样的向量。

下图通过可视化验证了该句子被成功分解为17个token。

##  ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDhgjW09BHGoIJSANsLy8foiawIImzDibFWHblDwyseEdEESZZnibUwjd7A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 

```
embedding_layer = torch.nn.Embedding(vocab_size, dim)
embedding_layer.weight.data.copy_(model["tok_embeddings.weight"])
token_embeddings_unnormalized = embedding_layer(tokens).to(torch.bfloat16)
token_embeddings_unnormalized.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDzKnAe5UnUeazT64j2wJWmMYKX0pDk8CTK3V71mF5KXel0NYUrILY0A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

## 构建 Transformer 的第一层

接下来，我们对嵌入向量应用 RMS 归一化（RMSNorm）进行标准化处理，以稳定训练并提升模型表现。该归一化操作对应于模型结构图中的标注位置，作为 Transformer 第一层的输入预处理步骤。![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDI9k3JsQibTVEGhLOTMdfibT3MVcAHicicIhyXfoFuk162QQrlwHVdBibl3g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)使用公式如下： ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDXzpS3lCXVxKbBHCBeUkAmAwjsnPHUicg6amYuFIq2Vpfddb9GxvZib5Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 

代码如下：

```
# def rms_norm(tensor, norm_weights):
#     rms = (tensor.pow(2).mean(-1, keepdim=True) + norm_eps)**0.5
#     return tensor * (norm_weights / rms)
def rms_norm(tensor, norm_weights):
return (tensor * torch.rsqrt(tensor.pow(2).mean(-1, keepdim=True) + norm_eps)) * norm_weights
```

这段代码定义了一个名为 `rms_norm` 的函数，用于对输入的张量（数据）进行 RMS 归一化处理。这里的 RMS 是“均方根”（Root Mean Square）的简称。

这个函数需要两个参数：

- `tensor`：要归一化的输入数据，一般是多维的向量或矩阵。
- `norm_weights`：归一化使用的权重，是对数据缩放的一个系数。

**函数的实现步骤如下：**

1. **平方**：对输入的每个元素求平方。
2. **求均值**：沿着最后的维度（也就是每个向量维度）计算这些平方值的平均值，并保持原有维度不变。
3. **计算均方根的倒数**：先给均值加上一个很小的数（`norm_eps`），避免除零错误，然后计算平方根的倒数。这个值可以看成是数据大小的标准化因子。
4. **归一化和缩放**：将原始输入乘以均方根倒数，再乘以归一化权重 `norm_weights`，得到归一化后的数据。

通过以上步骤，输入数据的整体规模被规范化，减少了不同样本间的大小差异，有利于模型稳定训练。

**注意**，归一化后数据的形状保持不变，例如 `[17 × 4096]`，只是数值经过了缩放处理。

```

token_embeddings = rms_norm(token_embeddings_unnormalized, model["layers.0.attention_norm.weight"])
token_embeddings.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDQlhlFpGPYH0yiaIzmLA2pZJbaDWsQ0zegA8gu4OWF07CibSiayWICcksg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDqbCvzDqXNO36eRav2icApia9hOn22DqzAiaRhjQdpGX0It0l7D6icWxdkw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

接下来，我们将详细介绍注意力机制的具体实现过程，该机制在下图红框标注的部分被高亮显示。通过这一部分的讲解，您将深入理解模型如何通过计算输入序列中各元素之间的相互关系，从而赋予模型捕捉上下文和长距离依赖的能力。这是 Transformer 架构的核心组成部分，对提升模型的表现至关重要。

### ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRNm04hVoLiaIuUNGbuiaoO4r6R5gbkcS2uWByg5bU45ygyibVCIKXE6kiag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)  ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDnwog1Jg03BJAT8fSsynwEOhCdTUJVYAibK7qhGD2ibSUy9q7h4DNR1ibw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**逐步解析多头注意力机制**

下面我们一步步讲解下图中多头注意力机制的实现过程，详细说明每个关键步骤的含义和执行方式。

1. 输入句子

- **描述**：这是我们输入给模型的一段文本句子。
- **解释**：模型将这段句子表示成一个矩阵 X，其中每一行对应一个词的嵌入向量，用数值形式捕捉词义和上下文信息。

2. 词向量嵌入

- **描述**：对句子中的每个词进行嵌入转换。
- **解释**：每个词被转换成对应的高维向量，形成最终的输入矩阵 X，为后续计算准备了可处理的数值特征。

3. 划分为多个注意力头

- **描述**：将矩阵 X 分成 8 个注意力头。分别用对应的权重矩阵 W^Q（查询）、W^K（键）、W^V（值）与矩阵 X 相乘。
- **解释**：多头注意力机制将输入拆分成多个子空间，每个“头”有自己独立的查询(Q)、键(K)、值(V)权重矩阵。具体地，矩阵 X 分别乘以 W^Q、W^K、W^V，得到对应的查询矩阵 Q、键矩阵 K 和值矩阵 V。

4. 计算注意力分数

- **描述**：利用 Q、K、V 计算注意力得分和输出。

- 解释

  ：对于每个头，计算步骤如下：

  1. 计算查询矩阵 Q 与键矩阵 K 的点积，表示词与词之间的相关性。
  2. 对点积结果进行缩放，防止数值过大影响梯度。
  3. 使用 softmax 函数将结果转换为概率分布，得到注意力权重。
  4. 用得到的权重乘以值矩阵 V，计算加权输出 Z。

5. 拼接各头输出并映射

- **描述**：将所有头得到的矩阵 Z 拼接，后乘以输出权重矩阵 W^O，生成整层的最终输出。
- **解释**：各头独立计算后，其输出沿特征维度拼接成一整块大矩阵，再乘以 W^O，实现信息融合和映射，得到整层注意力的最终结果。

------

额外说明

- **各权重矩阵形状**
  查询（Q）、键（K）、值（V）和输出（O）权重矩阵在模型中分别具有下面的典型形状：
  - 查询权重 Wq：4096×4096
  - 键权重 Wk：1024×4096
  - 值权重 Wv：1024×4096
  - 输出权重 Wo：4096×4096
- **并行计算**
  这些权重分布允许在计算时将多个注意力头的操作并行计算，从而提升效率。

这张图完整展示了 Transformer 模型中多头注意力机制的流程。它从输入词向量出发，依次分头处理、计算注意力得分，再拼接合并输出。每个步骤都不可或缺，保证模型能够捕捉输入序列中丰富的上下文信息和复杂关系。

**附注：**
当我们查看模型中加载的 Q、K、V、O 权重矩阵形状时，会发现它们并非完全独立的头维度拆分（如预期中每个头单独维度），反而是混合在一起的整体矩阵。这种设计利于并行计算，但乍一看结构较为复杂。

```

print(
model["layers.0.attention.wq.weight"].shape,
model["layers.0.attention.wk.weight"].shape,
model["layers.0.attention.wv.weight"].shape,
model["layers.0.attention.wo.weight"].shape
)
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDU3481qzMyoxOwVnZQUBjALsFKzah0wx0cnB3bgE4PKRM9ZHU7cQntw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. 查询（Query）权重矩阵（`wq.weight`）的形状是 `[4096, 4096]`。
2. 键（Key）权重矩阵（`wk.weight`）的形状是 `[1024, 4096]`。
3. 值（Value）权重矩阵（`wv.weight`）的形状是 `[1024, 4096]`。
4. 输出（Output）权重矩阵（`wo.weight`）的形状是 `[4096, 4096]`。

**分析输出结果：**

- 查询（Q）和输出（O）权重矩阵形状相同，均为 `[4096, 4096]`，这意味着它们处理的输入特征和输出特征维度均为4096。
- 键（K）和值（V）权重矩阵形状相同，均为 `[1024, 4096]`，表明它们的输入特征维度为4096，但输出特征被压缩至1024。

这种设计体现了模型架构上的权衡，键和值的维度缩小有助于降低计算复杂度和内存消耗，而查询和输出保持较高维度，则有利于保留更多信息。具体设置因模型结构和应用需求而异。

### QKV权重矩阵的作用完整解析

假设你想使用 LLaMA-3 模型生成一句合适的文本，例如输入：

```
我 欣赏 马斯克
```

模型的任务是根据给定的输入内容，合理地预测并续写后面的文字，譬如生成：

```
我 欣赏 马斯克 ， 因为 他 创立 了 特斯拉。
```

现在，我们通过 Transformer 的多头注意力机制，一步步详细展示从输入句子开始，到最终模型如何通过 **Q/K/V 的计算**做出对应的预测。

#### 初始化词嵌入 (Embedding)

Transformer 首先将输入的每一个token（词语），转化为一个高维的向量。真实模型中每个词对应一个4096维向量，这里为了手算和理解简化为2维举例：

| token  | 向量示例（2维，假设） |
| ------ | --------------------- |
| 我     | [0.9, 0.2]            |
| 欣赏   | [0.5, 1.0]            |
| 马斯克 | [1.0, 0.8]            |

> 实际上，真实的模型向量在4096维，这里仅用两维以便直观理解。

#### Transformer 多头注意力机制逐步讲解

##### 第一步：计算 token 的 Q、K、V 向量

通过三个由模型训练的权重矩阵（W_Q、W_K、W_V），每个 token 映射出：

- Q (Query)：代表当前 token 更关心上下文的哪种信息；
- K (Key)：每个 token 向其他 token 提供的特征，类似于身份或匹配依据；
- V (Value)：每个 token 向模型提供的具体语义信息。

对“我 欣赏 马斯克”三个 token 举例如下：

| Token  | 查询(Q) | 键(K) | 值(V) | 意义说明                     |
| ------ | ------- | ----- | ----- | ---------------------------- |
| 我     | Q₁      | K₁    | V₁    | 专属于token“我”的QKV表示     |
| 欣赏   | Q₂      | K₂    | V₂    | 专属于token“欣赏”的QKV表示   |
| 马斯克 | Q₃      | K₃    | V₃    | 专属于token“马斯克”的QKV表示 |

##### 第二步：以“马斯克”为例，具体计算其注意力及新表示 Z₃

重点关注“马斯克”这个词的计算：

“马斯克”利用它自己的Q向量(Q₃)，去评估与句子中每个K的匹配程度（涵盖“我”、“欣赏”、“马斯克”本身）：

```
score(马斯克→我)   = Q₃ · K₁
score(马斯克→欣赏) = Q₃ · K₂
score(马斯克→马斯克)= Q₃ · K₃
```

对所有score归一化(Softmax)，得到对每个token的关注权重(均值总和为1)，例如：

```
α₁ (关注程度: 我), α₂ (关注程度: 欣赏), α₃ (关注程度: 马斯克)
```

根据以上的关注程度权重，整合句子全部token的Value信息，得到“马斯克”这个token新的上下文表示Z₃：

```
Z₃ = α₁·V₁ + α₂·V₂ + α₃·V₃
```

类似步骤同样适用于其他token（“我”、“欣赏”），各自计算出对应的Z₁、Z₂。

| Token  | 生成的新表示(Z) | 含义(上下文信息的综合表达)             |
| ------ | --------------- | -------------------------------------- |
| 我     | Z₁              | “我” 融合整句的上下文信息后的新表示    |
| 欣赏   | Z₂              | “欣赏” 融合整句的上下文信息后的新表示  |
| 马斯克 | Z₃              | “马斯克”融合整句的上下文信息后的新表示 |

**(注意：每个Z向量的计算都用到全部token的KV信息，绝不是孤立处理单独某个token)**

#### 第三步：拼接输出并进行最终变换

各个注意力头分别计算出类似的 Z 向量后，模型会把所有头的Z拼接成更长的上下文向量，进一步用一个输出投影矩阵W_O降到原始维度：

```
Attention输出 = [Z₁, Z₂, Z₃] → Wₒ → 输出到下一层Transformer
```

再经过残差连接、Layer Norm以及FFN（前馈神经网络）变换，形成每一层的最终输出 H_out：

```
H_out = FFN(LayerNorm(Attention输出 + 原始嵌入向量))
```

### 基于 Transformer 输出生成新词 (逐步预测Token)

假设这一步我们经过32层Transformer的连续变换后，现在只关注句子最后token“马斯克”对应的最终表示向量：

```
h_final(马斯克) = [2.5, 1.2] (假设，2 维举例)
```

接下来使用输出矩阵（W_out）对h_final进行投影，得出每个候选token的得分（logit）：

假设迷你词表举例：

| 候选Token | 向量(假设) | 点积logit          |
| --------- | ---------- | ------------------ |
| 奔驰      | [1.0, 0.8] | ≈ 3.34             |
| 了        | [0.3, 0.9] | ≈ 1.91             |
| 特斯拉    | [1.5, 1.7] | ≈ 5.91（最高得分） |

然后，使用softmax换算成概率，取得概率最大项：

```
预测出的token="特斯拉"
```

于是，句子变为：

```
我 欣赏 马斯克 特斯拉
```

再继续进⼊下一次预测迭代循环，依次逐个预测：

```
→ ， → 因为 → 他 → 创立 → 了 → 特斯拉 →。
```

最终得到完整文本：

```
我 欣赏 马斯克 特斯拉，因为 他 创立 了 特斯拉。
```

#### 总结 Transformer 中 Q、K、V、Z 和权重矩阵的作用：

- **W_Q 查询矩阵(Q矩阵)**： 用来将每个token映射成查询向量(Q)，表示当前token更关心什么样的上下文信息。
- **W_K 键矩阵(K矩阵)、W_V 值矩阵(V矩阵)**： 分别生成每个token的键(K)价值(V)向量，提供每个token的“可匹配信息”和“具体语义信息”。
- **W_O 输出矩阵(O矩阵)**： 对所有token的注意力输出Z拼接后进行降维、映射，并融合成统一的最终元素表示（H_out），为后续Transformer层继续处理。

#### 一句话总结QKVZ的作用：

> 每个token产生自己的QKV，通过Q和所有K计算出注意力权重融合所有V，形成该token的新表达Z。
> 最终这些Z经过残差连接与前馈网络生成最终隐藏表示，用来预测下个词，从而持续生成连贯文本。

以上示例与解释，希望能够完整、清晰、直观地呈现 LLaMA-3 Transformer 的核心机制——**多头注意力机制中QKVZ的过程及其实际应用**：从一个短小例子如何扩展成完整文本生成全过程。

### QKV的本质

首先明确：

Transformer 中的 Q、K、V 本身**并不是直接用来预测下一个 token 的**。它们只是 "注意力(Attention)" 机制计算中的临时中间产物，目的是更好地 **整合每个 token 周围的上下文信息**。

那么，为什么 Transformer 用 QKV 来实现预测下一个 token？

#### Transformer 是怎么理解一个句子的？

传统模型理解句子，可能直接是一个字一个字或一个词一个词独立看过去，很难深刻理解上下文关系。

而 Transformer 的方式是：

- **Token自己制造查询 (Query, Q)**：
  它会提出 "我应该关注句子的哪些部分？"
- **Token同时也制造Key、Value**：
  它同时也告诉别人："我这个Token有什么特征(K)，能贡献哪些信息(V)？"

然后每个 Token 进行一轮内部“互动”：

- 每个 Token 用 **自己的 Query(Q)** 去匹配 **句子中所有 Token 的 Key(K)**。
- 根据匹配结果，决定它使用哪些 Token 的 Value(V) 信息，并组合这些信息形成新的表达向量 (`Z`)。
- 这个新的向量 Z 就是一次上下文交互之后，更好、更明确地 "重新理解了上下文" 的向量描述。

最后经过若干次这种交互（32层Transformer Block）后，每个词的向量逐渐融合了整个句子的更多信息，表达更精确、信息更丰富，使得后面的预测变得更加精准。

#### 用简单的直观比喻理解（现实生活的类比）：

你把 Transformer 理解为一个“智慧专家论坛”：

1. 一群专家围坐一圈，每一个 Token 都是一个专家。
2. 每次专家发言之前（预测下一个词之前），他们都需要：
   - 提出自己关注的话题 (Q 向量)；
   - 表明自己的专长、特征 (K 向量)；
   - 同时准备好一份具体信息 (V 向量)，供别人采纳。
3. 然后，每位专家都会根据自己关心的主题 (Q)，与在座各位的专长特征 (K) 做个匹配，决定自己怎么从其他专家那里 "学习" 并组合其他专家所提供的的知识 (V)。
4. 经历几轮讨论后，每位专家的观点都融合了大伙儿的智慧 (经过多个 Transformer 层)。
5. 最终到投票（预测下一个词汇）阶段时，每位专家（每个token）的观点已经最充分融入了整个小组的上下文信息，从而给出最合理、最贴近上下文的下一步建议（下一个token预测）。

#### QKV 与推理预测下一个词的真实意义：

- Q/K/V 本身虽然是不直接进行最终的词语预测操作的；
- 但在预测下一个词之前，模型需要的是包含充分上下文语境、全面融合整体语义信息的表达；
- QKV结构确保了每个单词的表示逐渐受到整个句子的充分滋养，从而获得更准确的上下文语义理解；
- **只有经过了QKV这样的高度交互、融合的过程，模型的Token向量才能最充分地实现自我表达，达到一次最为准确、最具上下文逻辑连续性的单词预测。**

#### 回到刚才示例“我欣赏马斯克”：

- 一开始，“马斯克”仅有初步含义 ([1.0, 0.8]类似早期随机初始)，表达不够明确；
- 经过注意力机制 Q₃→K₁、K₂、K₃匹配，获得句子中“我”、“欣赏” Token的信息（V向量）；
- 将这些上下文信息融入自身向量，形成更准确的新隐藏表示Z₃；
- 32层下来，每个Token已经吸收了全句上下文精华。最终得到 "马斯克" 的新表示 (比如为 [2.5, 1.2])；
- 这样充分融合上下文“精华”的表示，用来预测下一个词时，将获得正确预测 (如预测出 "特斯拉")。

```
我 欣赏 马斯克 → 特斯拉
```

正因为Q/K/V过程实际上构建了逐层明确化、丰富化的上下文信息表达，最后进行词表预测时才更加精准、合适。

------

#### 一个核心精简总结：

- Q：每个词每一层关注什么
- K：每个词每一层的身份标签
- V：每个词所携带的信息
- 它们并不直接用于生成下一个token，而是通过高效融合上下文信息，产生融合了丰富且精确语境的隐藏向量表示 (Z→H_out)；
- 最终使用层层累加融合后的隐藏表示H_final去做下一个token预测，这才是对应Transformer QKV机制真正的预测意义与目的。



## **展开查询向量（Q）到多头格式**

在 LLaMA-3 中，每个注意力层有 32 个注意力头。
如果整层的查询权重矩阵 `wq.weight` 的形状是 **[4096 × 4096]**，那么需要把它按「头数 × 每头维度 × 原始维度」拆开，才能让 32 个头并行地各自做矩阵乘法。

> 4096（特征维度） ÷ 32（头数） = 128（每头维度）

```
# 读取第一层的查询（WQ）权重
q_layer0 = model["layers.0.attention.wq.weight"]        # [4096, 4096]

# 计算每个头负责的维度大小
head_dim = q_layer0.shape[0] // n_heads                 # 4096 // 32 = 128

# 重新 reshape 成 [头数, 每头维度, 原始维度]
q_layer0 = q_layer0.view(n_heads, head_dim, dim)        # [32, 128, 4096]

print(q_layer0.shape)                                   # torch.Size([32, 128, 4096])
```



| 维度 | 含义                                  |
| ---- | ------------------------------------- |
| 32   | 注意力头的数量 (`n_heads`)            |
| 128  | 每个头自己的查询向量维度 (`head_dim`) |
| 4096 | token 原始特征维度 (`dim`)            |

**为什么要这样拆？**

1. 多头注意力要求每个头独立地在子空间里计算注意力，因此需要把 WQ 分成 32 份。
2. 拆完后，同一个 token 的 4096 维向量会被分成 32 份（每份 128 维），分别与 32 份查询权重做乘法，得到 32 组子空间的 Q 向量。
3. 各头并行完成后，会把 32 份结果再拼接回来，继续后续的 Wₒ 投影、残差、Norm 等操作。这样既增加表达能力，也充分利用并行计算资源。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDL9PJWlcV3BrgMNzheLL3r5s8dib0pWGSDTo0xssKdbmXOuUanTB1xIA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

### 实现第一层的第一个注意力头

### 实现第一层的第一个注意力头

在上一节中，我们已经把整层查询权重 `wq.weight` reshape 成
`q_layer0  →  [n_heads, head_dim, dim] = [32, 128, 4096]`。
现在只需从中取出第 0 号头 (head-0) 的权重矩阵即可：

```
# 取第一层第 0 个头的查询权重
q_layer0_head0 = q_layer0[0]        # shape: [128, 4096]
print(q_layer0_head0.shape)         # → torch.Size([128, 4096])
```



解释：

| 维度 | 含义                                  |
| ---- | ------------------------------------- |
| 128  | head-0 专属的子空间维度（`head_dim`） |
| 4096 | 输入 token 的原始特征维度 (`dim`)     |

接下来即可用该矩阵去计算 **每个 token 在 head-0 中的查询向量**：

```
# token_embeddings 形状: [seq_len, 4096]
q_head0_per_token = token_embeddings @ q_layer0_head0.T   # [seq_len, 128]
```



这样就完成了“第一层 - 第 0 个注意力头”的 Q 向量生成步骤；
后续步骤同理再取对应的 W K、W V，完成 K、V 的计算与注意力打分。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDI8ibpWO6bfMJmuShJ46chrVlDPrI83Ebj1tD6KTSv5PaK0GB66Yzic7w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

### 将嵌入矩阵乘以查询权重，得到 Q 向量

我们现在把序列的嵌入向量 `token_embeddings` 与第一层第 0 号注意力头的查询权重 `q_layer0_head0` 相乘，得到 **每个 token 在该头上的查询向量 (`q_per_token`)**。

```
# token_embeddings:  [17, 4096]   17 个 token，每个 4096 维
# q_layer0_head0.T:  [4096, 128]  头 0 的查询权重（已转置）
q_per_token = torch.matmul(token_embeddings, q_layer0_head0.T)

print(q_per_token.shape)          # 结果：torch.Size([17, 128])
```



#### 形状理解

| 张量                   | 形状            | 含义                                       |
| ---------------------- | --------------- | ------------------------------------------ |
| `token_embeddings`     | `[17, 4096]`    | 17 个 token 的嵌入向量                     |
| `q_layer0_head0.T`     | `[4096, 128]`   | 查询权重（转置后）；128 = 每头维度         |
| **结果 `q_per_token`** | **`[17, 128]`** | 每个 token 在 **头 0** 上的 128 维查询向量 |

- **为什么得到 `[17 × 128]`？**
  矩阵乘法 `[17, 4096] · [4096, 128] → [17, 128]`。
  17 行对应 17 个 token，128 列对应该注意力头的子空间维度。
- **接下来做什么？**
  这些查询向量将与所有 token 的 K 向量做点积，计算注意力得分；然后用 soft-max 得到权重，再去加权各 V 向量，生成该头的输出 Z。随后再拼接所有头的 Z，完成多头注意力的全部流程。

这样就完成了**“第一层-第 0 头”** 的 Q 向量计算，为后续注意力打分奠定了基础。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDeWOX41w63Jg0q6dVGBzYkbRftkXymhZ8ZHCzjwwTSI2yvxJ8xmK6XA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

### 查询向量拆成多头的理解

下面把「我 欣赏 马斯克」这个极简示例继续往下推，专门解释

1. 为什么要把查询权重 WQ 拆成“多头”；
2. 拿出 **第 0 号头** 后，怎样算出每个 token 的 128 维查询向量；
3. 这些向量随后会怎样进入注意力打分。

为了既能和真实 LLaMA-3 的维度对齐，又能让数学量级看得懂，我分成两层叙述：

- 先用**真实维度数字**（32 头 × 128 维）告诉你形状怎么来的；
- 再用**袖珍 4 头 × 4 维**的小算例，把公式跑一遍，确保“看得见数字”。

------

#### 真实维度：为什么会有 [32 × 128 × 4096]

##### 整层查询权重

```
WQ                # 形状：4096 × 4096
```

- 行数 4096 = 输出维度
- 列数 4096 = 输入 token 的特征维度

##### 拆成 32 个头

```
n_heads  = 32
head_dim = 4096 // 32            # 128
WQ_heads = WQ.view(32, 128, 4096) # [头数, head_dim, dim]
```



得到张量形状 `[32 , 128 , 4096]`：

| 维度 | 含义                          |
| ---- | ----------------------------- |
| 32   | 头的数量 (`n_heads`)          |
| 128  | 每头自己的子空间维度          |
| 4096 | 输入 token 的特征维度 (`dim`) |

这样做的目的：**让 32 个头可以并行**地各自做 `Q = E @ WQ_headᵀ`，提高表达能力和计算效率。

------

##### 取第 0 号头的查询权重并算 Q 向量

```
WQ_h0 = WQ_heads[0]        # [128, 4096]
Q_h0  = token_embeddings @ WQ_h0.T   # [seq_len, 128]
```

- `token_embeddings`（句长 × 4096）与 `WQ_h0.T`（4096 × 128）相乘

- 结果

  ```
  Q_h0
  ```

  形状为

  ```
  [seq_len, 128]
  ```

  - 其中 `seq_len = 3`（“我 欣赏 马斯克”）
  - 每个 token 得到 **128 维** 查询向量，专属于 head-0

------

#### 袖珍 4 头 × 4 维小算例

为了让数字可见，把 4096 → 16，32 头 → 4 头，head_dim → 4。
用一句“一共 4 个 token”的假场景跑一下公式：

###### 准备

```
n_heads = 4
head_dim = 4
dim      = 16
seq_len  = 3          # 我、欣赏、马斯克
```

随机造一个小型 WQ（16×16），reshape：

```
WQ_heads.shape  →  [4, 4, 16]
```

###### 取第 0 号头权重

```
WQ_h0           # [4, 16]
```

###### 3 3 个 token 的嵌入（3×16）乘上 WQ_h0.T（16×4）

```
Q_h0 = E  @  WQ_h0.T    # 得到 (3 × 4)：
┌─────────────┐
│ q_我        │  (1×4)
│ q_欣赏      │  (1×4)
│ q_马斯克    │  (1×4)
└─────────────┘
```

此时就得到了**“第 0 号头”**想要的查询向量，每个 token 4 维。
后面步骤完全同单头 Attention：

1. 拿对应的 `K_h0`（同样算出来，形状 `[seq_len, 4]`）。
2. 每行 Q 点积 Kᵀ → `[seq_len, seq_len]` 得分矩阵。
3. softmax → 权重 α。
4. 权重 α 乘 `V_h0` → 得到 Z_h0（ `[seq_len, 4]` ）。
5. **4 个头**各自算完 Z 后再拼接成 `[seq_len, 16]`，乘 W_O，进入残差 / Norm / FFN。

#### 和「马斯克」那条主线对照

- 在真实 LLaMA-3 中，我们确实取 **“马斯克”** 这个 token 的最终隐藏向量（融合了 32 个头 × 32 层的上下文信息）去做词表投影，预测出“特斯拉”。
- 这里展示的“拆 WQ → 取第 0 头 → 得 [seq_len, 128] 的 Q 向量”就是 **第一层·第一头** 的最开始一步。
- 只有把 32 个头都算完、再跑完 32 层，才能得到那条例子里用来投影的 `h_final(马斯克)`。

------

#### 小结一句

> **拆成 [32, 128, 4096] → 取 head-0 → 乘嵌入**
> 只是整个注意力大链条的起步动作。
> 它保证每个 token 能在 32 个不同“子空间”里分别提问（Q），进而获得 32 份互补的上下文视角，最终让 LLaMA-3 生成更准确的下一个 token。





截止到目前，我们介绍完的内容处于下图位置：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRMKgyW0BicEvaarQAXdQpJicnjicjZsHUGiaqib4xnHWOExnFSjlVqhd1plg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

将图片放大：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRndwdop5tbzYkKvnlZnE0S6ibbJMia3wlrvYpJmfxkC6QCBSfmelYiagRA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)接下来，我们将从上图红框位置开始介绍，直到生成最终推理结果。由于后续步骤太多，本文不会罗列所有步骤，只梳理整体步骤，并对关键点进行说明，以帮助读者理解。

下面我们重新将上面那个极简示例，用更加详细且完整的方式展开，并尽可能丰满具体地阐述 Transformer 从输入到预测下一个 token（例如从“我 欣赏 马斯克”预测出“特斯拉”）的机制。「权重矩阵→Q/K/V向量→Attention→多头拼接→FFN→预测」每一步都会充分解释清楚为什么要这么做、具体怎么做。

#### Transformer 处理的完整流程概述

我们以一个句子为起点（假设句子为：“我 欣赏 马斯克”，一共3个token的prompt序列）。我们的目标是使用Transformer模型（如LLaMA-3）来预测接下来的一个合理token，比如“特斯拉”。

Transformer 的整个前向传播过程涉及多个步骤，其中最核心的是**“多头注意力”**（Multi-head Attention）机制，具体又涉及到**Q、K、V 这三个关键矩阵**的作用。下面完整梳理：

完整流程为：

```
输入Embedding → 线性变换获得QKV → 加入位置编码(RoPE) → 计算注意力权重 → softmax归一化 → 注意力与V相乘 → 拼接多头输出 → 输出投影 → 残差连接和前馈网络(FFN) → 获得每层输出  
→多层堆叠(32层)→ 得到最终隐藏表示 → 词表投影预测下一个token
```



我们接下来一步步展开每个步骤：

------

#### 二、详细一步步解释（“我 欣赏 马斯克”举例）

#### 💡 步骤1：Token Embedding（将词语转为向量）

为了让模型处理文字，我们把每个单词(“我”、“欣赏”、“马斯克”)转化成一个向量表示。实际模型采用4096维嵌入空间，这里为手算理解压缩到4维：

| Token  | 嵌入向量 (4维示例)   |
| ------ | -------------------- |
| 我     | [1.0, 0.0, 0.0, 0.0] |
| 欣赏   | [0.5, 1.0, 0.5, 0.0] |
| 马斯克 | [1.0, 0.5, 1.0, 1.0] |

此时输入Embedding矩阵的形状为 `[seq_len × dim] = [3×4]`

------

#### 💡 步骤2：线性变换获得Query、Key和Value矩阵

Transformer模型利用三个**训练好的权重矩阵**W_Q、W_K、W_V分别对输入向量进行线性映射，得到Query(Q)、Key(K)、Value(V)：

- 每个权重矩阵形状为 `[dim × dim] = [4×4]` (简单示例)，真实为 `[4096×4096]`

例如，“马斯克”的Q、K、V各自意义分别为：

- Q(“马斯克”): 表达马斯克关心序列中哪些token的信息（提出关注的问题）
- K(“马斯克”): 表达马斯克自身的标识特征（自己是什么）
- V(“马斯克”): 表达马斯克携带的具体信息（能给大家的信息是什么）

同样，其他词也有自己的QKV，整体形成：

```
Q = E × W_Qᵀ
K = E × W_Kᵀ
V = E × W_Vᵀ
```



------

#### 💡 步骤3：RoPE相对位置变换 (Rotary Positional Embedding)

之前步骤得到的Q、K中，还没有考虑词语顺序位置关系。例如“我 欣赏 马斯克”和“马斯克 欣赏 我”顺序不同，句意完全变化，我们需要在Q、K中体现位置差别。

Transformer的RoPE具体做法是将Q、K向量拆分为若干个2维小向量视为复数，每个小复数根据其在句子的位置旋转一个角度。这种旋转使得每个词的Q、K自然体现了与其他token的相对位置信息。

------

#### 💡 步骤4：计算注意力得分 (Q对K点积)

此时每个token都有自己的Q、K。
例如，我们用“马斯克”的Q向量(Q₃)和整个句子的所有K向量(K₁、K₂、K₃)进行点积计算：

```
score_马斯克→我 = Q₃ · K₁
score_马斯克→欣赏 = Q₃ · K₂
score_马斯克→马斯克 = Q₃ · K₃
```



这样得到表示“马斯克”关注每个token程度的分数。在真实场景，这个矩阵是`[seq_len×seq_len]`的方形矩阵（此处为3×3）。

------

#### 💡 步骤5：softmax归一化为注意力权重矩阵

将上一步得到的得分矩阵的每一行用softmax函数进行转换，变为每行和为1的概率分布。这些概率即“马斯克”对序列每个元素（包括自己）的关注程度（权重α）。

```
α(马斯克→所有token) = softmax([score_马斯克→我, score_马斯克→欣赏, score_马斯克→马斯克])
```



------

#### 💡 步骤6：注意力权重与V相乘，得到最终token表示Z

利用上面的权重α，根据每个token的权重加权融合所有token的Value(V)信息，产生更深的“上下文”新向量(Z)。
特别地，“马斯克”的新表示：

```
Z(马斯克) = α₁×V₁ + α₂×V₂ + α₃×V₃
```



经过这个步骤，“马斯克”就不再只是单纯表示某词，而是融合了整体上下文信息的表达。

------

#### 💡 步骤7：多头注意力（多个头结果拼接与输出投影）

真实LLaMA有32个这样的注意力头，每头做相同操作，产生自己的Z向量。

```
所有头Z向量拼接 → 乘一次Wₒ矩阵投影到原始维度 → 加上残差连接 → RMSNorm → FFN网络再加一次残差连接
```



这样获得单层Transformer的输出(H_out)，【形状和输入尺寸一致，仍为[seq_len, dim]】。

------

#### 💡 步骤8：经过32层得到最终隐藏表示（H_final）

32层后，每个token获得更深、更充分的上下文表征(H_final)。

- 拿出prompt的句尾token“马斯克”的隐藏向量(H_final_last)用于预测下一个词。

------

#### 💡 步骤9：词表投影预测下一个Token

拿H_final_last向量投影到模型学习到的大量语料库建立的词表(vocabulary)空间中。
例如token“马斯克”的H_final_last用W_out矩阵投影后通过softmax最高概率选择的下个token，假设为“特斯拉”。

最终推断：

```
我 欣赏 马斯克 → 特斯拉
```



若继续每次追加一个词并循环执行上面的步骤，可持续生成完整文本：

```
我 欣赏 马斯克 ， 因为 他 创立 了 特斯拉 。
```



------

#### 💡【本质总结：Q、K、V真实作用与意义】

- Q → 寻找信息（“我关注什么？”）
- K → 提供匹配特征（“我是谁”）
- V → 提供具体语义信息（“我携带什么知识”）

通过点积softmax后的权重，是每个token有效地融合整体信息，产生新表示的钥匙。
最后，只有这样融合充分的上下文表征(H_final)，才能够得到正确而流畅的token预测结果。

Transformer的真正威力正来源于此类精妙的上下文信息理解与融合过程。





## 查询向量的位置编码 (Q 的旋转位置编码 - RoPE)

在前面的步骤中，我们已经为输入句子中的每个 token 得到了各自的查询（Q）向量。但是截止到目前，这些查询向量仅仅包含了 token 本身的语义信息，还没有全面地考虑它们在句子中各自所处的位置信息。

考虑这样一个例子：

> The answer to the ultimate question of life, the universe, and everything is

句子里出现了三次相同的单词 `"the"`。从字面意义和语法上讲，每个 `"the"` 处在句子中的位置以及语境都是完全不同的，因此我们希望，这三个 `"the"` 的查询向量尽管来自相同的单词，但应该根据它们各自位置的差异具有不同的表达。换句话说，我们的查询向量不仅要表达“单词内容”，还要精准地体现出“这个单词在位置上的差别”。

Transformer 中使用一种高效的方法——RoPE (旋转位置嵌入, Rotary Positional Embedding) 来完成这一任务。

### 为什么需要 RoPE？

最初，我们获得的整个查询权重矩阵 (`wq.weight`) 的尺寸为 `[4096, 4096]`。而随着 Transformer 使用了多头注意力机制，我们会把这个巨大的子空间拆分成 32 个小而独立的子空间：

- 每个头负责处理 128 维的 Q 向量 (因为 `4096 ÷ 32 = 128`)。
- 所以整层 Q 向量的维度是 `[token数量, 4096]`，单个头 Q 向量维度则是 `[token数量, 128]`。

接着，我们为了更便于对Q向量进行位置旋转，会把128维向量进一步拆分成64个较小的2维向量对 (因为一个平面向量可以看作一个复数)。

------

### 具体操作说明及代码解析：

我们拿到的第一个头的查询向量（例如 `q_per_token` 的形状为 `[17,128]`，即17个token对应128维查询）进行预处理，随后再用于RoPE旋转：

```
# 第一步：转换为浮点数（精确计算）
q_per_token = q_per_token.float()

# 第二步：将[17,128]重新整理为[17,64,2]，以便做旋转操作
q_per_token_split_into_pairs = q_per_token.view(q_per_token.shape[0], -1, 2) 

print(q_per_token_split_into_pairs.shape)
# 输出 torch.Size([17,64,2])
```



以上代码的操作说明：

- 首先，`.float()` 是为了确保数值精确，在旋转（涉及到复杂数学运算）时，能准确处理小数。
- `.view(q_per_token.shape[0], -1, 2)` 则是对原有查询向量Q的一次简单重塑，从 `[17,128]` 重塑为 `[17,64,2]`。
  这样每个token的128维向量就能看做是64个二维向量的组合，每个二维向量恰好可视为一个复数（实部和虚部）。

需要特别指出的是，上述两行代码还**没有实际进行位置的旋转**，而只是为旋转位置操作做准备操作，即把大向量拆成小维度的复数形式，以便接下来充分利用复数旋转机制。

------

### 下一步：RoPE如何工作？

拆分完成后，我们现在已经获得了形状为 `[token数量,64,2]` 的tensor：

- 每个token现在由64个二维小向量组成 → 可以视作64个复数
- 我们对每个token 64对中的每一向量对进行旋转的操作
- 旋转的角度由token在整个句子中的位置（序号）决定
- 假设我们正在旋转第m个token，则每个token的第i对向量将旋转一个 `m × θ(i)` 的特定角度，其中 m 是当前token的位置，而 θ(i) 是预设的频率系数。

通过这样的RoPE旋转，每个词语的查询和键向量就自然地编码了**相对位置信息**，也就是说，同样的单词 `"the"`，在不同位置上，有了不同的Q/K编码形态。

这一步RoPE完成的位置编码，可以高效地为Transformer模型提供充足的相对位置信息（相比传统的绝对位置嵌入embedding）。

### 小结 - 清晰地回顾一下RoPE的完整步骤：

- **步骤1 (准备Q矩阵)**: 提取单个头(Q_Head)查询向量，初始为 `[token数量, 128]`
- **步骤2 (向量拆分)**: 重塑成 `[token数量, 64, 2]` 二维复数向量形式
- **步骤3 (旋转编码RoPE)**: 为每一小向量(复数)应用特定的旋转变换，在此过程中自然引入Token的相对位置信息
- **步骤4 (复数旋转后拆回)**: 将旋转后的复数形式向量还原回实数表示，重新变回 `[token数量, 128]` 继续后续的注意力打分计算流程。

通过完成RoPE旋转位置编码后的查询、键向量，模型获得带有明确位置上下文信息的表示，对后续进行注意力机制有深远意义：

- Token不仅“知道自己是谁”，更“知道自己在句子中的位置在哪里”；
- 能够精准地区分相同内容(如token是同一个词”的 token)，更细致、更丰富地融合句子信息到上下文表示中；
- 后续的QK计算、注意力权重组合、信息聚合都会更有意义、结果更准确，从而让模型最终给出更高质量、更合理的预测输出。

**用最直观的语言回顾以上内容的一句话总结：**

RoPE 做的事情，就是对每一个token的查询Q（以及键K），根据token在句子中的位置旋转一个独特角度，使得查询和键不仅代表token自身含义，还携带能够彰显位置特征的上下文信息，从而为高效、准确地计算注意力权重做准备。

 

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDia29Dua82HQIsmvB3RYFicwhb9c7mtJsM5ZzrsOMia3zen88Hcic89sictw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDHk4kj62jvEmnyxHrOjyYiaibWtPesPVJTZQKiaeh5sZ2pf5HDicTh34RIg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

```
zero_to_one_split_into_64_parts = torch.tensor(range(64))/64zero_to_one_split_into_64_parts
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDSSWiaU0my2WQsEO2YbOSPJPCvI9r7w1asrT2WzJlH3yicLPgAtkypmcQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

这个张量 `zero_to_one_split_into_64_parts` 可以用于多种场景，比如需要在 [0, 1] 区间内均匀采样的情况。在机器学习和数据处理中，这样的序列常用于归一化处理或作为算法中的参数。

- 
- 

```
freqs = 1.0 / (rope_theta ** zero_to_one_split_into_64_parts)freqs
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDpAKDX1D6febY4kmiaXSufpR1zQnpZG4VyGmicNAfp6gsH1toGwp31GRA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

这段代码使用了之前创建的 `zero_to_one_split_into_64_parts` 张量来计算一个新的张量 `freqs`。这里的计算涉及到指数和倒数的运算，具体步骤如下：

1. `rope_theta` 是一个预定义的常数或变量，其具体值在这段代码中没有给出，但它在这个表达式中起到了基数的作用。

2. `zero_to_one_split_into_64_parts` 是一个从 0 到接近 1 的值的序列，每个值的间隔为 1/64。

3. `rope_theta ** zero_to_one_split_into_64_parts`：这个操作对 `rope_theta` 进行了幂运算，其中指数是 `zero_to_one_split_into_64_parts` 中的每个元素。这意味着对于序列中的每个值，`rope_theta` 被乘方到相应的幂次。结果是 `rope_theta` 的幂次从 `rope_theta^0`（等于 1）到 `rope_theta^(63/64)` 的序列。

4. `1.0 / (rope_theta ** zero_to_one_split_into_64_parts)`：这一步取上一步计算结果的倒数。这样，对于每个元素，原来的幂运算结果被转换为其倒数。

   这个 `freqs` 张量可能用于表示频率或周期性的变化，其中 `rope_theta` 控制着变化的速率或范围。在自然语言处理中，特别是在使用 Transformer 模型时，这种类型的计算常用于生成位置编码。在相对位置编码（ROPE）的上下文中，这种频率的变化可以帮助模型理解和编码输入序列中不同位置之间的相对关系。

例如，如果 `rope_theta` 被设置为一个大于 1 的值，那么随着位置的增加，频率会逐渐减小，这可能对应于更长的周期或更慢的变化率。这样的编码可以帮助模型捕捉长距离的依赖关系，因为相对位置的影响会随着距离的增加而逐渐减弱。

```
freqs_for_each_token = torch.outer(torch.arange(17), freqs)
freqs_cis = torch.polar(torch.ones_like(freqs_for_each_token), freqs_for_each_token)
freqs_cis.shape
# viewing tjhe third row of freqs_cis
value = freqs_cis[3]
plt.figure()
for i, element in enumerate(value[:17]):
    plt.plot([0, element.real], [0, element.imag], color='blue', linewidth=1, label=f"Index: {i}")
    plt.annotate(f"{i}", xy=(element.real, element.imag), color='red')
plt.xlabel('Real')
plt.ylabel('Imaginary')
plt.title('Plot of one row of freqs_cis')
plt.show()
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDkMcyyqjFHiasI2nttLkFCe97BjAGT9ticUpQsA6HjvhQFxrKY9tPrsgA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)


这段代码通过计算频率的外积，将其转换为复数形式，并通过可视化特定行的复数向量，展示了这些复数在复平面上的分布。这种表示形式在处理周期性信号或进行频域分析时非常有用。

现在我们有了每个令牌查询元素的复数（角度变化向量），我们可以将我们的查询（我们分成对的那个）转换为复数，然后通过点积根据位置旋转查询。 

```
q_per_token_as_complex_numbers = torch.view_as_complex(q_per_token_split_into_pairs)q_per_token_as_complex_numbers.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRbhXnBTqic6Yqc1PP9iaN3GqD5vDkOStBZzOAvYicW2DtstIHho5wI2hUg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

```
q_per_token_as_complex_numbers_rotated = q_per_token_as_complex_numbers * freqs_cisq_per_token_as_complex_numbers_rotated.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRCicpIkHdmv72Tichrek8oP8NbQ19A64QQa6veyfj7m67drRictl0cLALg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

在获得旋转向量之后，我们可以通过再次将复数视为实数，将queries作为对重新获取。

```
q_per_token_split_into_pairs_rotated = torch.view_as_real(q_per_token_as_complex_numbers_rotated)q_per_token_split_into_pairs_rotated.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRdJ4wbgOAelB7SY56tGpHNKxUVInnFSC7bHCpbyyIt8tyIUlQaVAibZg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

旋转后的对现在已经合并，我们现在有了一个新的查询向量（旋转查询向量），其形状为 [17x128]，其中 17 是令牌的数量，128 是查询向量的维度。

```
q_per_token_rotated = q_per_token_split_into_pairs_rotated.view(q_per_token.shape)q_per_token_rotated.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRKGOV0IibazJyNSY18ToVFBFJYLpKtVAI3aLcrSCicTs400mrN8dfPLBA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**二、Key矩阵的RoPE更新**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRKBmOFrVxVxkD0BIGVx4wYzjOselS6XmCnXiaHRn8HgtydPjRgoIWz0g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**需要记住的是> 键生成的键向量的维数也是 128> 键的权重只有查询的 1/4，这是因为键的权重是由 4 个头共享的，以减少所需的计算量。> 由于同样的原因，键也会像查询一样被旋转以添加位置信息。 具体步骤不再展开。截止到目前，开头列出的七个步骤中，前两个步骤已经完成： 接下来完成如下步骤：**![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW5x5IHF3BzCe3DOrF9GqyU0fc2NCk6ibR0JcjPwHhmshIDn0vYGhd4IRsDtiaFBec8P35nLMzDuEVQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 

**三、多头注意力**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRV0tmIF0bMTc2TMM6K4YdYXv7gdryV714ZEgLDurnlY0jUYzJVaNKOw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)



我们现在拥有了第一层和第一个头的注意力值 ，现在我将运行一个循环，并对第一层中的每个头执行与上面单元格完全相同的数学运算。 

```

qkv_attention_store = []


for head in range(n_heads):
q_layer0_head = q_layer0[head]
k_layer0_head = k_layer0[head//4] # key weights are shared across 4 heads
v_layer0_head = v_layer0[head//4] # value weights are shared across 4 heads
q_per_token = torch.matmul(token_embeddings, q_layer0_head.T)
k_per_token = torch.matmul(token_embeddings, k_layer0_head.T)
v_per_token = torch.matmul(token_embeddings, v_layer0_head.T)


q_per_token_split_into_pairs = q_per_token.float().view(q_per_token.shape[0], -1, 2)
q_per_token_as_complex_numbers = torch.view_as_complex(q_per_token_split_into_pairs)
q_per_token_split_into_pairs_rotated = torch.view_as_real(q_per_token_as_complex_numbers * freqs_cis[:len(tokens)])
q_per_token_rotated = q_per_token_split_into_pairs_rotated.view(q_per_token.shape)


k_per_token_split_into_pairs = k_per_token.float().view(k_per_token.shape[0], -1, 2)
k_per_token_as_complex_numbers = torch.view_as_complex(k_per_token_split_into_pairs)
k_per_token_split_into_pairs_rotated = torch.view_as_real(k_per_token_as_complex_numbers * freqs_cis[:len(tokens)])
k_per_token_rotated = k_per_token_split_into_pairs_rotated.view(k_per_token.shape)


qk_per_token = torch.matmul(q_per_token_rotated, k_per_token_rotated.T)/(128)**0.5
mask = torch.full((len(tokens), len(tokens)), float("-inf"), device=tokens.device)
mask = torch.triu(mask, diagonal=1)
qk_per_token_after_masking = qk_per_token + mask
qk_per_token_after_masking_after_softmax = torch.nn.functional.softmax(qk_per_token_after_masking, dim=1).to(torch.bfloat16)
qkv_attention = torch.matmul(qk_per_token_after_masking_after_softmax, v_per_token)
qkv_attention = torch.matmul(qk_per_token_after_masking_after_softmax, v_per_token)
qkv_attention_store.append(qkv_attention)


len(qkv_attention_store)
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRdxoaiaQvEejsib19UvgiaQSxW6TU20e6iaiaxgPpvPKK69SI8LJU6icjtD9Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

我们现在拥有了第一层所有32个头的qkv_attention矩阵，接下来我将把所有注意力分数合并成一个大小为[17x4096]的大矩阵

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRCpPZK7enicVDOYsXyZpUPHqfVWmXC8DRjhnkicpKxTcRt5yJrWIVamUQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

\# 权重矩阵，最后步骤之一

```
w_layer0 = model["layers.0.attention.wo.weight"]w_layer0.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRhmmRHRU6w9CPatbyOMFQskbjYpHZdtm3xQ98r2gOsLDicUu3lupKwMQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

这是一个简单的线性层，所以我们只需 Matmul

```
embedding_delta = torch.matmul(stacked_qkv_attention, w_layer0.T)embedding_delta.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRIWpode7f3rGKkVQ1SemicHf0cmW3mqCWdkMicDzDC3PMWTfoJk52INsg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktR29QwjuC3h6RVWegUM7zIynVOCdL7Mc60hknM9Kt6omP9j5AABwmEFQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

现在，我们得到了关注后embedding value after attention，这应该是对original token embeddings的加法。

```
embedding_after_edit = token_embeddings_unnormalized + embedding_deltaembedding_after_edit.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRVLsH8bc7bjuO354ed9M3kfTXrskH43g9GHIJfeZia4tUqBsRhgl9avA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

我们对其进行归一化，然后通过嵌入差值运行一个前馈神经网络。

```
embedding_after_edit_normalized = rms_norm(embedding_after_edit, model["layers.0.ffn_norm.weight"])embedding_after_edit_normalized.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRorbZ48WFF2lWMjetIndR5BTiabbvNFdtwnhcY2K5SoDnfjXczJ85WeQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

## ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktR3wayibCFvh7vqT08CHurUdvITVibe6wHdIHVo6kEVwrxlrojibzZmnrLQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 

## 加载前馈权重并实现前馈网络

llama3使用了SwiGLU前馈网络，这种网络架构非常擅长在模型需要时添加非线性。如今，在大型语言模型（LLMs）中使用这种前馈网络架构已经相当标准：

```
w1 = model["layers.0.feed_forward.w1.weight"]w2 = model["layers.0.feed_forward.w2.weight"]w3 = model["layers.0.feed_forward.w3.weight"]output_after_feedforward = torch.matmul(torch.functional.F.silu(torch.matmul(embedding_after_edit_normalized, w1.T)) * torch.matmul(embedding_after_edit_normalized, w3.T), w2.T)output_after_feedforward.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRDUibAOeS3uu0hedwUA6ibWkDOa4VUicZmbkBSaHxSZUQuyD0nHCteTiaxQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**在第一层之后，我们终于为每个令牌获得了新的编辑过的嵌入**

在完成之前还有31层要走（只差一个for循环） 。你可以将这个编辑过的嵌入想象为包含了第一层上所有询问的信息 <br> 现在，每一层都将对提出的问题编码更多更复杂的查询，直到我们得到一个关于我们需要的下一个令牌的所有信息的嵌入。



```
layer_0_embedding = embedding_after_edit+output_after_feedforwardlayer_0_embedding.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRI3R9tWwTxDyPJ0160s1gNbTzibX2S2Fx3zC88xcIodiaxLYU94AUeWHw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

我们之前所做的一切，都一次完成，每一层都是。

```
final_embedding = token_embeddings_unnormalized
for layer in range(n_layers):
qkv_attention_store = []
layer_embedding_norm = rms_norm(final_embedding, model[f"layers.{layer}.attention_norm.weight"])
q_layer = model[f"layers.{layer}.attention.wq.weight"]
q_layer = q_layer.view(n_heads, q_layer.shape[0] // n_heads, dim)
k_layer = model[f"layers.{layer}.attention.wk.weight"]
k_layer = k_layer.view(n_kv_heads, k_layer.shape[0] // n_kv_heads, dim)
v_layer = model[f"layers.{layer}.attention.wv.weight"]
v_layer = v_layer.view(n_kv_heads, v_layer.shape[0] // n_kv_heads, dim)
w_layer = model[f"layers.{layer}.attention.wo.weight"]
for head in range(n_heads):
q_layer_head = q_layer[head]
k_layer_head = k_layer[head//4]
v_layer_head = v_layer[head//4]
q_per_token = torch.matmul(layer_embedding_norm, q_layer_head.T)
k_per_token = torch.matmul(layer_embedding_norm, k_layer_head.T)
v_per_token = torch.matmul(layer_embedding_norm, v_layer_head.T)
q_per_token_split_into_pairs = q_per_token.float().view(q_per_token.shape[0], -1, 2)
q_per_token_as_complex_numbers = torch.view_as_complex(q_per_token_split_into_pairs)
q_per_token_split_into_pairs_rotated = torch.view_as_real(q_per_token_as_complex_numbers * freqs_cis)
q_per_token_rotated = q_per_token_split_into_pairs_rotated.view(q_per_token.shape)
k_per_token_split_into_pairs = k_per_token.float().view(k_per_token.shape[0], -1, 2)
k_per_token_as_complex_numbers = torch.view_as_complex(k_per_token_split_into_pairs)
k_per_token_split_into_pairs_rotated = torch.view_as_real(k_per_token_as_complex_numbers * freqs_cis)
k_per_token_rotated = k_per_token_split_into_pairs_rotated.view(k_per_token.shape)
qk_per_token = torch.matmul(q_per_token_rotated, k_per_token_rotated.T)/(128)**0.5
mask = torch.full((len(token_embeddings_unnormalized), len(token_embeddings_unnormalized)), float("-inf"))
mask = torch.triu(mask, diagonal=1)
qk_per_token_after_masking = qk_per_token + mask
qk_per_token_after_masking_after_softmax = torch.nn.functional.softmax(qk_per_token_after_masking, dim=1).to(torch.bfloat16)
qkv_attention = torch.matmul(qk_per_token_after_masking_after_softmax, v_per_token)
qkv_attention_store.append(qkv_attention)


stacked_qkv_attention = torch.cat(qkv_attention_store, dim=-1)
w_layer = model[f"layers.{layer}.attention.wo.weight"]
embedding_delta = torch.matmul(stacked_qkv_attention, w_layer.T)
embedding_after_edit = final_embedding + embedding_delta
embedding_after_edit_normalized = rms_norm(embedding_after_edit, model[f"layers.{layer}.ffn_norm.weight"])
w1 = model[f"layers.{layer}.feed_forward.w1.weight"]
w2 = model[f"layers.{layer}.feed_forward.w2.weight"]
w3 = model[f"layers.{layer}.feed_forward.w3.weight"]
output_after_feedforward = torch.matmul(torch.functional.F.silu(torch.matmul(embedding_after_edit_normalized, w1.T)) * torch.matmul(embedding_after_edit_normalized, w3.T), w2.T)
final_embedding = embedding_after_edit+output_after_feedforward
```

**我们现在拥有了最终的嵌入，这是模型对下一个令牌所能做出的最佳猜测**

嵌入的形状与常规令牌嵌入相同，为 [17x4096]，其中17是令牌的数量，4096是嵌入维度。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRXlvziafDZl7jyUgh3FkPYKYhXfiar1jqpHicYI7AvK7pCXRvXw9OofEuw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

 最后，让我们将嵌入解码为令牌值：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktR31IcVNlSDg2zMLUDn1CgHpb8rsYohUXazfoEkcjVHcYlOLvu5qFKmA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRHTffgGmbvswQc4nf40Pib13dz1V3TSxStjA15pUy2XFiaZcjSELiaPXUg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**我们使用最后一个令牌的嵌入来预测下一个值**

希望在我们的情况下是42 。注意：根据《银河系漫游指南》一书，42是“生命、宇宙以及一切终极问题的答案”，大多数现代大型语言模型（LLMs）在这里都会给出42作为答案。

```
logits = torch.matmul(final_embedding[-1], model["output.weight"].T)logits.shape
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktR8QyeGN9oGMh3WLMUYibegx5ZkzibBeyoewyBuDoyVe4BCJ1LoDiaiboWGg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

```
next_token = torch.argmax(logits, dim=-1)next_token
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRf1j9dkFvvzdwthvVtJNia0S1ZpcXibib1viaAO64yx0CUWBBUAMBibuy7AA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRTVWy5cat0GRDDscvQW1r40Nw8PcCnYqVjSRXdgk7A0CnAp9HB34IpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)



```
tokenizer.decode([next_token.item()])
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRgEqGqAlDS81XLJ3LG00mic89mSv9hpPYdIbsX9hQqd0w404GNNticuHg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

参考文献：*https://github.com/naklecha/llama3-from-scratch?tab=readme-ov-file*