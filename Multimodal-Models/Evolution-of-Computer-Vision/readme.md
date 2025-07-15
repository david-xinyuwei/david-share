# 计算机视觉的演进与多模态建模：从CNN到视觉语言模型

## **引言**

计算机视觉（Computer Vision, CV）作为人工智能领域的重要研究方向，从最初尝试模拟人类视觉感知，到如今的多模态模型和通用智能，其发展经历了多个显著阶段：

- **从最早的手工设计特征**（如SIFT、HOG），到利用深度学习的**卷积神经网络（CNN）**，显著提升了视觉任务的精度和效率。
- 再到 **Transformer 视觉模型（如 ViT）** 的引入，用全局建模能力突破了局部特征的局限性。
- 最后发展到 **视觉语言模型（Vision Language Models, VLM）**，将图像编码器和语言生成组件结合，实现了从图像识别到语言生成、多模态推理等复杂任务的有机融合。

近年来，多种 VLM 模型（如 CLIP、Florence-2、Qwen2-VL）取得了优秀成绩，使计算机视觉逐步迈入多模态交互与智能推理的新阶段。以下我们将详细梳理 CV 的演化路径，并分析代表性技术和模型的应用特点。

### 视觉模型能力递进示意

① 纯视觉编码器
ResNet／ViT／DaViT …
↓（图像预处理 → 视觉特征提取，输出**纯视觉表示**）

② CLIP-类双编码器跨模态对齐
（视觉编码器 + 文本编码器 并列前向）
↓（对比学习将图像表示与文本表示映射到**统一语义嵌入空间**，支持零样本检索／分类）

③ 视觉语言模型（VLM）
Florence-2、BLIP-2、Qwen-VL …
↓（在已有**对齐机制**上，叠加文本解码器或跨模态 Transformer，引入**生成、对话、多任务**能力）

───
能力“叠加”说明
• 第一层：模型仅需理解图像，输出视觉特征。
• 第二层：通过跨模态对齐，让图像特征与文本语义互通，可直接比对或检索。
• 第三层：在对齐基础上接入语言解码／交互模块，使模型不仅理解图像，还能生成描述、回答问题、执行复杂推理。

注：多数 VLM 会重用 CLIP-式视觉塔或等价的图文对齐机制，但并非都“先训练 CLIP 再接解码器”；也有如 Florence-2 那样端到端的交互式 Encoder-Decoder 实现，原理同样基于“对齐 + 生成”两步。

## **1. CV 演进的主要阶段**

### **1.1 计算机视觉的简单示意等式**

下列“等式”用极简符号归纳各阶段模型的核心架构与逻辑特色：

#### 1. 卷积网络（CNN）阶段：强调局部特征建模

- AlexNet

  = 多层卷积 (Conv) + ReLU + MaxPool + LRN + Dropout

  - 引入 ReLU 非线性、局部响应归一化 (LRN)、Dropout 和双 GPU 并行，首次在 ImageNet 取得突破。

- ResNet

  = AlexNet + BatchNorm + Bottleneck + 残差连接 (Skip Connection)

  - 残差单元缓解退化/梯度消失，实现百层以上深网；BatchNorm 与 Bottleneck 设计兼顾收敛与计算效率。

- 特点

  - 局部特征提取高效；大感受野或非局部模块可增强全局感知，但纯 CNN 捕捉长距依赖仍有不足。

#### 2. 视觉 Transformer 阶段：强化全局建模

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

#### 3. 跨模态模型（VLM）阶段：图像 × 语言深度融合

- CLIP

  = 图像编码器 (ViT/ResNet) + 文本编码器 (Transformer) + 对比损失 (Contrastive Loss)

  - 图文对齐，构建共享嵌入空间，支持零样本任务。

- Florence-2

  = 多主干视觉编码器 (InternImage-H／SwinV2-G 等) + 多任务解码器 + Prompt 指令

  - 生成式多模态系统，统一分类、检测、分割、描述生成等任务。

