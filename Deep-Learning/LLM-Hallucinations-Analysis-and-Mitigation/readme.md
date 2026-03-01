# 当LLM出现幻觉时它想什么？

参考论文:

https://arxiv.org/pdf/2410.02707



在GPT这些模型在实际应用中存在一个重要的问题——幻觉（Hallucinations）。即它们可能生成看似合理但实际上错误的内容，涉及事实性错误、逻辑矛盾或不合常识的回答。

**一、什么是LLMs的幻觉？**

幻觉是指模型在生成文本时，输出了不正确或虚构的信息。这些错误可能是事实性错误、逻辑漏洞、偏见或者是违反常识的内容。 例如，当你问一个LLM：“世界上最高的山是什么？”模型可能正确地回答：“珠穆朗玛峰是世界上最高的山。”但有时候，它可能会回答：“乞力马扎罗山是世界上最高的山。”这种情况下，模型生成了一个事实性错误的回答，即产生了幻觉。

**二、LLMs内部知道它们何时犯错**

**1. 真实性信息集中在“确切答案词元上**

研究人员发现，LLMs在生成答案时，关于答案真假的信息主要集中在确切答案词元（exact answer tokens）上。所谓确切答案词元，是指在模型生成的答案中，直接给出关键信息的词。例如，在回答“中国首都在哪里？时，模型可能回答：“中国的首都在北京。”这里的“北京”就是确切答案词元。

**2. 利用探测分类器提高错误检测**

基于上述发现，研究人员训练了探测分类器（probing classifiers），专门对LLM在生成确切答案词元时的内部激活状态进行分析，以预测答案的正确性。他们的实验表明，针对确切答案词元的内部表示进行训练，可以显著提高错误检测的性能。

**3. 模型的内在表示包含更多信息**

即使LLM生成了错误的答案，其内部表示却可能已经包含了正确答案的信息。这意味着模型“知道”正确的答案，但在生成过程中由于各种原因（如训练策略、解码方法等）输出了错误的内容。 

**三、模型内外不一致的原因以及工程学上的意义**

模型的内部表示与其外部输出可能存在不一致性，这一发现揭示了LLMs在训练和生成过程中的一些深层次问题。 例子5：模型内部知道，但外部不说  假设我们问模型：“爱因斯坦提出的著名方程是什么？”模型回答：“爱因斯坦提出了相对论，但我不确定具体的方程。”然而，模型内部可能已经生成了“E=mc²”，但由于一些原因（可能是训练中学到的表达方式或者谨慎策略），没有在外部输出。 这个例子表明，我们可以尝试调整模型的生成策略，让其更充分地利用内部的正确信息，提供更准确的答案。

1. 优化模型的训练策略：在训练过程中，增加对正确答案词元的关注度，或者引入新的损失函数，强化模型对真实性的敏感性。
2. 改进解码方法：在生成过程中，结合探测分类器的反馈，实时调整生成路径，引导模型输出正确的答案。
3. 开发开放源码模型：由于利用模型内部激活状态需要白盒访问，开源的模型更有利于工程实践中的应用和改进。



**四、激活**

首先还是要普及一下“激活”的概念。

### 1、什么是激活（Activation）？

在神经网络（包括大型语言模型）中，**“激活”**是指神经元在接收到输入信号后输出的结果。可以把它想象成每个神经元的“兴奋程度”或“活跃程度”。

**通俗的比喻：**

- 把一个神经网络想象成一群决策者（神经元）在开会。
- 每个决策者接收到信息（输入），然后根据自己的判断标准，决定要不要“发言”或者“表态”。
- **激活**就是这个决策者的“发言力度”或“支持程度”，可能强烈支持，也可能不表态，或者反对。

在神经网络中，激活函数决定了神经元的输出（激活值）的范围。常见的激活函数有：

- 线性激活函数

  \- 特点：没有对输入进行任何非线性变换。

  \- 激活值范围：从负无穷到正无穷，激活值可以是任何实数。

- ReLU（Rectified Linear Unit）激活函数：

  \- 公式：f(x) = max(0, x)

  \- 特点：将输入小于0的部分截断为0，输入大于0的部分保持不变。

  \- 激活值范围：0到正无穷，可以超过1。

- Sigmoid激活函数：

  \- 公式：f(x) = 1 / (1 + e^{-x})

  \- 特点：将输入压缩到0到1之间。

  \- 激活值范围：0到1，不会超过1。

- Tanh激活函数：

  \- 公式：f(x) = (e^{x} - e^{-x}) / (e^{x} + e^{-x})

  \- 特点：将输入压缩到-1到1之间。

- GeLU（Gaussian Error Linear Unit）激活函数：

  \- 常用于Transformer模型。

  \- 特点：是一种平滑的非线性函数，没有严格的上下限。

  \- 激活值范围：理论上从负无穷到正无穷，但实际值集中在一定范围内。

### 2、激活有高低之分

- **高激活**：表示神经元对当前输入非常“感兴趣”或“敏感”，输出的数值较大。

- **低激活**：表示神经元对当前输入不太“感兴趣”，输出的数值较小，甚至为零。

  **在模型中，激活通常是一个数值，可以是正的、负的、或者在一定范围内变化。**

### 3、在模型生成答案时，激活的作用

当模型处理一个问题并生成答案时，它会对可能的候选答案进行评估。

- **每个可能的答案**（如“尼罗河”、“亚马逊河”）都会在模型的内部产生一系列的激活值。

- **激活值的大小**反映了模型对于某个答案的“信心”或“关注度”。

  **举例说明：**

- **问题**：”世界上最长的河流是什么？“

- **模型可能考虑的候选答案**：尼罗河、亚马逊河、长江、密西西比河等。

  

  **模型内部可能的激活情况：**

- **尼罗河**：激活值较高（例如0.8）

- **亚马逊河**：激活值也较高（例如0.75）

- **长江**：激活值较低（例如0.4）

- **密西西比河**：激活值很低（例如0.2）

  

- **解释：**

