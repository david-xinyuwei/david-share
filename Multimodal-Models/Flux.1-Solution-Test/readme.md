# Flux.1 Solution Test

## Flux的架构

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Flux.1-Solution-Test/images/7.jpg)

#### 视觉编码器（图像编码模块）

FLUX.1 支持上下文中图像生成和编辑，这需要图像编码器来处理视觉输入。在 FLUX.1 Kontext 模型中，使用卷积神经网络（CNN）图像编码器将输入图像嵌入到潜在表示中【101:4†source】。该编码器与相应的解码器共同构成一个变分自编码器（VAE），用于将图像压缩到潜在空间并重构回像素【101:4†source】。图像编码器通过将输入图像编码为潜在向量，保留了重要的视觉细节（用于编辑或风格迁移任务）。通过使用基于 CNN 的编码器-解码器，FLUX.1 能够“提取并修改视觉概念”，同时保持与原始内容的一致性【101:1†source】,【101:4†source】。本质上，视觉编码器提供了模型生成核心可以使用的图像学习表示，确保图像输入（若提供）被有效理解并整合入生成过程中。

对于纯文本生成图像（无图像输入），VAE 的编码器在训练和图像输出时仍起关键作用。它将训练图像压缩到较低维的潜在空间，扩散模型在该空间中运行。此设计遵循潜在扩散方法：模型不是直接生成全分辨率图像，而是生成潜在向量，由 VAE 解码器转换为最终图像。FLUX.1 的自动编码器相比早期设计有所改进，使用了更高维度的潜在表示（例如16个通道，而原始 Stable Diffusion 使用4个通道）【101:5†source】。这种更高容量的潜在空间保留更多图像细节，导致输出更清晰、更细致。VAE 在图像重构上进行训练（有时使用对抗损失以增强现实感【101:4†source】），随后在扩散变换器训练过程中冻结。总体上，视觉编码组件（VAE 的编码器-解码器）确保 FLUX.1 能够高效处理高分辨率图像：它加快了生成速度，提高了图像质量和细节，并加强输出的色彩保真度。

#### 文本编码器（CLIP 和 T5）

为了理解输入的提示，FLUX.1 利用了两种互补的文本编码器。首先，使用 CLIP（对比语言-图像预训练）中的模型将提示拆分为与视觉概念相关的标记。CLIP 文本编码器在图文对上预训练，因此擅长提取提示中的关键词和视觉主题（如物体、风格或属性），这有助于模型锁定提示中提及的“相关图像元素”。然而，CLIP 的文本编码器倾向于偏好简短、关键词导向的提示，可能无法充分捕捉复杂或冗长的指令。

因此，FLUX.1 还结合了 T5 文本编码器（一种文本到文本转换变换器）。T5 是一种强大的语言模型，能理解细腻且冗长的自然语言描述并遵循指令。在 FLUX.1 中，T5 编码器能够比单纯使用 CLIP 更有效地解析详尽或描述性的提示。换言之，“尽管 CLIP 模型偏好关键词式的提示，T5 编码器能够跟随详细的描述和指导”，显著提升模型对复杂句子的理解。该双编码器策略允许用户输入简洁的提示或详细叙述，并均能正确理解。

文本嵌入的融合：FLUX.1 并非简单选择其中一个编码器，而是同时利用两者。内部将 CLIP 编码器（多个模型）和 T5 编码器的输出融合，形成丰富的条件信号给图像生成器。实际上，模型“使用多个 CLIP 模型和一个 T5 模型编码文本，然后通过线性层组合所有特征。”通过合并这些嵌入，FLUX.1 捕捉了广泛的视觉语义（来自 CLIP）和精准的语言细微差别（来自 T5）。这带来了强大的提示遵从性——模型能准确反映复杂的场景描述，遵循指令（如具体的风格或布局请求），甚至能处理最高512个标记的长提示（FLUX.1 [dev] 模型）。因此，文本编码组件确保深度理解提示，使生成模型能够创作出高度契合用户描述的图像。

#### 扩散变换器架构（修正流变换器）

FLUX.1 的核心是一个基于扩散的生成模型，采用变换器架构替代传统的 U-Net。FLUX.1 的架构通常被描述为“修正流变换器”，由“融合多模态和并行扩散变换器块的混合架构”组成。该网络规模约为120亿参数，实际负责在潜在空间中从噪声预测图像，条件为文本（可选图像）嵌入【101:3†source】。