- Qwen-VL / Qwen-VL-Chat

  = 图像编码器 (ViT) + LLM 文本解码器 + M-ROPE (多模态 Rotary 位置编码)

  - 强调视觉语义与大语言模型融合，可对话、长视频推理。

- 特点

  - 图文对齐 + 生成/推理能力显著扩大应用边界。

#### 4. 未来全模态模型（示意）：迈向通用人工智能

- 全模态模型
  = Vision + Text + Audio + Motion + Tactile + Depth/LiDAR …

------

### **1.2 演化阶段对比表**

| **演化阶段**          | **代表模型**           | **核心特点**                                          | **典型任务 & 示例**                                          |
| --------------------- | ---------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| **传统方法时期**      | SIFT, HOG              | 手工特征 + 领域知识                                   | 形状识别：HOG 检测人形轮廓。                                 |
| **卷积网络（CNN）**   | AlexNet, VGG, ResNet   | 高效局部特征；残差解决深网退化                        | 图像分类：ResNet-50 在 ImageNet 猫狗分类。                   |
| **视觉 Transformer**  | ViT, DeiT, Swin, DaViT | 全局建模；蒸馏 / 分层 / 双注意力 优化小数据和密集预测 | 图像分割：Swin 用于自动驾驶车道线/实例分割。                 |
| **跨模态模型（VLM）** | CLIP                   | 图文对比学习，零样本泛化                              | “这是一张包含猫的图片” → 检索匹配图像。                      |
|                       | Florence-2             | 多任务解码 + Prompt 灵活性                            | 医疗影像：肿瘤分割并生成诊断描述。                           |
|                       | Qwen-VL / Qwen-VL-Chat | ViT + LLM，支持多轮对话推理                           | 视频问答：解析“人物何时开始跑步？”并多轮解释。               |
| **未来趋势**          | 全模态 AI              | Vision+Text+Audio+Motion 等多模态协同                 | 辅助机器人：融合摄像头、语音指令、机械运动与触觉，为仓储机器人提供全栈感知与控制。 |

------

## **2. 什么是视觉塔（Vision Tower）？**

### **2.1 概念解析**

视觉塔是视觉-语言模型中专门处理图像的 **视觉编码器**，将像素 → 高维语义特征，供文本解码器或多模态交互层使用，可类比“大脑的视觉皮层”。

### **2.2 视觉塔的常见实现**

1. **卷积神经网络（CNN）**：如 ResNet，参数高效，适合简单分类/匹配。
2. **Vision Transformer (ViT)**：原生全局注意力，现代 VLM 默认选项。
3. **混合架构（CNN+ViT）**：如 ConvNeXt、InternImage，将卷积效率与全局表示结合。

### **2.3 不同 VLM 中视觉塔对比**

| **模型**     | **视觉塔**                               | **典型任务 & 示例**                                      |
| ------------ | ---------------------------------------- | -------------------------------------------------------- |
| CLIP         | ResNet / ViT                             | 图文检索、零样本分类。                                   |
| Florence-2   | InternImage-H / SwinV2-G 等 + 任务解码头 | 医疗分割：高分辨肿瘤标注；复杂检测/描述多任务。          |
| Qwen-VL 系列 | ViT + M-ROPE                             | 视频问答、对话推理：“视频中的人物在做什么？”。           |
| Phi-Vision   | 轻量化 ViT 变体                          | 学术场景：读图表并生成推理报告，如“图中趋势是否线性？”。 |

------

## **3. 微调（Finetuning）最佳实践**

### 3.1 微调模式选择表

| **微调模式**     | **视觉塔**  | **文本解码器**             | **适用场景**                                  |
| ---------------- | ----------- | -------------------------- | --------------------------------------------- |
| 仅视觉塔微调     | ✅           | ❌ 冻结                     | 域差异大：医学影像、遥感；仅需调整视觉特征。  |
| 仅文本解码器微调 | ❌ 冻结      | ✅（全参或 LoRA/Prefix 等） | 文本风格或任务格式改变：儿童科普、新闻摘要。  |
| 跨模态交互层微调 | ✅（可冻结） | ✅（可 LoRA/Adapter）       | VQA、视觉对话：需强化融合但整体结构无需重训。 |
| 全参数微调       | ✅           | ✅                          | 高价值专域、数据充足；追求最优性能。          |

