# 计算机视觉的演进与多模态建模：从CNN到视觉语言模型

计算机视觉（Computer Vision, CV）作为人工智能领域的重要研究方向，从最初尝试模拟人类视觉感知，到如今的多模态模型和通用智能，其发展经历了多个显著阶段：

- **从最早的手工设计特征**（如SIFT、HOG），到利用深度学习的**卷积神经网络（CNN）**，显著提升了视觉任务的精度和效率。
- 再到 **Transformer 视觉模型（如 ViT）** 的引入，用全局建模能力突破了局部特征的局限性。
- 最后发展到 **视觉语言模型（Vision Language Models, VLM）**，将图像编码器和语言生成组件结合，实现了从图像识别到语言生成、多模态推理等复杂任务的有机融合。

近年来，多种 VLM 模型（如 CLIP、Florence-2、Qwen2-VL）取得了优秀成绩，使计算机视觉逐步迈入多模态交互与智能推理的新阶段。以下我们将详细梳理 CV 的演化路径，并分析代表性技术和模型的应用特点。

## 视觉模型能力递进示意

##### ① 纯视觉编码器

ResNet(属于CNN)／ViT／DaViT …
↓（图像预处理 → 视觉特征提取，输出**纯视觉表示**）

##### ② CLIP-类双编码器跨模态对齐

（视觉编码器 + 文本编码器 并列前向）
↓（对比学习将图像表示与文本表示映射到**统一语义嵌入空间**，支持零样本检索／分类）

##### ③ 视觉语言模型（VLM）

Florence-2、BLIP-2、Qwen-VL …
↓（在已有**对齐机制**上，叠加文本解码器或跨模态 Transformer，引入**生成、对话、多任务**能力）

───
能力“叠加”说明
• 第一层：模型仅需理解图像，输出视觉特征。
• 第二层：通过跨模态对齐，让图像特征与文本语义互通，可直接比对或检索。
• 第三层：在对齐基础上接入语言解码／交互模块，使模型不仅理解图像，还能生成描述、回答问题、执行复杂推理。

注：多数 VLM 会重用 CLIP-式视觉塔或等价的图文对齐机制，但并非都“先训练 CLIP 再接解码器”；也有如 Florence-2 那样端到端的交互式 Encoder-Decoder 实现，原理同样基于“对齐 + 生成”两步。



## **CV 演进的主要阶段**

### **演化阶段对比表**

| **演化阶段**          | **代表模型**           | **核心特点**                                          | **典型任务 & 示例**                                          |
| --------------------- | ---------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| **传统方法时期**      | SIFT, HOG              | 手工特征 + 领域知识                                   | 形状识别：HOG 检测人形轮廓。                                 |
| **卷积网络（CNN）**   | AlexNet, VGG, ResNet   | 高效局部特征；残差解决深网退化                        | 图像分类：ResNet-50 在 ImageNet 猫狗分类。                   |
| **视觉 Transformer**  | ViT, DeiT, Swin, DaViT | 全局建模；蒸馏 / 分层 / 双注意力 优化小数据和密集预测 | 图像分割：Swin 用于自动驾驶车道线/实例分割。                 |
| **跨模态模型（VLM）** | CLIP                   | 图文对比学习，零样本泛化                              | “这是一张包含猫的图片” → 检索匹配图像。                      |
|                       | Florence-2             | 多任务解码 + Prompt 灵活性                            | 医疗影像：肿瘤分割并生成诊断描述。                           |
|                       | Qwen-VL / Qwen-VL-Chat | ViT + LLM，支持多轮对话推理                           | 视频问答：解析“人物何时开始跑步？”并多轮解释。               |
| **未来趋势**          | 全模态 AI              | Vision+Text+Audio+Motion 等多模态协同                 | 辅助机器人：融合摄像头、语音指令、机械运动与触觉，为仓储机器人提供全栈感知与控制。 |

### 1.卷积网络（CNN）阶段：强调局部特征建模

卷积神经网络（CNN）曾长期主导视觉任务。从 LeNet（1989）、AlexNet（2012）到 VGG（2014），每一代 CNN 以「加深网络层数 / 增大卷积通道」来提升特征提取能力。然而，网络越深，梯度传递越困难，出现**退化现象**（degradation）：层数增加反而使训练与测试精度下降。