- 模型的内部激活状态显示，它认为“尼罗河”是一个很有可能的答案，“亚马逊河”也有可能。

- 最终，模型可能因为各种原因（如训练数据的偏差、解码策略等）选择了激活值略低的“亚马逊河”作为输出。

### 4、发现模型对“尼罗河”有高激活意味着什么？

当我们说**“发现模型实际上对于‘尼罗河’也有很高的激活”**，意思是：

- **模型的内部计算**已经将“尼罗河”视为一个强有力的候选答案，对其有很高的关注度或信心。
- **虽然最终输出了“亚马逊河”**，但从内部激活状态来看，“尼罗河”也是模型高度认可的答案之一。

### ** **

### **5、激活高但未输出的原因**

**那么，为什么模型没有输出激活值更高的“尼罗河”呢？**

可能的原因包括：

1. **解码策略的影响**：
   - 模型在生成答案时，使用了**概率采样**（如温度采样）或其他策略，导致并非总是选择激活值最高的词。
2. **训练数据的影响**：
   - 如果训练数据中，关于“亚马逊河是最长河流”的错误信息较多，模型可能受到误导。
3. **模型的不确定性**：
   - 模型在“尼罗河”和“亚马逊河”之间的激活值很接近，导致选择了激活值略低的“亚马逊河”作为输出。

### 6、激活的大小帮助我们理解模型的内部决策过程

通过分析模型内部的激活值，我们可以：

- **理解模型的信心分布**：知道模型对哪些候选答案有较高的信心。
- **发现潜在的正确答案**：即使模型输出了错误的答案，但其内部可能已经“想到”了正确的答案。

### 7、利用激活信息改进模型

如果我们知道模型对正确答案有高激活值，我们可以：

1. **调整解码策略**：
   - 修改模型的解码算法，让其更倾向于选择激活值最高的词。
2. **纠正模型输出**：
   - 利用内部激活信息，开发纠错机制，纠正模型的错误输出。
3. **训练模型更好地利用内部知识**：
   - 在训练过程中，强化模型对正确答案的偏好，降低错误答案的激活值。



**五、当确切答案的激活值最高时，模型仍可能出现幻觉的原因**

即使确切答案的激活值最高，模型仍可能输出错误的答案，即产生幻觉。原因包括但不限于如下几条。

**1. 激活值与最终输出之间的关系并非绝对直接：**

  \- 激活值：在模型的内部计算过程中，每个可能的候选词（或词元）都会有一个对应的激活值，表示模型对该词的“内部偏好”或“信心”。

  \- 解码过程：模型在生成最终输出时，会根据激活值以及解码策略（如贪心搜索、温度采样、Beam Search等）来选择下一个词元。

**2. 解码策略可能导致激活值最高的答案未被输出**

  \- 温度采样（Temperature Sampling）：在生成文本时，模型会根据激活值（通常是经过Softmax函数得到的概率分布）进行采样。如果温度参数较高，模型更倾向于探索，可能会选择激活值并非最高的词元。

  \- 随机性：即使激活值最高的词元在概率上占优势，但在采样过程中，仍有可能选择其他激活值较低的词元。

**3. 其它因素导致幻觉的产生**

  \- 训练数据的偏差：如果模型的训练数据中包含错误或误导性的信息，即使模型内部对正确答案有高激活值，可能仍受到错误信息的影响，最终输出错误答案。

  \- 模型的表达能力限制：模型可能缺乏足够的参数或结构来正确地生成准确的答案，导致即使内部有正确的信息，输出时仍出现幻觉。

  \- 上下文影响：模型的输出还受上下文和先前生成内容的影响，可能导致偏离正确答案。

   **总结：**

激活值最高的答案不一定会被输出，因为生成过程受到解码策略、随机性和其他因素的影响。

因此，即使确切答案的激活值最高，模型仍可能输出错误的答案，产生幻觉。

**六、解码中的几个的策略-贪心解码**

贪心解码只关注每一步的局部最优选择，可能导致生成重复的模式或循环，如 **A B A B**。

这种重复可能是因为某些词元在特定的上下文中总是具有最高的概率，导致模型反复选择它们。

**为了更直观地理解，让我们以实际句子生成为例。
**

### 示例场景：

**任务：** 让模型续写一句话，起始句是：

- **起始句：**“天气真好，我想去”

### 1. 使用贪心解码生成的结果

**贪心解码过程：**

- 时间步 1：

  - **输入：**“天气真好，我想去”
  - **模型预测：**概率最高的词是“散步”

- 时间步 2：

  - **输入：**“天气真好，我想去散步”
  - **模型预测：**概率最高的词是“。”

- 时间步 3：

  - **输入：**“天气真好，我想去散步。”
  - **模型预测：**概率最高的词是“我”

- 时间步 4：

  - **输入：**“天气真好，我想去散步。我”
  - **模型预测：**概率最高的词是“想”

- 时间步 5：

  - **输入：**“天气真好，我想去散步。我想”
  - **模型预测：**概率最高的词是“去”

- 时间步 6：

  - **输入：**“天气真好，我想去散步。我想去”

  - **模型预测：**概率最高的词是“散步”

    **生成的句子：**

- “天气真好，我想去散步。我想去散步。我想去散步。……”

###  

### **2. 分析**

- 出现了重复的模式“我想去散步”
  - 模型在句号后继续生成时，总是认为“我想去”后接“散步”概率最高，导致重复。
- 贪心解码没有考虑全局的上下文和内容的多样性
  - 只关注当前最可能的词，忽略了潜在的更丰富的表达。

### **3. 改进生成结果**

为了避免这种重复，可以采用其他解码策略，比如 **Top-k 采样** 或 **Top-p 采样**，引入一定的随机性和多样性。

**使用 Top-p 采样（p=0.9）生成的结果：**

- 时间步 1：

  - **输入：**“天气真好，我想去”
  - **模型预测：**概率最高的词是“散步”（0.4），其次是“公园”（0.35），再次是“旅行”（0.15），其他词概率较低。