### 3.2 性能维度比较

| **类别**          | **代表模型**    | **主要任务**                    | **示例**                                                     |
| ----------------- | --------------- | ------------------------------- | ------------------------------------------------------------ |
| 卷积神经网络      | ResNet、VGG     | 分类、检测（局部特征 + 低计算） | ResNet-50 区分 “虎猫 vs 家猫”。                              |
| 视觉 Transformer  | ViT、DeiT、Swin | 分割、全局分类（长程依赖）      | Swin 自动驾驶场景车道线/实例分割。                           |
| 跨模态模型（VLM） | CLIP            | 零样本检索、分类                | 文本查询 “海滩日落” → 匹配最相关图像。                       |
|                   | Florence-2      | 分类、检测、分割、生成          | 医疗图像：分割肿瘤并生成 “肿瘤位于 T2 区，疑似良性”。        |
|                   | Qwen-VL-Chat    | 多轮对话、推理、生成            | 用户上传视频问 “如何拆卸设备？” → 模型给出分步骤解释并可继续对话。 |

结论：

1. ViT 系列对复杂高维任务更优，但训练数据需求大；
2. VLM 通过图文融合显著扩展应用范围，生成与推理能力突出；
3. 适配特定场景时，可根据数据量与目标选择视觉塔微调、解码器微调或轻量 LoRA/Adapter 策略。

## **卷积神经网络与 ResNet**

卷积神经网络（CNN）曾长期主导视觉任务。从 LeNet（1989）、AlexNet（2012）到 VGG（2014），每一代 CNN 以「加深网络层数 / 增大卷积通道」来提升特征提取能力。然而，网络越深，梯度传递越困难，出现**退化现象**（degradation）：层数增加反而使训练与测试精度下降。

2015 年，He Kaiming 等提出 **Residual Network（ResNet）**，用 **残差学习** 框架解决深网退化问题。核心做法是在每个残差块（Residual Block）内添加 **跳跃连接**（Skip Connection）：

F(x) + x → y （F 表示卷积堆叠的残差映射）

该设计让网络直接学习「残差」而不是完整映射，信息能够跨层直达，缓解了梯度消失/爆炸。配合 **Batch Normalization** 与 **Bottleneck** 结构，ResNet-152 在 ImageNet-1K 取得约 78.6 % 的 Top-1 精度，把深度网络尺度推到 100+ 层，奠定了后续极深 CNN 的可训练性。

CNN 的优势在于卷积核的**局部归纳偏置**：局部特征提取高效，在中小数据集上表现稳健。但局部卷积要捕捉相距甚远的区域关联，必须层层堆叠扩大感受野，难以直接建立**全局依赖**。因此「在保持局部先验的同时，引入全局建模能力」成为 CNN 时代后期的重要课题，也为 Transformer 在视觉中的落地埋下伏笔。

------

## **Vision Transformer (ViT) 及改进**

### 1. ViT 基础

2020 年，Dosovitskiy 等提出 **Vision Transformer (ViT)**，将一张图像视为由固定大小补丁 (patch) 组成的序列——「把图像当句子」。流程：

1. 将 H × W 图像切成 N = (H/P)² 个 P × P 补丁；
2. 每个补丁展平后映射到 d 维向量，加上可学习 **位置编码**；
3. 将补丁序列送入纯 Transformer Encoder 计算 **全局自注意力**；
4. 取 **[CLS] token** 或所有 patch 表示用于下游任务。

在 JFT-300M 级别数据预训练 + ImageNet 微调后，ViT-Huge/14 Top-1 > 90 %，相比同规模 ResNet 提升约 10 个百分点，显示出 Transformer 对大规模数据的强大可扩展性与全局表征能力。

### 2. ViT 的数据需求与改进方向

直接在 ImageNet-1K（120 万张）从零训练 ViT 会明显落后同级别 CNN。围绕「数据高效」与「计算高效」两条主线，研究者提出多种改进：

