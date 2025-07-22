# Flux.1 Solution Test

FLUX.1 是由 Black Forest Labs 开发的开源图像生成模型。它提供多个版本以满足不同用户需求，包括 [pro]、[dev] 和 [schnell]。本文使用 FLUX.1 的 dev 版本进行了验证。FLUX.1 支持最高可达 2K 分辨率（2048 x 2048 像素）。

## FLUX.1 模型技术架构与处理流程

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/7.jpg)

FLUX.1 模型是一种基于 Transformer 的文本-图像多模态生成模型，整体生成流程包括：

### 1.模型输入（Inputs）:

- **文本提示（Text Prompt）**：用户给定的描述、指令或关键词。
- **CLIP文本编码器（CLIP）**：用于处理短文本或视觉关键词。
- **T5文本编码器（T5 Encoder）**：用于处理长文本、结构复杂的文本条件。
- **图像潜变量（Latent）**：VAE压缩的图像潜变量（进行图像编辑或图像+文本联合任务输入）。
- **时间步信息（Timesteps）**：扩散生成的阶段信息。
- **引导系数（Guidance）**：生成结果的引导参数（Classifier-free guidance）。
- **频率位置编码（Frequency Positional Embedding）**：用于空间位置和频率信息的编码表示。
- **文本Token标识 (Text Ids)、图像Token标识（Image Ids）**：用于区分文本和图像的Tokens标记。

### 2.模型处理过程（Processing & Architecture）：

#### 1）文本编码阶段（Text Encoding）:

- 同时使用两个文本编码器（CLIP & T5）：
  - **CLIP（Contrastive Language-Image Pre-training）**：擅长提取关键词和视觉相关概念；
  - **T5（Text-to-Text Transfer Transformer）**：擅长理解长而复杂的描述性提示，有效解析更长文本（可达512个token），为模型提供精确的丰富的语言理解与语义指导；
- 从两个文本编码器得到文本表示后，经由Transformer结构投影到模型内部统一的表示空间中。

#### 2).Transformer特征处理阶段（Transformer Processing）:

- 核心为“双流”扩散Transformer模型，包括两个层次（明确显示于架构图中）：

  ##### （1）N 个“双流多模态（Double Stream Multimodal）Transformer”块：

  - 分别接受图像潜变量（Latent）与文本嵌入特征（Text），单独处理这两个模态的特征。
  - 通过跨注意力（Cross-Attention）实现图像<-->文本的即时、双向的信息流，互相调制与融合特征，使图像与文本更加一致。

  ##### （2）N 个“单流（Single Stream）Transformer”块：

  - 对单独模态（如图像潜变量特征）进一步细化处理。
  - 使用旋转位置嵌入（RoPE）、调制方式（Modulation）、GELU激活函数增强模型表达能力。

#### 3).模型中间处理环节（Processing & Flow Matching训练）:

- FLUX.1利用流匹配训练方式（Flow Matching），特别是修正流（Rectified Flow）方式：
  - 修正流并不使用传统扩散模型的逐步去噪，而是在潜变量空间中直接学习连续变换路径（ODE），使模型训练更直接，生成路径更优化，提升采样效率与图像质量。
  - 模型训练时进一步选择具有视觉感知作用的频率尺度进行优化。

### 3.模型输出（Outputs）：

- Transformer输出潜变量预测（Latent Prediction）：
  - 模型生成过程中逐步获得图像潜变量的预测与更新。
- VAE解码器（VAE Decoder）：
  - 将经过扩散Transformer处理完成后的潜变量信息，解码还原为最终视觉图像（Image）。
- 生成图像（Final Output Image）：模型经上述处理流程后输出的最终图像结果。

## FLUX.1 与传统U-Net（如Stable Diffusion）对比：

- 传统扩散模型（Stable Diffusion）使用卷积U-Net及单向文本条件机制，图像过程不反馈到文本，文本特征固定处理，缺乏交互实时性。
- FLUX.1使用Transformer构成多模态双流设计，图像特征和文本特征可以实时进行双向交互处理，明显突破了文本仅为单向条件输入的局限性，实现更精准的细节渲染与文本理解。

- 潜在扩散VAE：16通道高细节潜变量 vs 传统4通道，增强图像保真度并原生支持1024×1024分辨率。
- 引导蒸馏（schnell）：实现快速采样（1～4步），用于高效推理场景。
- 并行注意力机制：在双流模块内同时执行图像和文本注意力操作，增强模态互动与解释性。

### **Flux**.1组件使用场景和组合列表

