# 从零开始实现llama3

在本文中，我们从头开始实现llama3。

```
git clone https://github.com/naklecha/llama3-from-scratch.git
```



Llama3的整体架构：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDt2YO8nqO6TayQm0GCIQVlUS2affqtqTnIviaIyZNW3szSbMQLXrDIag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

Llama3的模型参数：

让我们来看看这些参数在LlaMa 3模型中的实际数值。

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

[5] 将上述参数组合成Transformer
第一个矩阵是输入特征矩阵，通过Attention layer处理生成Attention Weighted features。在这幅图像中，输入特征矩阵只有5 x 3的大小，但在真实的Llama 3模型中，它增长到了8K x 4096，这是巨大的。

接下来是Feed-Forward Network中的隐藏层，增长到5325，然后在最后一层回落到4096。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPgS1JCcK6xhOhnqU66pNXxXCET6XEtIn6IFMeGBgnLHy9QK3mGeaQiaw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[6] Transformer block的多层**
LlaMa 3结合了上述32个transformer block，输出从一个block传递到下一个block，直到达到最后一个。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPQRa1cicqXxhnzZesxGpPobIX7Qq1TGu5icTq3QKvPIENWcLxEcehtakw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**[7] 把所有这些放在一起**
一旦我们启动了所有上述部分，就是时候把它们整合在一起，看看它们是如何产生LlaMa效果的。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXduK3dyBoCWQGDLq1icleOPLzibicmYGtmUC8IcmlJBO4CGa9A14VnF1oQVtqTLPAD18GgY1YMhKrfg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)


步骤1：首先我们有我们的输入矩阵，大小为8K（context-window）x 128K（vocabulary-size）。这个矩阵经过嵌入处理，将这个高维矩阵转换为低维。

步骤2：在这种情况下，这个低维结果变为4096，这是我们之前看到的LlaMa模型中特征的指定维度。

在神经网络中，升维和降维都是常见的操作，它们各自有不同的目的和效果。

**升维**通常是为了增加模型的容量，使其能够捕捉更复杂的特征和模式。当输入数据被映射到一个更高维度的空间时，不同的特征组合可以被模型更容易地区分。这在处理非线性问题时尤其有用，因为它可以帮助模型学习到更复杂的决策边界 。

**降维**则是为了减少模型的复杂性和过拟合的风险。通过减少特征空间的维度，模型可以被迫学习更加精炼和泛化的特征表示。此外，降维可以作为一种正则化手段，有助于提高模型的泛化能力。在某些情况下，降维还可以减少计算成本和提高模型的运行效率 。

在实际应用中，升维后再降维的策略可以被视为一种特征提取和变换的过程。在这个过程中，模型首先通过增加维度来探索数据的内在结构，然后通过降维来提取最有用的特征和模式。这种方法可以帮助模型在保持足够复杂性的同时，避免过度拟合训练数据 。