2015 年，He Kaiming 等提出 **Residual Network（ResNet）**，用 **残差学习** 框架解决深网退化问题。核心做法是在每个残差块（Residual Block）内添加 **跳跃连接**（Skip Connection）：

F(x) + x → y （F 表示卷积堆叠的残差映射）

该设计让网络直接学习「残差」而不是完整映射，信息能够跨层直达，缓解了梯度消失/爆炸。配合 **Batch Normalization** 与 **Bottleneck** 结构，ResNet-152 在 ImageNet-1K 取得约 78.6 % 的 Top-1 精度，把深度网络尺度推到 100+ 层，奠定了后续极深 CNN 的可训练性。

CNN 的优势在于卷积核的**局部归纳偏置**：局部特征提取高效，在中小数据集上表现稳健。但局部卷积要捕捉相距甚远的区域关联，必须层层堆叠扩大感受野，难以直接建立**全局依赖**。因此「在保持局部先验的同时，引入全局建模能力」成为 CNN 时代后期的重要课题，也为 Transformer 在视觉中的落地埋下伏笔。

- AlexNet

  = 多层卷积 (Conv) + ReLU + MaxPool + LRN + Dropout

  - 引入 ReLU 非线性、局部响应归一化 (LRN)、Dropout 和双 GPU 并行，首次在 ImageNet 取得突破。

- ResNet

  = AlexNet + BatchNorm + Bottleneck + 残差连接 (Skip Connection)

  - 残差单元缓解退化/梯度消失，实现百层以上深网；BatchNorm 与 Bottleneck 设计兼顾收敛与计算效率。

- 特点

  - 局部特征提取高效；大感受野或非局部模块可增强全局感知，但纯 CNN 捕捉长距依赖仍有不足。

### 2.视觉 Transformer 阶段：强化全局建模

#### ViT 基础

2020 年，Dosovitskiy 等提出 **Vision Transformer (ViT)**，将一张图像视为由固定大小补丁 (patch) 组成的序列——「把图像当句子」。流程：

1. 将 H × W 图像切成 N = (H/P)² 个 P × P 补丁；
2. 每个补丁展平后映射到 d 维向量，加上可学习 **位置编码**；
3. 将补丁序列送入纯 Transformer Encoder 计算 **全局自注意力**；
4. 取 **[CLS] token** 或所有 patch 表示用于下游任务。

在 JFT-300M 级别数据预训练 + ImageNet 微调后，ViT-Huge/14 Top-1 > 90 %，相比同规模 ResNet 提升约 10 个百分点，显示出 Transformer 对大规模数据的强大可扩展性与全局表征能力。

#### ViT 的数据需求与改进方向

直接在 ImageNet-1K（120 万张）从零训练 ViT 会明显落后同级别 CNN。围绕「数据高效」与「计算高效」两条主线，研究者提出多种改进：

• **DeiT**：引入 Distillation Token 的 **知识蒸馏**，在 ImageNet-1K 单卡训练即可与 ResNet-50 打平甚至反超。
• **Swin Transformer**：采用 **分层金字塔 + 滑窗注意力**，兼顾全局建模与高分辨率密集预测；成为分割/检测等任务新基线。
• **ConvNeXt**：回到卷积视角，用卷积实现 ViT 式宏观设计，取卷积/Transformer 之长。
• **SoViT（Shape-Optimized ViT）**：系统搜索宽深比，400 M 参数模型即可逼近 1 B+ 模型精度。
• **DaViT（Dual Attention ViT）**：在不同层交替加入 **空间自注意力 + 通道自注意力**，以极小代价提升分类/分割精度，DaViT-Giant Top-1 ≈ 90.4 %。

- ViT

  = 图像切块 (Patches) + 全局自注意力 (Self-Attention)

  - 将图像分为固定 patch，再用 Transformer 捕获长距离依赖。

- DeiT

  = ViT + Distillation Token (Token-level 蒸馏)

  - 额外引入 distillation token，使小数据也能训练纯 Transformer。

- Swin

  = ViT + 分层/滑窗注意力 (Window-based)

  - 采用窗口自注意力与层次化金字塔，提升密集预测任务性能。

- DaViT (Dual Attention ViT)

  = ViT + 并联 空间注意力 + 通道注意力

  - 学术改进模型，强化细粒度空间/通道表示。