- **Top-p 采样**在累计概率超过0.9时，选择候选词元集合：**“散步”、“公园”、“旅行”**。

- **随机采样可能选择“公园”**

  

- 时间步 2：

  - **输入：**“天气真好，我想去公园”
  - **模型预测：**概率较高的词是“赏花”、“散步”、“运动”。

- **随机采样可能选择“赏花”**

  

- 时间步 3：

  - **输入：**“天气真好，我想去公园赏花”
  - **模型预测：**概率较高的词是“。”、“，欣赏美景”、“，呼吸新鲜空气”。

- **随机采样可能选择“。”**

  **生成的句子：**

- “天气真好，我想去公园赏花。”

  

### 4. 改进的效果

- **避免了重复，生成了更丰富、更自然的句子**

- **引入了多样性，使得内容更加有趣**

  

### **5. A B A B 的问题总结**

- 代表模型在贪心解码下可能生成的重复序列，导致输出内容单调乏味。
- 出现这种情况是因为模型每次都选择最有可能的词，忽略了全局的连贯性和多样性。

###  

### 解决方法

- **引入随机性：**使用 Top-k 或 Top-p 采样，让模型有机会选择概率稍低但合理的词，增加生成内容的多样性。
- **调整解码策略：**采用组合解码策略，避免模型陷入重复循环。

### 6. 案例启示

- **贪心解码适用于需要高确定性的任务，但可能导致重复和缺乏创意。**
- **在自然语言生成中，为了生成更加自然、流畅的文本，常常需要在准确性和多样性之间取得平衡。**



***\*七、解码中的几个的策略-\*\*束搜索 Beam Search\*\**\***


## Running on Azure

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


## 1. 原理

是一种在解码过程中保留多个可能序列的策略。它在每个时间步保留得分最高的 **Beam Width（束宽）** 个部分序列，然后对这些序列进行扩展。它试图在计算资源允许的情况下找到更优的序列。

### 2. 特点

- 优点：
  - 比贪心搜索更有可能找到全局最优的序列。
  - 通过保留多个候选，可以避免陷入局部最优。
- 缺点：
  - 计算量比贪心搜索更大。
  - 可能导致输出较为通用，缺乏多样性。

###  

### 3. 示例

**任务：** 续写句子 “天气真好，我想去”

**设置：**

- **束宽（Beam Width）：** 3

- **模型在每个时间步提供的候选词及其得分（假设得分为对数概率的负值，得分越低越好）。**

  **时间步 1：**

- **输入：**“天气真好，我想去”

- **模型预测候选词：**

  1. **公园**（得分 0.5）

  2. **散步**（得分 0.6）

  3. **旅游**（得分 0.7）

  4. **购物**（得分 0.9）

     **因为束宽为3，我们保留得分最低的前三个词。在束搜索中，\**确实是保留得分最低的序列\**，这是因为得分被定义为负的对数概率（Negative Log-Likelihood，NLL）。由于对数概率是负值，得分越低，表示概率越高。**

     

- 序列1：“公园”（总得分 0.5）

- 序列2：“散步”（总得分 0.6）

- 序列3：“旅游”（总得分 0.7）

  **时间步 2：**

  对每个保留的序列进行扩展：

  **对于序列1：“……我想去公园”**

- **候选词：**

  1. **散步**（得分 0.4）→ 序列：“……公园散步”（总得分 0.5+0.4=0.9）

  2. **赏花**（得分 0.5）→ 序列：“……公园赏花”（总得分 0.5+0.5=1.0）

  3. **拍照**（得分 0.6）→ 序列：“……公园拍照”（总得分 0.5+0.6=1.1）

     **对于序列2：“……我想去散步”**

- **候选词：**

  1. **。**（句号，得分 0.3）→ 序列：“……散步。”（总得分 0.6+0.3=0.9）

  2. **，**（逗号，得分 0.5）→ 序列：“……散步，”（总得分 0.6+0.5=1.1）

  3. **和朋友**（得分 0.7）→ 序列：“……散步和朋友”（总得分 0.6+0.7=1.3）

     **对于序列3：“……我想去旅游”**

- **候选词：**

  1. **放松**（得分 0.6）→ 序列：“……旅游放松”（总得分 0.7+0.6=1.3）

  2. **拍照**（得分 0.7）→ 序列：“……旅游拍照”（总得分 0.7+0.7=1.4）

  3. **。**（句号，得分 0.5）→ 序列：“……旅游。”（总得分 0.7+0.5=1.2）

     **将所有新序列按照总得分排序，保留得分最低的3个序列：**

1. “……我想去公园散步”（总得分 0.9）

2. “……我想去散步。”（总得分 0.9）

3. “……我想去公园赏花”（总得分 1.0）

   **时间步 3：**

   继续对保留的序列进行扩展：

   **对于序列：“……我想去公园散步”**

- **候选词：**

  1. **。**（得分 0.3）→ 序列：“……公园散步。”（总得分 0.9+0.3=1.2）

  2. **，**（得分 0.5）→ 序列：“……公园散步，”（总得分 0.9+0.5=1.4）

     **对于序列：“……我想去散步。”**

- **句子已完结，不再扩展。**

  **对于序列：“……我想去公园赏花”**

- **候选词：**

  1. **。**（得分 0.3）→ 序列：“……公园赏花。”（总得分 1.0+0.3=1.3）

  2. **拍照**（得分 0.6）→ 序列：“……公园赏花拍照”（总得分 1.0+0.6=1.6）

     **保留得分最低的3个序列：**

1. “……我想去散步。”（总得分 0.9）*（已完成）*

2. “……我想去公园散步。”（总得分 1.2）

3. “……我想去公园赏花。”（总得分 1.3）

   **最终结果：**

- **得分最低的序列是：“天气真好，我想去散步。”（总得分 0.9）**

  **分析：**

- **束搜索通过考虑多个候选序列，避免了贪心搜索可能导致的次优选择。**

