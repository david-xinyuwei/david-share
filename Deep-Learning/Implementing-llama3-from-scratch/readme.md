# 从零实现 Llama3 模型

本文旨在全面解析并从零开始实现 LLaMA 3 模型。通过结合理论讲解与实践代码示例，带你深入理解 LLaMA 3 的模型架构、核心原理及关键实现细节。

无论你是机器学习初学者，还是深度学习爱好者，都可以在本文中找到详细且易于上手的指导内容。

**Refer to：**

```
https://github.com/naklecha/llama3-from-scratch.git
https://github.com/wdndev/llama3-from-scratch-zh?tab=readme-ov-file
```

本文主要参考上述文章并增加了备注，以便在关键点进行理解。

## Llama3的整体架构

下图展示了 LLaMA 3 模型的整体架构示意。作为一个大型基于 Transformer 的语言模型，LLaMA 3 由多个核心模块组成，包括输入嵌入层、多个堆叠的 Transformer Block 以及输出预测层。每个 Transformer Block 内部包含多头自注意力机制和前馈神经网络，协同作用实现强大的语言理解与生成能力。

### 查看 LLaMA 3 模型的参数配置

```
import json

with open("Meta-Llama-3-8B/params.json", "r") as f:
    config = json.load(f)

print(config)
```

```
[
    "tok_embeddings.weight",
    "layers.0.attention.wq.weight",
    "layers.0.attention.wk.weight",
    "layers.0.attention.wv.weight",
    "layers.0.attention.wo.weight",
    "layers.0.feed_forward.w1.weight",
    "layers.0.feed_forward.w3.weight",
    "layers.0.feed_forward.w2.weight",
    "layers.0.attention_norm.weight",
    "layers.0.ffn_norm.weight",
    "layers.1.attention.wq.weight",
    "layers.1.attention.wk.weight",
    "layers.1.attention.wv.weight",
    "layers.1.attention.wo.weight",
    "layers.1.feed_forward.w1.weight",
    "layers.1.feed_forward.w3.weight",
    "layers.1.feed_forward.w2.weight",
    "layers.1.attention_norm.weight",
    "layers.1.ffn_norm.weight",
    "layers.2.attention.wq.weight"
]
```



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



## 读取模型文件

在理解模型架构和参数基础上，下一步是实际使用模型进行数据处理。这包括如何加载词表，进行文本编码，以及如何加载模型的权重。

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/model.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/model.png)

```
# 加载模型权重
model = torch.load("Meta-Llama-3-8B-Instruct/consolidated.00.pth")
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

## 将文本转换为 token

在自然语言处理模型中，文本数据需要经过分词器（Tokenizer）转换为模型能够处理的数字序列（即 tokens）。这些 tokens 是模型输入的基础，它们将文本映射成数字ID，便于后续的嵌入计算和模型处理。

这里使用 tiktoken（OpenAI 的库）作为分词器

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/tokens.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/tokens.png)

```
prompt = "the answer to the ultimate question of life, the universe, and everything is "

# 编码为token
tokens = [128000] + tokenizer.encode(prompt)
print(tokens)
tokens = torch.tensor(tokens)

# 将每个 token 解码为对应的文本
prompt_split_as_tokens = [tokenizer.decode([token.item()]) for token in tokens]
print(prompt_split_as_tokens)
```



```
    [128000, 1820, 4320, 311, 279, 17139, 3488, 315, 2324, 11, 279, 15861, 11, 323, 4395, 374, 220]
    ['<|begin_of_text|>', 'the', ' answer', ' to', ' the', ' ultimate', ' question', ' of', ' life', ',', ' the', ' universe', ',', ' and', ' everything', ' is', ' ']
```

到目前为止，我们处理的17个令牌（形状为 [17×1] 的序列）已经被转换为对应的嵌入向量，形成了一个形状为 [17×4096] 的张量。也就是说，每个令牌被映射成一个长度为4096的向量，总共有17个这样的向量。

下图通过可视化验证了该句子被成功分解为17个token。

## 将 token 转换为 embedding

这里使用内置的神经网络模块

无论如何, `[17x1]` token 现在是 `[17x4096]`，即每个 token 的长度为 4096 的 embeddings

注意：跟踪 shapes，这样一切将变得理解更容易

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/embeddings.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/embeddings.png)

```
# 加载嵌入层并复制权重
embedding_layer = torch.nn.Embedding(vocab_size, dim)
embedding_layer.weight.data.copy_(model["tok_embeddings.weight"])

# 获取未归一化的 token 嵌入
token_embeddings_unnormalized = embedding_layer(tokens).to(torch.bfloat16)
token_embeddings_unnormalized.shape
```



```
torch.Size([17, 4096])
```



## 接下来使用 RMS 归一化嵌入

接下来，我们对嵌入向量应用 RMS 归一化（RMSNorm）进行标准化处理，以稳定训练并提升模型表现。该归一化操作对应于模型结构图中的标注位置，作为 Transformer 第一层的输入预处理步骤。

请注意，经过此步骤后 shapes 不变， 只是值被归一化

接下来，我们对嵌入向量应用 RMS 归一化（RMSNorm）进行标准化处理，以稳定训练并提升模型表现。该归一化操作对应于模型结构图中的标注位置，作为 Transformer 第一层的输入预处理步骤。![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDI9k3JsQibTVEGhLOTMdfibT3MVcAHicicIhyXfoFuk162QQrlwHVdBibl3g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

需要注意的是，需要一个 norm_eps（来自配置）以避免不小心将 RMS 设置为 0 并导致除以 0 的情况

这是公式:

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/rms.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/rms.png)

```
# rms 归一化函数

# def rms_norm(tensor, norm_weights):
#     rms = (tensor.pow(2).mean(-1, keepdim=True) + norm_eps)**0.5
#     return tensor * (norm_weights / rms)

def rms_norm(tensor, norm_weights):
    return (tensor * torch.rsqrt(tensor.pow(2).mean(-1, keepdim=True) + norm_eps)) * norm_weights
```



# 构建第一个 Transformer 层

### 归一化

从模型字典中访问 `layer.0` （这是第一层）

归一化后 shapes 仍然是 `[17x4096]`， 与嵌入相同但已归一化

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/norm.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/norm.png)

```
# 归一化token嵌入
token_embeddings = rms_norm(token_embeddings_unnormalized, model["layers.0.attention_norm.weight"])
token_embeddings.shape
```



```
torch.Size([17, 4096])
```



### 从头实现注意力机制



加载第一个 Transformer 层的注意力头

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/qkv.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/qkv.png)

当我们从模型中加载 `query`， `key`，`value` 和 `output` 向量时，注意到 shapes 分别为 `[4096x4096]`， `[1024x4096]`， `[1024x4096]`， `[4096x4096]`

乍一看这有些奇怪，因为在理想情况下我们希望每个头单独拥有各自的 q，k，v 和 o

这里作者将其捆绑在一起，为什么会这样呢? 因为这样有助于并行化注意力头的计算

将展开所有内容...

```
# 打印第一个层的注意力权重 shapes
print(
    model["layers.0.attention.wq.weight"].shape,
    model["layers.0.attention.wk.weight"].shape,
    model["layers.0.attention.wv.weight"].shape,
    model["layers.0.attention.wo.weight"].shape
)
```



```
torch.Size([4096, 4096]) 
torch.Size([1024, 4096]) 
torch.Size([1024, 4096]) 
torch.Size([4096, 4096])
```



### 展开 query



在下一节中，将展开多个注意力头的 query，得到的 shapes 为 `[32x128x4096]`

这里的 32 是 Llama3 的注意力头数量，128 是 query 向量的大小，4096 是 token 嵌入的大小

```
# reshape query 权重为[头数，头维度，嵌入维度]

q_layer0 = model["layers.0.attention.wq.weight"]
head_dim = q_layer0.shape[0] // n_heads
q_layer0 = q_layer0.view(n_heads, head_dim, dim)
q_layer0.shape
```



```
torch.Size([32, 128, 4096])
```



### 实现第一层的第一个头



这里查询了第一个层的第一个头的 `query` 权重矩阵，其大小为 `[128x4096]`

```
q_layer0_head0 = q_layer0[0]
q_layer0_head0.shape
```



```
torch.Size([128, 4096])
```



### 现在将 query 权重与 token 嵌入相乘，以获得每个 token 的 query



这里可以看到得到的 shape 是 `[17x128]`， 这是因为有 17 个 token，每个 token 有一个长度为 128 的 query

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/q_per_token.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/q_per_token.png)

```
q_per_token = torch.matmul(token_embeddings, q_layer0_head0.T)
q_per_token.shape
```



```
    torch.Size([17, 128])
