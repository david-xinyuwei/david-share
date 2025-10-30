## NVFP4 解析与工程实践

### **摘要与要点**

- NVFP4 是 NVIDIA 为 Blackwell Tensor Core 定制优化的 4-bit 浮点量化数据类型，采用 **E2M1 元素格式**（1 符号位 + 2 指数位 + 1 尾数位，共 4 bit）与**双层缩放**机制：每 16 个权重共用一个 FP8 精度的局部缩放因子（**微块级**，即"分组粒度"为 16），整个张量再配一个 FP32 高精度全局缩放因子（张量级），以此平衡存储压缩与数值稳定性。实测结果显示：在激活与权重均采用 NVFP4 时，吞吐可比 INT4 提升约 2.35 倍（RTX 6000 Pro, vLLM 0.10.0, Llama-3.3-70B-Instruct）。
- 与主流 4-bit INT4（AWQ、AutoRound、bitsandbytes）相比，NVFP4 在大模型（>10B参数）上精度差异并不明显。**关键优势在于 Blackwell GPU 的硬件加速**：权重+激活全用 NVFP4 时，Tensor Core 可"automatically handle the microscaled FP4 data"(NVIDIA官方说法)，直接处理microscaling格式数据，减少了INT4方案中的数据类型转换开销。若只做权重量化（NVFP4A16），激活仍为FP16，硬件优势大幅削弱，吞吐只略高于 INT4。
- **重要限制**：NVFP4 的**性能优势主要在 Blackwell 架构（GB200/GB300/RTX 6000 Pro等）上体现**。在老GPU（Hopper/Ampere/Ada）上，NVFP4 模型可以运行，但需要实时反量化到 FP16 才能计算（类似 INT4 的处理方式）。由于缺少针对 NVFP4 的优化内核，性能可能不如成熟的 INT4 实现（如 AWQ/AutoRound）。作者明确表示："I can't see any good reasons for using NVFP4 with older GPUs."（意思是老GPU上用NVFP4没有性能优势，不是说不能用）
- MXFP4（OCP Microscaling 标准）采用 E2M1 元素、E8M0 幂次缩放、**微块大小 32**（即每 32 个权重共享一个缩放因子），无全局 FP32 缩放；计算以移位为主，元数据开销更小，更偏跨平台与部署简单性。OpenAI 的开源模型（如 gpt-oss-20b/120b）采用 MXFP4 做 PTQ，并在少量模块上保留高精度（modules_to_not_convert）。
- **选型建议**：
  - ✅ **有 Blackwell GPU**：优先 NVFP4（权重+激活），可获得 2.35 倍吞吐提升
  - ⚠️ **老GPU（H100/A100/RTX 40/30系列）**：NVFP4 模型可以运行，但**性能优势不明显**，推荐使用成熟的 INT4（AWQ/AutoRound）或 MXFP4。如果只是为了节省显存（4-bit存储），NVFP4 仍然有效，但速度不会比 INT4 快
  - ⚠️ **小模型（<10B）**：精度和性能差异尚缺实测数据，建议实际评估后决策

### **一、背景：为什么需要 NVFP4？**

 随着 LLM 参数规模不断爬升，哪怕是纯推理也越来越受限于显存带宽和内存容量。4-bit 量化是当下最具性价比的路径之一，但传统 INT4 路线会遇到两个现实瓶颈：

- 反量化开销难以彻底消除：即便工程优化已很激进（如 vLLM、SGLang、TensorRT-LLM 的 kernel fusion、流水并行等），权重往往仍需在算子入口还原到 16-bit（或更高），才能利用通用的张量核心执行主计算。
- 动态范围与保真度的博弈：INT4 常以较大的组（如 128）共享缩放因子，能减少元数据，但遇到强烈异质分布或离群值时，小值更容易丢失或被压扁，需要更精巧的分组策略和校准。

NVFP4 的提出，核心在于"在 4-bit 存储与计算的同时，尽可能减少反量化和精度损失"，并通过硬件原生支持，将这一设计转化为实际可测量的吞吐性能提升。



### **二、NVFP4 的核心设计**

1. 元素与数值范围

- 元素格式：FP4 E2M1（1 符号位、2 指数位、1 尾数位）
- 单值范围：约 -6 到 +6（数量级级别的有限覆盖） 仅有 4-bit 显然不足以直接覆盖 LLM 内部张量的真实分布，于是 NVFP4 引入“两层缩放”。

1. 双层缩放（Dual Scaling）

- 微块缩放（block-level）
  - 粒度：16 个元素为一块（block size = 16）
  - 缩放因子类型：FP8 E4M3
  - 关键点：E4M3 允许非 2 的幂的“小数缩放”，即尺度可细粒度地贴近张量的真实局部幅值，不容易被离群值一棍子打死。
- 全局缩放（tensor-level）
  - 每个张量配一个高精度 FP32 缩放，用于吸收长尾范围与跨层差异，让每个微块的 FP8 缩放在更合适的区间内工作。

重构公式可写为： x ≈ xq × s_block(FP8 E4M3) × s_tensor(FP32)

理解要点

- 微块从 32（MXFP4）缩小到 16（NVFP4），意味着更细粒度地适应局部分布，弱化离群值对整个小分组的“拖拽”。
- FP8 E4M3 比单纯幂次缩放更灵活，能够降低量化误差的系统性偏差。
- 全局 FP32 缩放相当于再加一层安全气囊，保证模型在跨层、跨张量尺度不一致时依然能稳定工作。



### **三、NVFP4 与 Blackwell 架构创新**

根据 NVIDIA 官方白皮书，Blackwell 架构的相关技术创新包括：

**第二代 Transformer Engine** (官方明确信息):
- 支持 FP4 精度（**包括社区定义的 microscaling 格式**）
- 采用 **micro-tensor scaling**（微张量缩放）技术来优化性能和精度
- 相比传统方法可使性能翻倍

**关键认知: micro-tensor scaling (microscaling) 是硬件+格式标准！**

**硬件层面 (NVIDIA官方明确说法)**:
> "Blackwell introduces **native Tensor Core support** for NVFP4"
> 
> 意思: Blackwell的Tensor Core**硬件原生支持**NVFP4格式的计算

**格式层面 (OCP标准)**:
- **Microscaling** = OCP定义的数据格式标准
- 核心思想: 每小块(micro-block)共享一个scale,而非整个张量共享

**简单说就是**:
1. **Microscaling格式** = 软件层面的数据组织方式 (怎么存数据)
2. **Tensor Core原生支持** = 硬件层面直接识别并加速 (怎么算数据)
3. Blackwell = 硬件能直接"看懂"并加速microscaling格式

**具体实现对比**:

| 标准 | 元素格式 | 微块大小 | Scale格式 | 全局Scale | 硬件支持 |
|------|----------|----------|-----------|-----------|----------|
| **NVFP4** | E2M1 (4-bit) | 16个元素 | FP8 E4M3 | FP32 | Blackwell Tensor Core原生支持 ✓ |
| **MXFP4** | E2M1 (4-bit) | 32个元素 | E8M0 (幂次) | 无 | 软件实现,需模拟 |

**micro-tensor scaling 解决了什么问题？(大白话版)**

传统量化的痛点：
```
你有一堆数字: [0.001, 0.003, 100.5, 200.8]
→ 用一个scale压缩: 除以100 → [0.00001, 0.00003, 1.005, 2.008]
→ 问题: 小数字(0.001)被"抹平"了，精度全丢了！
```

**microscaling的做法**: 每小块用自己的scale

```
分组缩放:
第1组: [0.001, 0.003] → scale=0.01  → 压缩后 [0.1, 0.3]  ✓ 保留精度
第2组: [100.5, 200.8] → scale=100   → 压缩后 [1.0, 2.0]  ✓ 保留精度
```

**为什么叫"fine-grain scaling"(细粒度缩放)?**
- 粗粒度: 整个1000万参数共享1个scale → 精度差
- **细粒度(micro)**: 每16-32个参数有1个scale → 精度高
- 代价: 需要存储更多scale值 (但scale用FP8/E8M0存,开销很小)

**NVIDIA Blackwell 的硬件优势**:
1. "optimize performance" → 硬件原生支持 FP4×FP8 的 microscaling 计算
2. "and accuracy" → 双层缩放(微块FP8 + 全局FP32)保证数值稳定
3. "doubles the performance" → 官方说相比传统方法快2倍

**我们实测看到的**: NVFP4 (microscaling实现) 比传统 INT4 快 2.35 倍

**NVIDIA 官方关于 Blackwell 硬件支持的说法**:

> "NVIDIA Blackwell fifth-generation Tensor Core architecture implements NVFP4 and can **automatically handle** the microscaled FP4 data including the grouping of elements, dynamic scaling, and 4-bit matrix operations."
> 
> 来源: [Introducing NVFP4 for Efficient and Accurate Low-Precision Inference](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)

**关键词解读**:
- **"implements NVFP4"** → Tensor Core 硬件内置了 NVFP4 支持
- **"automatically handle"** → 自动处理 microscaling 数据（包括分组、动态缩放）
- **"4-bit matrix operations"** → 直接执行 4-bit 矩阵运算

**官方未明确说明的内容**:
- 是否完全"免反量化"（zero-dequantization）
- 具体的硬件数据流路径设计
- FP4×FP8 缩放的电路级实现细节

**从实测数据观察到的现象**:

NVFP4 在 Blackwell 上相比 INT4 有约 2.35 倍吞吐提升。可能的原因包括:
- **硬件原生支持**: Tensor Core 可以"automatically handle the microscaled FP4 data"(官方说法),直接处理microscaling格式
- **带宽优势**: 4-bit 数据传输量与 INT4 相当,减少了INT4方案中的数据类型转换开销
- **自动缩放处理**: 硬件自动处理微块缩放,不需要额外的软件操作
- **双层缩放机制**: FP8 微块 scale + FP32 全局 scale 保证数值稳定性

**关于不同量化方案的对比** (基于公开信息的观察):

| 方案 | 数据格式 | 观察到的特点 |
|------|----------|------------|
| INT4 | 整数 + scale | 成熟工具链,需反量化步骤 |
| H100 FP8 | FP8浮点 | Hopper原生支持,但scale操作可能需要精度提升 |
| NVFP4 | FP4浮点 + FP8 scale + FP32 scale | Blackwell优化,实测吞吐高 |

**重要说明**: 
上述对比基于公开的性能数据和架构特性描述。具体的硬件实现细节(如是否有专用融合单元、数据流路径设计等)未在NVIDIA官方文档中详细说明，需等待更多技术披露。



### **四、NVFP4 的实验结论与工程意义**

1. 精度

- 与 FP8 对比：多个基准上差异 ≤ 1%，个别基准（如 AIME 2024）NVFP4 看似更好，但属于统计波动范围内，结论应理解为"NVFP4≈FP8"。
- 与 INT4（AWQ、AutoRound、bitsandbytes）对比：大模型（如 Llama 3.3）上，NVFP4 和优秀的 INT4 方法总体接近。有时 INT4 微幅更优，有时相当。更小模型（<10B）可能更能显露差异，这值得后续跟进。
- NVFP4A16 与 NVFP4：即便 NVFP4 还量化激活，精度与 NVFP4A16（只量化权重）依然相近。这与双层缩放设计有关。

1. 存储与吞吐

- 平均存储开销:约 4.5 bits/值(因为 block=16、每块 1 个 FP8 缩放 + 每张量 1 个 FP32 缩放),比典型 INT4(大多用 block=128)更高,Llama 3.3 的 NVFP4 模型比 INT4 大约多 7GB。
- 吞吐优势:关键结论是 Blackwell 上 NVFP4 的硬件原生支持。权重与激活都为 NVFP4 时,Tensor Core 可以"automatically handle the microscaled FP4 data"(NVIDIA官方说法),直接处理microscaling格式数据。实测吞吐相对 INT4 提升约 2.35 倍。
- NVFP4A16 的代价:当仅权重量化、激活仍为 16-bit,运算中会发生数据类型转换或退化,NVFP4A16 的吞吐大多只比 INT4 略快,无法充分发挥 NVFP4 的"权重+激活全4-bit"优势。



#### 第一张图 —— 推理吞吐量对比（RTX 6000 Pro, vLLM v0.10.0）

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/NVFP4/images/1.png)

**图表含义：**

- 深绿色条（Speed Input）：输入侧 token 生成速率（tokens/sec）
- 浅蓝色条（Speed Output）：输出侧 token 生成速率（tokens/sec）
- 模型名左侧不同条目代表不同量化策略或来源的模型

**关键性能数据解读：**

1. **NVFP4 / Custom NVFP4**（绿色箭头第二梯队）
  - NVIDIA 发布的官方 NVFP4 模型：Input 1692，Output 3342 tokens/s [注1]
  - 社区复现（本仓库示例自量化）NVFP4：Input 1693，Output 3358，结果与官方几乎一致（用于说明工具链可稳定复现官方性能）
   - 结论：无论官方还是自量化，只要是 **权重+激活全 NVFP4** 并在 Blackwell 上推理，吞吐比 INT4 系列 **提升约 2.3 倍**（AWQ/INT4 Output ≈ 1431-1437 tokens/s）。
2. **NVFP4A16**（仅权重量化，激活保持 16-bit）
   - Input ≈ 774，Output ≈ 1534
   - 性能只略高于普通 INT4，验证了之前的结论：**吞吐优势主要来自激活也用 NVFP4，Tensor Core 可直接处理 microscaling 数据**（而非转换到 FP16）。
3. **INT4 系列（AWQ/OPEA GPTQ）**
   - Input ≈ 720-723，Output ≈ 1431-1437
   - 性能相近，说明这几种 INT4 优化在 vLLM 上的成熟度都很高，但因需要反量化，速度不及 NVFP4。
4. **BNB 4bit（bitsandbytes）**
   - 明显更慢：Input 585，Output 1150
   - 推测为 kernel 与框架优化强度弱于 AWQ。
5. **INT2**
   - 因为位宽更低，理论上更节省显存，但吞吐未显著提高（甚至更低：Input 659，Output 1222），可能因为计算核未优化。

**总结**：
在 Blackwell 上，NVFP4（权重+激活）吞吐性能碾压其他方案（包括 INT4 变种），**速度翻倍以上**；NVFP4A16 失去大部分优势，接近 INT4；BNB4bit 和 INT2 进一步落后。

------

[注1] 基准来源与测量方法：本文实验在 RTX 6000 Pro (Ada) 上进行（CUDA 12.4，NVIDIA Driver 555.xx，Python 3.10，PyTorch 2.3，vLLM 0.10.0，禁用 FlashInfer）。测试配置：单请求；输入上下文长度 1 token；生成 512 new tokens；预热 1 次；tokens/s = 生成 token 数 ÷ 纯生成耗时。该数字仅代表该特定配置下的点测结果，非跨 batch/并发的峰值吞吐。完整脚本与日志示例见 `benchmarks.md`。

#### 第二张图 —— 精度 + 模型体积对比

![images](https://github.com/david-xinyuwei/david-share/blob/master/Deep-Learning/NVFP4/images/2.png)

**图表含义：**

- 蓝色条（Score）：统一基准得分（涵盖指令跟随、常识知识、多语言三类能力）
- 绿色数字（Size GB）：模型在磁盘的大小
- 该图关注"量化精度保真度"与"存储占用"。

**关键精度与体积数据：**

1. **精度分布**
   - NVFP4 / Custom NVFP4：Score ≈ 43.8，属于全场最高，与全精度极为接近
   - NVFP4A16：Score ≈ 39.9，比全 NVFP4 略低
   - AWQ / OPEA INT4：Score ≈ 36.8-37.1，精度比 NVFP4 略低
   - BNB 4bit：Score ≈ 39.8，与 NVFP4A16 接近
   - INT2：Score 仅 24.4，精度下降明显
2. **模型体积**
   - AWQ/INT4 ≈ 5900MB（约 5.9GB）
   - NVFP4/NVFP4A16 ≈ 5854~5878MB
   - BNB4bit ≈ 5814MB
   - INT2 ≈ 5488MB
   - **注意**：这里的“MB”疑似是笔误，应理解为 “MB 单位 * 千”，实为 5.x GB ~ 7GB 级别（根据之前文本背景，NVFP4 模型比 INT4 模型大约多 7GB）。
3. **结合背景推断**
   - 体积差异主要源自：
     - NVFP4 block size 小（16 vs 128）→ 缩放因子数量更多
     - 全 NVFP4 需要存储 FP8 缩放因子 + FP32 全局缩放
     - INT4 系列缩放元数据更少，因而更省空间
   - 精度上，NVFP4 系列强于 INT4，尤其全 NVFP4 比 NVFP4A16 更接近全精度。

------

## 综合性能与精度分析

- **性能维度**（第一图）：
  在 Blackwell 上，全 NVFP4 模型吞吐性能显著超过其它 4-bit 方案（~2.3x INT4），优势源于 **激活也量化为 NVFP4，Tensor Core 硬件原生支持 microscaling 计算**。
- **精度维度**（第二图）：
  全 NVFP4 在精度上几乎等于 FP8，比 INT4 / MXFP4 常规实现略好，但模型文件更大。
- **工程取舍**：
  - 有 Blackwell → 全 NVFP4 = 最优速度 + 高精度
  - 追求体积最小 → INT4 / MXFP4 更省存储，但速度取决于内核优化
  - 旧 GPU → 用 NVFP4 权重可省显存，但速度无显著优势

### **五、MXFP4 是什么？与 NVFP4 的关键差异**

MXFP4 是 OCP（Open Compute Project）提出的 Microscaling FP4 标准，核心特征是：

- 元素类型：同为 FP4 E2M1
- 微块大小：32（每 32 个值共享一套缩放元数据）
- 缩放因子：E8M0，仅指数位，等效“2 的幂次缩放”，实现为高效移位
- 无全局 FP32 缩放，全靠微块级别的幂次缩放 设计出发点
- 幂次缩放计算极简（移位），实现路径短、对硬件和 kernel 的优化空间大
- 微块更大，缩放元数据更少，存储更省
- 小值保留相对较好，对离群值鲁棒性强（浮点指数的天然优势）

与 NVFP4 的对比要点

- NVFP4 的缩放更灵活（E4M3 + FP32），微块更小（16），更偏精度与吞吐的平衡；MXFP4 更偏通用性与工程简洁（幂次缩放、移位）。
- NVFP4 的速度优势依赖 Blackwell 原生内核直通；MXFP4 的性能取决于厂商是否提供了针对 MXFP4 的 4-bit 内核（如 vLLM/Ollama 的专用路径）。
- 在元数据与模型体积上，MXFP4 往往更省（微块 32 + 幂次缩放），而 NVFP4 在大模型上可能更“重”，但换来的是 Blackwell 上的极致吞吐。

```
| 特性               | NVFP4（NVIDIA Blackwell 定制）                          | MXFP4（OCP Microscaling 标准）                  |
|--------------------|--------------------------------------------------------|-----------------------------------------------|
| 元素格式           | FP4 E2M1（1符号位+2指数位+1尾数位）                     | FP4 E2M1（1符号位+2指数位+1尾数位）             |
| 微块大小           | 16                                                    | 32                                            |
| 微块缩放因子格式   | FP8 E4M3（支持非2的幂，小数缩放）                      | E8M0（仅指数，2的幂缩放，移位友好）             |
| 全局缩放因子       | 有，全局FP32缩放（Per-tensor）                         | 无，仅微块缩放                                |
| 重构公式           | x ≈ xq × s_block(FP8 E4M3) × s_tensor(FP32)           | x ≈ xq × 2^k（k来自E8M0）                     |
| 动态范围与鲁棒性   | 双层缩放+小微块，适应异质分布与异常值                  | 幂次缩放，小值保持好，对异常值有抵抗力          |
| 计算代价           | FP8缩放需乘法（Blackwell原生加速）                     | 幂次缩放移位操作，极简高效                     |
| 硬件执行路径       | Blackwell Tensor Core 硬件原生支持 microscaling       | 依厂商内核支持，未必有原生直通                |
| 硬件加速效果       | Blackwell上激活+权重全NVFP4时硬件直接处理；NVFP4A16需转换 | 若无原生支持需转换到高精度                     |
| 吞吐表现（对INT4） | ~2.3×（Blackwell+全NVFP4）                            | 视实现情况，资料未提供                         |
| 精度表现           | 与FP8基本持平，误差≤1%                                | 高于传统INT4，小值保留好；与NVFP4对比数据缺失   |
| 平均存储开销       | 约4.5 bits/值                                         | 通常更省（微块32，幂次缩放元数据更少）          |
| 模型体积           | 比常见INT4模型大（如Llama3.3 +7GB）                   | 小于NVFP4（依实现）                           |
| 校准需求           | 全量化需少量校准样本；NVFP4A16不需要                   | 权重量化可少/无校准；激活量化通常需要           |
| 工具与生态         | llm-compressor可量化，vLLM支持（Blackwell）           | OCP标准，llm-compressor暂不支持               |
```



### 六、工程工作流与落地实践

#### 0. llm-compressor 来历与定位（为什么选它做 NVFP4 量化）

llm-compressor 并非单独的 “NVIDIA 官方仓库”，它的来源与定位如下：

- 开源归属：托管在 `vllm-project/llm-compressor` GitHub 组织下，核心目标是为 **vLLM 推理框架** 提供统一的“模型压缩 + 直接可推理”产物（权重量化、激活量化、稀疏化、结构变换）。
- 贡献者生态：维护者与贡献者来自 vLLM 社区、Neural Magic（开源了 `compressed-tensors` 与早期 SparseML 量化/稀疏化经验）、Red Hat AI 等。Citation 中标注 “Red Hat AI and vLLM Project”。
- 设计继承：大量 `Modifier` / `oneshot` API 风格延续了 SparseML 的工程抽象（如 QuantizationModifier、GPTQModifier、AWQ 等），但面向推理端与 vLLM 原生消费。
- 文件格式：使用 `compressed-tensors`（safetensors 扩展）记录低比特块结构、缩放元数据与量化 scheme（包括 NVFP4、FP8、INT4 等），使生成的 checkpoint 可以被 vLLM 直接加载并触发对应 kernel 路径。
- NVFP4 支持方式：通过在 `quant_scheme.py` 中定义 FP4/NVFP4 配置（block size、缩放形式等）+ vLLM 的后端 kernel；不是 NVIDIA 专属仓库，但实现了对 **NVIDIA Blackwell** 新增 NVFP4 数据格式的开源支持。
- 官方/社区关系：NVIDIA 在 Blackwell 生态中推广 NVFP4 数据类型；llm-compressor 在开源侧率先给出可复现实例（示例脚本链接、W4A4 & W4A16 方案），因此在“开源实践层面”可视为 NVFP4 的推荐工具链之一。
- 适配优势：
  1. 统一多种量化算法（Simple PTQ / GPTQ / AWQ / SmoothQuant / Mixed Precision）。
  2. 直接产出可被 vLLM 加载的目录，无需额外转换脚本。
  3. 支持非均匀/分层混合量化（不同子模块使用不同位宽或算法）。
  4. 结合 Sequential Onloading 等机制，适合大模型（几十到上百 B）分段量化。
- 当前局限：
  1. NVFP4 的高性能路径主要依赖 vLLM，其他推理框架暂未完善直通内核。 
  2. 微调/QLoRA 在 NVFP4 上暂不成熟，需反量化或选用 INT4/MXFP4 路径。
  3. 激活-only NVFP4 模式尚未提供；全链路收益依赖"权重+激活"同为 NVFP4。

简要判断：若你的目标是 **在Blackwell上获得NVFP4的性能提升** 或 **统一管理多种量化策略并快速迭代实验**，llm-compressor 是当前开源社区最直接、组合灵活、与 vLLM 深度整合的选择；若希望跨多框架、关注极限体积与通用性，则可同时评估 MXFP4 + INT4（AWQ/GPTQ）与后续可能出现的其它低比特内核。

#### 1. 量化流程

- 量化工具:llm-compressor 已支持 NVFP4 / NVFP4A16。它是 vLLM 项目维护的通用 LLM 压缩库,整合多种低比特与稀疏算法；通过 `compressed-tensors` 方案产出可被 vLLM 快速加载的模型目录。NVFP4 配置来源于开源实现并针对 Blackwell 硬件路径做对接,目标是在几乎不牺牲精度的前提下提升吞吐与降低权重/激活存储。
- 校准集规模：128～512 条通常足够（本文档示例使用 512）；理论上 1024 以上收益递减
- 序列长度建议：不要低于 2048,若目标是长上下文推理,建议更长,但量化代价会显著增加,需要在质量与成本间权衡
- 数据预处理要点：与模型训练时的输入格式一致（chat template）、避免重复注入 bos token
- 量化方案选择：
  - NVFP4：权重+激活均量化，牺牲极少精度换吞吐极大提升
  - NVFP4A16：仅权重量化，激活保 16-bit，通常无需校准集，但大部分吞吐优势不再

#### 2. 推理框架

- vLLM v0.10.0 基本可用
- 开发者遇到的两个实际坑：
  - FlashInfer：默认启用会在 NVFP4 下导致崩溃，临时做法是卸载。待后续修复后可能进一步加速。
  - Blackwell 环境下通过 pip 安装 vLLM 可能不完整，可以以源码编译方式解决，成功启用 NVFP4 推理路径。
- 一句话建议：Blackwell 上跑 NVFP4，先准备源码编译 vLLM 的预案，并关注 FlashInfer 版本兼容性。

### **3.旧架构 GPU 的兼容性思考**

- 3090（Ampere）或更老架构没有 NVFP4 的硬件原生支持
- 可以加载 NVFP4 量化权重以省显存，但推理时多半需要反量化到更高精度执行（例如 FP16 Tensor Core），速度优势会被抵消
- 结论：NVFP4 的性能提升需要 Blackwell 硬件支持；在老GPU上主要价值是节省显存（4-bit存储），而非提升推理速度

### **4、NVFP4 与 INT4（AWQ/AutoRound/bitsandbytes）的取舍**

- 精度：在大模型（如 Llama 3.3）上都很接近全精度；NVFP4 不显著优于最强的 INT4，但也没有明显劣势
- 模型体积：NVFP4 通常略大（微块 16 + FP8 + FP32），INT4（微块多为 128 + FP16/FP32 缩放）更省存储
- 吞吐：Blackwell 上 NVFP4 明显更快；而 INT4 再怎么优化，仍存在反量化或数据类型转换的路径阻抗
- 易用性：INT4 已有成熟生态（AWQ、AutoRound、bitsandbytes、GPTQ 等），NVFP4 则在 Blackwell 上原生更顺滑

工程建议

- 有 Blackwell 并追求极致 TPS/TTFT：优先 NVFP4（权重+激活）
- 无 Blackwell、但想压显存又不愿重写内核：成熟 INT4 更稳妥
- 跨平台与简洁部署：MXFP4（若已有专用 kernel 或框架直通）是务实选择

#### 附录：INT4 分组量化与 scale 选择速览

INT4 常见“分组量化”做法：每 N 个权重共享一个缩放因子 scale，先将浮点除以 scale 并四舍五入到 0..15（或有符号范围），再在计算前乘回（反量化）。

最简单示例（无符号 0..15）：

```
权重组: [3.14159, 2.71828, 1.41421, 0.57722]
max(|w|) = 3.14159
scale = 3.14159 / 15 ≈ 0.209439 → 0.2094
量化整数 q = round(w/scale): [15,13,7,3]
反量化 q*scale ≈ [3.141,2.722,1.466,0.628]
```

关键现象：最大值贴得很准，小/中值相对误差变大，因为所有权重共享一个 scale，被“拉伸”。

常见 scale 策略对比（精简版）：

| 策略 | 公式/思想 | 优点 | 缺点 | 适用场景 |
|------|-----------|------|------|-----------|
| Max-based | max(|w|)/(S) | 简单、不溢出 | 受离群值影响 | 大模型快速 PTQ |
| Percentile | P99(|w|)/S | 主体误差低 | 极端值饱和 | 长尾/有少量 outlier |
| Per-channel | 每通道单独 max/S | 精度最高 | 元数据多 | 小模型/敏感任务 |
| L2 最优 | min Σ(w - q*scale)^2 | 全局重构误差最小 | 求解成本高 | 离线高质量量化 |
| Learned Rounding (AutoRound) | 学习向上/向下舍入 | 保护重要权重 | 算法复杂 | 代码/数学任务 |
| Activation-aware (AWQ) | 依据激活统计加权通道 | 提升关键通道保真 | 需统计激活 | 小模型 & 多语言 |

离群值影响速览：若 127 个值在 [-0.8,0.8]，仅 1 个值=5.0：
- Max-based: scale≈5.0/15≈0.333 → 主体精度变粗
- Percentile(P99≈0.8): scale≈0.8/15≈0.0533 → 主体精度好，5.0 被截断到≈0.8（产生饱和误差）

简易误差近似（均匀分布）：步长 Δ = a/S，期望绝对误差 E[|ε|]≈Δ/2。减小 a（裁剪/忽略离群值）或增大 S（更多刻度/更细粒度）都可降低误差。

快速决策：
- 追求“够用+速度”：Max 或 Percentile 分组（128）
- 追求“小模型高保真”：Per-channel + AWQ/AutoRound
- 离线极致压缩：L2 优化 + Learned rounding 组合
- 有明显长尾：Percentile + 激活感知

这部分是对量化误差与 scale 选择的工程速览，方便在不同模型与任务下快速取舍。

### 5、MXFP4 的两种加载/计算模式

- 存储压缩模式（dequantize=True，Hugging Face 默认 LoRA 精调路径常见）
  - 加载到 GPU 时解为 BF16/FP16 全精度张量
  - 显存消耗高（接近 BF16），计算走高精度 matmul
  - 适合做 LoRA/全参微调（需要全精度梯度），或显存充足的离线推理
- 驻留计算模式（dequantize=False，Ollama / vLLM-gptoss 专用内核）
  - 保持 MXFP4 低比特权重常驻 GPU
  - 显存占用低（约 BF16 的 1/4），计算走低比特核/自定义 CUDA 核
  - 适合低显存场景的高效部署、边缘推理或 Hopper 系列配合优化内核

对工程的启示

- 以 MXFP4 格式发布的模型是否“真 4-bit 推理”，取决于你使用的框架与 dequantize 开关；不正确的加载路径会让你失去 4-bit 的显存与吞吐优势。
- OAI-OSS 的 mxfp4 PTQ 方案体现了“部分模块不转”的工程取舍：把最敏感/最关键路径保留为高精度，其余用 4-bit 浮点，兼顾压缩率与稳定性。

### 6、校准与数据集选择的实践建议

**基础建议**：
- 样本量：128～512 条通常已足够，想追求极致保真可到 1024，但收益递减
- 序列长度：建议 ≥2048；若业务目标是长上下文推理（32k/128k），校准时尽量覆盖更长序列，但计算开销会显著增加
- 分布匹配：尽可能让校准样本贴近真实线上分布（指令型、代码、数学、对话、多轮等）
- 模型输入一致性：保持与训练时的完整前处理管线（模板、分词、特殊符号），避免额外 bos token 导致分布飘移

**长序列校准进阶策略**（基于实践经验）：

当目标是长上下文推理（如处理 16k+ tokens 的文档）时，可采用**混合采样策略**：

```python
# 策略1: 仅用长序列（如 open-r1/OpenR1-Math-220k 中 >16k tokens 的样本）
TOKEN_THRESHOLD = 16000
ds = ds.filter(lambda ex: ex["n_tokens"] >= TOKEN_THRESHOLD)
ds = ds.shuffle(seed=42).select(range(512))

# 策略2: 混合长短序列（推荐）
# - 512个短序列（<16k）：覆盖常见分布
# - 512个长序列（>16k）：强化长上下文校准
short_samples = ds.filter(lambda ex: ex["n_tokens"] < 16000).shuffle(seed=42).select(range(512))
long_samples = ds.filter(lambda ex: ex["n_tokens"] >= 16000).shuffle(seed=43).select(range(512))
ds = concatenate_datasets([short_samples, long_samples])
```

**注意事项**：
- 长序列校准的**计算成本显著增加**（16k vs 2k 差异约 8 倍）
- 不建议所有样本都用 32k，会导致量化时间过长
- 如果发现长上下文性能仍不理想，可提高 `TOKEN_THRESHOLD` 或增加长序列样本占比
- 参考 notebook: `Quantize_LLMs_to_NVFP4_with_LLM_Compressor_Calibration_with_Long_Sequences.ipynb`

### 7、微调与增量训练：NVFP4 + QLoRA 的可行性

- 理论上：NVFP4 是数据类型与格式，QLoRA 可作用于任何底座
- 现实中：目前常见框架对"NVFP4 上的 QLoRA"尚未提供现成支持；实现难度不大，但工具链需要打通
- 建议：若你需要立刻做 LoRA/QLoRA，短期仍可选择 INT4 或 MXFP4 的成熟路径；若你瞄准 Blackwell 的极致吞吐，等待框架对 NVFP4 的训练/微调支持是合理的策略

### 8、选型决策树

- 你的线上推理是否部署在 Blackwell？
  - 是：优先 NVFP4（权重+激活）。若对精度有顾虑，先试 NVFP4；再降级 NVFP4A16 评估损失与吞吐反差。
  - 否：是否已有 MXFP4 的直通内核或使用 OAI-OSS 专用路径？有则优先 MXFP4；否则稳妥用 INT4（AWQ/AutoRound）。
- 你的显存是否极为吃紧但对速度要求一般？
  - 是：MXFP4 或 INT4（权重常驻、激活高精度）更好控成本；NVFP4A16 也可作为替代（主要省显存）。
- 你的任务是否长上下文或对小值保留敏感（如检索注意力、稀疏门控）？
  - 是：优先选择具备更细缩放与双层缩放的方案（NVFP4），或在 MXFP4 下保留关键模块为高精度。

### 9、常见问题

- vLLM + FlashInfer：NVFP4 下可能崩溃，临时卸载或禁用；关注版本修复进展
- Blackwell 上的 vLLM 安装：pip 版本可能不完整，优先源码编译
- NVFP4A16 的预期管理：吞吐不等于 NVFP4，只比 INT4 略快，不能套用 NVFP4 的速度宣传
- 校准样本偏差：样本过短或分布不匹配会导致长上下文或特定能力上的劣化
- 模块忽略策略：若忽略列表未覆盖真正敏感模块，易出现局部崩坏；反之忽略过多，会降低压缩比与吞吐
- 旧 GPU 跑 NVFP4：明白“能装下 ≠ 更快”，不要对速度抱过高期待

## 五、Code

```
pip install llmcompressor datasets transformers
```

**权重与激活同时量化：**

```
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

from datasets import load_dataset
NUM_CALIBRATION_SAMPLES=512
MAX_SEQUENCE_LENGTH=2048
# Load dataset.
ds = load_dataset("HuggingFaceH4/ultrachat_200k", split=f"train_sft[:{NUM_CALIBRATION_SAMPLES}]")
ds = ds.shuffle(seed=42)

# Preprocess the data into the format the model is trained with.
def preprocess(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False,)}
ds = ds.map(preprocess)

# Tokenize the data (be careful with bos tokens - we need add_special_tokens=False since the chat_template already added it).
def tokenize(sample):
    return tokenizer(sample["text"], padding=False, max_length=MAX_SEQUENCE_LENGTH, truncation=True, add_special_tokens=False)
ds = ds.map(tokenize, remove_columns=ds.column_names)

# Configure the quantization algorithm to run.
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4", ignore=["lm_head"])

# Apply quantization.
oneshot(
    model=model,
    dataset=ds,
    recipe=recipe,
    max_seq_length=MAX_SEQUENCE_LENGTH,
    num_calibration_samples=NUM_CALIBRATION_SAMPLES,
)

# Save to disk compressed.
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

**只量化权重**

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

# Load model.
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

# Configure the quantization algorithm and scheme.
# In this case, we:
#   * quantize the weights to fp4 with per group 16 via ptq
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4A16", ignore=["lm_head"])

# Apply quantization.
oneshot(model=model, recipe=recipe)


# Save to disk in compressed-tensors format.
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4A16"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

量化LM Head

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

# Load model.
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

# Configure the quantization algorithm and scheme.
# In this case, we:
#   * quantize the weights to fp4 with per group 16 via ptq
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4A16")

# Apply quantization.
oneshot(model=model, recipe=recipe)


# Save to disk in compressed-tensors format.
SAVE_DIR = MODEL_ID.rstrip("/").split("/")[-1] + "-NVFP4A16LMH"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
```

### 5.1 改进示例：混合长/短序列 NVFP4 校准（推荐实践）

下面的示例在原“快速上手”基础上，加入：
1. 序列长度统计与分桶：同时覆盖长上下文与常规指令分布，降低只用短样本导致长序列退化的风险。
2. 混合采样策略：优先抽取指定数量的长序列（例如 ≥16k tokens），再补足短序列至总校准数。
3. Fallback 逻辑：如果数据集中长序列不足，会自动降低长阈值或用更短样本填充，不中断流程。
4. 轻量评估：量化前后对一小批样本计算代理 loss 和生成吞吐，帮助快速验证质量与性能。
5. 估算显存：给出简易公式帮助评估 NVFP4 与 NVFP4A16 的显存占用差异。

适用场景：追求更稳定的长上下文能力（聊天、检索、多轮工具调用、代码补全）而又不希望校准成本指数增长。

```python
import math, time, torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"  # 可换成你的模型
NUM_CALIBRATION_SAMPLES = 1024          # 总校准样本目标
LONG_TARGET = 512                       # 期望长序列样本数
LONG_TOKEN_THRESHOLD = 16000            # 长序列判定阈值（可调 12k~24k）
SHORT_MIN_LENGTH = 2048                 # 最短保留长度
MAX_SEQUENCE_LENGTH = 32000             # 统一截断上限（兼顾显存）
SEED = 42

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto")

ds = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft[:5000]")
ds = ds.shuffle(seed=SEED)

# 1. 应用原聊天模板，保持与训练格式一致
def apply_template(example):
  return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}
ds = ds.map(apply_template)

# 2. 粗分词统计 token 长度（不加特殊符号重复）
def length_only(example):
  ids = tokenizer(example["text"], add_special_tokens=False)["input_ids"]
  return {"token_length": len(ids)}
ds = ds.map(length_only)

# 3. 分桶筛选长/短样本
long_ds = ds.filter(lambda x: x["token_length"] >= LONG_TOKEN_THRESHOLD)
short_ds = ds.filter(lambda x: SHORT_MIN_LENGTH <= x["token_length"] < LONG_TOKEN_THRESHOLD)

actual_long = min(LONG_TARGET, len(long_ds))
needed_short = NUM_CALIBRATION_SAMPLES - actual_long

# Fallback：若长序列不足，打印提示；若短也不足，回退到任意样本补足
if actual_long < LONG_TARGET:
  print(f"[Fallback] 仅获得 {actual_long} 条长序列 (<{LONG_TARGET}). 将用更多短序列补足。")
if len(short_ds) < needed_short:
  print(f"[Fallback] 短序列不足 {needed_short}，当前 {len(short_ds)}。使用其它样本填充。")
  remaining = needed_short - len(short_ds)
  # 用未被选择的样本补齐（这里简单用 ds 中未选到的）
  extra_pool = ds.filter(lambda x: x["token_length"] < SHORT_MIN_LENGTH)
  extra_take = min(remaining, len(extra_pool))
  short_ds = short_ds.select(range(len(short_ds)))
  extra_ds = extra_pool.select(range(extra_take))
  from datasets import concatenate_datasets
  short_ds = concatenate_datasets([short_ds, extra_ds])

calib_long = long_ds.select(range(actual_long))
calib_short = short_ds.select(range(min(needed_short, len(short_ds))))

from datasets import concatenate_datasets
calib_ds = concatenate_datasets([calib_long, calib_short]).shuffle(seed=SEED)
print("校准集组成：长", len(calib_long), "短", len(calib_short), "总", len(calib_ds))

# 4. 真正分词 + 截断（避免重复添加 bos）
def tokenize(example):
  return tokenizer(example["text"], add_special_tokens=False, truncation=True, max_length=MAX_SEQUENCE_LENGTH)
token_cols = [c for c in calib_ds.column_names if c not in ("text", "token_length")]
calib_ds = calib_ds.map(tokenize, remove_columns=token_cols)

# 5. 配置 NVFP4（权重+激活），忽略 lm_head 以降低精度风险
recipe = QuantizationModifier(targets="Linear", scheme="NVFP4", ignore=["lm_head"])

oneshot(
  model=model,
  dataset=calib_ds,
  recipe=recipe,
  max_seq_length=MAX_SEQUENCE_LENGTH,
  num_calibration_samples=len(calib_ds),
)

# 6. 轻量评估：生成吞吐 + loss 代理
def quick_loss(batch_size=4):
  subset = calib_ds.select(range(batch_size))
  total, count = 0.0, 0
  for sample in subset:
    ids = torch.tensor([sample["input_ids"]], device=model.device)
    out = model(input_ids=ids, labels=ids)
    total += out.loss.item()
    count += 1
  return total / max(count, 1)

def gen_speed(prompt="Hello", steps=64, warmup=1):
  for _ in range(warmup):
    _ = model.generate(tokenizer(prompt, return_tensors="pt").input_ids.to(model.device), max_new_tokens=8)
  start = time.time()
  _ = model.generate(tokenizer(prompt, return_tensors="pt").input_ids.to(model.device), max_new_tokens=steps)
  t = time.time() - start
  return steps / t

loss_proxy = quick_loss()
tokens_per_sec = gen_speed()
print(f"[Eval] Proxy Loss: {loss_proxy:.3f} | Gen Speed: {tokens_per_sec:.1f} tok/s")

# 8. 保存压缩权重（可与 vLLM 直接兼容）
SAVE_DIR = MODEL_ID.split("/")[-1] + "-NVFP4-mixed-calib"
model.save_pretrained(SAVE_DIR, save_compressed=True)
tokenizer.save_pretrained(SAVE_DIR)
print("Saved ->", SAVE_DIR)

# 9. 显存估算提示（近似）：
# NVFP4 平均 ~4.5 bits/param；NVFP4A16 ~4 bits/param（仅权重）；
# FP16 ~16 bits/param。可用 param_count * bits/8/1024**3 估算 GB。
param_count = sum(p.numel() for p in model.parameters())
nvfp4_gb = param_count * 4.5 / 8 / 1024**3
fp16_gb = param_count * 16 / 8 / 1024**3
print(f"Param Count: {param_count/1e9:.2f}B | NVFP4≈{nvfp4_gb:.2f}GB | FP16≈{fp16_gb:.2f}GB (权重部分近似)")
```

> 使用建议：若后续发现长上下文性能仍偏低，可提高 `LONG_TOKEN_THRESHOLD` 或增加总校准样本数；若显存紧张，先尝试 NVFP4A16 再评估吞吐与质量差异。

#### FAQ 追加（与工具链相关）

**Q: llm-compressor 量化后是否只能用 vLLM 推理？**  
A: 不是。全 NVFP4 的性能提升需要**Blackwell GPU + vLLM（或其他支持 NVFP4 的框架）**；其它框架可能会反量化后加载，失去硬件加速优势。NVFP4A16（仅权重）更容易跨框架使用，但也失去了大部分性能优势。

**Q: llm-compressor 是 NVFP4 官方推荐的量化工具吗？**  
A: 仓库 README 提供 NVFP4 / NVFP4A16 示例与配置（W4A4/W4A16），属于当前开源生态中对 NVFP4 最直接的正式支持路径，可视为“官方支持实现”。

**Q: 能否只量化激活不量化权重 (Activation-only NVFP4)?**  
A: 当前工具链未提供该模式；NVFP4 的核心优势来自权重+激活共同低比特以触发硬件直通，否则性能收益极低。

**Q: 如果我需要 LoRA/QLoRA 微调怎么办？**  
A: 目前建议反量化回 FP16/BF16 或使用 INT4/MXFP4 的成熟训练路径；NVFP4 上的增量训练支持尚在生态完善中。




## 七、结论

如果你有 Blackwell GPU，NVFP4 是值得优先尝试的 4-bit 量化方案：在几乎不牺牲精度的前提下，通过硬件原生支持获得远超 INT4 的推理吞吐。这一优势的关键在于"权重+激活全 NVFP4"，以及 dual-scaling（微块 FP8 + 全局 FP32）带来的稳健数值特性。

若你的环境跨平台或暂不具备 Blackwell，MXFP4 是成熟而务实的工程解法，尤其在 OAI-OSS 的实践中已给出可复用的 PTQ 配置范式（保留关键模块不转，其余用 4-bit 浮点）。在未来一段时间里，预计 NVFP4 的生态将持续完善（含微调路径与采样内核修复），MXFP4 的标准化与多厂商优化也会加速，这两条路线很可能将长期并存：一条在"硬件特化吞吐极致"，一条在"生态通用与部署简洁"。

---

## 八、参考资料与出处

### NVIDIA 官方资源
- **Blackwell 架构白皮书**: [NVIDIA Blackwell Platform Overview](https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/)
- **NVFP4 开发者博客**: [NVIDIA Developer Blog - FP4 Quantization](https://developer.nvidia.com/blog/)

### 开源工具与实现
- **llm-compressor**: [vllm-project/llm-compressor](https://github.com/vllm-project/llm-compressor) - NVFP4/NVFP4A16 量化工具
- **vLLM 推理框架**: [vllm-project/vllm](https://github.com/vllm-project/vllm) - 支持 NVFP4 硬件直通
- **compressed-tensors**: [neuralmagic/compressed-tensors](https://github.com/neuralmagic/compressed-tensors) - NVFP4 权重存储格式

### 行业标准与规范
- **OCP MXFP4 标准**: [Open Compute Project - Microscaling Formats](https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf)
- **OpenAI gpt-oss 实现**: [openai/gpt-oss](https://github.com/openai/gpt-oss) - MXFP4 PTQ 参考实现

### INT4 量化方法对比
- **AWQ**: [mit-han-lab/llm-awq](https://github.com/mit-han-lab/llm-awq) - 激活感知权重量化
- **AutoRound**: [intel/auto-round](https://github.com/intel/auto-round) - 学习型舍入优化
- **GPTQ**: [IST-DASLab/gptq](https://github.com/IST-DASLab/gptq) - 经典 INT4 量化
- **bitsandbytes**: [TimDettmers/bitsandbytes](https://github.com/TimDettmers/bitsandbytes) - 4-bit 量化库

### 评测基准
- **实验环境**: RTX 6000 Pro (Ada), CUDA 12.4, vLLM 0.10.0, Llama-3.3-70B-Instruct
- **复现方法**: 详见 `benchmarks.md` 完整脚本与配置
- **测试协议**: 单请求、输入1 token、生成512 tokens、预热1次、禁用FlashInfer