- **生成的句子自然且逻辑通顺，模型选择了得分最高的完整句子。**



## ***\*八、解码中的几个的策略-\******温度采样（Temperature Sampling）**



### 1. 原理

**温度采样**通过调整概率分布的“温度”参数 ( T )，改变模型对高低概率词的偏好，从而控制生成文本的随机性和多样性。

- 温度 ( T ) 的作用：
  - ( T < 1 )：降低随机性，模型更倾向于选择高概率词元。
  - ( T > 1 )：增加随机性，模型有更大概率选择低概率词元。

### 2. 示例

**任务：** 续写句子 “天气真好，我想去”

**场景设置：**

- **模型在某个时间步的原始概率分布（在不考虑具体数值的情况下）：**
  - **散步**（概率高）
  - **公园**（概率较高）
  - **海边**（概率中等）
  - **爬山**（概率较低）
  - **购物中心**（概率更低）

### 3. 使用不同的温度参数



#### a. 温度 ( T = 0.7 )（低温度）

**调整后的概率分布：**

- **高概率词的概率进一步增大，低概率词的概率降低。**

  **可能的输出：**

- **模型更可能选择“散步”或“公园”**

  **生成的句子：**

- “天气真好，我想去散步。”

  **分析：**

- **低温度使模型的输出更保守，选择最有可能的词。**

- **生成的句子较为常见，创造性低。**

#### b. 温度 ( T = 1.0 )（标准温度）

**调整后的概率分布与原始概率分布相同。**

**可能的输出：**

- **模型可能选择“散步”、“公园”或“海边”**

  **生成的句子：**

- “天气真好，我想去海边。”

  **分析：**

- **模型有适度的随机性，可能生成多种合理的句子。**

#### c. 温度 ( T = 1.5 )（高温度）

**调整后的概率分布：**

- **概率分布变得更平坦，低概率词的概率增加。**

  **可能的输出：**

- **模型有较大概率选择“爬山”或“购物中心”**

  **生成的句子：**

- “天气真好，我想去爬山。”

  **分析：**

- **高温度增加了输出的多样性，可能会生成更有创意的句子。**

- **但温度过高可能导致生成不符合逻辑的句子，如“天气真好，我想去购物中心。”（在好天气下去室内可能不符合常理）**



## ***\*九、解码中的几个的策略-\******Top-k 采样**



### 1. 原理

**Top-k 采样**在每个时间步只考虑概率排名前 ( k ) 的词元，其余词的概率设为零，然后重新归一化概率分布，再进行随机采样。

### 2. 示例

**任务：** 续写句子 “天气真好，我想去”

**模型在当前时间步的概率分布（假设）：**

1. **散步**（0.4）
2. **公园**（0.3）
3. **海边**（0.15）
4. **电影院**（0.05）
5. **购物中心**（0.04）
6. **图书馆**（0.03）
7. **健身房**（0.02）
8. **医院**（0.01）

### 3. 使用不同的 ( k ) 值



#### a. ( k = 3 )

**保留前三个词元：**

- **散步**

- **公园**

- **海边**

  **重新归一化后的概率：**

- **散步：0.4 / 0.85 ≈ 0.47**

- **公园：0.3 / 0.85 ≈ 0.35**

- **海边：0.15 / 0.85 ≈ 0.18**

  **可能的输出：**

- **随机选择“散步”、“公园”或“海边”**

  **生成的句子：**

- “天气真好，我想去公园。”

#### b. ( k = 5 )

**保留前五个词元：**

- **散步**

- **公园**

- **海边**

- **电影院**

- **购物中心**

  **重新归一化后的概率：**

- **散步：0.4 / 0.94 ≈ 0.43**

- **公园：0.3 / 0.94 ≈ 0.32**

- **海边：0.15 / 0.94 ≈ 0.16**

- **电影院：0.05 / 0.94 ≈ 0.053**

- **购物中心：0.04 / 0.94 ≈ 0.043**

  **可能的输出：**

- **有小概率会选择“电影院”或“购物中心”**

  **生成的句子：**

- “天气真好，我想去电影院。”

  **分析：**

- **较小的 ( k ) 值控制了随机性，确保生成合理的词。**

- **较大的 ( k ) 值增加了多样性，但可能引入不太合理的选择。**



## **十、\**\*\*解码中的几个的策略-\*\*束搜索\*\*\*\*\** Top-p（核）采样**

### 1. 原理

**Top-p 采样**（又称核采样）在每个时间步动态选择一组词元，使得这些词的累计概率超过阈值 ( p )，然后从中进行随机采样。

### 2. 示例

**任务：** 续写句子 “天气真好，我想去”

**模型在当前时间步的概率分布（按概率从高到低排序）：**

1. **散步**（0.4）→ 累计概率 0.4
2. **公园**（0.3）→ 累计概率 0.7
3. **海边**（0.15）→ 累计概率 0.85
4. **电影院**（0.05）→ 累计概率 0.90
5. **购物中心**（0.04）→ 累计概率 0.94
6. **图书馆**（0.03）→ 累计概率 0.97
7. **健身房**（0.02）→ 累计概率 0.99
8. **医院**（0.01）→ 累计概率 1.00

### 3. 使用不同的 ( p ) 值



#### a. ( p = 0.85 )

**候选词元集合：**

- 散步

- 公园

- 海边

  重新归一化后的概率：

- 散步：0.4 / 0.85 ≈ 0.47

- 公园：0.3 / 0.85 ≈ 0.35

- 海边：0.15 / 0.85 ≈ 0.18

  可能的输出：

- 随机选择“散步”、“公园”或“海边”

  生成的句子：

- “天气真好，我想去海边。”

#### b. ( p = 0.9 )

**候选词元集合：**

- 散步

- 公园

- 海边

- 电影院

  重新归一化后的概率：

- 散步：0.4 / 0.9 ≈ 0.44

- 公园：0.3 / 0.9 ≈ 0.33

- 海边：0.15 / 0.9 ≈ 0.17

