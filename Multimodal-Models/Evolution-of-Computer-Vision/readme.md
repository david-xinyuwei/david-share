# 计算机视觉的演进与多模态建模：从CNN到视觉语言模型

计算机视觉（Computer Vision, CV）作为人工智能领域的重要研究方向，从最初尝试模拟人类视觉感知，到如今的多模态模型和通用智能，其发展经历了多个显著阶段：

- **从最早的手工设计特征**（如SIFT、HOG），到利用深度学习的**卷积神经网络（CNN）**，显著提升了视觉任务的精度和效率。
- 再到 **Transformer 视觉模型（如 ViT）** 的引入，用全局建模能力突破了局部特征的局限性。
- 最后发展到 **视觉语言模型（Vision Language Models, VLM）**，将图像编码器和语言生成组件结合，实现了从图像识别到语言生成、多模态推理等复杂任务的有机融合。

近年来，多种 VLM 模型（如 CLIP、Florence-2、Qwen2-VL）取得了优秀成绩，使计算机视觉逐步迈入多模态交互与智能推理的新阶段。以下我们将详细梳理 CV 的演化路径，并分析代表性技术和模型的应用特点。

## 视觉模型能力递进示意

##### 1.纯视觉编码器

ResNet(属于CNN)／ViT／DaViT …
↓（图像预处理 → 视觉特征提取，输出**纯视觉表示**）

##### 2.CLIP-类双编码器跨模态对齐

（视觉编码器 + 文本编码器 并列前向）
↓（对比学习将图像表示与文本表示映射到**统一语义嵌入空间**，支持零样本检索／分类）

##### 3. 视觉语言模型（VLM）

Florence-2、BLIP-2、Qwen-VL …
↓（在已有**对齐机制**上，叠加文本解码器或跨模态 Transformer，引入**生成、对话、多任务**能力）
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

| 维度 / 等式示意              | Florence-2                                                   | Phi-3 Vision                                                 | LLaVA-1.5                                                    | CLIP                                                         | ViT-L/14-336（纯视觉）                                     |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------- |
| **核心等式（组件逐级列出）** | **DaViT** (4-stage) → 1024-d 线性投影 → **Text-Encoder (12 层)** → **Text-Decoder (12 层)** + Decoder-Cross-Attn ← 视觉 patch | **CLIP ViT-L/14-336** → HD-Transform + MLP 1024→3072 → **Phi-3 Text-Decoder (32 层)** + Decoder-Cross-Attn ← 视觉 patch | **CLIP ViT-L/14-336** → 线性 / MLP projector (768→4096) → **Vicuna-7B Decoder**；视觉嵌入作为 **Prefix Token**（拼在自回归序列） | **视觉 Encoder** (ViT-L/14-336 或 ResNet-50/101) ∥ **文本 Encoder** (12 层 768 hid) + proj-head-768；<br>两塔输出做 **对比损失** | **ViT-L/14-336** 单塔；CLS/EOS 向量 1024-d 作为图像表征    |
| **模型类别**                 | Seq2Seq 全功能视-文生成模型                                  | Decoder-only 轻量视-文生成模型                               | “CLIP 视觉塔 + LLM” 生成式 VLM                               | 双塔对比检索模型                                             | 纯视觉编码器                                               |
| **视觉塔权重来源**           | DaViT 预训练（FLD-5B、COCO 等）                              | **直接复用 OpenAI CLIP** ViT-L/14-336 权重                   | **直接复用 OpenAI CLIP** ViT-L/14-336 权重                   | 本体即 CLIP 视觉 Encoder 权重                                | 可来自 ImageNet-21k / 自监督 (DINO, MAE …)，不含跨模态对齐 |
| **文本 Encoder**             | ✅ 12 层 (d=1024, heads=16)                                   | —                                                            | —                                                            | ✅ 12 层 (d=768, heads=12)                                    | —                                                          |
| **文本 Decoder**             | ✅ 12 层 (d=1024)                                             | ✅ 32 层 Phi-3 (d=3072)                                       | ✅ Vicuna-7B (32 层, d=4096)                                  | —                                                            | —                                                          |
| **跨模态交互方式**           | Decoder-Side **Cross-Attention**（视觉 patch ←→ 文本 Decoder） | Decoder-Side **Cross-Attention**                             | **Prefix Token**（视觉嵌入直接拼接，依靠 Self-Attn）         | ❌ 无交互层（仅对比）                                         | ❌                                                          |
| **训练范式**                 | 大规模多任务图文预训练 + 指令 SFT / RLHF                     | 复用 CLIP 视觉 + 多任务预训 + 指令 SFT                       | 视觉塔冻结/LoRA，LLM 对齐 + 指令 SFT                         | 4 亿图文对比学习 (InfoNCE)                                   | ImageNet 监督或自监督 (MAE, DINO …)                        |
| **主要能力**                 | Caption / VQA / OD / 分割 / 多轮对话                         | Caption / VQA / 轻量推理                                     | Caption / VQA / 对话                                         | 零样本分类 / 图文检索                                        | 分类、检测特征提取                                         |