双流（多模态）变换器块：FLUX.1 变换器独特之处在于并行处理图像潜在向量和文本标记。它设有“两套分别对应两种模态的权重”（图像分支和文本分支）以及“两条并行路径供信息流动”。在每个变换器层中，模型首先通过图像分支的自注意力及前馈层更新图像潜在标记，同时通过单独文本分支的自注意力及前馈层更新文本标记。关键是这两个分支相互作用：FLUX.1 在每个模块中引入跨模态注意力融合，允许图像与文本表征互相注意。换言之，在每个 MM-DiT（多模态扩散变换器）块的中间部分，所有图像标记都可以关注文本标记，反之亦然，有效地混合两种信息流。这一设计有时称为“联合注意”或全注意，因其将自注意力和交叉注意力融合为对图像和文本标记集合的统一操作。结果是文本和图像领域间的信息双向流动：文本不仅调节图像生成，中间的图像特征也能影响文本标记表征【101:6†source】。这种双流、跨注意力架构帮助模型实现提示与生成内容的精准对齐。例如，它改进了文本理解和视觉-文本对齐（避免忽略提示细节或图像中错误生成文本），甚至比单向调节方法更好地处理图像中的排版等难题【101:6†source】。

并行注意力与效率：FLUX.1 变换器块设计旨在最大化硬件效率。由于图像和文本分支并行运行（直至通过注意力融合），计算可同时执行，更好利用现代加速器。FLUX.1 团队称之为“并行注意力层”，这项架构创新结合其它优化显著提升吞吐率。实际上，联合注意机制意味着模型无需单独顺序执行交叉注意步骤——它在一体操作中完成自注意和交叉注意，从而节省时间。尽管模型庞大，这些效率优化助力更快推理和良好扩展性。

位置嵌入：如同所有变换器，FLUX.1 需要标记序列的位置信息。其注意力层采用旋转位置嵌入（RoPE）。RoPE 通过旋转坐标嵌入编码标记位置，能保留相对位置关系且对长序列内存友好。引入 RoPE 很可能帮助 FLUX.1 处理更长文本序列（[dev]版中高达512标记）和大量图像标记而不牺牲连贯性。考虑到 FLUX 较高的潜在分辨率尤为重要（512×512图像潜在尺寸为64×64，即4096个空间标记，远超 Stable Diffusion 的32×32标记，且因通道数更大）。RoPE 支持如此多标记的稳定注意力，成就 FLUX.1 在空间细节和长文本提示上的优异表现。

综上，FLUX.1 的扩散模型是基于变换器的扩散网络，用深层注意力块替代早期模型的卷积 U-Net 骨干。通过采用 MM-DiT 架构——并行双流模块与跨模态融合，FLUX.1 达到先进的图像生成逼真度与提示对齐度。Black Forest Labs 报告称此架构结合大规模训练，“确立了文本到图像合成的新标杆”，在质量和提示遵从度上超越同期产品如 Midjourney v6、DALL·E 3 和 Stable Diffusion XL。

#### 变分自编码器（VAE）与图像解码器

与许多潜在扩散模型相似，FLUX.1 借助变分自编码器在高维图像像素空间与扩散过程所在的低维潜在空间之间架桥。VAE 编码器（即前文提及的视觉编码器）将图像压缩为潜在代码，VAE 解码器则将潜在码还原为图像。在 FLUX.1 架构中，VAE 在训练和推理过程中扮演关键角色：使模型的任务可行且提升输出质量。

潜在空间优势：在 VAE 潜在空间工作极大减轻计算负担。例如，FLUX.1 的自动编码器将一张512×512图像（约78.6万像素）压缩为64×64×16的潜在张量——空间尺寸缩小12倍。潜在编码保留图像核心内容，但需要建模的数值大幅减少。扩散变换器在该压缩表征上运行，令高分辨率处理变得可行。此设计源于 Stable Diffusion 使用的潜在扩散理念，但 FLUX.1 更进一步。团队选用潜在维度 d=16（即16个潜在通道），高于 Stable Diffusion v1 使用的4通道和 SDXL 的8通道。他们发现“容量更大的模型能在更大 d 下表现更好，带来更高图像质量”，通过16通道释出更多细节。代价则是模型更大（FLUX.1 规模达120亿参数，部分因应对更复杂潜在），但高效变换器架构减小了影响。

自动编码器训练：VAE 可能在广泛图像数据集上预训练，随后扩散训练中冻结。相关报道指出，FLUX.1 自编码器通过提升图像保真度的技术改进——如采用感知损失或对抗损失使重构更真实【101:4†source】。在 FLUX.1 Kontext 中，团队“训练卷积编码-解码器复现图像，并骗过判别器判为真实”，表明采用类似 GAN 的目标以锐化细节【101:4†source】。之后冻结编码器，扩散变换器则专注生成能解码成逼真图像的潜在码。自动编码器还使用色彩增强和优化，确保解码图像色彩鲜明正确，解决了简易扩散模型常见的颜色褪色问题【101:7†source】。