• **DeiT**：引入 Distillation Token 的 **知识蒸馏**，在 ImageNet-1K 单卡训练即可与 ResNet-50 打平甚至反超。
• **Swin Transformer**：采用 **分层金字塔 + 滑窗注意力**，兼顾全局建模与高分辨率密集预测；成为分割/检测等任务新基线。
• **ConvNeXt**：回到卷积视角，用卷积实现 ViT 式宏观设计，取卷积/Transformer 之长。
• **SoViT（Shape-Optimized ViT）**：系统搜索宽深比，400 M 参数模型即可逼近 1 B+ 模型精度。
• **DaViT（Dual Attention ViT）**：在不同层交替加入 **空间自注意力 + 通道自注意力**，以极小代价提升分类/分割精度，DaViT-Giant Top-1 ≈ 90.4 %。

------

## **CLIP：跨模态对齐的视觉-语言预训练**

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

------

## **视觉语言大模型（VLM）**

### 1. Florence-2（Microsoft, 2024）

• **Seq-to-Seq Transformer**：视觉编码器 (InternImage-H / SwinV2-G) + 文本解码器。
• **统一 Prompt 接口**：分类、检测、分割、Caption、OCR…均用文本指令描述任务。
• **FLD-5B 数据集**：5.4 B 多模态标注，涵盖 44 个任务类型。
• **效果**：在 80+ Benchmark 获得 SOTA / 次 SOTA；零样本检测与分割表现尤为突出。

### 2. Qwen-VL / Qwen-VL-Chat（Alibaba, 2024）

• **架构**：ViT 视觉塔 + 70 B 级 Qwen-LLM，采用 **M-ROPE** 多模态旋转位置编码。
• **能力**：多轮对话、长视频逐帧推理、跨语言 OCR；在 DocVQA、MathVista、MMMU 等基准超越多款闭源模型。
• **开源**：提供 7 B / 2 B 量级模型（Apache-2.0），移动端即可部署。

### 3. 共同特征

1. **生成式 + 对话式**：图像/视频输入 → 文本输出，可多轮交互。
2. **多任务统一**：单模型覆盖分类、检测、分割、VQA、Caption…
3. **跨模态推理**：结合视觉与世界知识完成复杂逻辑。
4. **大模型加持**：借助 LLM 语言推理能力，视觉理解跃升到认知层面。
5. **开放生态**：Hugging Face、vLLM、DeepSpeed 等工具链加速落地。

------

## **方法与架构 (Methodology & Architecture)**

### 1. Vision Transformer 前向示例

```
import torch, torch.nn as nn

class SimpleViT(nn.Module):
    def __init__(self, img_size=224, patch_size=16, d=768,
                 layers=12, heads=12):
        super().__init__()
        n_patches = (img_size // patch_size) ** 2
        self.patch_embed = nn.Conv2d(3, d, patch_size, patch_size)
        self.cls_token  = nn.Parameter(torch.zeros(1, 1, d))
        self.pos_embed  = nn.Parameter(torch.zeros(1, 1 + n_patches, d))
        enc_layer = nn.TransformerEncoderLayer(d, heads, dim_feedforward=4*d)
        self.encoder = nn.TransformerEncoder(enc_layer, layers)

    def forward(self, x):
        B = x.size(0)
        x = self.patch_embed(x).flatten(2).transpose(1, 2)   # (B, N, d)
        cls = self.cls_token.expand(B, -1, -1)               # (B, 1, d)
        x = torch.cat([cls, x], 1) + self.pos_embed[:, :x.size(1)]
        x = self.encoder(x)
        return x[:, 0]                                        # (B, d)
```



该示例展示了「Patch → 位置编码 → 全局自注意力」的标准 ViT 流程，单层注意力复杂度 O(N²d)。对高分辨率输入常用 Swin 等局部窗口或稀疏注意力降低计算。

### 2. 视觉语言模型的融合范式