- 特点

  - 全局建模强；模型规模与训练数据要求较高，需蒸馏、分层或卷积混合缓解成本。

### 3. 跨模态模型（VLM）阶段：图像 × 语言深度融合

OpenAI 2021 年提出 **CLIP（Contrastive Language-Image Pre-training）**，开创了大规模图文对比学习范式。

• **双编码器架构**
图像编码器（ResNet 或 ViT）与文本编码器（Transformer）分别输出 d 维向量，再映射到共享嵌入空间。
• **对比损失**
在一个 batch 内最大化正确图文对的相似度，最小化错配对的相似度。
• **训练规模**
4 亿对互联网图文，无需人工清洗。
• **零样本能力**
在未见过的下游任务，只需将类别描述写成文本 Prompt，与图像嵌入做相似度即可完成分类检索；ImageNet-1K 零样本 Top-1≈ 76 %。

CLIP 证明了「图像-文本可共享语义空间」，也成为后续多模态基础模型（BLIP-2、LLaVA、Florence-2 等）的重要组成。

#### 1. Florence-2（Microsoft）

• **Seq-to-Seq Transformer**：视觉编码器 (InternImage-H / SwinV2-G) + 文本解码器。
• **统一 Prompt 接口**：分类、检测、分割、Caption、OCR…均用文本指令描述任务。
• **FLD-5B 数据集**：5.4 B 多模态标注，涵盖 44 个任务类型。
• **效果**：在 80+ Benchmark 获得 SOTA / 次 SOTA；零样本检测与分割表现尤为突出。

#### 2. Qwen-VL / Qwen-VL-Chat（Alibaba）

• **架构**：ViT 视觉塔 + 70 B 级 Qwen-LLM，采用 **M-ROPE** 多模态旋转位置编码。
• **能力**：多轮对话、长视频逐帧推理、跨语言 OCR；在 DocVQA、MathVista、MMMU 等基准超越多款闭源模型。
• **开源**：提供 7 B / 2 B 量级模型（Apache-2.0），移动端即可部署。

#### 3. 共同特征

1. **生成式 + 对话式**：图像/视频输入 → 文本输出，可多轮交互。
2. **多任务统一**：单模型覆盖分类、检测、分割、VQA、Caption…
3. **跨模态推理**：结合视觉与世界知识完成复杂逻辑。
4. **大模型加持**：借助 LLM 语言推理能力，视觉理解跃升到认知层面。
5. **开放生态**：Hugging Face、vLLM、DeepSpeed 等工具链加速落地。



#### 未来全模态模型（示意）：迈向通用人工智能

- 全模态模型
  = Vision + Text + Audio + Motion + Tactile + Depth/LiDAR …



## ViTs 与 CNNs：性能对比

CNN的架构图如下：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Evolution-of-Computer-Vision/images/2.png)

ResNet（Residual Network）属于卷积神经网络（CNN）范畴。

1. 基本运算单元是卷积层（Conv）和池化层（Pool），与经典 CNN 架构一致。
2. 残差连接（Skip Connection）只是为了解决深层 CNN 训练中的退化/梯度消失问题，对网络“卷积本质”没有改变。
3. 网络各层之间的信息流仍以卷积特征图（feature map）的形式传递，不包含自注意力或 Transformer 结构。

因此，ResNet 归类为 CNN，而非 Transformer 或混合模型。



ViT的架构图如下：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Evolution-of-Computer-Vision/images/2.png)

两者对比：

- CNN 更像细节侦探，依靠局部卷积核在小感受野内捕捉纹理与形状；
- ViT 更像艺术评论家，借助自注意力从一开始就“环顾全局”，同时建模远距离依赖。

这种根本处理方式的差异，对性能带来以下影响：

- 准确性——在经过大规模预训练或拥有充足标注数据时，ViT 通常能取得比同规模 CNN 更高的 Top-1 精度，尤其擅长需要全局上下文或细粒度关系的任务；若数据较少、直接从零开始训练，传统 CNN 仍可能更稳健。
- 可扩展性——研究显示 ViT 的 **Scaling Law** 更陡：参数或计算量翻倍时，损失下降幅度往往大于 CNN。现代大模型（ViT-G/14、ViT-Huge 等）正是借此优势突破 90 % Top-1。但注意新一代卷积网络（ConvNeXt、EfficientNet-V2）也依旧随规模持续提升，并非完全“天花板”。
- 数据需求——ViT 缺乏卷积的局部先验，训练效率对数据量更敏感；DeiT 之前，在仅有 ImageNet-1K 的情况下直接训练 ViT 常低于 ResNet，同步采用蒸馏、强增广可显著缓解。
- 计算成本——原始 ViT 的全局注意力在高分辨率下计算 / 内存昂贵；分层窗口 (Swin)、稀疏或线性注意力、Token Merging 等技术已把推理开销降到与高效 CNN 接近，甚至更优。

