# MInference的实践



**一、TTFT速度的暴力拉升**

微软最新发布了一个推理工具：MInference：https://github.com/microsoft/MInference，从首页面介绍看，长上下文语言模型推理速度提升（TTFT）8倍。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhB7Dzyd8Lg7OprzxjH0m1rBhGouiaucKauCx0Z9WHNjF72ctYqd7reJ6A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

那么实测效果如何呢？

**二、长上下文语言模型推理的主要两个阶段**

### 1. **预填充阶段（Prefill Stage）**

- **描述**：在这个阶段，模型会处理输入的初始部分，通常是较长的上下文或提示。这一阶段的计算量较大，因为需要处理大量的输入数据。
- **目标**：快速高效地处理长上下文，生成初始的隐藏状态和注意力权重。
- **具体步骤**：
  - **输入处理**：模型接收并处理输入的长上下文或提示。
  - **注意力计算**：模型计算输入序列的注意力权重，通常使用稀疏注意力机制来加速计算。
  - **隐藏状态生成**：模型生成初始的隐藏状态，这些状态将用于后续的解码阶段。

### 2. **解码阶段（Decoding Stage）**

- **描述**：在预填充阶段之后，模型进入解码阶段。在这个阶段，模型会根据预填充阶段生成的隐藏状态和注意力权重，逐步生成新的输出（例如，生成文本的下一个词）。
- **目标**：逐步生成输出，通常是一个词一个词地生成，直到达到预定的长度或满足某个终止条件。
- **具体步骤**：
  - **逐步生成**：模型根据当前的隐藏状态和注意力权重，生成下一个词或标记。
  - **状态更新**：模型更新隐藏状态和注意力权重，以便生成下一个词。
  - **终止条件**：模型检查是否满足终止条件（例如，达到预定长度或生成结束标记），如果满足则停止生成。

### 具体示例

假设我们使用一个长上下文语言模型生成一篇文章的摘要，推理过程可能如下：

1. **预填充阶段**：
   - **输入**：整篇文章。
   - **处理**：模型处理文章的前几段，生成初始的隐藏状态和注意力权重。
   - **输出**：初始的隐藏状态和注意力权重。
2. **解码阶段**：
   - **输入**：预填充阶段生成的隐藏状态和注意力权重。
   - **逐步生成**：模型逐步生成摘要的每一句话，直到生成完整的摘要。
   - **状态更新**：每生成一个词，模型更新隐藏状态和注意力权重。
   - **终止条件**：生成达到预定长度或生成结束标记时停止。

### 也就是说：

- **预填充阶段（Prefill Stage）**：处理输入的长上下文，生成初始的隐藏状态和注意力权重。

- **解码阶段（Decoding Stage）**：根据预填充阶段生成的隐藏状态和注意力权重，逐步生成输出。

  这两个阶段协同工作，使得长上下文语言模型能够高效地处理输入并生成高质量的输出。希望这个简化的解释能更清晰地帮助你理解这两个关键阶段。

**三、MInference优化了什么？**

MInference 主要是优化了预填充阶段（Prefill Stage）的时间。

### 预填充阶段的优化

1. **稀疏计算方法**：
   - MInference 通过引入稀疏计算方法，减少了需要计算的注意力矩阵元素数量，从而加速了预填充阶段的计算。
   - 具体来说，MInference 识别了三种独特的稀疏模式：A形、垂直斜线和块稀疏，这些模式可以在 GPU 上进行高效的稀疏计算。
2. ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBauNAoqBoCfTSpkoGZZvOVF0XticeWib7t2UsOyb4PDNqmzo1IeCHVjjA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)
3. 
4. **动态稀疏编译器**：
   - MInference 使用动态稀疏编译器（如PIT和Triton）来构建优化的稀疏注意力内核，从而进一步加速计算。
   - 例如，对于垂直斜线模式，MInference 使用最后的查询（Q）和键（K）之间的注意力计算来估计垂直线和斜线的最佳索引，然后利用动态稀疏编译器构建垂直斜线FlashAttention内核。
5. **均值池化和矩阵乘法**：
   - 对于A形、垂直斜线和块稀疏模式，MInference 在注意力计算中使用查询（Q）和键（K）的均值池化，通过利用均值池化和矩阵乘法（MatMul）的交换性来估计稀疏索引。
   - 然后，使用Triton构建相应的稀疏FlashAttention内核，加速注意力计算。

### 解码阶段的影响

虽然MInference的主要目标是优化预填充阶段的时间，但这些优化也可能间接影响解码阶段的效率。以下是一些可能的影响：

1. **初始状态的高效生成**：
   - 通过加速预填充阶段，MInference 可以更快地生成初始的隐藏状态和注意力权重，这些状态和权重将用于解码阶段。
   - 更快的预填充阶段意味着解码阶段可以更早地开始，从而提高整体推理效率。
2. **稀疏注意力机制的延续**：
   - 如果解码阶段也能利用类似的稀疏注意力机制，那么解码阶段的计算也可能得到加速。
   - 例如，在逐步生成输出时，如果可以继续使用稀疏注意力计算，那么解码阶段的效率也会提高。

### 总结