推理时，扩散变换器生成潜在向量，VAE 解码器输出最终图像。得益于高质量 VAE，FLUX.1 输出细节丰富，细微结构准确还原。总结而言，VAE 组件加速图像生成，“提升细节质量与深度，增强颜色表现”，有效作为系统的图像解码器【101:4†source】，确保变换器预测的抽象潜在可转化为清晰逼真的最终图像。

#### 流匹配训练方法

FLUX.1 优异性能的关键因素之一是其训练范式——流匹配（Flow Matching）。流匹配是一种相对较新的生成模型训练方法，结合了连续归一化流与扩散模型的思想【101:8†source】。在传统扩散模型训练（如 Stable Diffusion）中，模型学习通过得分匹配逐步去噪加噪图像。相比之下，流匹配直接训练模型去拟合概率流场，将数据分布沿选定路径变换为纯噪声。该方法描述为“通过回归沿固定概率路径的向量场，训练连续归一化流（CNFs）的一种无模拟方法”，并且“包括了扩散路径作为特殊情况”。简言之，训练定义了从真实图像到噪声的连续路径（例如潜在空间线性插值），模型学习预测使样本沿该路径移动一小步的瞬时变化率（速度）。通过积分这些学习到的“速度”场，即可生成新样本——相当于解常微分方程（ODE），而非模拟随机扩散过程【101:7†source】。

修正流（Rectified Flow）：Black Forest Labs 采用了修正流，这是一种流匹配的变体，其中数据和噪声之间的路径在潜在空间中为直线【101:6†source】,【101:7†source】。从概念上讲，模型学习直接线性地将图像分布变换成噪声，而非标准扩散中的多步随机损坏。修正流具有理论优势（为分布间的“最优传输”直线路径）且概念简单【101:6†source】。然而，直接使用直线路径可能导致忽视过程中期的重要细节。BFL 研究人员通过偏向“感知相关尺度”的训练采样（即调整训练中噪声等级或时间步采样）加以解决【101:6†source】,【101:7†source】。在其“扩展修正流变换器”研究中，他们发现使用对数正态分布采样时间（噪声等级）效果最佳【101:5†source】,【101:7†source】，这加强了模型对信号与噪声平衡且难以建模的中间时刻的聚焦，从而改善了生动色彩和细节生成（避免由于不合理噪声调度导致的色彩暗淡输出）【101:7†source】。

流匹配的优势：通过流匹配训练带来更强的稳定性与效率。实际上，有观察显示流匹配扩散路径训练提供了“更稳健和稳定的扩散模型训练替代方案”。FLUX.1 博客指出“利用流匹配这一简单却强大的生成模型训练方法，FLUX.1 超越了先前的最先进扩散模型”。一个主要优点是流匹配模型通常能用更少的推理步长达到相同采样质量。因模型学的是一个 ODE（连续流），可以利用更大积分步长或先进 ODE 求解器，比传统需要数十甚至数百个小去噪步的扩散过程生成图像更快。原始流匹配研究展示“使用现成 ODE 求解器进行快速可靠采样”，并实现优于等效扩散训练模型的似然和质量【101:7†source】。在实际中，FLUX.1 训练可能结合了流匹配与无分类器引导（模型为文本条件），即为条件与无条件分支均学习了直线生成流。这种方法使模型极其准确，可以通过解学到的 ODE 在极少步长下生成高保真图像。流匹配框架奠定了 FLUX.1 高效优质图像生成能力基础，增强其“顶级输出质量”和相较传统扩散模型的性能优势。

#### 快速采样的引导蒸馏

除了核心架构与训练范式外，FLUX.1 采用引导蒸馏提升生成效率。无分类器引导是一种常用扩散模型技术，在推理时通过启发式方法提升对文本提示的忠实度（实质上是推动模型向条件输出靠拢）。但通常这要求每步多次模型调用（分别预测条件和无条件输出，并进行加权组合）且步骤数较多，导致高质量扩散慢。引导蒸馏通过将引导效果内置于模型本身解决此问题。经过蒸馏过程，一个模型即可单次推断模拟引导过程。该技术由包括 FLUX 创始人在内的研究者提出，即先取得预训练引导扩散模型，再用以训练新模型模拟其输出。第二阶段通过进行渐进蒸馏（反复倍增步长）减少去噪步骤数。最终模型可用极少步长（例如 2到4 步）达到高保真图像生成，依据最初研究结果。