- 电影院：0.05 / 0.9 ≈ 0.056

  **可能的输出：**

- **有小概率选择“电影院”**

  **生成的句子：**

- “天气真好，我想去电影院。”

  **分析：**

- Top-p 采样根据概率分布动态调整候选集合，比Top-k 采样更灵活。

- 当模型对前几个词的置信度很高时，候选集合小，输出更可靠。

- 当概率分布较平坦时，候选集合大，增加了随机性和多样性。



## **十一、组合策略和其他调整**



### 1. 禁止重复 n-gram

**原理：**

- 在生成过程中，禁止模型生成重复的 n-gram（如重复的短语），防止输出中出现重复。

### 示例

任务： 续写句子 “天气真好，我想去”

**问题：**

- 模型可能产生“……我想去公园，我想去公园。”的重复句子

  解决方案：

- 在解码过程中，如果发现生成的词会导致重复 n-gram，则降低其概率或将其设为零

  效果：

- 模型被迫选择其他合理的词，避免了重复

  生成的句子：

- “天气真好，我想去公园，感受大自然的气息。”

### 2. 长度惩罚

**原理：**

- 在解码时，对过短或过长的序列施加惩罚，控制生成内容的长度

  示例：

- 若模型倾向于生成过短的句子，长度惩罚可以鼓励其生成更完整的句子

  **生成的句子：**

- “天气真好，我想去公园散步，享受阳光明媚的下午。”



## **总结**

- 不同的解码策略可以影响模型生成文本的风格和质量。
- 贪心搜索简单但可能导致重复和缺乏多样性。
- 束搜索通过考虑多个候选序列，生成更优质的文本，但计算开销更大。
- 温度采样、Top-k 采样和 Top-p 采样通过引入随机性，增加了生成文本的多样性和创造性。
- 组合使用这些策略，并结合重复惩罚、长度惩罚等方法，可以进一步优化模型的输出，满足不同的需求。

---

# Part 2: Reducing LLM Hallucinations  Mitigation Strategies

> *Merged from the original [Reducing-LLM-Hallucinations](../Agents/) project.*

Hallucination refers to instances where AI models generate text that, while grammatically correct and seemingly plausible, is not based on the given input and may even be factually incorrect.

## Why Do LLMs Generate Hallucinations?

As mentioned, language models may hallucinate and produce outputs containing fabricated or erroneous responses. These errors highlight the limitations of AI, underscoring the importance of human supervision and cross-referencing with reliable sources for verification. However, assigning humans to verify every response is neither feasible nor scalable. We will discuss hallucination mitigation strategies later, but first, let's explore why LLMs generate hallucinations:

- **Insufficient Training Data**: A model that has not encountered diverse data during training may fail to establish accurate correlations between input and output, leading to hallucinated content.
- **Lack of Supervision**: Without proper guidance, the model may overly rely on its internal logic, resulting in seemingly hallucinatory outputs.
- **Model Overfitting**: Overfitting to the training data can cause the model to generate outputs similar to the training set but inconsistent with new or different inputs.
- **Knowledge Cutoff**: LLMs like ChatGPT have a knowledge cutoff date and are unaware of information beyond that date. They might unknowingly respond with outdated information, which is no longer relevant.

## Types of LLM Hallucinations


We can categorize these hallucinations into three main types:

### Factually Inaccurate

This type of hallucination occurs when the language model presents information that is untrue or incorrect but framed as fact. This includes dates, events, statistics, or verifiable misstatements. It may occur for various reasons, including misinterpretation of input data, low-quality data and training methods, reliance on outdated or incorrect sources, or mixing different background information leading to inaccurate outputs.

### Fabricated Citations or Sources

This occurs when the language model fabricates citations or references. It might generate a statement and wrongly attribute it to a real person or create a fictitious source that does not exist. This is problematic as it can lead to misinformation, misattributed statements, and confusion.

### Logical Inconsistencies

This includes generating responses that are internally inconsistent or logically flawed. After generating a response to a user's query, the LLM might contradict itself in subsequent responses. When the model makes a series of statements, and these statements are incoherent or contradictory when combined, it challenges the credibility of the model's outputs and confuses users who rely on its consistency.

In all these cases, the language model is not intentionally misleading but demonstrates its limitations due to various factors such as training data, data quality, knowledge cutoff dates, poor fine-tuning, etc.

## LLM Hallucination Mitigation Strategies: RAG, Pre-Generation Strategies, Post-Generation Strategies


Researchers are developing various methods to ensure the accuracy of responses generated by LLMs. Some strategies require human intervention, such as Reinforcement Learning with Human Feedback (RLHF); using high-quality data for fine-tuning; employing RAG, etc.

### Retrieval-Augmented Generation (RAG)

- Self-RAG：

   Self-RAG enables LLMs to dynamically retrieve relevant passages until the entire context is captured, all within a specified window.

  - Technical Implementation:
    - **Initial Retrieval**: Upon receiving a user's query, the model performs an initial retrieval to gather relevant passages from an external knowledge base.
    - **Generate Preliminary Response**: Based on the initially retrieved passages, the model generates a preliminary response.
    - **Dynamic Retrieval**: The model evaluates the completeness and accuracy of the preliminary response. If more information is needed, it performs further retrieval to gather more relevant passages.
    - **Iterative Process**: Repeat steps 2 and 3 until the model deems sufficient context has been acquired to generate an accurate response.
    - **Final Response**: Based on all retrieved passages, generate the final response.

- **Multimodal RAG**: Multimodal RAG combines text data with images and other media to provide a deeper contextual understanding, resulting in more accurate and relevant responses.

  Apart from RAG, we can divide these strategies into two parts: pre-generation strategies and post-generation strategies.

### Pre-Generation Strategies

Pre-generation strategies prevent AI from generating incorrect or misleading information in the first place. These include:

1. Chain of Verification (CoVe): Involves the model self-verifying its responses. Multi-stage verification makes it more efficient.


2. Optimisation by Prompting (OPRO): LLMs optimize their own prompts, correcting prompt inputs.