| **任务类型/场景**                                     | **核心组件**                                                 | **组件组合逻辑与使用情况**                                   |
| ----------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **1. 纯文本生成图像（Text-to-Image）**                | **CLIP 文本编码器** / **T5 文本编码器** / **扩散 Transformer（双流架构）** / **VAE 解码器** | - **CLIP 文本编码器**：提取关键词（如提示短、含关键词，如“夜晚的东京霓虹灯”）。 <br>- **T5 文本编码器**：处理复杂、长提示（如分段或详细描述）。 <br>- **扩散 Transformer**：生成潜在空间中的图像。 <br>- **VAE 解码器**：将潜在表示还原成高分辨率图像。 |
| **2. 图像+文本联合生成（Image+Text-to-Image）**       | **视觉编码器（VAE Encoder）** / **CLIP 文本编码器** / **T5 文本编码器** / **扩散 Transformer** / **VAE 解码器** | - **视觉编码器**：输入图像编码为潜在向量，用作生成的初始条件或参考背景图像。<br>- **CLIP + T5**：文本部分用于指定目标图像某些生成细节（如层次关系、风格描述）。<br>- **扩散 Transformer**：在潜在空间中结合图像与文本特征完成生成。<br>- **VAE 解码器**：完成潜在向量到图像的解码。 |
| **3. 图像编辑（Image Editing）**                      | **视觉编码器（VAE Encoder）** / **文本编码器（T5 或 CLIP）** / **扩散 Transformer** / **VAE 解码器** | - **视觉编码器**：将输入图像转换为潜在空间表示，作为编辑的操作起点。<br>- **文本编码器**：解析提示，指导修改目标（如“将天空调成粉红色”）。<br>- **扩散 Transformer**：根据文本条件和图像潜在表示生成结果。<br>- **VAE 解码器**：解码修改后的潜在特征生成最终图像。 |
| **4. 风格迁移（Style Transfer）**                     | **视觉编码器（VAE Encoder）** / **文本编码器（CLIP 或 T5）** / **扩散 Transformer** / **VAE 解码器** | - **视觉编码器**：将输入原始图像映射到潜在空间，保留基本内容信息。<br>- **文本编码器**：理解目标风格描述（如“梵高风格”）。<br>- **扩散 Transformer**：在潜在空间中整合风格信息，最终生成风格化图像。<br>- **VAE 解码器**：输出含新风格的高分辨率图像。 |
| **5. 清晰度/分辨率增强（Super-Resolution）**          | **视觉编码器（VAE Encoder）** / **扩散 Transformer（低效版）** / **VAE 解码器** | - **视觉编码器**：将低清晰度图像压缩到潜在空间。<br>- **扩散 Transformer**：在潜在空间增强细节并去除伪影。<br>- **VAE 解码器**：解码为高分辨率图像。 |
| **6. 局部修改（Inpainting/局部填充）**                | **视觉编码器（VAE Encoder）** / **辅助工具模块（如深度映射模块）** / **扩散 Transformer** / **VAE 解码器** | - **视觉编码器**：局部涂抹的图像作为输入，转换至潜在空间。<br>- **辅助模块**：如深度映射、边缘检测等，为扩散生成提供附加信息引导。<br>- **扩散 Transformer**：生成被移除部分的补全结果。<br>- **VAE 解码器**：解码最终完整图像。 |
| **7. 高速生成（Quick Synthesis）**                    | **CLIP（文本编码）** / **简化版扩散 Transformer（Few-Step 推理）** / **轻量级 VAE 解码器** | - **CLIP**：快速解析关键词/简单的文本描述（主要针对快速生成需求）。<br>- **简化版扩散模型（Schnell Version）**：少步数推理（通常为 4 步）。<br>- **轻量级 VAE**：更快的潜在特征解码器。 |
| **8. 专注语义对齐（Prompt-to-Image 精度变量测试）**   | **CLIP** / **T5** / **Full Diffusion Transformer (高参数版)** / **VAE 解码器** | - **CLIP & T5**：语义解析和精度对齐逻辑深耦合。<br>- **高参数扩散 Transformer**：通过多 Token 提升对多层次提示的精确生成。<br>- **VAE 解码器**：解码高保真细节。 |
| **9. 强控制（自定义，例如 Depth-to-Image/边缘检测）** | **视觉编码器（附加控制模块）** / **扩散 Transformer** / **辅助模块（如 ControlNet）** / **VAE 解码器** | - **控制工具模块（扩展）**：输入的图像深度图（Depth Map）或边缘图作为额外的生成条件。<br>- **扩散 Transformer**：结合控制信号和模态完成生成。<br>- **VAE 解码器**：生成边缘约束精确的最终图像。 |