[神经网络背后的数学-下](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663556652&idx=1&sn=7e4b81f60d881b49668f7e8501030adc&chksm=81d5e154b6a26842f2d7a43690a2474efe8d9508656f9b3aa5111d128b420e5116995fe9e7ed&scene=21#wechat_redirect)

步骤3：这个特征通过Transformer block进行处理，首先由Attention layer处理，然后是FFN layer。Attention layer横向跨特征处理，而FFN layer则纵向跨维度处理。

步骤4：步骤3为Transformer block的32层重复。最终，结果矩阵的维度与用于特征维度的维度相同。

步骤5：最后，这个矩阵被转换回原始的词汇矩阵大小，即128K，以便模型可以选择并映射词汇中可用的单词。

这就是LlaMa 3在那些基准测试中取得高分并创造LlaMa 3效应的方式。



**我们将容易搞混的几个术语用简短的语言总结一下：**

### 1. max_seq_len (最大序列长度)

这是模型在单次处理时能够接受的最大token数。

在LlaMa 3-8B模型中，这个参数设定为8,000个tokens，即Context Window Size = 8K。这意味着模型在单次处理时可以考虑的最大token数量为8,000。这对于理解长文本或保持长期对话上下文非常关键。

### 2. Vocabulary-size (词汇量)

这是模型能识别的所有不同token的数量。这包括所有可能的单词、标点符号和特殊字符。模型的词汇量是128,000，表示为Vocabulary-size = 128K。这意味着模型能够识别和处理128,000种不同的tokens，这些tokens包括各种单词、标点符号和特殊字符。



### 3. Attention Layers (注意力层)

Transformer模型中的一个主要组件。它主要负责通过学习输入数据中哪些部分最重要（即“注意”哪些token）来处理输入数据。一个模型可能有多个这样的层，每层都试图从不同的角度理解输入数据。

LlaMa 3-8B模型包含32个处理层，即Number of Layers = 32。这些层包括多个Attention Layers及其他类型的网络层，每层都从不同角度处理和理解输入数据。



### 4. transformer block 

包含多个不同层的模块，通常至少包括一个Attention Layer和一个Feed-Forward Network（前馈网络）。一个模型可以有多个transformer block，这些block顺序连接，每个block的输出都是下一个block的输入。也可以称transformer block为decoder layer。 



在Transformer模型的语境中，通常我们说模型有“32层”，这可以等同于说模型有“32个Transformer blocks”。每个Transformer block通常包含一个自注意力层和一个前馈神经网络层，这两个子层共同构成了一个完整的处理单元或“层”。

因此，当我们说模型有32个Transformer blocks时，实际上是在描述这个模型由32个这样的处理单元组成，每个单元都有能力进行数据的自注意力处理和前馈网络处理。这种表述方式强调了模型的层级结构和其在每个层级上的处理能力。

总结来说，"32层"和"32个Transformer blocks"在描述Transformer模型结构时基本是同义的，都指模型包含32次独立的数据处理周期，每个周期都包括自注意力和前馈网络操作。

### 5. Feature-dimension (特征维度)

这是输入token在模型中表示为向量时，每个向量的维度。

每个token在模型中被转换成一个含4096个特征的向量，即Feature-dimension = 4096。这个高维度使得模型能够捕捉更丰富的语义信息和上下文关系。

### 6. Attention-Heads (注意力头)

在每个Attention Layer中，可以有多个Attention-Heads，每个head独立地从不同的视角分析输入数据。

每个Attention Layer包含32个独立的Attention Heads，即Number of Attention Heads = 32。这些heads分别从不同的方面分析输入数据，共同提供更全面的数据解析能力。

### 7. Hidden Dimensions (隐藏维度)

这通常指的是在Feed-Forward Network中的层的宽度，即每层的神经元数量。通常，Hidden Dimensions会大于Feature-dimension，这允许模型在内部创建更丰富的数据表示。

在Feed-Forward Networks中，隐藏层的维度为5325，即Hidden Dimensions = 5325。这比特征维度大，允许模型在内部层之间进行更深层次的特征转换和学习。

### 关系和数值：

- Attention Layers 和 Attention-Heads 的关系：每个Attention Layer可以包含多个Attention-Heads。
- 数值关系：一个模型可能有多个transformer blocks，每个block包含一个Attention Layer和一个或多个其他层。每个Attention Layer可能有多个Attention-Heads。这样，整个模型就在不同层和heads中进行复杂的数据处理。



下载Llama3模型的官方链接脚本：https://llama.meta.com/llama-downloads/ 



**二、查看模型**

下面这段代码展示了如何使用`tiktoken`库来加载和使用一个基于Byte Pair Encoding (BPE) 的分词器。这个分词器是为了处理文本数据，特别是在自然语言处理和机器学习模型中使用。

我们输入hello world,看分词器如何进行分词。

```
from pathlib import Path
import tiktoken
from tiktoken.load import load_tiktoken_bpe
import torch
import json
import matplotlib.pyplot as plt


tokenizer_path = "Meta-Llama-3-8B/tokenizer.model"
special_tokens = [
"<|begin_of_text|>",
"<|end_of_text|>",
"<|reserved_special_token_0|>",
"<|reserved_special_token_1|>",
"<|reserved_special_token_2|>",
"<|reserved_special_token_3|>",
"<|start_header_id|>",
"<|end_header_id|>",
"<|reserved_special_token_4|>",
"<|eot_id|>",  # end of turn
        ] + [f"<|reserved_special_token_{i}|>" for i in range(5, 256 - 5)]
mergeable_ranks = load_tiktoken_bpe(tokenizer_path)
tokenizer = tiktoken.Encoding(
    name=Path(tokenizer_path).name,
    pat_str=r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+",
    mergeable_ranks=mergeable_ranks,
    special_tokens={token: len(mergeable_ranks) + i for i, token in enumerate(special_tokens)},
)


tokenizer.decode(tokenizer.encode("hello world!"))
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDplZPbMkESRW96gXZoHJZo2Y1QrUHXPpGSC4nwTvib3cG9WDVhRmLjpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**读取模型文件**



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDWq3cUFHcGLTqNZyGibr7kGXicpiaqCVtLU1jXqXaHFFcQgtTqKlmwzSYg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

查看加载的模型文件中包含的前20个参数或权重的名称。

```
model = torch.load("Meta-Llama-3-8B/consolidated.00.pth")
print(json.dumps(list(model.keys())[:20], indent=4))
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDm8K80nAiaH3iaSLjseMZWBwy3btkT2rgYanlWXOn7cTCjIZK7u5jWroQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. "tok_embeddings.weight"：这表示模型有一个词嵌入层，用于将输入的单词（或者更一般的，token）转换为固定维度的向量。这是大多数自然语言处理模型的第一步。

2. "layers.0.attention..." 和 "layers.1.attention..."：这些参数表示多个层中，每层都包含一个注意力机制模块。在这个模块中，`wq`、`wk`、`wv`、`wo`分别代表查询（Query）、键（Key）、值（Value）和输出（Output）的权重矩阵。这是Transformer模型的核心组成部分，用于捕捉输入序列中不同部分之间的关系。

3. "layers.0.feed_forward..." 和 "layers.1.feed_forward..."：这些参数表示每个层还包含一个前馈网络（Feed Forward Network），它通常由两个线性变换组成，中间有一个非线性激活函数。`w1`、`w2`、`w3`可能代表这个前馈网络中的不同线性层的权重。

4. "layers.0.attention_norm.weight" 和 "layers.1.attention_norm.weight"：这些参数表示每个层中的注意力模块后面有一个归一化层（可能是Layer Normalization），用于稳定训练过程。

5. "layers.0.ffn_norm.weight" 和 "layers.1.ffn_norm.weight"：这些参数表示前馈网络后面也有一个归一化层。

   上面代码输出内容，与下图相同，也就是Llama3中的一个transformer block。

   ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRhJ7lib0q1qrnjeXgFwZtpDUbkCSDQChWqTW97ECQM5NLoRSKmD2M82w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

总的来说，这个输出结果揭示了一个基于Transformer架构的深度学习模型的关键组成部分。这种模型广泛用于自然语言处理任务，如文本分类、机器翻译、问答系统等。每一层的结构几乎相同，包括注意力机制、前馈网络和归一化层，这有助于模型捕捉复杂的输入序列特征。



查看Llama3模型的参数配置：

```
with open("Meta-Llama-3-8B/params.json", "r") as f:
    config = json.load(f)
config

```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDrNrD9wDLcrBc80VibiaDIhCB07evn5fMSj7icEIcGJJrZIlkz7vFQCFJg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. 'dim': 4096 - 表示模型中的隐藏层维度或特征维度。这是模型处理数据时每个向量的大小。
2. 'n_layers': 32 - 表示模型中层的数量。在基于Transformer的模型中，这通常指的是编码器和解码器中的层的数量。
3. 'n_heads': 32 - 表示在自注意力（Self-Attention）机制中，头（head）的数量。多头注意力机制是Transformer模型的关键特性之一，它允许模型在不同的表示子空间中并行捕获信息。
4. 'n_kv_heads': 8 - 这个参数不是标准Transformer模型的常见配置，可能指的是在某些特定的注意力机制中，用于键（Key）和值（Value）的头的数量。
5. 'vocab_size': 128256 - 表示模型使用的词汇表大小。这是模型能够识别的不同单词或标记的总数。
6. 'multiple_of': 1024 - 这可能是指模型的某些维度需要是1024的倍数，以确保模型结构的对齐或优化。
7. 'ffn_dim_multiplier': 1.3 - 表示前馈网络（Feed-Forward Network, FFN）的维度乘数。在Transformer模型中，FFN是每个注意力层后的一个网络，这个乘数可能用于调整FFN的大小。
8. 'norm_eps': 1e-05 - 表示在归一化层（如Layer Normalization）中使用的epsilon值，用于防止除以零的错误。这是数值稳定性的一个小技巧。
9. 'rope_theta': 500000.0 - 这个参数不是标准Transformer模型的常见配置，可能是指某种特定于模型的技术或优化的参数。它可能与位置编码或某种正则化技术有关。

## 我们使用这个配置来推断模型的细节，比如

1. 模型有32个Transformer层
2. 每个多头注意力块有32个头
3. 词汇表的大小等等 

```
dim = config["dim"]
n_layers = config["n_layers"]
n_heads = config["n_heads"]
n_kv_heads = config["n_kv_heads"]
vocab_size = config["vocab_size"]
multiple_of = config["multiple_of"]
ffn_dim_multiplier = config["ffn_dim_multiplier"]
norm_eps = config["norm_eps"]
rope_theta = torch.tensor(config["rope_theta"])
```



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDUBSbb8Ss1ynwSr363SkibxtDHgvQJ6iab8YlEzGn3ulWpfau02kTbpeQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**将Text转化为Token**

代码如下：

```

prompt = "the answer to the ultimate question of life, the universe, and everything is "
tokens = [128000] + tokenizer.encode(prompt)
print(tokens)
tokens = torch.tensor(tokens)
prompt_split_as_tokens = [tokenizer.decode([token.item()]) for token in tokens]
print(prompt_split_as_tokens)
```

```
[128000, 1820, 4320, 311, 279, 17139, 3488, 315, 2324, 11, 279, 15861, 11, 323, 4395, 374, 220]['<|begin_of_text|>', 'the', ' answer', ' to', ' the', ' ultimate', ' question', ' of', ' life', ',', ' the', ' universe', ',', ' and', ' everything', ' is', ' ']
```



##  ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDhgjW09BHGoIJSANsLy8foiawIImzDibFWHblDwyseEdEESZZnibUwjd7A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 将令牌转换为它们的嵌入表示

截止到目前，我们的[17x1]令牌现在变成了[17x4096]，即长度为4096的17个嵌入（每个令牌一个）。

下图是为了验证我们输入的这句话，是17个token。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktR0t2PkrnRT2bV4HhxskAcTCC9ClV6pLU8dIP6pyIbQibjwp0ZXR6yTyQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

代码如下：

```
embedding_layer = torch.nn.Embedding(vocab_size, dim)
embedding_layer.weight.data.copy_(model["tok_embeddings.weight"])
token_embeddings_unnormalized = embedding_layer(tokens).to(torch.bfloat16)
token_embeddings_unnormalized.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDzKnAe5UnUeazT64j2wJWmMYKX0pDk8CTK3V71mF5KXel0NYUrILY0A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

### 三、构建Transformer的第一层

**我们接着使用 RMS 归一化对嵌入进行归一化，也就是图中这个位置：**![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDI9k3JsQibTVEGhLOTMdfibT3MVcAHicicIhyXfoFuk162QQrlwHVdBibl3g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)使用公式如下： ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDXzpS3lCXVxKbBHCBeUkAmAwjsnPHUicg6amYuFIq2Vpfddb9GxvZib5Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1) 

代码如下：

```
# def rms_norm(tensor, norm_weights):
#     rms = (tensor.pow(2).mean(-1, keepdim=True) + norm_eps)**0.5
#     return tensor * (norm_weights / rms)
def rms_norm(tensor, norm_weights):
return (tensor * torch.rsqrt(tensor.pow(2).mean(-1, keepdim=True) + norm_eps)) * norm_weights
```

这段代码定义了一个名为 `rms_norm` 的函数，它实现了对输入张量（tensor）的RMS（Root Mean Square，均方根）归一化处理。这个函数接受两个参数：`tensor` 和 `norm_weights`。`tensor` 是需要进行归一化处理的输入张量，而 `norm_weights` 是归一化时使用的权重。



函数的工作原理如下：

1. 首先，计算输入张量每个元素的平方（`tensor.pow(2)`）。
2. 然后，对平方后的张量沿着最后一个维度（`-1`）计算均值（`mean`），并保持维度不变（`keepdim=True`），这样得到每个元素的均方值。
3. 接着，将均方值加上一个很小的正数 `norm_eps`（为了避免除以零的情况），然后计算其平方根的倒数（`torch.rsqrt`），得到RMS的倒数。
4. 最后，将输入张量与RMS的倒数相乘，再乘以归一化权重 `norm_weights`，得到归一化后的张量。



在进行归一化处理后，我们的数据形状仍然保持为 [17x4096]，这与嵌入层的形状相同，只不过数据已经过归一化。

```

token_embeddings = rms_norm(token_embeddings_unnormalized, model["layers.0.attention_norm.weight"])
token_embeddings.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDQlhlFpGPYH0yiaIzmLA2pZJbaDWsQ0zegA8gu4OWF07CibSiayWICcksg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDqbCvzDqXNO36eRav2icApia9hOn22DqzAiaRhjQdpGX0It0l7D6icWxdkw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)接下来，我们介绍注意力机制的实现，也就是下图中的红框标注的位置：

### ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRNm04hVoLiaIuUNGbuiaoO4r6R5gbkcS2uWByg5bU45ygyibVCIKXE6kiag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)  ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDnwog1Jg03BJAT8fSsynwEOhCdTUJVYAibK7qhGD2ibSUy9q7h4DNR1ibw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)我们一步一步地解释这张图，详细说明每个步骤。 

### 1. 输入句子

- **描述**：这是我们的输入句子。
- **解释**：输入句子被表示为一个矩阵 ( X )，其中每一行代表一个词的嵌入向量。

### 2. 嵌入每个词

- **描述**：我们对每个词进行嵌入。
- **解释**：输入句子中的每个词被转换为一个高维向量，这些向量组成了矩阵 ( X )。

### 3. 分成8个头

- **描述**：将矩阵 ( X ) 分成8个头。我们用权重矩阵 ( W^Q )、( W^K ) 和 ( W^V ) 分别乘以 ( X )。
- **解释**：多头注意力机制将输入矩阵 ( X ) 分成多个头（这里是8个），每个头有自己的查询（Query）、键（Key）和值（Value）矩阵。具体来说，输入矩阵 ( X ) 分别与查询权重矩阵 ( W^Q )、键权重矩阵 ( W^K ) 和值权重矩阵 ( W^V ) 相乘，得到查询矩阵 ( Q )、键矩阵 ( K ) 和值矩阵 ( V )。