```



## 位置编码



当前，每个 token 都有一个 query 向量，但如果你想一想 -- 其实各个 query 向量并不知道它们在 prompt 中的位置。

```text
query: "the answer to the ultimate question of life, the universe, and everything is "
```



在我示例 prompt 中，使用了三次 `"the"`，需要根据它们在 prompt 中的位置为每个 `"the"` token 生成不同的 `query` 向量（每个长度为128）。可以使用 RoPE（旋转位置编码）来实现这一点。

### RoPE



来看看这个视频(我就是看的这个)可以理解其中的数据学逻辑。 https://www.youtube.com/watch?v=o29P0Kpobz0&t=530s

> 国内B站视频链接：[Rotary Positional Embeddings Combining Absolute and Relative](https://www.bilibili.com/video/BV1nt421N7U5/?vd_source=6bc8f793c75740c7bcfb8e281f986a8e&t=530s)

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/rope.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/rope.png)

```
q_per_token_split_into_pairs = q_per_token.float().view(q_per_token.shape[0], -1, 2)
q_per_token_split_into_pairs.shape
```



```
torch.Size([17, 64, 2])
```



这里为 prompt 中每个位置生成了旋转位置编码。可以看到，这些编码是正弦和余弦函数的组合。

在上的步骤里, 将 `query` 向量分成对, 并对每对应用旋转角度移位!

现在有一个大小为 `[17x64x2]` 的向量，这是针对 prompt 中的每个 token 将 128 个长度的 query 分为 64 对！ 这 64 对中的每一对都将旋转 `m*(theta)`，其中 `m` 是旋转查询的 token 的位置！

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/qsplit.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/qsplit.png)

## 使用复数点积计算旋转向量



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/freq_cis.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/freq_cis.png)

```
zero_to_one_split_into_64_parts = torch.tensor(range(64))/64
zero_to_one_split_into_64_parts
```



```
tensor([0.0000, 0.0156, 0.0312, 0.0469, 0.0625, 0.0781, 0.0938, 0.1094, 0.1250,
        0.1406, 0.1562, 0.1719, 0.1875, 0.2031, 0.2188, 0.2344, 0.2500, 0.2656,
        0.2812, 0.2969, 0.3125, 0.3281, 0.3438, 0.3594, 0.3750, 0.3906, 0.4062,
        0.4219, 0.4375, 0.4531, 0.4688, 0.4844, 0.5000, 0.5156, 0.5312, 0.5469,
        0.5625, 0.5781, 0.5938, 0.6094, 0.6250, 0.6406, 0.6562, 0.6719, 0.6875,
        0.7031, 0.7188, 0.7344, 0.7500, 0.7656, 0.7812, 0.7969, 0.8125, 0.8281,
        0.8438, 0.8594, 0.8750, 0.8906, 0.9062, 0.9219, 0.9375, 0.9531, 0.9688,
        0.9844])
```



```
freqs = 1.0 / (rope_theta ** zero_to_one_split_into_64_parts)
freqs
```



```
tensor([1.0000e+00, 8.1462e-01, 6.6360e-01, 5.4058e-01, 4.4037e-01, 3.5873e-01,
            2.9223e-01, 2.3805e-01, 1.9392e-01, 1.5797e-01, 1.2869e-01, 1.0483e-01,
            8.5397e-02, 6.9566e-02, 5.6670e-02, 4.6164e-02, 3.7606e-02, 3.0635e-02,
            2.4955e-02, 2.0329e-02, 1.6560e-02, 1.3490e-02, 1.0990e-02, 8.9523e-03,
            7.2927e-03, 5.9407e-03, 4.8394e-03, 3.9423e-03, 3.2114e-03, 2.6161e-03,
            2.1311e-03, 1.7360e-03, 1.4142e-03, 1.1520e-03, 9.3847e-04, 7.6450e-04,
            6.2277e-04, 5.0732e-04, 4.1327e-04, 3.3666e-04, 2.7425e-04, 2.2341e-04,
            1.8199e-04, 1.4825e-04, 1.2077e-04, 9.8381e-05, 8.0143e-05, 6.5286e-05,
            5.3183e-05, 4.3324e-05, 3.5292e-05, 2.8750e-05, 2.3420e-05, 1.9078e-05,
            1.5542e-05, 1.2660e-05, 1.0313e-05, 8.4015e-06, 6.8440e-06, 5.5752e-06,
            4.5417e-06, 3.6997e-06, 3.0139e-06, 2.4551e-06])
```



```
freqs_for_each_token = torch.outer(torch.arange(17), freqs)
freqs_cis = torch.polar(torch.ones_like(freqs_for_each_token), freqs_for_each_token)
freqs_cis.shape

# 查看freqs_cis的第三行
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



[![png](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/implllama3_30_0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/implllama3_30_0.png)

### 现在每个 token 的 query 元素都有一个复数（角度变化向量）



可以将 query（将其拆分成对）转换为复数，然后进行点积以根据位置旋转查询

```
q_per_token_as_complex_numbers = torch.view_as_complex(q_per_token_split_into_pairs)
q_per_token_as_complex_numbers.shape
```



```
torch.Size([17, 64])
```



```
q_per_token_as_complex_numbers_rotated = q_per_token_as_complex_numbers * freqs_cis
q_per_token_as_complex_numbers_rotated.shape
```



```
torch.Size([17, 64])
```



### 得到旋转向量后



可以通过再次将复数看作实数来返回成对的 query

```
q_per_token_split_into_pairs_rotated = torch.view_as_real(q_per_token_as_complex_numbers_rotated)
q_per_token_split_into_pairs_rotated.shape
```



```
torch.Size([17, 64, 2])
```



旋转对现在已合并，现在有了一个新的 query 向量（旋转 query 向量），其 shape 为 `[17x128]`，其中 17 是 token 的数量，128 是 query 向量的维度

```
q_per_token_rotated = q_per_token_split_into_pairs_rotated.view(q_per_token.shape)
q_per_token_rotated.shape
```



```
torch.Size([17, 128])
```



# keys（几乎与 query 一模一样）



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/keys.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/keys.png)

我是个懒鬼，所以不打算详细讲 keys 的数学过程，只需要记住以下几点：

- keys 生成的 key 向量的维度也是 128
- **keys 的权重只有 query 的 1/4，因为 keys 的权重在 4 个头之间共享，以减少计算量**
- keys 也像 query 一样被旋转以添加位置信息，其原因相同