FLUX.1 利用引导蒸馏打造更加高效的变体。旗舰 FLUX.1 [pro] 模型被蒸馏为 FLUX.1 [dev]，该开源权重模型采样更快。开发者指出 FLUX.1 [dev] “采用引导蒸馏训练”，提升效率同时“保持与[pro]模型类似质量和提示遵从度”。换言之，[dev] 已学会在内部近似高强度无分类器引导效果，无需额外计算。此外，FLUX.1 [schnell]（德语表示“快”）是更快速模型——一种几步扩散器，针对快速生成优化，是激进蒸馏的产物，略微牺牲输出保真度但大幅减少采样步骤。它被认为是同类中最先进的少步长扩散模型之一，超越其他蒸馏模型。凭借引导蒸馏，用户能用 FLUX.1 远比传统扩散模型更快生成图像；[schnell] 模型仅需约4步即可获得良好结果，而典型引导扩散需20至50步，[dev] 则介于两者之间质量较高。这使得 FLUX.1 更适合交互式使用和高吞吐场景，体现了其不仅改进图像质量，也优化生成流程以提升用户体验。

#### 其他架构创新与模块

除上述主要组件外，FLUX.1 还包含若干额外创新和模块，进一步提升生成能力：

- 多模态融合块（MM-DiT）：FLUX.1 中 MM-DiT 块的设计——具有双流和联合注意——本身就是重要创新。通过允许文本和图像特征并行处理后融合，这些模块确保模型在每一层都紧密结合提示与图像。这带来更强一致性（例如图像不同部分或不同图像中的角色或风格保持一致）和精准跨模态对齐。以往文本到图像模型多采用单向交叉注意（仅文本 → 图像）；相比之下，FLUX 的双流融合提供双向交流，帮助模型“更好理解和实现复杂文本提示”。例如，若提示要求图像中出现文字（如标牌或标签），图像标记可影响文本标记表征以确保拼写和排版正确——这是早期模型难以做到的，而 FLUX 表现明显更佳【101:6†source】。
- 并行注意力实现：“并行注意力层”一词也暗示特定的实现技巧。部分资料指出，FLUX 的注意力机制为融合式——将所有标记（图像+文本）在一个大型注意力操作中同时处理，而非分开自注意和交叉注意步骤。这可视为组合注意矩阵（有时称为“全注意”），同时计算模态内与跨模态交互。此举不仅提升对齐度，也更有效利用现代硬件，避免串行计算两次注意力。FLUX 开发团队称此举显著提升“硬件效率”，是其规模达百亿参数并能处理长序列且保持较低延迟的部分原因。
- 训练数据与标题增强：虽非架构“模块”，但值得一提的是 FLUX.1 在数据层面的创新。团队利用合成标题丰富训练描述，采用先进视觉-语言模型 CogVLM 为图像生成详尽标题，并与人工编写标题混合。这可能提升模型处理详尽与具体提示的能力。此外，他们进行了数据集过滤（剔除低质或不当内容，去重）以聚焦高质量图文对，增强最终模型的生成质量和提示可靠性。
- 图像编辑的增强模块：在扩展的 FLUX 生态中，Black Forest Labs 推出了 Flux.1 工具集（如 Flux.1 Fill、Depth、Canny、Redux），基于基础模型【101:2†source】。这些工具使用额外编码器或控制信号（如深度图、边缘图）指导生成完成特定任务（修补、深度到图像等）。例如，Flux.1 Depth 从输入图像提取深度图，辅以额外深度估计模块约束生成变换器。这些工具体现了 FLUX 设计的模块化——核心120亿参数变换器可扩展多种条件编码器进行特化控制，类似 ControlNet 向 Stable Diffusion 添加条件分支。这些附加组件超越基本 FLUX.1 架构，展现了模型的拓展性。

#### 总结

FLUX.1 的架构和训练流程融合了众多前沿组件：强大的双文本编码器配置、高保真图像 VAE、庞大的双流扩散变换器与跨模态注意力融合，采用流匹配 ODE 训练技巧并辅以蒸馏优化。这些部分——从视觉与文本编码器到修正流扩散变换器及各类优化模块——协同作用，使 FLUX.1 成为“突破性”的文本到图像模型，达成最先进的图像质量、提示遵从和生成效率。各部分相辅相成：编码器理解输入，变换器创新融合模态产出结果，训练方法确保输出高质且生成迅速。结果是，FLUX.1 在图像合成领域树立了新的标杆，验证了其精心设计的组件和创新训练策略在生成式人工智能中的有效性。

## 组件之间的配合

### **FLUX.1 组件使用场景和组合列表**

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

------

#### **总结：FLUX.1 的模块化让其在场景适配和性能优化上表现优异**

FLUX.1 的组件并非每次都被全部调用，模块间的松耦合让系统能够按需灵活组合。这种设计既支持高性能生成需求，也能在低资源环境下实现快速推理。

### 与其他模型对比

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