**何时选用 ViT？**
‒ 拥有千万级以上图像或已可用的大型预训练权重；
‒ 任务需要捕捉跨区域长距依赖（遥感全景理解、医学 Whole-Slide 分析、关系推理等）；
‒ 对未来扩容（更大模型、更大数据）有明确规划。

**何时仍偏向 CNN？**
‒ 数据规模有限、想从头训练获得稳定基线；
‒ 部署端对延迟 / 内存极端敏感，且模型大小受严格限制；
‒ 任务特征以局部纹理为主、对全局关系要求有限（如简单分类、低分辨率摄像头边缘推理）。

**展望未来，两条技术路线正加速融合：**
‐ ConvNeXt 等「带卷积味的 ViT」；
‐ Hybrid ViT（卷积 Tokenizer + Transformer Encoder）；
‐ 视觉 Mamba / State Space 模型等新序列结构。
它们试图兼得 CNN 的高效局部先验与 Transformer 的全局表达，为下一代图像识别打开新空间。



## **什么是视觉塔（Vision Tower）？**

### **概念解析**

视觉塔是视觉-语言模型中专门处理图像的 **视觉编码器**，将像素 → 高维语义特征，供文本解码器或多模态交互层使用，可类比“大脑的视觉皮层”。

### **视觉塔的常见实现**

1. **卷积神经网络（CNN）**：如 ResNet，参数高效，适合简单分类/匹配。
2. **Vision Transformer (ViT)**：原生全局注意力，现代 VLM 默认选项。
3. **混合架构（CNN+ViT）**：如 ConvNeXt、InternImage，将卷积效率与全局表示结合。

### **不同 VLM 中视觉塔对比**

| **模型**     | **视觉塔**                               | **典型任务 & 示例**                                      |
| ------------ | ---------------------------------------- | -------------------------------------------------------- |
| CLIP         | ResNet / ViT                             | 图文检索、零样本分类。                                   |
| Florence-2   | InternImage-H / SwinV2-G 等 + 任务解码头 | 医疗分割：高分辨肿瘤标注；复杂检测/描述多任务。          |
| Qwen-VL 系列 | ViT + M-ROPE                             | 视频问答、对话推理：“视频中的人物在做什么？”。           |
| Phi-Vision   | 轻量化 ViT 变体                          | 学术场景：读图表并生成推理报告，如“图中趋势是否线性？”。 |

------

## VLM类别细分

| 维度 / 等式示意            | Florence-2                                                   | Phi-3 Vision                                                 | LLaVA-1.5（CLIP-based VLM）                                  | CLIP                                                         | ViT（纯视觉）                                    |
| -------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------ |
| **核心等式**               | Florence-2 = 视觉编码器(InternImage-H / SwinV2-G …) + Cross-Attn + 文本Decoder + Prompt | Phi-3 Vision = SigLIP-ViT 视觉塔 → Prefix + 轻量 LLM Decoder + Cross-Attn + Prompt | LLaVA-1.5 = **CLIP 视觉塔** + 线性投影 + 大语言模型(LLM) + Cross-Attn + Prompt | CLIP = 视觉Encoder(ViT / ResNet / ConvNeXt) ∥ 文本Encoder(Transformer) + 对比损失 | ViT = 图像Patch + 位置编码 + Transformer Encoder |
| 模型类别                   | 视觉语言生成 VLM                                             | 轻量生成/推理 VLM                                            | 生成式 VLM（直接继承 CLIP 视觉塔）                           | 双塔跨模态对齐模型                                           | 纯视觉编码器                                     |
| **是否直接使用 CLIP 权重** | ❌                                                            | ✅（SigLIP 属 CLIP 家族）                                     | ✅（直接加载 OpenAI CLIP ViT-L/14 等权重）                    | 本体即 CLIP                                                  | ❌                                                |
| 图像编码器（视觉塔）       | InternImage-H / SwinV2-G                                     | SigLIP-ViT                                                   | CLIP-ViT / CLIP-ResNet                                       | CLIP-ViT / CLIP-ResNet / ConvNeXt                            | ViT                                              |
| 文本编码器（Encoder）      | 无独立 Encoder（Seq2Seq 统一编码）                           | 无独立 Encoder（视觉前缀接入 LLM）                           | 无独立 Encoder（视觉前缀接入 LLM）                           | Transformer 文本 Encoder                                     | —                                                |
| 文本解码器（Decoder）      | ✅ Transformer                                                | ✅ LLM                                                        | ✅ LLM                                                        | —                                                            | —                                                |
| 跨模态交互                 | ✅ Cross-Attention                                            | ✅ Cross-Attention                                            | ✅ Cross-Attention                                            | ❌（对比对齐）                                                | ❌                                                |
| 训练范式                   | 图文多任务预训 + 指令微调                                    | 图文多任务预训 + 指令微调                                    | CLIP 视觉塔冻结/微调 + LLM 对齐 + 指令微调                   | 大规模图文对比学习                                           | 监督或自监督                                     |
| 主要能力概览               | 描述 / VQA / 检测 / 分割 / 多轮对话                          | 描述 / VQA / 轻量推理                                        | 描述 / VQA / 多轮对话（依托 CLIP 视觉）                      | 零样本分类 / 图文检索                                        | 分类 / 检测特征提取                              |

### Florence-2和Phi-3 Vision对比

Florence-2和Phi-3 Vision可以都归入 “VLM（Vision-Language Model，视觉-语言模型）” 这个大圈子，但二者在侧重点与设计路线并不完全相同，常见的划分方法有两种：

1. 按 “是否具备生成能力” 细分
   • 判别式 VLM：侧重匹配、检索、对齐（如 CLIP、ALIGN）。
   • 生成式 VLM：既能理解又能**生成/对话**（如 BLIP-2、LLaVA、Qwen-VL、Florence-2、Phi-3 Vision）。
   ——在这个视角下，Florence-2 与 Phi-3 Vision 同属 “生成式 VLM”。
2. 按 “系统形态” 细分
   • Encoder-Decoder 式（Seq2Seq）VLM
   - 视觉编码器 + 文本解码器，专门为多任务输出设计
   - 代表：Florence-2、PaLI-X、KOSMOS-2
     • LLM-Prefix 式 VLM
   - 先用视觉塔把图像转成 token 前缀，再送入大语言模型；语言侧几乎保持原 LLM 结构
   - 代表：Phi-3 Vision、LLaVA-1.5、Qwen-VL
     ——在这个视角下，二者同为 VLM，但属不同 **子范式**：
     Florence-2 → Encoder-Decoder 式生成 VLM
     Phi-3 Vision → LLM-Prefix 式生成 VLM

总结
• 把二者都称为 “VLM” 没问题，它们都能把视觉信息与语言信息结合起来进行理解和生成。
• 若需更细致说明，可再加一个限定词：

- “Florence-2 是 **多任务 Encoder-Decoder VLM**（偏视觉任务全面覆盖）”
- “Phi-3 Vision 是 **LLM-Prefix VLM**（侧重轻量推理与对话）”

### LLaVA 和 Florence-2对比

LLaVA 和 Florence-2 都是“视觉塔 + 大语言模型”的生成式 VLM，但两者出发点和工程权衡并不相同。
• LLaVA：直接把​公开的 CLIP-ViT (视觉塔) 冻结或轻微微调，再接一个开源 LLM（Vicuna、Mistral…）＋少量交互层。目标是用极低成本快速得到“看图对话”功能；定位偏轻量级实验或产品 MVP。
• Florence-2：微软自研 InternImage-H / SwinV2-G 视觉主干，端到端多任务预训练（分类、检测、分割、OCR、Caption…），再用解码器统一生成输出。目标是成为“视觉 GPT”，对精度、任务覆盖面和可扩展性要求更高，因此没有沿用 CLIP。

为什么 Phi-3 Vision 不直接用 CLIP？

1. 体积：Phi-3 主打“小模型手机端可跑”，SigLIP-ViT Base 比 CLIP ViT-L/14 轻得多。
2. 授权：SigLIP（Google 2023）完全开源，依赖更少；OpenAI CLIP 权重虽可商用，但部分衍生文件受限。
3. 单塔简化：SigLIP 本身把图文对齐做成“单塔”损失，更容易直接接到 LLM 前缀。

Qwen-VL（阿里 2024）用的不是原版 CLIP，而是自行预训练的 ViT-G 视觉塔（声明基于 EVA-CLIP 技术路线）。也就是说：
• 视觉编码阶段仍然使用 CLIP 式对比损失；
• 但权重并非直接加载 OpenAI CLIP，而是用更大模型、更多中文数据重新训练。

总体趋势：
• 早期开源 VLM（MiniGPT-4、LLaVA、Qwen-VL-v1）大量“直接借 CLIP”；
• 最近的新版本逐渐改用自家或第三方更大、更高效、版权更清晰的 CLIP-like 模型（EVA-CLIP、SigLIP、AlignClip 等），甚至完全抛弃双塔对齐，走 Florence-2 那种端到端路线。
原因无外乎三点：尺寸／精度权衡、训练数据与版权、以及想把视觉特征定制到自家场景，所以看起来“大家都不再用原版 CLIP”，其实是“在用更适合自己需求的 CLIP 家族或替代方案”。

## VLM**微调（Finetuning）最佳实践**

### 微调模式选择表

| **微调模式**     | **视觉塔**  | **文本解码器**             | **适用场景**                                  |
| ---------------- | ----------- | -------------------------- | --------------------------------------------- |
| 仅视觉塔微调     | ✅           | ❌ 冻结                     | 域差异大：医学影像、遥感；仅需调整视觉特征。  |
| 仅文本解码器微调 | ❌ 冻结      | ✅（全参或 LoRA/Prefix 等） | 文本风格或任务格式改变：儿童科普、新闻摘要。  |
| 跨模态交互层微调 | ✅（可冻结） | ✅（可 LoRA/Adapter）       | VQA、视觉对话：需强化融合但整体结构无需重训。 |
| 全参数微调       | ✅           | ✅                          | 高价值专域、数据充足；追求最优性能。          |



### Florence-2 微调选项

| 微调范围                                | 可行性 | 典型场景                                                     | 风险 / 成本                                          |
| --------------------------------------- | ------ | ------------------------------------------------------------ | ---------------------------------------------------- |
| 仅视觉塔 (InternImage-H / SwinV2-G 等)  | ✅      | 医学影像、遥感、工业瑕疵：视觉分布与通用数据差异大，但语言输出样式保持不变 | 需要同域图文对或伪标注维持跨模态对齐                 |
| 仅文本解码器 (Transformer Decoder)      | ✅      | 调整输出语气 / 语种；编写法律、儿童科普等特定文风            | 对视觉新域无增益；若 prompt 格式变化大须额外指令数据 |
| 仅跨模态交互层 (Cross-Attention / 投影) | ✅      | 轻量适配 VQA、机器人对话，GPU 资源有限                       | 效果提升有限，难以覆盖大域间差异                     |
| 视觉塔 + 交互层                         | ✅      | 新视觉域 + 新任务格式：如医学问诊对话                        | 训练开销中等；需平衡视觉与语言梯度                   |
| 全参数 (视觉塔 + 解码器 + 交互层)       | ✅      | 高价值垂直场景、数据充足：自动驾驶多任务套件                 | 计算 / 显存最高，容易过拟合小数据                    |



### Phi-3 Vision 微调选项

| 微调范围               | 可行性 | 典型场景                                       | 风险 / 成本                          |
| ---------------------- | ------ | ---------------------------------------------- | ------------------------------------ |
| 仅 ViT (SigLIP-ViT)    | ✅      | 医学、遥感等视觉域迁移                         | 需图文对保持 CLIP 对齐；超出域易失配 |
| 仅 LLM Decoder (Phi-3) | ✅      | 改变语气、格式、多语言输出                     | 对视觉新域无帮助                     |
| 仅投影 / 交互层        | ✅      | 极低显存快速适配 UI 截图问答                   | 提升幅度有限                         |
| ViT + 投影层 + LLM     | ✅      | 高价值专域、充足图文对：如企业专有产品手册问答 | 训练与显存成本最高；需精细学习率调度 |

（Phi-3 Vision 架构无独立文本 Encoder，因此不存在 “只调文本 Encoder” 这一选项。）