```
k_layer0 = model["layers.0.attention.wk.weight"]
k_layer0 = k_layer0.view(n_kv_heads, k_layer0.shape[0] // n_kv_heads, dim)
k_layer0.shape
```



```
torch.Size([8, 128, 4096])
```



```
k_layer0_head0 = k_layer0[0]
k_layer0_head0.shape
```



```
torch.Size([128, 4096])
```



```
k_per_token = torch.matmul(token_embeddings, k_layer0_head0.T)
k_per_token.shape
```



```
torch.Size([17, 128])
```



```
k_per_token_split_into_pairs = k_per_token.float().view(k_per_token.shape[0], -1, 2)
k_per_token_split_into_pairs.shape
```



```
torch.Size([17, 64, 2])
```



```
k_per_token_as_complex_numbers = torch.view_as_complex(k_per_token_split_into_pairs)
k_per_token_as_complex_numbers.shape
```



```
torch.Size([17, 64])
```



```
k_per_token_split_into_pairs_rotated = torch.view_as_real(k_per_token_as_complex_numbers * freqs_cis)
k_per_token_split_into_pairs_rotated.shape
```



```
torch.Size([17, 64, 2])
```



```
k_per_token_rotated = k_per_token_split_into_pairs_rotated.view(k_per_token.shape)
k_per_token_rotated.shape
```



```
torch.Size([17, 128])
```



## 现在，已经有了每个 token 的旋转后的 query 和 key



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/keys0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/keys0.png)

每个 query 和 key 的 shape 都是 `[17x128]`。

## 接下来，将 query 和 key 的矩阵相乘



这样做会得到每一个 token 相互映射的分数

这个分数描述了每个 token 的 query 与每个 token 的 key 的相关度。这就是自注意力 :)

注意力得分矩阵（qk_per_token）的 shape 是 `[17x17]`，其中 17 是 prompt 中的 token 数量

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/qkmatmul.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/qkmatmul.png)

```
qk_per_token = torch.matmul(q_per_token_rotated, k_per_token_rotated.T)/(head_dim)**0.5
qk_per_token.shape
```



```
torch.Size([17, 17])
```



# 现在必须屏蔽 QK 分数



在 llama3 的训练过程中，未来的 token qk 分数被屏蔽。

为什么？因为在训练过程中，只学习使用过去的 token 来预测 token 。

因此，在推理过程中，将未来的 token 设置为零。

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/mask.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/mask.png)

```
def display_qk_heatmap(qk_per_token):
    _, ax = plt.subplots()
    im = ax.imshow(qk_per_token.to(float).detach(), cmap='viridis')
    ax.set_xticks(range(len(prompt_split_as_tokens)))
    ax.set_yticks(range(len(prompt_split_as_tokens)))
    ax.set_xticklabels(prompt_split_as_tokens)
    ax.set_yticklabels(prompt_split_as_tokens)
    ax.figure.colorbar(im, ax=ax)
    
display_qk_heatmap(qk_per_token)
```




[![png](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/implllama3_50_0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/implllama3_50_0.png)​

```
mask = torch.full((len(tokens), len(tokens)), float("-inf"), device=tokens.device)
mask = torch.triu(mask, diagonal=1)
mask
```



```
tensor([[0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf, -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., -inf],
        [0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]])
```



```
qk_per_token_after_masking = qk_per_token + mask
display_qk_heatmap(qk_per_token_after_masking)
```




[![png](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/implllama3_52_0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/implllama3_52_0.png)​

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/softmax.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/softmax.png)

```
qk_per_token_after_masking_after_softmax = torch.nn.functional.softmax(qk_per_token_after_masking, dim=1).to(torch.bfloat16)
display_qk_heatmap(qk_per_token_after_masking_after_softmax)
```




[![png](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/implllama3_54_0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/implllama3_54_0.png)​

## values (注意力机制的最后部分)



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/value.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/value.png)

这些分数（0-1）用于确定每个 token 中使用了多少 value 矩阵

> these scores (0-1) are used to determine how much of value matrix is used per token

和 key 一样，value 权重也在每 4 个注意力头之间进行共享（以节省计算量）

因此，下面的 value 权重矩阵的 shape 为 `[8x128x4096]`

```
v_layer0 = model["layers.0.attention.wv.weight"]
v_layer0 = v_layer0.view(n_kv_heads, v_layer0.shape[0] // n_kv_heads, dim)
v_layer0.shape
```



```
torch.Size([8, 128, 4096])
```



llama3的第一层，第一个头的权值矩阵如下所示：

```
v_layer0_head0 = v_layer0[0]
v_layer0_head0.shape
```



```
torch.Size([128, 4096])
```



## value 向量



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/v0.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/v0.png)

现在使用 value 权重来获取每个 token 的注意力值，其大小为 `[17x128]`，其中 17 是 prompt 中的 token 数，128 是每个 tokene 的 value 向量的维度

```
v_per_token = torch.matmul(token_embeddings, v_layer0_head0.T)
v_per_token.shape
```



```
torch.Size([17, 128])
```



