## Llama-4 is Landing on Azure AML/AI Foundry

Refer to：

*https://ai.meta.com/blog/llama-4-multimodal-intelligence/*



**一、Llama 4 的诞生：新的大模型时代**

在历经整整一年的等待后，Meta 再次放出重磅炸弹：Llama 4 正式登场。相比之前的第三代，这次的参数规模直接飙到了惊人的三个数量级：约 1090 亿、4000 亿，以及最高达 2 万亿的“巨无霸”版本。这种级别的模型让人不禁感慨，Meta 对大模型的野心依然不减。

如果说上一代还有在小模型上精雕细琢的打算，那么到了 Llama 4，Meta 似乎更加专注于大规模训练的优势。在他们庞大的 GPU 集群支持下，巨型模型的训练似乎不再成为瓶颈。接下来，我们就来探究一下 Llama 4 的内部奥秘，以及它将为多模态AI的发展带来哪些新火花。

**二、三款新模型：Scout、Maverick 和 Behemoth**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/3.png)

Llama 4 这次的“产品线”里包括三个名字颇具个性的模型：Scout、Maverick 和 Behemoth。其中，Scout 和 Maverick 已经对外开放下载（但需要先注册，和往常一样），而体量最为夸张的 Behemoth（2 万亿参数！）则还处于训练阶段，内部用来给中小模型做“老师”。

1. Llama 4 Scout 是一个拥有 16 位专家的 170 亿个活跃参数模型，是同类产品中世界上最好的多模式模型，比所有上一代 Llama 模型都更强大，同时适用于单个 NVIDIA H100 GPU。此外，Llama 4 Scout 提供业界领先的 10M 上下文窗口，并且在广泛报道的基准测试中比 Gemma 3、Gemini 2.0 Flash-Lite 和 Mistral 3.1 提供更好的结果。
2. Llama 4 Maverick 是一个拥有 128 位专家的 170 亿个活跃参数模型，是同类中最好的多模态模型，在广泛报道的基准测试中击败了 GPT-4o 和 Gemini 2.0 Flash，同时在推理和编码方面取得了与新 DeepSeek v3 相当的结果——活跃参数不到一半。Llama 4 Maverick 提供了一流的性价比，其实验性聊天版本在[LMArena](https://lmarena.ai/leaderboard)上的 ELO 得分为 1417 。
3. 这些模型是我们迄今为止最好的模型，这要归功于 Llama 4 Behemoth 的提炼，Llama 4 Behemoth 是一个拥有 16 位专家的 2880 亿个活跃参数模型，是我们迄今为止最强大的模型，也是世界上最智能的 LLM 之一。Llama 4 Behemoth 在多个 STEM 基准测试中的表现优于 GPT-4.5、Claude Sonnet 3.7 和 Gemini 2.0 Pro。Llama 4 Behemoth 仍在训练中，我们很高兴在它仍在飞行时分享有关它的更多详细信息。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/1.png)



目前Scout、Maverick模型已经可以在AML/AI Foundry上部署，需要使用Azure ND H100.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/7.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/6.png)

**三、Mixture of Experts（MoE）的大变革**

值得一提的是，Llama 4 相比以往最大的架构调整，基于 Mixture-of-Experts（MoE）进行训练。这个思路在之前的一些大模型（如 DeepSeek）里也出现过精髓：与传统的稠密 Transformer 不同，MoE 并不是把所有参数一起激活，而是只在每一层为特定的 token 路由到少量专家模块。

举个例子，Maverick 有 128 个专家和 1 个共享专家组合，合并起来达到了 4000 亿参数，但推理时每个 token 只会访问 170 亿左右。这样就能兼顾大规模的知识容量和较低的推理成本，让你不至于为硬件资源发愁。路由器模块会学习如何对 token 进行分配，以实现更优的准确度和效率。

**四、“原生”多模态：文本与图像的融合**

Llama 4 的另一个里程碑在于它从一开始就将文本和图像视为同级输入，不再像过去那样“补丁式”地拼接一个图像子网络。Scout 和 Maverick 使用了所谓“早期融合”（early fusion）的训练方式：视觉 token 跟语言 token 一起通过同一个 Transformer 层。

具体来说，这得益于 MetaCLIP 视觉编码器，将图像嵌入与文本嵌入对齐到同一坐标系里。一开始，图像部分还搭配了一个被冻结的语言模型做预对齐，最后成功实现在相同流里处理多张图片与文本交互动。更棒的是，Maverick 一次性可以输入多达 48 张图像——不过官方建议 8 张左右时质量最佳。


**五、释放 1000 万 token 的超长上下文**

Llama 4 里的 Scout 版本最令人惊叹的地方，莫过于它支持的上下文长度竟然可以达到 1000 万个 token！这是一个极其恐怖的数字。为了驾驭如此长的序列，Meta 采取了渐进式的序列训练策略，从 256K token 慢慢往上堆叠。此外，还使用了 iRoPE（Interleaved RoPE）技术，通过在注意力层间隔使用带旋转位置嵌入和不带的位置嵌入，让模型更好地处理远距离依赖。

在推理阶段，模型还采用了变温度（temperature scaling）方法，根据上下文的长度动态调节 softmax 激活，避免在超大文本时精度急剧下降。不过，这个部分在实际应用中能不能稳定地跑个几百万甚至上千万 token，还有待社区继续测试和验证。