1. **双流 + 对比对齐（CLIP）**：图文各自编码，训练期用对比损失对齐，推理期做向量检索。
2. **单流 + 交互注意力（BLIP / Florence-2）**：图像 patch / 区域特征与文本 token 拼接，共同进入跨模态 Transformer；适合 VQA、Caption 等细粒度对齐任务。
3. **混合范式（BLIP-2、LLaVA-1.5、Qwen-VL）**：先用 CLIP 式对齐取视觉摘要，再将摘要嵌入 LLM 作长文本生成与推理。

------

## **实战经验 (Practical Experience)**

| 技术                        | 作用/优势                                  | 典型工具 & 备注                              |
| --------------------------- | ------------------------------------------ | -------------------------------------------- |
| **LoRA / Adapter / BitFit** | 仅增量训练少量参数，降显存防过拟合         | 🤗 PEFT、LoRA-PyTorch 等                      |
| **QLoRA**                   | 4-bit 权重量化 + LoRA 训练，显存省 60-70 % | Unsloth / bitsandbytes                       |
| **FlashAttention 2**        | 自定义 CUDA 内核，Attention 更快、显存更低 | 集成于 PyTorch 2.1 / xFormers / Unsloth      |
| **ZeRO-3 / Offload**        | 张量切分+梯度分布，单机多卡训练百亿模型    | DeepSpeed、ColossalAI                        |
| **Gradient Checkpointing**  | 保存显存换取少量计算                       | transformers.enable_gradient_checkpointing() |

示例：在 BLIP-VQA 上插入 LoRA 低秩适配，仅更新 0.5 % 参数，即可在单张 24 GB GPU 上完成微调。

------

## **从零训练 ViT：数据与优化要点**

1. **强数据增广**：RandAugment, Mixup, CutMix, Random Erasing。
2. **长周期训练**：300-400 epoch + Cosine LR + Warm-up。
3. **知识蒸馏**：DeiT 方案，CNN 教师 → ViT 学生，硬标签 + 软标签 KL。
4. **架构搜寻**：SoViT 指出合理「宽 / 深」比例与 token-FFN 维度比。
5. **高效训练**：fp16/bf16 + 多卡并行 + Checkpointing。

在中小数据集（≤ ImageNet-1K）场景，自监督或蒸馏 + 预训练权重仍明显优于纯从头训练。

------

## **实验性能对比 (Selected Benchmarks)**

| 模型           | 预训练规模    | ImageNet-1K Top-1 | 备注                           |
| -------------- | ------------- | ----------------- | ------------------------------ |
| ResNet-152     | 1.2 M（监督） | 78.6 %            | 152 层残差网络                 |
| ViT-B/16       | 21 K + 1 K    | 84-85 %           | 86 M 参数，需更大数据发挥潜力  |
| ViT-H/14       | JFT-300 M     | > 90 %            | 600 M 参数，全球首个 90 %+ ViT |
| SoViT-400 M/14 | JFT-3 B       | 90.3 %            | Shape-Optimized，400 M 参数    |
| DaViT-Giant    | 1.5 B 图文对  | 90.4 %            | 双注意力，分类/分割均 SOTA     |

在更复杂任务（DocVQA、MathVista、MMMU 等）上，Qwen-VL-Chat-72 B 已超过 GPT-4V (2023) 与 Claude-3.5（闭源），标志开源 VLM 首次达到顶级水平。

------

## **总结与展望**

1. **技术演进**：
   CNN→ResNet 解决深度退化；ViT 引入全局自注意力，依赖大数据；CLIP 打通图文语义；VLM 将视觉推向认知智能。
2. **未来趋势**：
   • 全模态（Vision + Text + Audio + Motion + Tactile 等）；
   • 更高效的稀疏/低秩注意力与模型压缩；
   • 强跨模态推理与动作规划；
   • 自监督、生成式 RLHF 的新训练范式；
   • 可信、安全、多模态伦理框架。

计算机视觉正从**感知时代**迈向**认知时代**。借助统一的大模型与开放工具链，视觉 AI 的应用边界将被持续拓宽——从手机端实时助手到工业机器人，再到专业医学诊断，未来十年值得期待。