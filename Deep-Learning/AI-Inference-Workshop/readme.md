# AI Inference Workshop

## Inference Process

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/17.png)

https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/1.png

### Prefill与decoding

1. **Prefill（预填充）阶段**
   在这个阶段，模型会对初始输入的**提示（prompt）\**或\**上下文**进行处理。具体来说：

- **编码输入**：模型将输入的文本转换为内部的表示形式，通常是通过嵌入层将词或子词映射到向量空间。

- **计算初始上下文**：利用模型的编码器或自注意力机制，计算输入序列的表示，建立输入中各个token之间的关联。

- **并行处理**：由于输入是已知的固定序列，模型可以一次性并行地处理所有输入token，提高计算效率。

  这个阶段的目的是建立一个初始的上下文状态，为后续的生成奠定基础。

2. **Decoding（解码）阶段**
   在解码阶段，模型开始**自回归地（autoregressively）**生成文本，即：

- **逐步生成**：从上一步得到的上下文开始，模型预测下一个token的概率分布，然后采样或选择最可能的token作为输出。
- **更新输入序列**：将生成的token加入到输入序列中，作为下一个时间步的输入。
- **循环迭代**：重复上述过程，逐个生成token，直到满足停止条件（如生成了特殊的结束符，达到预设的长度等）。
- **顺序处理**：由于每一步生成都依赖于之前的输出，这个过程是顺序的，无法并行。

**为什么这两个阶段是必要的？**

- **自回归性质**：大多数生成模型，如GPT系列，都是自回归模型，依赖于之前的token来预测下一个token。
- **模型架构**：Transformer架构的解码器部分就是设计用于这种自回归生成。
- **计算效率**：将已知的输入部分在Prefill阶段一次性处理，可以避免重复计算，提高整体推理效率。

### **Iteration**与Discipline

1. **Iteration**

在图中，“Iteration” 表示模型生成过程中的每一步。每一次迭代，模型都会基于之前的上下文生成一个新的 token（比如一个词或标点符号）。这是语言模型生成文本时的 **自回归过程**。

- **Iteration 1**: 在 **Prefill Phase**，模型处理用户输入的初始上下文（prompt），比如 `"Computer science is"`。
- **Iteration 2**: 在 **Decoding Phase**，模型根据之前的上下文生成了第一个 token，图中显示生成的 token 是 `"discipline"`。
- **Iteration 3**: 接着生成第二个 token，图中是 `"."`（句号）。
- **Iteration 4**: 最终生成 `<EOS>`（End of Sentence），表示生成结束。



2. **Discipline**

- 图中 `discipline` 是模型在 **Iteration 2** 中生成的 token。

- 它是对输入 `"Computer science is"` 的补充，符合语言模型的生成逻辑。

- 生成的 `discipline` 代表了一种上下文关联性，模型根据语言的统计规律和上下文语义，推测合理的下一个 token。

  例如：

- 输入 `"Computer science is"` 后，模型预测接下来的内容可能是 `"a discipline"`，表示计算机科学是一门学科。

- 接下来生成 `"."`，完成句子。

  

3. **Iteration 与 Discipline 的关系**

在生成过程中：

- **Iteration** 是生成的步骤。
- **Discipline** 是某一步（Iteration 2）中生成的具体内容（token）。
- 每一步生成的 token 会被加入上下文，成为下一步生成的输入。



### 总结

“Iteration Discipline” 如果结合图来理解，可以解释为：

- 语言模型在 **每次迭代 (Iteration)** 中生成新的 token，`discipline` 是其中某一步的输出内容。
- 这种逐步生成的过程体现了语言生成的**自回归特点**，并通过上下文和缓存（KV-Cache）来高效完成生成任务。

## Inference Engine

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/2.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/1.png)

***Flash Attention3:***

*https://mp.weixin.qq.com/s/UEd-a9v7v5XbK8pdlZMYGA?token=1109685727&lang=zh_CN*

## Affordable alternative to 4090

https://www.runpod.io/compare/l4-vs-a100sxm

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/7.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/8.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/10.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/9.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/11.png)

## GPU VM performance

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/14.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/13.png)

*https://mp.weixin.qq.com/s/uTOGjz6p7OaOXX86ntETFg?payreadticket=HBWyiLTwNfMzbnPtYge5g1_q39Oedvw8B6jP6tlCCEJHpdx5xzn79t2pc8lZCwqlwMATtms*



![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/15.png)

***Please click below pictures to see my demo video on Youtube about spot VM***:
[![Spot-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/wDf4WA_7myM)

## Phi-4 quantization Fine-Tuning and inference speedup

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/12.png)

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Phi4

https://mp.weixin.qq.com/s/6FJBsLHkKYLSMV-CHYjLmw?token=1109685727&lang=zh_CN

## Inference Performance test

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/LLM-Inference-performance-test

## Estimating Memory Need in AI model Inference

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/Estimate-Inference-Memory

https://github.com/xinyuwei-david/Backend-of-david-share/tree/main/Deep-Learning/Estimate-Inference-Memory

```
(base) root@davidgpt:~# conda activate EstimatingMemoryInference
(EstimatingMemoryInference) root@davidgpt:~# streamlit run streamlit-estimating.py

Collecting usage statistics. To deactivate, set browser.gatherUsageStats to false.


  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8503
  Network URL: http://10.0.0.5:8503
  External URL: http://68.218.112.37:8503
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/AI-Inference-Workshop/images/6.png)

## End-to-end Stable Diffusion test on Azure NC A100/H100 MIG

https://techcommunity.microsoft.com/blog/machinelearningblog/end-to-end-stable-diffusion-test-on-azure-nc-a100h100-mig/4227803