## 注意力(attention)



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/attention.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/attention.png)

和每个 token 的 value 相乘后得到的注意力向量的 shape 为 `[17*128]`

```
qkv_attention = torch.matmul(qk_per_token_after_masking_after_softmax, v_per_token)
qkv_attention.shape
```



```
torch.Size([17, 128])
```



# 多头注意力 (multi head attention)



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/heads.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/heads.png)

现在已经有了第一层和第一个头的注意力值

现在将运行一个循环，并执行与上面单元格中相同的数学运算，但只针对第一层中的每个头

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



```
32
```



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/stacked.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/stacked.png)

现在有了第一个层的 32 个头的 qkv_attention 矩阵，接下来将把所有注意力分数合并成一个大矩阵，大小为 `[17x4096]`

```
stacked_qkv_attention = torch.cat(qkv_attention_store, dim=-1)
stacked_qkv_attention.shape
```



```
torch.Size([17, 4096])
```



# 权重矩阵，最后几步之一



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/weightmatrix.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/weightmatrix.png)

对于第0层，最后要做的一件事是，将权重矩阵相乘

```
w_layer0 = model["layers.0.attention.wo.weight"]
w_layer0.shape
```



```
torch.Size([4096, 4096])
```



### 这是一个简单的线性层，所以只需要进行乘法运算



```
embedding_delta = torch.matmul(stacked_qkv_attention, w_layer0.T)
embedding_delta.shape
```



```
torch.Size([17, 4096])
```



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/afterattention.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/afterattention.png)

注意之后，现在有了嵌入值的变化，应该将其添加到原始的 token embeddings 中

```
embedding_after_edit = token_embeddings_unnormalized + embedding_delta
embedding_after_edit.shape
```



```
torch.Size([17, 4096])
```



## 将其归一化，然后运行一个前馈神经网络



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/norm_after.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/norm_after.png)

```
embedding_after_edit_normalized = rms_norm(embedding_after_edit, model["layers.0.ffn_norm.weight"])
embedding_after_edit_normalized.shape
```



```
torch.Size([17, 4096])
```



## 加载 FFN 权重并实现前馈网络



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/swiglu.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/swiglu.png)

在 llama3 中，使用了 `SwiGLU` 前馈网络，这种网络架构非常擅长非线性计算。

如今，在 LLMS 中使用这种前馈网络架构是相当常见的

```
w1 = model["layers.0.feed_forward.w1.weight"]
w2 = model["layers.0.feed_forward.w2.weight"]
w3 = model["layers.0.feed_forward.w3.weight"]
output_after_feedforward = torch.matmul(torch.functional.F.silu(torch.matmul(embedding_after_edit_normalized, w1.T)) * torch.matmul(embedding_after_edit_normalized, w3.T), w2.T)
output_after_feedforward.shape
```



```
torch.Size([17, 4096])
```



# 在第一层之后，终于为每个 token 编辑了新的 EMBEDDINGS



离结束还剩 31 层（一层 for 循环）

可以将经过编辑的 embedding 想象为包含有关第一层上提出的所有 query 的信息

现在，对所有提出的问题每一层都会对 query 进行越来越复杂的编码，直到得到一个 embedding，其中包含了需要的下一个 token 的所有信息。

```
layer_0_embedding = embedding_after_edit+output_after_feedforward
layer_0_embedding.shape
```



```
torch.Size([17, 4096])
```



# 整合



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/god.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/god.png)

就是这样。 之前为每一层所做的一切都需要一次性完成。

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



# 得到最终 Embedding，对下一个 token 做预测



embedding 的 shape 与常规 token embedding shape `[17x4096]` 相同，其中 17 是 token 数量，4096 是 embedding 维度

[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/last_norm.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/last_norm.png)

```
final_embedding = rms_norm(final_embedding, model["norm.weight"])
final_embedding.shape
```



```
torch.Size([17, 4096])
```



# 最后，将 embedding 解码为 token value



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/finallayer.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/finallayer.png)

将使用输出解码器将最终 embedding 转换为 token。

```
model["output.weight"].shape
```



```
torch.Size([128256, 4096])
```



# 使用最后一个 token 的 embedding 来预测下一个值



希望在我们预料之内, 42 :)

注意：根据《银河系漫游指南》书中提到，“生命、宇宙和一切的终极问题的答案是 42 ” 。大多数现代语言模型在这里应该会回答 42，这应该能验证我们的整个代码！祝我好运 :)

```
logits = torch.matmul(final_embedding[-1], model["output.weight"].T)
logits.shape
```



```
torch.Size([128256])
```



### 模型预测的 token 编号是 2983，这是否代表 42 的 token 编号？



这已经是代码的最后一部分了，希望你已经信心满满 :)

```
next_token = torch.argmax(logits, dim=-1)
next_token
```



```
tensor(2983)
```



# 解码



[![img](https://github.com/wdndev/llama3-from-scratch-zh/raw/main/images/42.png)](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/42.png)

```
tokenizer.decode([next_token.item()])
```



## 备注1：注意力层QKV权重矩阵的作用的理解

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



#### 如果用更简单的直观比喻理解（现实生活的类比）：

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



## 备注二：查询向量拆成多头的理解

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





## 备注3：查询向量的位置编码的理解 (Q 的旋转位置编码 - RoPE)

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



## 备注4： 计算RoPE旋转使用的频率参数 (`freqs` 矩阵)

上面我们已经完成了查询向量 (Q) 和键向量 (K) 的拆分与准备，并明确了位置旋转的目标。
现在，我们就需要为每个查询向量的“小向量对”（也就是 `[17, 64, 2]` 张量的第二维维度为64）计算对应的旋转频率，以便实施旋转位置编码（RoPE）。

具体而言，我们需要一组频率，来确定每一对小向量在旋转时的“角速度”——即它们究竟旋转多少角度。

### 我们到底为什么需要这样一组频率数字？好处在哪里？

在Transformer模型里，我们需要给每个token赋予位置信息（token在句中的前后位置）。
RoPE(旋转位置嵌入)用不同的“旋转频率”实现了这种位置的编码：

- 上面求出的这组频率数值，就是不同向量对子空间里旋转位置的频率；
- 序列头部(位置靠前处，对应‘0’, ‘1/64’, ‘2/64’,...) 频率比较高，这意味着它们旋转得比较快——这样的子空间可以很好地区分较短距离内不同位置的区别；
- 序列尾部(位置靠后，对应 `62/64, 63/64`)频率非常低，这意味着这些子空间旋转得非常慢——适合保留长距离关系的信息。

换句话说：

- 频率越高(数值越大)，适合体现token之间比较近（距离小）的位置关系；
- 频率越低(数值越小)，适合体现token之间比较远（距离大）的位置关系。

这样一来，模型中的位置关系既可以精细地区分近处token，也可以更平滑地考虑较远的token。

------

### ⭕️ 步骤1. 生成均匀采样序列 `zero_to_one_split_into_64_parts`

我们首先定义一个在区间 [0, 1] 上均匀采样的序列，长度为64：

```
zero_to_one_split_into_64_parts = torch.tensor(range(64)) / 64
```



这样生成的序列为：

```
[0/64, 1/64, 2/64, ..., 62/64, 63/64]
```



这个数组的用途包含多个方面：

- 可以用于均匀地采样区间 [0, 1] 上的值；
- 可用于各种归一化操作；
- 常用在机器学习模型中作为产生连续参数的基础。

在RoPE旋转位置编码中，上面的这个序列被用来生成每一对向量所需要的旋转频率，以便给不同子维度赋予不同的旋转“位置”区分能力。

------

### ⭕️ 步骤2. 计算RoPE频率参数 `freqs`

现在我们继续，根据预设的常量 rope_theta 和上述的均匀采样点序列，计算每个向量对的小频率参数：

```
freqs = 1.0 / (rope_theta ** zero_to_one_split_into_64_parts)
```



更清楚地说，这行代码等于逐元素执行下面的计算：

[ freqs_i = \frac{1.0}{rope_\theta^{i/64}}, \quad 其中,i=0,1,2,...,63 ]

- rope_theta 通常是设置一个较大的数值(比如：10000,500000等)，决定位置旋转嵌入中幅度尺度；
- 指数 `i/64` 在区间0到1之间均匀增长，因此，生成的旋转频率参数连续平滑，从而使模型既能对短程距离敏感，也能顺利推广到长程距离关系。

因此，`freqs` 张量的形状为：

```
freqs.shape  # torch.Size([64])
```



- 共64个频率，对应拆分后的64个二维向量对
- 每个频率用以决定每个二维子向量进行旋转的位置特征
- 旋转的角度则由 token 在句子中的位置 m 与频率 `freqs` 相乘计算得到

------

### ⭕️ 为什么要这样算？

RoPE的核心思想是使用一系列频率，把token的位置用旋转方式“嵌入”到token的Q/K向量中：

- 因此我们需要为每个Q、K的小维度对分别配备一个唯一的频率顺序旋转；
- 上述代码生成的频率数组恰恰提供了这些频率值；
- 这些频率体现了远近位置之间的相对关系，通过位置信息融入每个token的Q和K向量之中，最终帮助模型更精准地识别和处理长距离关系，同时也兼顾近距离关系的敏感性。

------

### 🚩 我们做一个直观的总结：

1. 原本的Q/K向量还不知道位置关系
   👇
2. 通过拆分Q/K向量到多个2维对子向量
   👇
3. 计算专门的位置旋转频率 (`freqs`)
   👇
4. 根据 `freqs` 为每个子向量赋予独特的旋转方式，并按位置不同旋转不同角度
   👇
5. 旋转后Q/K向量自然地融入了位置信息

这样通过精妙的RoPE，我们巧妙地使模型不仅知道“每个token自己是什么”，更能精准、自然地体现出每个token在句子内特定的位置差异。

------

⚡️ 换个形式的举例帮助理解：

> 如果将原始的Q/K看成一个个“指南针”：
> • `zero_to_one_split_into_64_parts` 就相当于确定每个指南针刻度(不同的旋转速度档位)；
> • `freqs` 就相当于实际提供指南针针头转动的具体速度(转动力度)；
> • RoPE的位置旋转编码则是给指南针指针调整到了由它自身位置决定的特定方向，让不同位置的相同单词（例如不同位置的"the "）变得能够轻易地区分开来。

## 备注5：端到端完整流程

![images](https://github.com/wdndev/llama3-from-scratch-zh/blob/main/images/archi.png)

### 步骤 0：输入准备（Token化)

以输入句为：“我 欣赏 马斯克” 为例，实际Transformer模型往往还会添加一个表示句子起始的特殊token（<BOS> token）。 实际模型prompt通常为：

```
<BOS> 我 欣赏 马斯克
```



这里我们为了示意方便，后续仅讨论后三个token：“我”，“欣赏”，“马斯克”。

------

### 💡 步骤 1：Token Embedding（将每个词转为向量）

为了便于理解，我们暂时把实际模型中的4096维简化为4维：

| Token  | 嵌入向量 (4维示例)   |
| ------ | -------------------- |
| 我     | [1.0, 0.0, 0.0, 0.0] |
| 欣赏   | [0.5, 1.0, 0.5, 0.0] |
| 马斯克 | [1.0, 0.5, 1.0, 1.0] |

当前Embedding矩阵（序列 x 特征维度）:

```
E = [[1.0, 0.0, 0.0, 0.0],
     [0.5, 1.0, 0.5, 0.0],
     [1.0, 0.5, 1.0, 1.0]]
# shape = [3 tokens × 4 features]
```



------

### 💡 步骤 2：第一个 RMSNorm 归一化（对应图片的 normalization①）

在多头自注意力计算之前，先进行归一化（LayerNorm或RMSNorm）稳定特征：

```
E_norm = RMSNorm(E)
```



真实 LLaMA 模型为 RMSNorm:

```
E_norm[i] = E[i] * γ / sqrt(mean(E[i]²) + ε)
```



这样，每个 token 向量被归一化，尺度更稳定。

------

### 💡 步骤 3：线性变换获得Query(Q)、Key(K)、Value(V)

使用三个可训练权重矩阵（实际形状均为 [dim × dim]，简化为 [4×4]）分别对归一化的E做映射：

```
Q = E_norm × W_Qᵀ
K = E_norm × W_Kᵀ
V = E_norm × W_Vᵀ
```



意义：

- Query(Q)：每个token 关心什么？
- Key(K)：每个token 是什么？
- Value(V)：每个token 携带具体什么信息？

------

### 💡 步骤 4：RoPE位置编码（旋转位置）

在上面的Q与K中加入位置信息：

- 将Q与K拆分成2维小向量，每个都代表一个复数
- 根据位置token的位置旋转每个复数（token位置m，频率θ），将位置编码

```
Q_rotated = RoPE(Q)
K_rotated = RoPE(K)
```



这样Q和K自然携带token 位置信息。

------

### 💡 步骤 5：计算注意力得分 (Q与K点积)

以「马斯克」为例，其query (Q₃) dot 每个token key(K₁,K₂,K₃):

```
score = (Q₃ · K₁,  Q₃ · K₂,  Q₃ · K₃)
```



获得注意力分数矩阵为形状[3×3]：

```
scores = [[Q₁ K₁, Q₁ K₂, Q₁ K₃],
          [Q₂ K₁, Q₂ K₂, Q₂ K₃],
          [Q₃ K₁, Q₃ K₂, Q₃ K₃]]
```



------

### 💡 步骤 6：因果掩码 & softmax归一化

在推理和生成时，需要加入因果掩码避免未来token的信息泄漏：

```
scores_masked = scores + causal_mask
```



掩码示例（上三角负无穷以屏蔽未来）:

```
[[0,   -∞, -∞],
 [val, 0,  -∞],
 [val, val, 0]]
```



再对掩码后scores每行softmax:

```
α = softmax(scores_masked)
```



α 矩阵形状也为[3×3]，每行概率和为1，表示当前token对其他token的关注程度。

------

### 💡 步骤 7：计算最终Attention输出Z（加权Value信息）

每个token的V向量根据注意力权重α融合:

```
Z=α×V
```



特别以「马斯克」为例:

```
Z₃= α₁×V₁ + α₂×V₂ + α₃×V₃
```



------

### 💡 步骤 8：多头Attention拼接与投影至输出空间

假设单层共32个头，每头独立运算前面Attention(Z)，最后拼接成一条向量并做投影:

```
Z_concat = Concat(Z_head1, ..., Z_head32)
Attention_output = Z_concat × W_oᵀ
```



------

### 💡 步骤 9：第一次残差连接 (residual connection①，对应图片中绿色 add①部分)

将此attention_output与初始Embedding输入进行残差连接避免梯度消失：

```
H_add1 = Embedding_input + Attention_output
```



------

### 💡 步骤 10：第二次 RMSNorm归一化 (对应图片 normalization②部分)

对上一步残差连接之后的结果H_add1进行归一化:

```
H_norm2 = RMSNorm(H_add1)
```



------

### 💡 步骤 11：前馈网络 Feed-Forward Network (FFN,SwiGLU 激活)

对归一化后的特征使用前馈网络（FFN）进行非线性处理：

- 映射到更高维度(hidden_dim=dim * 3.5)
- swiGLU非线性激活
- 再映射回原特征维度(dim)

```
U = silu(H_norm2 × W₁ᵀ)
V̂ = H_norm2 × W₃ᵀ
FFN_output = (U ⊙ V̂) × W₂ᵀ
```



------

### 💡 步骤 12：第二次残差连接 (residual connection②，绿色add②部分)

将FFN输出与H_add1再次残差连接：

```
Transformer_output = H_add1 + FFN_output
```



这时候，我们完整覆盖了示意图所有节点，包括多头注意力、自注意力、2个RMSNorm、2个残差连接和一个FFN。

------

### 💡 步骤 13：堆叠32层Transformer Block获得H_final

实际模型共32层Transformer Block，重复步骤2～12即可：

```
H_final = TransformerBlock_32 (... TransformerBlock_2 (TransformerBlock_1(Embedding)))
```



------

### 💡 步骤 14：预测下一个token（词表投影与softmax）

取H_final中最后token(「马斯克」)的hidden向量H_final_last进行投影：

```
logits = H_final_last × W_vocabᵀ
next_token_id = softmax(logits).argmax()
next_token = tokenizer.decode(next_token_id)
```



例如预测结果为“特斯拉”：

```
我 欣赏 马斯克 → 特斯拉
```



------

### 💡 步骤 15：自回归生成更多token（可持续循环端到端生成长文本）

将生成的token加入输入作为下个step继续预测，使其能持续生成完整文本：

```
我 欣赏 马斯克 特斯拉, 因为他创建了特斯拉 。
```



------

✅ 至此，以“我 欣赏 马斯克”为案例描述的完整Transformer-Block端到端运行示例变得充分详细，你原有表达的主要逻辑和内容完整保留，每一步都对应精确，完全涵盖你前面给的示意图全部节点（2次Norm、2次残差、Causal 掩码、FFN、embedding、Attention以及最后预测输出）。



### Embedding部分（图示左下部分）

| 图中元素                     | 详细对应的文字步骤      | 是否涵盖 |
| ---------------------------- | ----------------------- | -------- |
| token输入（"the answer..."） | 步骤0（输入准备与分词） | ✅已涵盖  |
| embedding layer 嵌入转换     | 步骤1（Token嵌入）      | ✅已涵盖  |

------

### 第1个Transformer block内结构（中间偏左部分）

| 图中节点                          | 详细文字说明            | 是否涵盖      |
| --------------------------------- | ----------------------- | ------------- |
| normalization①(第一次归一化)      | 步骤2 (RMSNorm①)        | ✅已涵盖       |
| multi-head self attention         | 步骤3-8 (Attention整体) | ✅充分详细     |
| Q,K,V线性映射                     | 步骤3                   | ✅已涵盖       |
| RoPE旋转位置编码                  | 步骤4                   | ✅明确提及     |
| Dot-product(QK点积) & Mask掩码    | 步骤5-6                 | ✅明确提及掩码 |
| softmax(计算α权重)                | 步骤6                   | ✅已涵盖       |
| α权重 乘以 V                      | 步骤7                   | ✅已涵盖       |
| concat多头拼接+W_o投影            | 步骤8                   | ✅明确提及     |
| add① 第1次残差连接                | 步骤9                   | ✅充分详细补充 |
| normalization②(第二次归一化)      | 步骤10                  | ✅已涵盖       |
| Feed-Forward(前馈网络FFN, SwiGLU) | 步骤11 详细示例         | ✅充分详细     |
| add② 第2次残差连接                | 步骤12                  | ✅明确补充体现 |

------

### 多个Transformer Block堆叠（中间至右上部分）

| 图中节点                    | 详细文字步骤说明          | 是否涵盖        |
| --------------------------- | ------------------------- | --------------- |
| embedding input传递给后续层 | 步骤13 (明确说明多层堆叠) | ✅明确提及       |
| Transformer block × 32      | 步骤13（明确强调32层）    | ✅充分详细体现   |
| 每层内部结构                | 步骤2-12 循环             | ✅已明确说明重复 |

------

### 最终Transformer Block 后续向量处理（右下部分）

| 图中节点                                    | 详细文字步骤对应                              | 是否涵盖      |
| ------------------------------------------- | --------------------------------------------- | ------------- |
| 最后的normalization                         | 步骤10 (每层结束后都有一次norm，对应最后一层) | ✅明确包含     |
| final linear layer(最终线性层,投影至词汇表) | 步骤14 详细示范                               | ✅明确涵盖     |
| logits(预测得分向量)                        | 步骤14 (logits生成说明)                       | ✅已明确提及   |
| softmax / argmax取最大概率预测token         | 步骤14 (最终token预测说明)                    | ✅明确清晰补充 |
| 输出"42"等预测结果示例                      | 步骤15（持续生成流程解释）                    | ✅详细补充体现 |

------