- **主要优化**：MInference 主要优化了预填充阶段（Prefill Stage）的时间，通过引入动态稀疏注意力机制和优化的稀疏注意力内核，显著减少了预填充阶段的计算量和时间。
- **间接影响**：虽然MInference的主要目标是预填充阶段，但这些优化也可能间接提高解码阶段（Decoding Stage）的效率，特别是如果解码阶段也能利用类似的稀疏注意力机制。

**四、MInference 识别了三种独特的稀疏模式详解**

### 1. **Λ形头（Λ-shape head）**

- **特点**：
  - 这种模式的稀疏结构呈现出一个倒V字形（Λ形）。
  - 在这种结构中，只有对角线及其附近的元素会被计算，其他部分则被忽略。
- **实现方法**：
  - 在注意力计算中，我们首先使用查询（Q）和键（K）的均值池化（mean pooling）。
  - 通过利用均值池化和矩阵乘法（MatMul）的交换性，我们估计出Λ形的稀疏索引。
  - 然后，我们使用Triton构建Λ形FlashAttention内核，加速注意力计算。
- **适用场景**：
  - **自然语言处理**：在处理句子时，词语与其相邻词语之间的关系往往更为重要。
  - **时间序列数据**：在时间序列数据中，当前时间点与其前后时间点之间的关系通常更为重要。

### 2. **垂直斜线头（vertical-slash head）**

- **特点**：
  - 这种模式的稀疏结构由垂直线和斜线组成。
- **实现方法**：
  - 我们首先使用最后的查询（Q）和键（K）之间的注意力计算来估计垂直线和斜线的最佳索引。
  - 然后，我们利用动态稀疏编译器PIT和Triton构建垂直斜线FlashAttention内核，加速注意力计算。
- **适用场景**：
  - **问答系统**：在问答系统中，问题的关键词和答案的关键词之间的关系可能更为重要。
  - **信息检索**：在信息检索任务中，查询词和文档中相关词之间的关系可能更为重要。

### 3. **块稀疏头（block-sparse head）**

- **特点**：
  - 这种模式的稀疏结构由若干个块状区域组成。
- **实现方法**：
  - 在注意力计算中，我们首先使用查询（Q）和键（K）的均值池化（mean pooling）。
  - 通过利用均值池化和矩阵乘法（MatMul）的交换性，我们估计出块稀疏的索引。
  - 然后，我们使用Triton构建块稀疏FlashAttention内核，加速注意力计算。
- **适用场景**：
  - **长文档处理**：在处理长文档时，某些段落可能包含了大部分的关键信息。
  - **图像处理**：在图像处理任务中，某些区域可能包含了大部分的关键信息。

### 总结

- **Λ形头**：通过均值池化和矩阵乘法的交换性估计Λ形稀疏索引，适用于相邻元素之间关系更为重要的情况。

- **垂直斜线头**：通过最后的Q和K之间的注意力计算估计垂直线和斜线的最佳索引，适用于特定位置的元素之间关系更为重要的情况。

- **块稀疏头**：通过均值池化和矩阵乘法的交换性估计块稀疏索引，适用于信息集中在特定块状区域的情况。

  通过选择合适的稀疏注意力模式，可以在保持模型准确性的同时，大大减少计算量，从而加速推理过程。每种模式都有其特定的适用场景，根据任务的特点选择最合适的模式，可以获得最佳的性能。

**五、实测结果**

我放四组图，分别是对比在不同长度的input下，MInference和HF对比，TTFT的时间：

**第一组：MIference是HF TTFT速度的6.2倍：**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBRzauL6NZNClwzS1ibh2o6ghk0W45McAjSdJOTzrSVJGHtia3qMjqlkdA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBc8W2NWkM1XAn6qxv3GEEMsIQ1qp0BQKnccspyyL77aul8nCXoz1stQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**第二组：MIference是HF TTFT速度的21%：**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhB3oJDViaj1wyYAArtLgNialiccpnqjpVVc3icEQoSAhKO5yqScWt69Pz45g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhB4J9ukzZiadjYQgVB8E8S2LZIsCCdzU3hdtW91iaz4ycDT4kVbZPjcdlA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**第三组：MIference是HF TTFT速度的73%：**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBzaamQ99eiatIHf26Wa18pTmM5XkleNlrNDGlLBAjQldPMaJgUf9A40Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBEzLmJN2F7IroY1sQLHk3LAj4aZfLmZWXibjnuHRf6LvPXXb5DMsJZbA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**第四组：MIference是HF TTFT速度的1.15倍：**

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBCMPEfouMl9YAaqW2Ebp7WswFq9Jiaribn7ceiaN3ZwqkwxVID3IJQsRibg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBSYGY8XWvW5iaTR56Ho81AYcHsR405KNIL4oF1MdjSje8SNj5rREWfYQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

从以上四组数据，我们可以大致判断出来，当输入在9K-10K时，MIference的速度开始比HF TTFT速度的快。随着输入的增加，MIference的TTFT速度快速提升。

我测试的数据，与MInference官网的数据也是基本一致的。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbh5eMicZRkJWU3eUeQNIhBy3Yzzee1lILlLicRHNFPlVVzCaEJ8nQ2BzHbRaCl8TrVu1OVGGwMj2A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

**六、结论**

微软开源的MInference，其核心是动态稀疏注意力。Minference在输入token长的情况下才发挥好的作用。在常规推理场景下，如聊天，其性能不如paged atten。因此，MInference属于在特定场景下TTFT速度的暴力提升，但它不属于推理圈的常规作战武器。