**六、背后的训练系统与技术细节**

1. 训练精度：对重量级模型来说，存储和带宽开销绝对是核心挑战。Llama 4 整个训练过程用 FP8 精度，再配合 FP16 的主权重。加上动态损失缩放和随机舍入，一方面节省了巨大资源，另一方面也保持了训练的稳定性。
2. 训练策略：基本依旧采用 AdamW 优化器和余弦退火的学习率衰减等常见方法，但也融合了一些独家“黑科技”，如 MetaP 的分层学习率缩放和初始化。
3. 数据规模：据说 Llama 4 动用了超过 30 万亿个 token（涵盖 200 多种语言、代码、图文数据以及视频帧截取）。在中后期，还融入超长合成序列来强化模型的“记忆”能力及多跳推理。
4. 微调与对齐：在预训练结束后，先进行了过滤后的 SFT（监督微调），再在一个类似 PPO 的在线 RL 流程中，用蒸馏得到的奖励模型对表现进行评估和指导。如果某些提示无法贡献有效学习，便会被丢弃。最后，再用直接偏好优化（DPO）来减少模型的幻觉输出，并提高对真实世界场景的符合度。

**七、Llama4后训练的经验**

1. 为什么要做“后训练”（post-training）？
   - Llama 4 Maverick 模型在常规训练完成后，需要额外的微调来针对“多模态输入（图像、文字等）”“推理能力”“对话能力”进行平衡优化。因为模型不仅要看文本，还可能处理图像或其他形式的输入，同时需要兼顾复杂推理与与人交流的效果。
2. 面临的主要挑战是什么？
   - 最大难点是如何在多模态、推理和对话能力之间保持平衡。换句话说，既要让模型在视觉、文本等不同输入上表现优秀，也要在编程、数学或逻辑推理等场景下保持高准确度，还要保证对话连贯、自然。
3. 新的训练策略：
   - 他们引入了一个新的三步后训练流程：
     (1) 轻量监督微调（lightweight SFT）
     (2) 在线强化学习（online RL）
     (3) 轻量直接偏好优化（lightweight DPO）
4. 重大发现：
   - 过多或难度较低的数据在 SFT 和 DPO 步骤中，可能让模型“学得太死”，限制了模型在强化学习过程中的探索能力，从而导致一些理解、推理或代码生成场景的效果不足。
5. 具体做法：
   - 首先，他们用 Llama 模型初步判断哪些数据比较“简单”，把超过一半的简单数据剔除，仅对剩下相对困难的数据做轻量 SFT，避免模型因为“简单样本”而被过度束缚。
   - 接下来进入多模态的在线强化学习阶段，通过挑选更难的提示（prompts）来继续训练，促使模型在推理、编程、或图像等复杂场景中有更好的表现。
   - 另外，他们还采用了“连续”的在线强化学习流程：轮流进行模型训练和数据过滤。也就是说，训练一段时间后，又用当前模型去过滤数据，只留下中等和困难的 prompt 继续训练，从而有效平衡了计算成本和准确度。
6. 最后的 DPO（Direct Preference Optimization）处理：
   - 在训练接近结束时，他们再次做了一次轻量的 DPO，主要是为了处理一些模型响应质量的边缘或特殊情况（corner cases），并确保模型的对话与推理能力同时保持在较高水平。
7. 总体效果：
   - 这种分步骤的管线（pipeline）设计，加上在在线强化学习中动态难度筛选的策略，让他们最终获得了一个在通用对话、推理和图像等多模态理解方面都处于行业领先水平的聊天模型。

**八、Behemoth：2 万亿参数的内部巨兽**

Behemoth 作为家族中的巨无霸，采用与 Scout、Maverick 相似的 MoE 和多模态结构，但在规模上继续突破了想象的极限。它最主要的作用，是通过一种名为“共同蒸馏”（codistillation）的方法，为其它模型提供更加丰富的目标分布。

在 RL 阶段，常规的分布式 PPO 难以处理如此庞大的模型，Meta 为此量身定做了一个异步 RL 系统，能够根据显存需求和模型大小动态分配 GPU 工作负载，效率提升远非以往可比。如果你看到某些基准测试中 Behemoth 能在 MATH-500、GPQA Diamond 等榜单上击败 GPT-4.5 等“老对手”，也不必过度惊讶。各家机构的测评标准不同，比分差距也可能在一些细节调优中悄悄逆转。



**八、AMD的Blog**

https://www.linkedin.com/pulse/llama-4-day0-support-amd-instinct-gpus-amd-cgm5e/

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/4.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Llama-4/images/5.png)

后续我会使用Azure ND MI300X GPU VM进行验证。

**结语**

总体来看，Llama 4 引入的 Mixture-of-Experts 架构、多模态支持和超长上下文窗口，代表了新一代大模型追求在规模和实用性之间的进一步平衡。Scout、Maverick、Behemoth 各司其职，既满足科研和工业界的多元需求，也为大模型的发展开启了更多可能性。虽然还无法确定 Meta 的这一战略会带来多大冲击，但毫无疑问，接下来很长一段时间里，Llama 4 都将是人们热议的焦点。

对于想要在本地折腾新魔法的开发者来说，Scout 也许会是最现实的选择。期待未来的社区工具和教程，让我们能更轻松地体验、微调并挖掘 Llama 4 系列在各领域的真正潜力。