------

#### **组件使用总结：按需选择模块的灵活性**

1. **始终参与组件**：
   - **扩散 Transformer** 是 FLUX.1 的“引擎核心”，所有生成和编辑任务都需要它的参与。
   - **VAE 解码器** 负责潜在空间到最终高质量图像的还原，无论何种任务都不可或缺。
2. **根据任务动态启用的组件：**
   - **视觉编码器（VAE Encoder）** 仅在图像输入、局部编辑等任务中启动，纯文本生成时不参与。
   - **文本编码器（CLIP/T5）** 根据提示类型（长文本与短描述）动态选择使用，甚至可以仅启用 CLIP（如快速生成）。
   - **辅助模块（如 Depth Map 工具）** 是任务需求导向，即在需要深度图、边缘检测的特殊生成任务时调用。
3. **简化版本支持特定场景：**
   - 快速生成任务主要依赖 **Schnell 简化版扩散模型** 和 **CLIP 编码器**，最大程度减少多组件的复杂性。

#### **总结：FLUX.1 的模块化让其在场景适配和性能优化上表现优异**

FLUX.1 的组件并非每次都被全部调用，模块间的松耦合让系统能够按需灵活组合。这种设计既支持高性能生成需求，也能在低资源环境下实现快速推理。

### Flux与其他模型对比

| **维度 / 等式示意**          | **Florence-2**                                               | **Phi-3 Vision**                                             | **LLaVA-1.5**                                                | **CLIP**                                                     | **ViT-L/14-336（纯视觉）**                               | **FLUX.1**                                                   |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------ |
| **核心等式（组件逐级列出）** | DaViT (4-stage) → 1024-d 线性投影 → Text-Encoder (12 层) → Text-Decoder (12 层) + Decoder-Cross-Attention ← 视觉 patch | CLIP ViT-L/14-336 → HD-Transform + MLP 1024→3072 → Phi-3 Text-Decoder (32 层) + Decoder-Cross-Attention ← 视觉 patch | CLIP ViT-L/14-336 → 线性 / MLP projector (768→4096) → Vicuna-7B Decoder；视觉嵌入作为 Prefix Token（拼在自回归序列） | 视觉 Encoder (ViT-L/14-336 或 ResNet-50/101) ∥ 文本 Encoder (12 层 768 hid) + proj-head-768；双塔输出做对比损失 | ViT-L/14-336 单塔；CLS/EOS 向量 1024-d 作为图像表征      | CLIP 文本编码器 + T5 文本编码器 → 双流扩散 Transformer（跨模态交互：视觉 latent ←→ 文本 embedding） → 并行注意力层 → VAE 解码器 生成图像 |
| **模型类别**                 | Seq2Seq 全功能视觉-文本生成模型                              | Decoder-only 轻量视觉-文本生成模型                           | “CLIP 视觉塔 + LLM” 生成式 VLM                               | 双塔对比检索模型                                             | 纯视觉编码器                                             | 高质量视觉生成模型，支持多任务：Text-to-Image、Image+Text-to-Image、局部编辑、风格迁移等 |
| **视觉塔权重来源**           | DaViT 预训练（FLD-5B、COCO 等）                              | 直接复用 OpenAI CLIP ViT-L/14-336 权重                       | 直接复用 OpenAI CLIP ViT-L/14-336 权重                       | 本体即 CLIP 视觉 Encoder 权重                                | 可来自 ImageNet-21k / 自监督 (DINO, MAE …)，无跨模态对齐 | CLIP ViT-L 权重 + 自定义训练的 CNN 编码器（用于 VAE 的 Encoder 及 Kontext 工具） |
| **文本 Encoder**             | ✅ 12 层 (d=1024, heads=16)                                   | —                                                            | —                                                            | ✅ 12 层 (d=768, heads=12)                                    | 无                                                       | ✅ 结合 CLIP 文本编码器（12 层）和 T5 文本编码器（XXL 版本，24 层 d=4096），解析语义和长提示 |
| **文本 Decoder**             | ✅ 12 层 (d=1024)                                             | ✅ 32 层 Phi-3 (d=3072)                                       | ✅ Vicuna-7B Decoder (32 层, d=4096)                          | ❌ 无文本生成能力，仅视觉 / 文本特征对比                      | ❌ 无                                                     | 使用扩散 Transformer 负责生成潜在空间图像，VAE 解码器最终解码为高分辨率图像 |
| **跨模态交互方式**           | Decoder-Side Cross-Attention（视觉 patch ←→ 文本 Decoder）   | Decoder-Side Cross-Attention                                 | Prefix Token（视觉嵌入拼接至自回归序列，依靠 Self-Attn 完成交互） | ❌ 无交互层，仅对比                                           | ❌ 无跨模态交互                                           | 双流交互：视觉 latent 和文本 embedding 独立处理，自注意力和跨模态交互融合（融合点 → 并行 attention） |
| **训练范式**                 | 大规模多任务图文预训练 + 指令 SFT / RLHF                     | 复用 CLIP 视觉塔 + 多任务预训 + 指令 SFT                     | 视觉塔冻结 / LoRA 对齐，LLM 指令微调                         | 4 亿图文对比学习 (InfoNCE)                                   | ImageNet 监督或自监督 (MAE, DINO …)                      | - Flow Matching：改进的线性路径生成器<br>- 大规模图文监督学习（LAION-2B, COCO 等)<br>- 指导蒸馏：支持更高效少步推理 (如 “Schnell” 支持 4 步生成) |
| **主要能力**                 | Caption / VQA / OD / 分割 / 多轮对话                         | Caption / VQA / 轻量推理                                     | Caption / VQA / 对话                                         | 零样本分类 / 图文检索                                        | 分类、目标检测、特征提取                                 | 图像生成：Text-to-Image、多模态输入处理、图像编辑 (Inpainting)、风格迁移 (Style Transfer)、局部生成 |