🔍 CLIP 比“裸 ViT-L/14-336”多出的关键部件

1. **文本 Encoder（CLIP TextModel）**：12 层 Transformer，词表 49 k，输出 768-d。
2. **双投影头**：视觉 1024-d、文本 768-d 各接一条线性层映射到 **共同 768-d 嵌入空间**。
3. **对比温度 (logit_scale)**：可训练标量；配合 InfoNCE 损失把同对图文拉近、不同对拉远。
4. **对比预训练语义对齐**：赋予零样本分类、检索能力。

单独的 ViT-L/14-336 只有视觉主干，并不具备 2-4 项，因此也就没有天然的跨模态对齐与零样本推理能力。



主流生成式视觉-语言模型很少把 “CLIP 整机（视觉塔 + 文本 Encoder + 对比头）” 原封不动搬进来，通常只拿走它的视觉塔。背后的原因可以归结为 5 大类：

1. 任务目标不匹配
   • CLIP 的文本分支是一个 **77 token 上限、无解码能力的 Encoder**，训练目标是 InfoNCE 对比损失，只输出一句话的全局向量。
   • 生成式 VLM 需要 **按 token 自回归解码**（Caption、VQA、对话…），必须配备一个能预测下一个词的 LLM Decoder。CLIP TextModel 根本不具备这个功能。
2. 模型规模与知识储备差距
   • CLIP Text Encoder 只有 ~63 M 参数（ViT-L/14 配套版本）。
   • 现代 LLM（Llama / Vicuna / Phi-3 等）动辄数十亿参数，经过大规模语料预训和指令调优，拥有丰富的语言/世界知识。
   → 若直接沿用 CLIP Text Encoder，生成质量、上下文长度和对话能力都会严重受限。
3. 架构衔接更简单
   • 把 **CLIP 视觉塔** 视作“高质量视觉特征提取器”，再通过线性投影 / Cross-Attention / Prefix Token 等方式接入现有 LLM，工程上最省事。
   • 如果要连同 CLIP Text Encoder 一起保留，就得面对“三塔系统”（视觉塔 + CLIP 文本塔 + LLM Decoder）的接口设计与显存开销，性价比低。
4. 训练范式不同
   • CLIP 想继续优化就需要 **正/负图文对**，而生成式微调（SFT、RLHF）只要“图 + 参考答案”即可。
   • 保留 CLIP 对比头 ⇢ 还得准备大批负样本；省去它 ⇢ 直接用交叉熵就能训练。
5. 功能侧重点不同
   • 检索 / 零样本分类——CLIP 双塔最强；
   • 文本生成 / 多轮对话——LLM + 视觉桥更强。
   多数应用更看重后者，于是“视觉塔继承自 CLIP、语言侧自己换”成为主流方案。

补充：
• 某些模型（CoCa、SigLIP、EVL 等）会在生成头之外 **保留或再挂一个对比头**，兼顾检索任务，但它们照样放弃 CLIP Text Encoder，改用更大的 LLM 来负责生成。
• 如果纯粹做检索或零样本分类，直接用 CLIP 整机依然是最简洁且效果很好的选择。



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

**代码参考1：**

https://github.com/xinyuwei-david/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning

**代码参考2：**

https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/Florence_2_Fine_tunning.ipynb



**代码1（DocVQA 全参数微调）**