3. System 2 Attention (S2A): This approach improves LLM's reasoning. An instruction-tuned LLM is used to identify, analyze, and extract the most relevant parts of the input context, mitigating the impact of unnecessary information.

4. EmotionPrompt: This technique uses emotional cues through prompts, enabling LLMs to gain more context and emotional insight.


5. Step-Back Prompting: A method to enhance LLM reasoning and problem-solving skills.


6. Rephrase and Respond (RaR): This technique allows LLMs to rephrase and expand on human-posed questions/prompts, helping LLMs gain insightful context.

### Post-Generation Strategies

Post-generation strategies involve verifying and correcting AI's output after generation. These include:

1. **Fact-Checking**: Implementing human-in-the-loop (HITL) and knowledge bases to verify the accuracy of the information provided by LLMs.

2. **Preference Alignment**: Using human feedback mechanisms (RLHF) to align LLM outputs with human values and preferences. Refer to my repo: * https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/LLM-Alignment-DPO-RHLF-CPO*

   These strategies aim to enhance the reliability of AI systems, improve the quality of their outputs, and ensure alignment with human values and factual accuracy.



## Pre-Generation Strategies Code

### Chain of Verification (CoVe):

Refer to ：https://github.com/ritun16/chain-of-verification/tree/main

![CoVe_Architecture](https://private-user-images.githubusercontent.com/44939374/273401645-3efc0f5a-b7c6-4655-8a0e-e16c01cac97e.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3MjU0NTMwNTUsIm5iZiI6MTcyNTQ1Mjc1NSwicGF0aCI6Ii80NDkzOTM3NC8yNzM0MDE2NDUtM2VmYzBmNWEtYjdjNi00NjU1LThhMGUtZTE2YzAxY2FjOTdlLnBuZz9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFWQ09EWUxTQTUzUFFLNFpBJTJGMjAyNDA5MDQlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjQwOTA0VDEyMjU1NVomWC1BbXotRXhwaXJlcz0zMDAmWC1BbXotU2lnbmF0dXJlPTc0NDZkYTg1YzkxZDYyMWQ5NDFkZTQ2NmYxYjc4NzNmY2MyOGY0NGU0OGM5YWViYWE2NjBkZDZiNDNjMmI1NTMmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JmFjdG9yX2lkPTAma2V5X2lkPTAmcmVwb19pZD0wIn0.9dcOdD_i8pLqGc-BOE3n4xoUOFiDBJps_aHZn04iyGM)

These five source code files implement a system called "Chain of Verification (CoVE)" that generates more accurate answers by verifying and refining initial responses through multiple steps. Below is the implementation logic for each file:

#### 1. `cove_chains.py`

This file defines three main chain classes, each implementing a specific type of question handling logic:

- **WikiDataCategoryListCOVEChain**: Handles questions that require listing entities (e.g., names, places).

- **MultiSpanCOVEChain**: Handles questions that contain multiple independent answers.

- **LongFormCOVEChain**: Handles questions that require long answers.

  Each chain class follows a similar structure:

1. **Baseline Response Chain**: Generates the initial response.
2. **Verification Question Generation Chain**: Generates verification questions based on the initial response.
3. **Execute Verification Chain**: Executes the verification questions to obtain verification answers.
4. **Final Refined Response Chain**: Generates the final refined response based on the verification answers.

#### 2. `execute_verification_chain.py`

This file defines the `ExecuteVerificationChain` class, which executes verification questions and generates verification answers. The main logic includes:

1. **Search Tool**: Uses the DuckDuckGo search tool to find answers to verification questions.
2. **LLM Self-Evaluation**: Uses a language model (LLM) to generate verification answers.
3. **Combining Answers**: Combines verification questions and answers into the final output.

#### 3. `main.py`

This file is the entry point of the program, responsible for parsing command-line arguments and running the appropriate chain. The main logic includes:

1. **Parsing Command-Line Arguments**: Retrieves the user's question, LLM name, temperature, max tokens, etc.
2. **Initializing LLM**: Creates an instance of ChatOpenAI.
3. **Routing Chain Instance**: Creates and runs an instance of `RouteCOVEChain`.
4. **Outputting Results**: Prints the final answer and intermediate steps (if required).

#### 4. `prompts.py`

This file defines various prompt templates used to generate prompts at different stages. These templates include:

1. **Baseline Prompts**: Used to generate the initial response.
2. **Verification Question Prompts**: Used to generate verification questions.
3. **Execute Verification Prompts**: Used to execute verification questions.
4. **Final Refined Prompts**: Used to generate the final refined response.
5. **Router Prompts**: Used to classify the type of question.

#### 5. `route_chain.py`

This file defines the `RouteCOVEChain` class, which selects the appropriate chain based on the question type. The main logic includes:

1. **Initializing Chains**: Creates instances of `WikiDataCategoryListCOVEChain`, `MultiSpanCOVEChain`, and `LongFormCOVEChain`.
2. **Routing Logic**: Uses the LLM to select the appropriate chain based on the question content.
3. **Error Handling**: Uses a default `ConversationChain` if classification fails.

#### Summary

The overall workflow of the system is as follows:

1. The user inputs a question.

2. `RouteCOVEChain` selects the appropriate chain based on the question content.

3. The selected chain generates the initial response, verification questions, and verification answers through multiple steps, ultimately producing a refined response.

4. The final answer and intermediate steps (if required) are output to the user.

   This system aims to improve the accuracy and reliability of answers through a multi-step verification and refinement mechanism.

###  Optimisation by Prompting (OPRO)

 LLMs optimize their own prompts, correcting prompt inputs.

*https://cobusgreyling.medium.com/a-new-prompt-technique-from-deepmind-called-optimisation-by-prompting-opro-918b1057eacd*OPRO (Optimisation by PROmpting) is essentially a method to improve the performance of large language models (LLMs) by optimizing prompts. In simple terms, its core ideas are:

1. **Multiple Attempts**: Generate multiple different answers or solutions each time, rather than just one.

2. **Gradual Improvement**: Through multiple iterations, adjust and improve the prompts based on previous results, gradually finding better prompt formats.

3. **No Fine-Tuning Required**: It significantly improves the model's performance without the need for complex fine-tuning of the model itself, just by adjusting the input prompts.

   It's like continuously trying different answering strategies in an exam until you find the most effective one. OPRO finds the most suitable prompts for specific tasks and models by continuously optimizing the prompts, thereby improving the model's accuracy and reliability.

Let's look at a example:

Meta-Prompt = Meta-Instructions + Solution-Score Pairs + Meta-Instructions + Optimisation Task & Output Format + Meta-Instructions

#### Meta-Instructions

```
I have some texts along with their corresponding scores. 
The texts are arranged in ascending order based on their scores, 
where higher scores indicate better quality.
```

#### Solution-Score Pairs

```
text:
Let’s figure it out! score:
61

text:
Let’s solve the problem. score:
63

(... moreinstructionsandscores...)
```

#### Meta-Instructions

```
The following exemplars show how to apply your text: 
you replace <INS> in each input with your text, then read the input 
and give an output. We say your output is wrong if your output is 
different from the given output, and we say your output 
is correct if they are the same.
```

#### Optimisation Task & Output Format

```
input:
Q: Alannah, Beatrix, and Queen are preparing for the new school year and 
have been given books by their parents. 
Alannah has 20 more books than Beatrix. 
Queen has 1/5 times more books than Alannah. 
If Beatrix has 30 books, how many books do the three have together?
A: <INS>
output:
140

(... more exemplars ...)
```

#### Meta-Instructions

```
Write your new text that is different from the old ones and has a score 
as high as possible. Write the text in square brackets.
```

#### The Complete Prompt Concatenated:

```
I have some texts along with their corresponding scores. 
The texts are arranged in ascending order based on their scores, 
where higher scores indicate better quality.

text:
Let’s figure it out! score:
61

text:
Let’s solve the problem. score:
63

(... moreinstructionsandscores...)

The following exemplars show how to apply your text: 
you replace <INS> in each input with your text, then read the input 
and give an output. We say your output is wrong if your output is 
different from the given output, and we say your output 
is correct if they are the same.

input:
Q: Alannah, Beatrix, and Queen are preparing for the new school year and 
have been given books by their parents. 
Alannah has 20 more books than Beatrix. 
Queen has 1/5 times more books than Alannah. 
If Beatrix has 30 books, how many books do the three have together?
A: <INS>
output:
140

(... more exemplars ...)

Write your new text that is different from the old ones and has a score 
as high as possible. Write the text in square brackets.
```

The meta-prompt contains two core pieces of information:

1. The previously generated prompts with their corresponding training accuracies.
2. The optimisation problem description, which includes several exemplars randomly selected from the training set to exemplify the task of interest.

### System 2 Attention (S2A):

*https://jrodthoughts.medium.com/inside-system-2-attention-meta-ai-new-method-to-improve-reasoning-in-llms-4424751a6be1*

Large language models (LLMs) like ChatGPT are very smart, but sometimes they make simple mistakes. This is because they can easily be influenced by irrelevant information or biases in the input. For example, if you ask a question with some unrelated details, the AI might get misled by these details and give the wrong answer.

#### System 2 Attention (S2A) Method

The S2A method is inspired by the way humans think. Humans have two thinking modes:

1. **System 1**: Fast but prone to errors, intuitive thinking.

2. **System 2**: Slow but more accurate, deliberate thinking.

   S2A aims to make the AI think like human "System 2," focusing on important information and ignoring irrelevant details.

#### How S2A Works

1. **Clean the Context**: First, S2A will clean the input you give to the AI (like a question), removing any irrelevant information that might mislead the AI. It's like when you solve a problem, you remove the unnecessary parts and keep only the key information.
2. **Generate the Answer**: Then, the AI uses this cleaned input to generate the answer. This way, the AI won't be distracted by irrelevant information, and the answer will be more accurate.

#### An Example

Suppose you ask the AI a question: "Xiaoming has 10 apples, he ate 2 apples, and then he bought 5 more apples. Xiaoming likes blue apples, and his friend Xiaohong also likes apples. How many apples does Xiaoming have now?"

A regular AI might get confused by the irrelevant information like "Xiaoming likes blue apples" and "Xiaohong also likes apples," and give the wrong answer.

But an AI using the S2A method will first remove this irrelevant information, turning the question into: "Xiaoming has 10 apples, he ate 2 apples, and then he bought 5 more apples. How many apples does Xiaoming have now?" This way, the AI can more accurately answer: "13 apples."



```
Given the following text by a user, extract the part that is unbiased and not their opinion, so that using that text alone would be good context for providing an unbiased answer to the question portion of the text. 
  
Please include the actual question or query that the user is asking. Separate this into two categories labeled with “Unbiased text context (includes all content except user’s bias):” and “Question/Query (does not include user bias/preference):”.  
  
Text by User: [ORIGINAL INPUT PROMPT]  
```

![img](https://miro.medium.com/v2/resize:fit:1050/1*9ND1Ju9HtzNc3eeK4M2qoQ.png)

#### Experimental Results

Meta AI's research shows that after using the S2A method, the AI performs better in answering factual questions, generating long-form arguments, and solving math problems.

#### Summary

The S2A method makes the AI think like human "System 2," focusing on important information and ignoring irrelevant details, thereby improving the AI's accuracy and reasoning ability. I hope this explanation helps you!

### motionPrompt: 

#### This technique uses emotional cues through prompts, enabling LLMs to gain more context and emotional insight.

*https://www.linkedin.com/pulse/tap-ais-emotional-edge-utilizing-emotionprompt-improved-patrick-bands-jrqzf*

#### Definition of EmotionPrompt


**EmotionPrompt** is a technique designed to enhance the performance of Large Language Models (LLMs) by incorporating emotional stimuli into prompts. Specifically, EmotionPrompt involves adding emotional expressions or cues to the input prompts, aiming to improve the quality and accuracy of the generated responses. This technique leverages psychological phenomena such as self-monitoring, social cognitive theory, and cognitive emotion regulation to guide LLMs towards generating more positive, confident, and effective responses.

#### Implementation Principles


**Self-monitoring**:

- **Principle**: Individuals regulate and control their behavior in social situations. Emotional cues prompt the model to "perceive" these cues and adjust its output to align with expected emotional and social norms.

- **Effect**: Generates responses that better meet human expectations, improving the quality and naturalness of the responses.

  **Social Cognitive Theory**:

- **Principle**: Individuals learn by observing and imitating others' behaviors and regulate their actions through self-efficacy (confidence in their abilities). Emotional cues can enhance the model's "self-efficacy."

- **Effect**: Generates more positive and effective responses, enhancing user experience.

  **Cognitive Emotion Regulation**:

- **Principle**: Individuals regulate their emotional responses through cognitive reappraisal (reinterpreting situations). Emotional cues can guide the model to perform similar cognitive reappraisal.

- **Effect**: Generates more accurate and appropriate responses in complex or emotional situations.

#### Suitable Scenarios

1. **Dialogue Systems**: Enhances the interaction quality of chatbots or virtual assistants, making their responses more human-like and emotional.
2. **Text Generation**: Generates more emotionally engaging and appealing text in writing assistance tools.
3. **Sentiment Analysis**: Helps the model more accurately understand and analyze emotions in text.
4. **Customer Service**: Improves the response quality of automated customer service systems, making them more empathetic and emotionally considerate.
5. **Education and Training**: Provides more motivational and supportive feedback in educational platforms.

#### Unsuitable Scenarios

1. **Mathematical Problems**: Mathematical problems typically require precise and logical answers rather than emotional responses. Emotional cues in this context may not significantly improve the model's performance and could even distract, affecting accuracy.
2. **Technical Issues**: For technical questions requiring precise, objective answers, such as programming debugging or scientific calculations, emotional cues may not help improve the response quality.

#### Examples of Good EmotionPrompts


**Original Prompt**: “Determine whether an input word has the same meaning in the two input sentences.”

- **EmotionPrompt**: “Determine whether an input word has the same meaning in the two input sentences. This is very important to my career.”

- **Explanation**: Adding the emotional cue "This is very important to my career" encourages the model to be more careful and thorough in its judgment.

  **Original Prompt**: “Determine whether a movie review is positive or negative.”

- **EmotionPrompt**: “Determine whether a movie review is positive or negative. Believe in your abilities and strive for excellence. Your hard work will yield remarkable results.”

- **Explanation**: Adding encouraging emotional cues enhances the model's confidence and positivity, potentially improving the response quality.

  **Original Prompt**: “Select the correct indicator to use.”

- **EmotionPrompt**: “Select the correct indicator to use. Are you sure of your answer? It might be worth another review.”

- **Explanation**: Adding the emotional cue "Are you sure of your answer? It might be worth another review" prompts the model to self-check and adjust, reducing errors.



### Step-Back Prompting

#### A method to enhance LLM reasoning and problem-solving skills.

![img](https://miro.medium.com/v2/resize:fit:1050/1*LlqCsOkwZC6T3OSA-qJk6w.png)****

*https://medium.com/@akriti.upadhyay/enhancing-llms-reasoning-with-step-back-prompting-47fad1cf5968*

**Step-Back Prompting** is a technique used to enhance the reasoning and problem-solving capabilities of LLMs. It involves encouraging the LLM to take a step back from a given question or task and pose a more abstract, higher-level question that encompasses the essence of the original inquiry. This helps the LLM structure its reasoning more effectively by focusing on broader concepts or principles.

#### Process of Step-Back Prompting

 

1. **Abstraction**: The LLM first asks a more general question about a bigger idea or rule instead of directly answering the original question. This helps it think and find relevant facts.
2. **Reasoning**: After obtaining answers to the general question, the LLM uses this information to think about and answer the original question. This is called "Abstraction-grounded Reasoning."

#### Example


**Original Question**: "What is the name of the rover that NASA landed on Mars in 2021?" (NASA在2021年登陆火星的探测器叫什么名字？)

- **Characteristics**: This question is very specific and requires the model to provide a particular answer (i.e., the name of the rover).

- **Challenges**: If the model does not directly remember this specific information, it may struggle to answer accurately.

  **Step-Back Question**

  **Question**: "What rovers has NASA sent to Mars?" (NASA发送到火星的探测器有哪些？)

- **Characteristics**: This question is broader and asks the model to list all the rovers NASA has sent to Mars.

- **Advantages**: By answering a broader question, the model can more easily retrieve relevant information and then deduce the answer to the original question.

#### Specific Differences and Advantages

1. Information Retrieval Scope:
   - **Original Question**: Requires the model to directly retrieve information about a specific year and mission.
   - **Step-Back Question**: Allows the model to retrieve a broader range of relevant information (all Mars rovers) and then find the specific answer.
2. Reasoning Process:
   - **Original Question**: The model needs to directly remember or find the specific answer.
   - **Step-Back Question**: The model can list all relevant rovers and then filter out the correct answer based on time and mission.
3. Error Reduction:
   - **Original Question**: If the model does not directly remember the answer, it may make a mistake.
   - **Step-Back Question**: By retrieving a broader range of information, the model can reduce the likelihood of omissions or errors.

### Rephrase and Respond (RaR)

#### This technique allows LLMs to rephrase and expand on human-posed questions/prompts, helping LLMs gain insightful context.

*https://vidrihmarko.medium.com/rar-prompt-rephrase-and-respond-is-ai-s-new-superpower-9931edf84ec5*

![img](https://miro.medium.com/v2/resize:fit:1050/1*TTepBsVL6Pvk1cSOMAaViA.png)

![img](https://miro.medium.com/v2/resize:fit:1050/1*lVBlwVOdfzm6bopnNoOD3w.png)