## Flux.1开放模型

## 

## Flux.1 开放模型

*Refer to：https://github.com/black-forest-labs/flux?tab=readme-ov-file*

Flux.1 has many Open-weight models:

| Name                      | Usage                                                        | HuggingFace repo                                             | License                                                      |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `FLUX.1 [schnell]`        | [Text to Image](https://github.com/black-forest-labs/flux/blob/main/docs/text-to-image.md) | https://huggingface.co/black-forest-labs/FLUX.1-schnell      | [apache-2.0](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-schnell) |
| `FLUX.1 [dev]`            | [Text to Image](https://github.com/black-forest-labs/flux/blob/main/docs/text-to-image.md) | https://huggingface.co/black-forest-labs/FLUX.1-dev          | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Fill [dev]`       | [In/Out-painting](https://github.com/black-forest-labs/flux/blob/main/docs/fill.md) | https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev     | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Canny [dev]`      | [Structural Conditioning](https://github.com/black-forest-labs/flux/blob/main/docs/structural-conditioning.md) | https://huggingface.co/black-forest-labs/FLUX.1-Canny-dev    | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Depth [dev]`      | [Structural Conditioning](https://github.com/black-forest-labs/flux/blob/main/docs/structural-conditioning.md) | https://huggingface.co/black-forest-labs/FLUX.1-Depth-dev    | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Canny [dev] LoRA` | [Structural Conditioning](https://github.com/black-forest-labs/flux/blob/main/docs/structural-conditioning.md) | https://huggingface.co/black-forest-labs/FLUX.1-Canny-dev-lora | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Depth [dev] LoRA` | [Structural Conditioning](https://github.com/black-forest-labs/flux/blob/main/docs/structural-conditioning.md) | https://huggingface.co/black-forest-labs/FLUX.1-Depth-dev-lora | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Redux [dev]`      | [Image variation](https://github.com/black-forest-labs/flux/blob/main/docs/image-variation.md) | https://huggingface.co/black-forest-labs/FLUX.1-Redux-dev    | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |
| `FLUX.1 Kontext [dev]`    | [Image editing](https://github.com/black-forest-labs/flux/blob/main/docs/image-editing.md) | https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev  | [FLUX.1-dev Non-Commercial License](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev) |

 

## Buildup PoC environment

I did the test on Azure NC40 H100.

```
conda create --name=FluxKontext  python=3.11
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -r requirements.txt
python main.py --listen 0.0.0.0 --port 8188
```

### Test 1: Do Image Inpaint 

**Using  models/flux1-fill-dev.safetensors**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/3.png)

Detailed test process:

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/D5Vt_lPIkNs)



Image before backfill:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/1.png)

Prompt:

``` 
Please backfill the missing parts of the picture, only the natural landscape
```

Image after backfill:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/2.png)

GPU usage during before action:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/4.png)

### **Test 2: Flux Kontext Dev(Grouped)**

**Using models:**

- vae/ae.safetensors

- text encoders /t5xxl fp16.safetensors
- diffusion models /fux1-dev-kontext fp8 scaled.safetensors

[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/L7aDBOdz4_U)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/1.jpg)