1. 训练信号
   A. 文本流
   • 任务指令 token：<DocVQA>
   • 普通文字 token：question 文本 + 纯文字答案
   • 无坐标离散 token（<LOC_xxx> 不出现）
   B. 图像流
   • 扫描文档图片 → patch-embedding 序列
2. 参与训练的组件
   • 视觉塔（InternImage / Swin 等） ✅
   • 图-文交互层（投影、Cross-Attention） ✅
   • 文本解码器 + lm_head ✅
   说明：for param in model.vision_tower.parameters(): param.is_trainable=False
   只是打标记，没改 requires_grad，optimizer 拿到 **全部** 参数 ⇒ “全参数微调”。
3. 实际强化的能力
   • OCR：在文档场景识别文字
   • 信息抽取 & 理解：根据问题生成文字答案
   • 坐标 / 框 ✖（没有监督信号）
   可能副作用：全参更新 → 其它原生能力（检测、caption 等）有被“洗掉”的风险。

**代码2（自制检测数据集 + LoRA 微调）**

1. 训练信号
   A. 文本流
   • 任务指令 token：<OD> 或你自定义的 prompt
   • 普通文字 token：类别名等
   • 坐标离散 token：<LOC_000> … <LOC_999> （x₁ y₁ x₂ y₂）
   B. 图像流
   • 检测场景图片 → patch-embedding 序列
2. 参与训练的组件
   • 视觉塔      插 LoRA（Conv2d/Linear）
   • 图-文交互层   插 LoRA（q/k/v/o_proj …）
   • 文本解码器 + lm_head 插 LoRA（q/k/v/o_proj、fc2、lm_head）
   • 基座参数 (≈99%) 全部 requires_grad=False
   ⇒ 真正更新的只有 LoRA 的低秩矩阵和可能的 bias，属于“参数高效微调”。
3. 实际强化的能力
   • 目标检测 / 区域标注：输出类别 + `<LOC_xxx>` 坐标
   • 因为基座冻结，Caption、VQA 等原生功能大概率被保留
   • 资源占用大幅降低，易组合/卸载 LoRA

**两个代码核心区别对比** 

1. 数据监督
   • 代码1：只有文字答案 → 训练“读文档答问”
   • 代码2：文字 + 坐标 token → 训练“画框 + 打标签”
2. 权重更新方式
   • 代码1：全参数都改，显存 / 计算量高，易遗忘旧能力
   • 代码2：只改 LoRA 小矩阵，显存 / 计算量低，旧能力保留
3. 覆盖组件
   • 两者都把视觉塔 + 交互层 + 解码器纳入“可调范围”
   • 差别在于：脚本①直接改基座；脚本②在相同组件里挂 LoRA 增量
4. 新增/强化的能力
   • 代码1：文档 OCR + QA
   • 代码2：坐标级目标检测
   → 谁“能力更多”取决于业务：需要文档问答选代码1，需要检测选代码2；若想“增而不减”且资源有限，一般选 LoRA 方案代码2。



### Phi-3 Vision 微调

| 微调范围               | 可行性 | 典型场景                                       | 风险 / 成本                          |
| ---------------------- | ------ | ---------------------------------------------- | ------------------------------------ |
| 仅 ViT (SigLIP-ViT)    | ✅      | 医学、遥感等视觉域迁移                         | 需图文对保持 CLIP 对齐；超出域易失配 |
| 仅 LLM Decoder (Phi-3) | ✅      | 改变语气、格式、多语言输出                     | 对视觉新域无帮助                     |
| 仅投影 / 交互层        | ✅      | 极低显存快速适配 UI 截图问答                   | 提升幅度有限                         |
| ViT + 投影层 + LLM     | ✅      | 高价值专域、充足图文对：如企业专有产品手册问答 | 训练与显存成本最高；需精细学习率调度 |

（Phi-3 Vision 架构无独立文本 Encoder，因此不存在 “只调文本 Encoder” 这一选项。）

**代码参考：**

*https://github.com/xinyuwei-david/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning*

上面链接的代码做的是 **“全参数微调”**

- 没有冻结视觉塔（SigLIP-ViT）
- 没有冻结语言侧 Phi-3.5 LLM
- 没有筛选投影 / 交互层；`optimizer = optim.AdamW(model.parameters(), …)` 

把 **全部可训练参数** 都丢进了优化器。