### 4. 计算注意力

- **描述**：使用得到的查询、键和值矩阵计算注意力。
- **解释**：对于每个头，使用查询矩阵 ( Q )、键矩阵 ( K ) 和值矩阵 ( V ) 计算注意力分数。具体步骤包括：
  1. 计算 ( Q ) 和 ( K ) 的点积。
  2. 对点积结果进行缩放。
  3. 应用softmax函数得到注意力权重。
  4. 用注意力权重乘以值矩阵 ( V ) 得到输出矩阵 ( Z )。

### 5. 拼接结果矩阵

- **描述**：将得到的 ( Z ) 矩阵拼接起来，然后用权重矩阵 ( W^O ) 乘以拼接后的矩阵，得到层的输出。
- **解释**：将所有头的输出矩阵 ( Z ) 拼接成一个矩阵，然后用输出权重矩阵 ( W^O ) 乘以这个拼接后的矩阵，得到最终的输出矩阵 ( Z )。

### 额外说明

- **查询、键、值和输出向量的形状**：在加载查询、键、值和输出向量时，注意到它们的形状分别是 [4096x4096]、[1024x4096]、[1024x4096]、[1024x4096] 和 [4096x4096]。
- **并行化注意力头的乘法**：将它们捆绑在一起有助于并行化注意力头的乘法。

这张图展示了Transformer模型中多头注意力机制的实现过程，从输入句子的嵌入开始，经过多头分割、注意力计算，最后拼接结果并生成输出。每个步骤都详细说明了如何从输入矩阵 ( X ) 生成最终的输出矩阵 ( Z )。



> 当我们从模型中加载查询（query）、键（key）、值（value）和输出（output）向量时，我们注意到它们的形状分别是 [4096x4096]、[1024x4096]、[1024x4096]、[4096x4096]
>
> 乍一看这很奇怪，因为理想情况下我们希望每个头的每个q、k、v和o都是单独的

```

print(
model["layers.0.attention.wq.weight"].shape,
model["layers.0.attention.wk.weight"].shape,
model["layers.0.attention.wv.weight"].shape,
model["layers.0.attention.wo.weight"].shape
)
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDU3481qzMyoxOwVnZQUBjALsFKzah0wx0cnB3bgE4PKRM9ZHU7cQntw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

1. 查询（Query）权重矩阵 (wq.weight) 的形状是 [4096, 4096]。
2. 键（Key）权重矩阵 (wk.weight) 的形状是 [1024, 4096]。
3. 值（Value）权重矩阵 (wv.weight) 的形状是 [1024, 4096]。
4. 输出（Output）权重矩阵 (wo.weight) 的形状是 [4096, 4096]。

输出结果表明：

- 查询（Q）和输出（O）权重矩阵的形状是相同的，都是[4096, 4096]。这意味着对于查询和输出，输入特征和输出特征的维度都是4096。
- 键（K）和值（V）权重矩阵的形状也是相同的，都是[1024, 4096]。这表明键和值的输入特征维度为4096，但输出特征维度被压缩到了1024。



这些权重矩阵的形状反映了模型设计者如何设置注意力机制中不同部分的维度。特别是，键和值的维度被减小可能是为了减少计算复杂度和内存消耗，而保持查询和输出的较高维度可能是为了保留更多的信息。这种设计选择依赖于特定的模型架构和应用场景 



我们继续使用句子“我欣赏李鸿章”来解释WQ、WK、WV和WO这些权重矩阵的作用。

在Transformer模型中，每个词都会通过词嵌入转换成一个向量。这些向量接下来会通过一系列的线性变换来计算注意力分数。这些线性变换就是通过权重矩阵WQ、WK、WV和WO来实现的。

1. WQ（权重矩阵Q）：这个矩阵用于将每个词的向量转换成“查询（Query）”向量。在我们的例子中，如果我们想要关注“欣赏”这个词，我们会将“欣赏”的向量乘以WQ来得到查询向量。

2. WK（权重矩阵K）：这个矩阵用于将每个词的向量转换成“键（Key）”向量。同样地，我们会将每个词，包括“我”和“李鸿章”，的向量乘以WK来得到键向量。

3. WV（权重矩阵V）：这个矩阵用于将每个词的向量转换成“值（Value）”向量。每个词的向量乘以WV后，我们得到的是值向量。

   这三个矩阵（WQ、WK、WV）是用来为每个头生成不同的查询、键和值向量的。这样做可以让每个头关注句子的不同方面。

4. WO（权重矩阵O）：在计算了注意力分数并得到了每个头的输出之后，我们需要将这些输出合并起来，以便为下一层或最终输出生成一个统一的表示。我们将所有头的输出向量拼接起来，然后乘以WO来得到最终的输出向量。

   在整个过程中，WQ、WK、WV和WO是通过训练学习得到的，它们决定了模型如何将输入的词向量转换成不同的表示，以及如何组合这些表示来得到最终的输出。这些矩阵是Transformer模型中注意力机制的核心部分，它们使得模型能够捕捉到句子中不同词之间的关系。



WQ（权重矩阵Q）、WK（权重矩阵K）、WV（权重矩阵V）和WO（权重矩阵O）这些矩阵是Transformer模型中的参数，它们是在模型训练过程中通过反向传播算法和梯度下降等优化方法学习得到的。

让我们来看看这个学习过程是如何进行的：

1. 初始化：在训练开始之前，这些矩阵通常会被随机初始化。这意味着它们的初始值是随机选取的，这样可以打破对称性并开始学习过程。

2. 前向传播：在模型的训练过程中，输入数据（如句子“我欣赏李鸿章”）会通过模型的各个层进行前向传播。在注意力机制中，输入的词向量会与WQ、WK、WV矩阵相乘，以生成查询、键和值向量。

3. 计算损失：模型的输出会与期望的输出（通常是训练数据中的标签）进行比较，计算出一个损失值。这个损失值衡量了模型的预测与实际情况的差距。

4. 反向传播：损失值会通过反向传播算法传回模型，计算每个参数（包括WQ、WK、WV和WO）对损失的影响，即它们的梯度。

5. 参数更新：根据计算出的梯度，使用梯度下降或其他优化算法来更新这些矩阵的值。这个过程会逐渐减小损失值，使模型的预测更加准确。

6. 迭代过程：这个前向传播、损失计算、反向传播和参数更新的过程会在训练数据上多次迭代进行，直到模型的性能达到一定的标准或者不再显著提升。

   通过这个训练过程，WQ、WK、WV和WO这些矩阵会逐渐调整它们的值，以便模型能够更好地理解和处理输入数据。在训练完成后，这些矩阵将固定下来，用于模型的推理阶段，即对新的输入数据进行预测。

**四、展开查询向量**

在本小节中，我们将从多个注意力头中展开查询向量，得到的形状是 [32x128x4096] 这里，32 是 llama3 中注意力头的数量，128 是查询向量的大小，而 4096 是令牌嵌入的大小。

```
q_layer0 = model["layers.0.attention.wq.weight"]head_dim = q_layer0.shape[0] // n_headsq_layer0 = q_layer0.view(n_heads, head_dim, dim)q_layer0.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDL9PJWlcV3BrgMNzheLL3r5s8dib0pWGSDTo0xssKdbmXOuUanTB1xIA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

这段代码通过对模型中第一层的查询（Q）权重矩阵进行重塑（reshape），将其分解为多个注意力头的形式，从而揭示了`32`和`128`这两个维度。

1. `q_layer0 = model["layers.0.attention.wq.weight"]`：这行代码从模型中提取第一层的查询（Q）权重矩阵。
2. `head_dim = q_layer0.shape[0] // n_heads`：这行代码计算每个注意力头的维度大小。它通过将查询权重矩阵的第一个维度（原本是4096）除以注意力头的数量（`n_heads`），得到每个头的维度。如果`n_heads`是32（即模型设计为有32个注意力头），那么`head_dim`就是`4096 // 32 = 128`。
3. `q_layer0 = q_layer0.view(n_heads, head_dim, dim)`：这行代码使用`.view()`方法重塑查询权重矩阵，使其形状变为`[n_heads, head_dim, dim]`。这里`dim`很可能是原始特征维度4096，`n_heads`是32，`head_dim`是128，因此重塑后的形状是`[32, 128, 4096]`。
4. `q_layer0.shape` 输出：`torch.Size([32, 128, 4096])`：这行代码打印重塑后的查询权重矩阵的形状，确认了其形状为`[32, 128, 4096]`。

之所以在这段代码中出现了`32`和`128`这两个维度，而在之前的代码段中没有，是因为这段代码通过重塑操作明确地将查询权重矩阵分解为多个注意力头，每个头具有自己的维度。`32`代表了模型中注意力头的数量，而`128`代表了分配给每个头的特征维度大小。这种分解是为了实现多头注意力机制，其中每个头可以独立地关注输入的不同部分，最终通过组合这些头的输出来提高模型的表达能力。 



### 实现第一层的第一个头

访问了第一层第一个头的查询（query）权重矩阵，这个查询权重矩阵的大小是 [128x4096]。

```
q_layer0_head0 = q_layer0[0]
q_layer0_head0.shape
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDI8ibpWO6bfMJmuShJ46chrVlDPrI83Ebj1tD6KTSv5PaK0GB66Yzic7w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

我们现在将查询权重与令牌嵌入相乘，以获得令牌的查询

在这里，你可以看到结果形状是 [17x128]，这是因为我们有17个令牌，每个令牌都有一个长度为128的查询（每个令牌在一个头上方的查询）。

```
q_per_token = torch.matmul(token_embeddings, q_layer0_head0.T)q_per_token.shape
br
```

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDeWOX41w63Jg0q6dVGBzYkbRftkXymhZ8ZHCzjwwTSI2yvxJ8xmK6XA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)这段代码执行了一个矩阵乘法操作，将令牌嵌入（token_embeddings）与第一层第一个头的查询（query）权重矩阵（q_layer0_head0）的转置（.T）相乘，以生成每个令牌的查询向量（q_per_token）。

1. q_per_token = torch.matmul(token_embeddings, q_layer0_head0.T)：
   - torch.matmul 是PyTorch中的矩阵乘法函数，它可以处理两个张量的乘法。
   - token_embeddings 应该是一个形状为 [17, 4096] 的张量，表示有17个令牌，每个令牌由4096维的嵌入向量表示。
   - q_layer0_head0 是第一层第一个头的查询权重矩阵，其原始形状为 [128, 4096]。.T 是PyTorch中的转置操作，将 q_layer0_head0 的形状转置为 [4096, 128]。
   - 这样，token_embeddings 和 q_layer0_head0.T 的矩阵乘法就是 [17, 4096] 和 [4096, 128] 的乘法，结果是一个形状为 [17, 128] 的张量。
2. q_per_token.shape 和输出：torch.Size([17, 128])：
   - 这行代码打印出 q_per_token 张量的形状，确认其为 [17, 128]。
   - 这意味着对于输入的每个令牌（共17个），我们现在都有了一个128维的查询向量。这128维的查询向量是通过将令牌嵌入与查询权重矩阵相乘得到的，可以用于后续的注意力机制计算。

总之，这段代码通过矩阵乘法将每个令牌的嵌入向量转换为查询向量，为实现注意力机制的下一步做准备。每个令牌现在都有了一个与之对应的查询向量，这些查询向量将用于计算与其他令牌的注意力得分。



截止到目前，我们介绍完的内容处于下图位置：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRMKgyW0BicEvaarQAXdQpJicnjicjZsHUGiaqib4xnHWOExnFSjlVqhd1plg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

将图片放大：

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWh5lMF3XhC4RRattZsnktRndwdop5tbzYkKvnlZnE0S6ibbJMia3wlrvYpJmfxkC6QCBSfmelYiagRA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)接下来，我们将从上图红框位置开始介绍，直到生成最终推理结果。由于后续步骤太多，本文不会罗列所有步骤，只梳理整体步骤，并对关键点进行说明，以帮助读者理解。完整代码步骤见文后。

整体的逻辑是：

1. Embedding：首先，输入的prompt会被第一层做embedding，转换为一个矩阵。

2. 矩阵乘法：然后，我们将输入嵌入（一个矩阵）与特定于查询（Q）、键（K）和值（V）的学习权重矩阵（另一个矩阵）相乘，得到Q、K、V矩阵。

3. RoPE位置更新：接着，我们使用RoPE将位置信息添加到Q、K矩阵中。这个过程可以看作是矩阵加法，我们将RoPE编码的位置信息添加到Q、K矩阵中。

4. 计算Q和K的点积：这一步涉及到矩阵乘法。我们计算Q和K之间的点积，得到一个注意力得分矩阵。

5. 应用softmax函数：然后，我们通过softmax函数将这个点积矩阵归一化。这个归一化的过程可以将点积矩阵转换为一个概率分布，使得每一行的和为1。这样，我们就可以将这个概率分布看作是注意力得分，它描述了输入序列中的每个元素对输出的贡献程度。

6. 应用掩码：然后，我们将一个掩码应用到注意力得分矩阵上，以忽略序列中的某些元素。

7. 将注意力得分矩阵与V矩阵相乘：最后，这一步同样涉及到矩阵乘法。我们将注意力得分矩阵（一个矩阵）与V矩阵（另一个矩阵）相乘，以生成最终的输出。

   

   这里面涉及到几个小的步骤：

- V矩阵的准备：在Transformer模型的自注意力机制中，V（值）矩阵是通过输入数据与模型中的V权重矩阵进行矩阵乘法得到的。这意味着，V矩阵并不是直接给定的，而是需要根据当前的输入和模型参数动态计算出来的。第一段代码是关于如何从模型中提取并重塑V权重矩阵，以便用于这一计算。
- 每个Token的值（Value）向量：第二段代码通过将输入嵌入（token embeddings）与V权重矩阵进行矩阵乘法，为每个token生成了一个值（Value）向量。这一步是必要的，因为它实际上是在生成V矩阵，即根据当前输入计算出每个token的表示。没有这一步，我们就没有V矩阵来与注意力得分矩阵相乘。
- 注意力得分矩阵的计算：注意力得分矩阵是通过查询（Query）和键（Key）矩阵的点积，然后应用softmax函数得到的。这个过程描述了输入序列中的每个元素对输出的贡献程度。如果没有经过前面的步骤来准备Q、K和V矩阵，我们就无法计算出这个得分矩阵，也就无法进行后续的乘法操作。在这个步骤中，qk_per_token_after_masking_after_softmax 是注意力得分矩阵，它描述了输入序列中的每个元素对输出的贡献程度。v_per_token 是每个token的值（Value）向量。通过将注意力得分矩阵与值向量进行矩阵乘法，我们可以得到最终的输出，即注意力向量 qkv_attention。这个注意力向量的形状是 [17, 128]，其中 17 是 prompt 中 token 的数量，128 是每个 token 的值向量的维度。



本文中会涉及到大量的数学运算，我先整体理清。

- 权重矩阵的形状 ([4096, 4096]): 当我们提到查询权重矩阵（例如，wq.weight）的形状为[4096, 4096]时，这指的是每个权重矩阵将输入维度（这里是4096）映射到输出维度（也是4096）。这是模型中的参数，用于转换输入特征。
- 查询向量的生成 ([17, 128]): 在实际的操作中，当我们有一个输入批次，例如大小为[17, 4096]（这里17代表批次中的句子或令牌数量，4096是每个令牌的特征维度），这个输入会通过查询权重矩阵进行变换。在多头注意力的设置中，通常会将这4096维分割成多个“头”，比如说32个头，每个头处理一部分维度，也就是128。
- torch.Size([17, 64, 2]): 这表示将查询向量q_per_token（原始形状为[17, 128]）重塑为三维张量，以便每个令牌的128维向量被分割成64个2维向量。这样做是为了将其转换为复数形式，以应用旋转位置编码。
- torch.Size([17, 64]): 这可能代表从[0,1]等间隔划分的位置分数，用于计算每个位置的频率。
- torch.Size([17, 64, 2]): 再次将频率或与位置相关的某个参数重塑为与q_per_token相同的形状，以便进行元素级的操作。
- torch.Size([17, 128]): 将处理后的查询向量从复数形式转换回实数形式，并重塑回原始的[17, 128]形状，这样每个令牌的查询向量都进行了位置编码的调整。
- torch.Size([8, 128, 4096]) 和 torch.Size([128, 4096]): 这些形状涉及到权重矩阵的形状，可能用于描述在不同头中查询（Q）、键（K）和值（V）的线性变换。例如，128可能是每个头的维度，4096是输入特征的维度。
- torch.Size([17, 17]): 这表示自注意力机制中的分数矩阵，其中每个元素[i, j]描述了第i个令牌的查询向量和第j个令牌的键向量之间的相似度。
- torch.Size([17, 4096]): 这表示每个令牌经过自注意力机制处理后的输出向量，其中包含了所有头的信息。这通常是将所有头的输出向量拼接并通过一个输出权重矩阵处理得到的。



需要指出的是：

当我们说权重矩阵的形状是 `[4096, 4096]`，这意味着这个矩阵用于将任何4096维的输入向量映射到另一个4096维的空间。这个矩阵本身的形状并没有改变，它始终是 `[4096, 4096]`。

当我们提到有17个token，每个token是4096维，组成了一个 `[17, 4096]` 的输入矩阵时，我们实际上是在描述一个批次的数据。这里的“17”代表批次中的样本数（在这个上下文中，每个样本是一个token），而“4096”代表每个样本的特征维度。

这个 `[17, 4096]` 的矩阵与 `[4096, 4096]` 的权重矩阵进行矩阵乘法时，我们并没有改变权重矩阵的形状。相反，我们是在对每个4096维的token向量应用相同的转换（即权重矩阵）。这个过程可以视为：

1. 对于输入矩阵中的每一行（即每个token），都乘以权重矩阵 `[4096, 4096]`。
2. 结果是每个token都被映射到了新的4096维空间，因此输出矩阵的形状仍然是 `[17, 4096]`。

这里没有将4096行变成17行的操作。实际上，每个4096维的token都独立地通过权重矩阵进行了转换，而权重矩阵本身作为模型的参数是不变的。这个过程是批量处理的一部分，允许模型同时处理多个token，每个token都按照相同的方式（即通过相同的权重矩阵）进行转换。



**一、query的positioning encoding**

截止到目前，每个prompt中的token都有一个查询向量，但单个查询向量对于其在prompt中的位置是不知道的，例如查询：“

the answer to the ultimate question of life, the universe, and everything is” 

在提示中，我们使用了三次“the”，我们需要所有3个“the”标记的查询向量根据它们在查询中的位置拥有不同的查询向量（每个大小为[1x128]）。我们使用RoPE（旋转位置嵌入）来执行这些旋转。

原始的查询权重矩阵是 [4096, 4096]，在实际的多头注意力计算中，输入向量会被分割成32个独立的部分，每部分由128维处理。这样，每个头只关注输入的一个128维的子空间，而整体上，所有头合在一起仍然能够覆盖整个4096维的输入空间。

- 
- 

```
q_per_token_split_into_pairs = q_per_token.float().view(q_per_token.shape[0], -1, 2)q_per_token_split_into_pairs.shape
```

 

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDia29Dua82HQIsmvB3RYFicwhb9c7mtJsM5ZzrsOMia3zen88Hcic89sictw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

上面这两行代码本身并没有直接进行位置编码（无论是绝对位置编码还是相对位置编码）。这行代码主要执行了两个操作：

1. **类型转换**：`q_per_token.float()` 将 `q_per_token` 张量的数据类型转换为浮点数。这通常是为了确保后续的数学运算能够包含小数。

2. **重塑张量**：`.view(q_per_token.shape[0], -1, 2)` 重新调整张量的形状。这里的操作是将原始的二维张量 `q_per_token`（形状为 `[17, 128]`）转换为一个三维张量，其中第一维保持不变（17），第二维自动计算以保持元素总数不变，第三维设置为 2。这种重塑操作通常用于准备数据以适应特定的算法需求，但它本身并不改变数据的内容或含义。

   

现在我们有了一个大小为 [17x64x2] 的向量，这是将长度为 128 的查询分成了每个提示符中的 64 对。这 64 对中的每一对都将旋转 m*(theta)，其中 m 是我们正在旋转查询的那个标记的位置！

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXDxBIZznevtX3bCmAQSzfDHk4kj62jvEmnyxHrOjyYiaibWtPesPVJTZQKiaeh5sZ2pf5HDicTh34RIg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

- 
- 

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