关键证据

1. ```
   model = AutoModelForCausalLM.from_pretrained(...)
   ```

   - 直接加载整套权重，没有任何 `requires_grad=False` 的过滤。

2. 之后调用 `model.parameters()` 构建 `AdamW`，说明视觉塔、交互层、LLM 全部参与反向传播。

3. 训练循环里 `loss.backward()` 后并未按名称筛选梯度，仅做梯度累积再 `optimizer.step()`。

所以它实际上属于表格中的这一行：

| 微调范围                       | 可行性 | 典型场景                   | 风险 / 成本                                        |
| ------------------------------ | ------ | -------------------------- | -------------------------------------------------- |
| **ViT + 投影层 + LLM（全参）** | ✅      | 高价值专域、电商多字段抽取 | 训练与显存成本最高；若数据单一易过拟合、破坏原对齐 |

若想改成“只调视觉塔”或“只调 LLM / 投影层”，需要显式冻结其他部分，例如：

```
for name, param in model.named_parameters():
    if name.startswith("vision_tower"):   # 只调视觉塔
        param.requires_grad = True
    else:
        param.requires_grad = False
```



或用 PEFT/LoRA 方式仅在目标模块插入可训练增量。



## VLM and LLM 文本生成能力对比

### 文本生成能力对比



[![images](https://github.com/xinyuwei-david/david-share/raw/master/Multimodal-Models/VLM-vs-LLM/images/6.png)](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/VLM-vs-LLM/images/2.png)

1. – 对 7B 小模型来说，引入多模态后语言任务表现下降明显； – 对 72B 大模型来说，VLM 版本的语言任务表现优于纯语言模型，且量化 (AWQ) 后也仍然保持优势。
2. 推理成本与内存占用比较 • VLM 模型的参数量会多出一部分（因为新增了视觉编码器和相关输入处理），但其实比同规模 LLM 只多占不到 1.5 GB 左右的显存；推理速度也没有明显差异。 • 对于有足够 GPU 资源的人来说，使用 VLM 替代 LLM 在纯文本任务上也许更好，因为它语言能力不减反增；而如果硬件资源有限或只使用小模型 (例如 7B)，则 VLM 可能拖慢语言任务的成绩。

**原因分析：**

之所以在 72B 这种较大规模模型上，VLM（多模态版本）反而能在语言任务上超越纯语言模型，根本原因主要有以下几点：

1. 额外的训练与数据增益 大多数多模态后训练（post-training）并非只接入视觉 encoder 那么简单，往往还会在引入图像数据的同时继续加入新文本数据，并对模型进行进一步的语言训练。对于大模型而言，这就相当于模型经历了“二次强化”——不仅接受了新的多模态数据，也接受了更多文本数据。在足够大的参数空间里，这些额外的训练步骤往往能带来语言能力的进一步提升。

2. 大模型容量更容易吸收多模态训练 对于 7B 这样相对小的模型，加入视觉编码和多模态能力后，很可能会产生“挤占”或“遗忘”现象：模型有限的参数容量需要在原有语言能力和新增视觉能力之间分配，导致语言能力有所退化。在 72B 这样的大模型中，模型参数量更充裕，学习能力更强，能够更好地同时吸收视觉和语言信息，最终反映在对语言任务的表现上不但没有下降，反而提升了。

3. 多模态训练策略对语言也有正面影响 如果多模态训练策略是“继续训练 LLM 自身的参数”，而不是“冻结原有 LLM + 只训练视觉适配器”，那么原本的语言部分也会随新数据一起被进一步调整、优化。在大模型中，这种同步更新往往会巩固并拓展语言能力，让模型在理解上下文、生成文本等方面得到强化。

4. 更丰富的上下文与表征能力 大模型在处理多模态信息的时候，如果视觉与语言模块之间有较好的融合机制，模型可能会对语言信息建立更广泛、更深层次的关联。例如，处理图片描述和 OCR 场景时，模型会进一步强化语义理解和世界知识，这些在语言任务中也能起到正向的迁移作用。

   综合来看，72B 级别的大模型拥有更充足的“容量”去应对多模态后训练带来的新知识和新任务，不仅不会牺牲原有的语言能力，反而会因额外的再训练过程而进一步提升语言表现。相较之下，小模型在多模态后训练中更容易出现“舍此取彼”的现象，导致语言任务表现退化。

### Phi-3.5v的架构



以Phi为例。

[![images](![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Evolution-of-Computer-Vision/images/5.png)

查看模型层级

```
======== Model Config ========
{'_attn_implementation_autoset': False,
 '_attn_implementation_internal': 'flash_attention_2',
 '_commit_hash': '4a0d683eba9f1d0cbfb6151705d1ee73c25a80ca',
 '_name_or_path': 'microsoft/Phi-3.5-vision-instruct',
 'add_cross_attention': False,
 'architectures': ['Phi3VForCausalLM'],
 'attention_dropout': 0.0,
 'auto_map': {'AutoConfig': 'microsoft/Phi-3.5-vision-instruct--configuration_phi3_v.Phi3VConfig',
              'AutoModelForCausalLM': 'microsoft/Phi-3.5-vision-instruct--modeling_phi3_v.Phi3VForCausalLM'},
 'bad_words_ids': None,
 'begin_suppress_tokens': None,
 'bos_token_id': 1,
 'chunk_size_feed_forward': 0,
 'cross_attention_hidden_size': None,
 'decoder_start_token_id': None,
 'diversity_penalty': 0.0,
 'do_sample': False,
 'early_stopping': False,
 'embd_layer': {'embedding_cls': 'image',
                'hd_transform_order': 'sub_glb',
                'projection_cls': 'mlp',
                'use_hd_transform': True,
                'with_learnable_separator': True},
 'embd_pdrop': 0.0,
 'encoder_no_repeat_ngram_size': 0,
 'eos_token_id': 2,
 'exponential_decay_length_penalty': None,
 'finetuning_task': None,
 'forced_bos_token_id': None,
 'forced_eos_token_id': None,
 'hidden_act': 'silu',
 'hidden_size': 3072,
 'id2label': {0: 'LABEL_0', 1: 'LABEL_1'},
 'img_processor': {'image_dim_out': 1024,
                   'model_name': 'openai/clip-vit-large-patch14-336',
                   'name': 'clip_vision_model',
                   'num_img_tokens': 144},
 'initializer_range': 0.02,
 'intermediate_size': 8192,
 'is_decoder': False,
 'is_encoder_decoder': False,
 'label2id': {'LABEL_0': 0, 'LABEL_1': 1},
 'length_penalty': 1.0,
 'max_length': 20,
 'max_position_embeddings': 131072,
 'min_length': 0,
 'model_type': 'phi3_v',
 'no_repeat_ngram_size': 0,
 'num_attention_heads': 32,
 'num_beam_groups': 1,
 'num_beams': 1,
 'num_hidden_layers': 32,
 'num_key_value_heads': 32,
 'num_return_sequences': 1,
 'original_max_position_embeddings': 4096,
 'output_attentions': False,
 'output_hidden_states': False,
 'output_scores': False,
 'pad_token_id': 32000,
 'prefix': None,
 'problem_type': None,
 'pruned_heads': {},
 'remove_invalid_values': False,
 'repetition_penalty': 1.0,
 'resid_pdrop': 0.0,
 'return_dict': True,
 'return_dict_in_generate': False,
 'rms_norm_eps': 1e-05,
 'rope_theta': 10000.0,
 'sep_token_id': None,
 'sliding_window': 262144,
 'suppress_tokens': None,
 'task_specific_params': None,
 'temperature': 1.0,
 'tf_legacy_loss': False,
 'tie_encoder_decoder': False,
 'tie_word_embeddings': False,
 'tokenizer_class': None,
 'top_k': 50,
 'top_p': 1.0,
 'torch_dtype': torch.bfloat16,
 'torchscript': False,
 'transformers_version': '4.38.1',
 'typical_p': 1.0,
 'use_bfloat16': False,
 'use_cache': True,
 'vocab_size': 32064}

======== Full Model Structure ========
Phi3VForCausalLM(
  (model): Phi3VModel(
    (embed_tokens): Embedding(32064, 3072, padding_idx=32000)
    (embed_dropout): Dropout(p=0.0, inplace=False)
    (vision_embed_tokens): Phi3ImageEmbedding(
      (drop): Dropout(p=0.0, inplace=False)
      (wte): Embedding(32064, 3072, padding_idx=32000)
      (img_processor): CLIPVisionModel(
        (vision_model): CLIPVisionTransformer(
          (embeddings): CLIPVisionEmbeddings(
            (patch_embedding): Conv2d(3, 1024, kernel_size=(14, 14), stride=(14, 14), bias=False)
            (position_embedding): Embedding(577, 1024)
          )
          (pre_layrnorm): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
          (encoder): CLIPEncoder(
            (layers): ModuleList(
              (0-23): 24 x CLIPEncoderLayer(
                (layer_norm1): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
                (mlp): CLIPMLP(
                  (activation_fn): QuickGELUActivation()
                  (fc1): Linear(in_features=1024, out_features=4096, bias=True)
                  (fc2): Linear(in_features=4096, out_features=1024, bias=True)
                )
                (layer_norm2): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
                (self_attn): CLIPAttentionFA2(
                  (k_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (v_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (q_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (out_proj): Linear(in_features=1024, out_features=1024, bias=True)
                )
              )
            )
          )
          (post_layernorm): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
        )
      )
      (img_projection): Sequential(
        (0): Linear(in_features=4096, out_features=3072, bias=True)
        (1): GELU(approximate='none')
        (2): Linear(in_features=3072, out_features=3072, bias=True)
      )
    )
    (layers): ModuleList(
      (0-31): 32 x Phi3DecoderLayer(
        (self_attn): Phi3FlashAttention2(
          (o_proj): Linear(in_features=3072, out_features=3072, bias=False)
          (qkv_proj): Linear(in_features=3072, out_features=9216, bias=False)
          (rotary_emb): Phi3SuScaledRotaryEmbedding()
        )
        (mlp): Phi3MLP(
          (gate_up_proj): Linear(in_features=3072, out_features=16384, bias=False)
          (down_proj): Linear(in_features=8192, out_features=3072, bias=False)
          (activation_fn): SiLU()
        )
        (input_layernorm): Phi3RMSNorm()
        (resid_attn_dropout): Dropout(p=0.0, inplace=False)
        (resid_mlp_dropout): Dropout(p=0.0, inplace=False)
        (post_attention_layernorm): Phi3RMSNorm()
      )
    )
    (norm): Phi3RMSNorm()
  )
  (lm_head): Linear(in_features=3072, out_features=32064, bias=False)
)

======== Immediate Child Modules ========
model -> Phi3VModel
lm_head -> Linear

======== Modules Potentially Related to Vision or Text ========
model.vision_embed_tokens -> Phi3ImageEmbedding
model.vision_embed_tokens.drop -> Dropout
model.vision_embed_tokens.img_processor -> CLIPVisionModel
model.vision_embed_tokens.img_processor.vision_model -> CLIPVisionTransformer
model.vision_embed_tokens.img_processor.vision_model.embeddings -> CLIPVisionEmbeddings
model.vision_embed_tokens.img_processor.vision_model.embeddings.patch_embedding -> Conv2d
model.vision_embed_tokens.img_processor.vision_model.embeddings.position_embedding -> Embedding
model.vision_embed_tokens.img_processor.vision_model.pre_layrnorm -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder -> CLIPEncoder
model.vision_embed_tokens.img_processor.vision_model.encoder.layers -> ModuleList
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.post_layernorm -> LayerNorm
model.vision_embed_tokens.img_projection -> Sequential
model.vision_embed_tokens.img_projection.0 -> Linear
model.vision_embed_tokens.img_projection.1 -> GELU
model.vision_embed_tokens.img_projection.2 -> Linear
model.layers.0 -> Phi3DecoderLayer
model.layers.1 -> Phi3DecoderLayer
model.layers.2 -> Phi3DecoderLayer
model.layers.3 -> Phi3DecoderLayer
model.layers.4 -> Phi3DecoderLayer
model.layers.5 -> Phi3DecoderLayer
model.layers.6 -> Phi3DecoderLayer
model.layers.7 -> Phi3DecoderLayer
model.layers.8 -> Phi3DecoderLayer
model.layers.9 -> Phi3DecoderLayer
model.layers.10 -> Phi3DecoderLayer
model.layers.11 -> Phi3DecoderLayer
model.layers.12 -> Phi3DecoderLayer
model.layers.13 -> Phi3DecoderLayer
model.layers.14 -> Phi3DecoderLayer
model.layers.15 -> Phi3DecoderLayer
model.layers.16 -> Phi3DecoderLayer
model.layers.17 -> Phi3DecoderLayer
model.layers.18 -> Phi3DecoderLayer
model.layers.19 -> Phi3DecoderLayer
model.layers.20 -> Phi3DecoderLayer
model.layers.21 -> Phi3DecoderLayer
model.layers.22 -> Phi3DecoderLayer
model.layers.23 -> Phi3DecoderLayer
model.layers.24 -> Phi3DecoderLayer
model.layers.25 -> Phi3DecoderLayer
model.layers.26 -> Phi3DecoderLayer
model.layers.27 -> Phi3DecoderLayer
model.layers.28 -> Phi3DecoderLayer
model.layers.29 -> Phi3DecoderLayer
model.layers.30 -> Phi3DecoderLayer
model.layers.31 -> Phi3DecoderLayer
```



**结构分析：**

模型整体结构梳理

1. **图片编码器 (CLIP Vision)** • 在打印结果里，你可以看到 model.vision_embed_tokens.img_processor -> CLIPVisionModel(vision_model)。 • 这实际上就是一个 CLIP 的视觉分支（ClipVit-Large-Patch14-336），用来把图像转成高维视觉特征。官方给它命名为 CLIPVisionModel，这部分只负责处理图像，没有对应的 CLIP 文本编码器。 • 输出的视觉特征再经过一个 img_projection 的 MLP（model.vision_embed_tokens.img_projection），把维度从 1024 投影到与文本同样的 hidden_size(3072)。

"model_name": "openai/clip-vit-large-patch14-336" 这正是 CLIP 的 ViT-L 模型（patch size 为 14、输入分辨率 336）。

1. 文本解码器 (Phi3DecoderLayer × 32) • model.layers 内含 32 个 Phi3DecoderLayer，用于文本生成或对多模态信息进行解码；最后再经过 lm_head (model.lm_head) 映射到词表完成输出。 • 这部分就是 Phi-3.5 模型专门的“语言模型”或称“decoder”。

在名字上： • “model.vision_embed_tokens.*” → 视觉端(编码器)相关，包括 CLIPVisionModel 和后续 MLP 的投影部分(img_projection)。 • “model.layers.” (Phi3DecoderLayer) → 文本解码器(Decoder)层。 • “model.embed_tokens” → 文本输入的词向量 (Embedding)。 • “model.norm” → 文本最后一层归一化，一般也属于文本部分。 • “lm_head” → 文本输出投射层，也属于文本解码侧。

### 微调的模块



1. **“只微调视觉，冻结文本解码器”的思路**

如果你想 **“只更新视觉编码器”**，需要让 `vision_embed_tokens` 下的参数保持 `requires_grad = True`，而文本侧（包括 `decoder`、`embedding`、`lm_head` 等）全部 `requires_grad = False`。

以下是伪代码示例：

```
for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就微调，否则冻结  
    if "vision_embed_tokens" in name:  
        param.requires_grad = True  
    else:  
        param.requires_grad = False  
  
# 只把可训练参数传给优化器  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就微调，否则冻结  
    if "vision_embed_tokens" in name:  
        param.requires_grad = True  
    else:  
        param.requires_grad = False  
  
# 只把可训练参数传给优化器  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  
```



这样，`model.vision_embed_tokens.*` 会更新，而文本部分（如 `model.layers.*`、`model.embed_tokens`、`lm_head`）不会变动。

1. **“只微调文本，冻结视觉编码器”的思路**

反过来，如果你想 **“只更新文本解码器”**，而冻结 `CLIPVisionModel` 等视觉部分，则需要让 `vision_embed_tokens` 相关的所有参数 `requires_grad = False`，文本侧（如 `embedding`、`decoder layer`、`lm_head`）设置为 `True`。

以下是伪代码示例：

```
for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就冻结，否则训练  
    if "vision_embed_tokens" in name:  
        param.requires_grad = False  
    else:  
        param.requires_grad = True  
  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  
```



完整微调步骤参考：

*https://github.com/xinyuwei-david/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning*