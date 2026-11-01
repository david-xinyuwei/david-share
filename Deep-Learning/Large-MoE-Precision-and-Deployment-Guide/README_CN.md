# 大型 MoE 模型组件精度与部署指南

[![Models](https://img.shields.io/badge/models-3-0078D4)](#部署配置参考)
[![Precisions](https://img.shields.io/badge/precision-BF16%20%7C%20FP8%20%7C%20NVFP4-76B900)](#逐模型组件精度)
[![Scope](https://img.shields.io/badge/evidence-documents%20%2B%20configuration-555555)](#证据边界)
[![Checked](https://img.shields.io/badge/checked-2026--11--01-0078D4)](#证据边界)

作者：魏新宇（Xinyu Wei） · [English](README.md)

## 目的

本项目提供 Muse Spark Open 816B-A42B、NVIDIA Nemotron 3 Ultra 550B-A55B 和 Inkling 975B 的组件精度参考，覆盖原厂 BF16、原厂 NVFP4 及指定伙伴 FP8 版本。用于核对权重、激活、矩阵乘法、累加与输出、KV Cache 和其他状态缓存，并选择与硬件及推理引擎相匹配的部署路径。

交付内容包括逐模型组件表、固定权重版本与配置证据、H100/H200 兼容执行和 Blackwell 原生执行路径、资源复算工具及验证步骤。**精度结论以对应配置或实现为依据；本项目尚未执行模型推理，生产验收需使用目标环境和业务输入。** 价格与云区域供应不在本项目范围内。

### 精度定义与配置范围

以 Nemotron 3 Ultra 的原厂 NVFP4 版本为例：导出规则将路由专家设为 NVFP4，却把共享专家和 Mamba 投影设为 FP8，并排除了 router/gate；官方 vLLM 示例又单独指定 FP8 KV cache 和 FP16 Mamba 状态 [N2][N3]。因此，“这个模型是 4 位”不能回答组件精度，更不能直接决定 GPU 数量。

| 精度类别 | 检查对象与判断边界 |
|---|---|
| 权重存储 | 检查数值编码、分组 scale、zero point 和混合精度例外。NVFP4 文件不表示所有张量都是 4 bit。 |
| 激活 | 检查各算子的输入、输出量化规则。权重 FP8 不表示所有中间值都是 FP8。 |
| 矩阵乘法 | 检查两个乘数进入实际内核时的类型。权重存 INT4 不表示 GPU 执行原生 INT4 乘法。 |
| 累加与输出 | 检查累加器、归约和返回张量的类型。FP4 乘数不表示全部累加在 FP4 中完成。 |
| 缓存与状态 | 分别检查 K、V、Mamba 和短卷积设置。缓存精度不自动跟随权重精度。 |

BF16 与 FP16 都占 16 bit，但指数与尾数分配不同，不是同一个数据类型。本文三个原厂基线都是 BF16，不另造“官方 FP16 版”。`W4A16` 和 `W8A8` 只说明权重与激活位宽，不能代替 INT4、FP8 E4M3、NVFP4 等具体编码及内核说明。

AWQ、GPTQ、GSQ 是求取低精度权重的方法；GGUF 是文件格式，`Q4_K_M` 等是量化编码或混合精度预设。这些名称不能与 NVFP4 硬件路径直接排成一条优劣顺序。NVFP4 使用 E2M1 数值、每 16 个数的 FP8 块缩放以及 FP32 全局缩放；即使数值字段是 4 bit，包含块 scale 后也不是每个数只占 4 bit [H1]。

<img src="images/nvfp4-two-level-scaling.gif" width="853" alt="NVIDIA 原图：NVFP4 的 E2M1 数值、每 16 个数一个 FP8 块缩放和 FP32 全局缩放">

来源：NVIDIA，《Introducing NVFP4 for Efficient and Accurate Low-Precision Inference》，Figure 2 [H1]，原始 GIF，未改图。看点是数值位宽与两级缩放分开保存；该图不证明某个模型所有模块都用 NVFP4，也不是本项目性能结果。

### 模型范围

| 模型 | 总参数<br>十亿 | 激活参数<br>十亿/token |
|---|---:|---:|
| Muse Spark Open | 816 | 42 |
| Nemotron 3 Ultra | 550 | 55 |
| Inkling | 975 | 41 |

- **Muse Spark Open：**多模态 MoE Transformer 和感知编码器；语言骨干 62 层、256 个专家、每 token 选择 8 个。Meta 发布 BF16/NVFP4 权重，访问需按 Muse Model License 申请 [M1][M2]。
- **Nemotron 3 Ultra：**Mamba-2、Attention、LatentMoE 混合架构及 MTP。NVIDIA 发布 BF16/NVFP4 权重，许可为 OpenMDW-1.1 [N1][N2]。
- **Inkling：**66 层局部/全局 Attention 与短卷积；256 个路由专家、2 个共享专家，每 token 选择 6 个路由专家。Thinking Machines Lab 发布 BF16/NVFP4 权重，许可为 Apache-2.0 [I1][I2]。

`B` 表示十亿参数，`A42B` 等表示每 token 激活参数，不是需要常驻的完整权重。MoE 通常仍需装载全部专家，或明确采用会增加传输和调度开销的卸载策略。不能按 42B、55B、41B 计算完整模型的权重显存。参数标签也不一定包括全部多模态组件、MTP 和导出额外张量，应以所选 revision 的实际文件和张量清单复核。

模型卡可读不等于已获得权重下载权限。Muse 的模型许可证还有分发标识与特定服务业务的额外条件，需按自己的交付方式审查；本文不代替许可证审查。

## 实现效果

### 逐模型组件精度

三个模型各保留完整的 25 个组件和状态项。列表示具体发布版本，行区分权重、激活、计算与缓存，避免把存储位宽写成计算位宽。

**术语：**“保留基线”表示保持原始张量类型，可能包含 BF16 和 FP32；“排除量化”是导出配置的明确规则，不自动等于 BF16；“按运行配置”指由启动参数及后端决定；“不适用”只用于模型不存在的组件。表后的配置说明列出权限限制、来源冲突和需要读取的参数，不以缺省值填充证据空缺。

九个发布版本的 revision 与配置摘要保存在 [model-evidence.json](data/model-evidence.json)。下表中的 FP8 分别指 AMD Quark 和 Red Hat AI 的指定版本 [M8][N8][I8]，不代表所有同名 FP8 文件。

#### Muse Spark Open

发布版本：Meta BF16、NVFP4；AMD Quark FP8 [M1][M2][M8]。

| 组件 | 精度：<br>BF16 | 精度：<br>FP8 | 精度：<br>NVFP4 |
|---|---|---|---|
| 权重：词嵌入 | BF16 [M1] | 保留基线 [M8] | 保留基线 [M3] |
| 权重：注意力投影 | BF16 [M1] | FP8 [M8] | 保留基线 [M3] |
| 权重：路由器 | 存储另见注释 [M4] | BF16 声明 [M8] | 存储另见注释 [M4] |
| 权重：路由专家 | BF16 [M1] | FP8 [M8] | NVFP4 [M3] |
| 权重：共享专家 | 不适用 [M4] | 不适用 [M4] | 不适用 [M4] |
| 权重：专家前后投影 | 保留基线 [M4] | 排除量化 [M8] | 保留基线 [M4] |
| 权重：Mamba 投影 | 不适用 | 不适用 | 不适用 |
| 权重：Mamba 状态参数 | 不适用 | 不适用 | 不适用 |
| 权重：短卷积 | 不适用 | 不适用 | 不适用 |
| 权重：归一化与偏置 | 保留基线 [M1] | 保留基线 [M8] | 保留基线 [M3] |
| 权重：视觉与音频 | 保留基线 [M1] | BF16 声明 [M8] | 保留基线 [M3] |
| 权重：预测辅助模型 | 独立权重 [M3] | 独立权重 | 独立权重 [M3] |
| 权重：输出层 | BF16 [M1] | 排除量化 [M8] | 保留基线 [M3] |
| 激活：注意力投影输入 | 16 bit | 动态 FP8 [M8] | 保留基线 [M3] |
| 激活：专家输入 | 16 bit | 动态 FP8 [M8] | 依内核选 FP4 / 16 bit [V1] |
| 激活：路由与残差 | FP32 [M4] | 按实现 [M8] | FP32 [M4] |
| 运算：Black&shy;well 专家 | BF16 | 发布路径为 AMD [M8] | 原生 FP4 [V1] |
| 运算：Hopper 专家 | BF16 | CUDA 支持另验 [M8] | H200 兼容路径 [M3] |
| 运算：累加与输出 | 按内核 | 非由 FP8 决定 | 高于 FP4 [H1] |
| K 缓存 | 按运行配置 | 按运行配置 | 按运行配置 |
| V 缓存 | 按运行配置 | 按运行配置 | 按运行配置 |
| 缓存缩放与注意力 | 按后端 | 按后端 | 按后端 |
| Mamba 状态缓存 | 不适用 | 不适用 | 不适用 |
| 短卷积状态缓存 | 不适用 | 不适用 | 不适用 |
| 推理验收 | 尚未执行 | 尚未执行 | 尚未执行 |

**配置说明。** Meta 公开说明只量化专家 [M3]；vLLM recipe 明确路由计算及残差使用 FP32，但没有单独给出 router 权重的存储 dtype [M4]，不能将两者混写。原厂 NVFP4 配置的匿名读取返回 401，需要授权后读取对应 revision；此访问限制不影响引用已公开的模型卡。AMD 模型卡声明路由、编码器及输出层保留 BF16，专家和注意力权重使用静态逐通道 FP8 E4M3、输入使用动态逐 token FP8 [M8]；其 Deployment 段仍为 `Todo`，不作为 CUDA 部署证明。

Muse 没有共享专家 [M4]。辅助预测使用独立的 draft checkpoint，其精度和内存须按该 checkpoint 另行记录。K/V dtype、scale 和注意力计算由运行参数及后端确定；QKV 投影使用 FP8，并不意味着 Attention 点积也使用 FP8。

#### NVIDIA Nemotron 3 Ultra

发布版本：NVIDIA BF16、NVFP4；Red Hat AI FP8 [N1][N2][N8]。

| 组件 | 精度：<br>BF16 | 精度：<br>FP8 | 精度：<br>NVFP4 |
|---|---|---|---|
| 权重：词嵌入 | BF16 [N1] | 排除量化 [N8] | 排除量化 [N3] |
| 权重：注意力投影 | BF16 [N1] | FP8 目标层 [N8] | 不在低精度规则中 [N3] |
| 权重：路由器 | 保留基线 [N1] | 排除量化 [N8] | 排除量化 [N3] |
| 权重：路由专家 | BF16 [N1] | FP8 [N8] | NVFP4 [N3] |
| 权重：共享专家 | BF16 [N1] | FP8 目标层 [N8] | FP8 [N3] |
| 权重：潜空间投影 | 保留基线 [N1] | 按目标与排除规则 [N8] | 排除量化 [N3] |
| 权重：Mamba 投影 | BF16 [N1] | FP8 目标层 [N8] | FP8 [N3] |
| 权重：Mamba 状态参数 | BF16 / FP32 [N1] | 卷积等排除 [N8] | 卷积等排除 [N3] |
| 权重：Inkling 短卷积 | 不适用 | 不适用 | 不适用 |
| 权重：归一化与偏置 | 保留基线 [N1] | 排除量化 [N8] | 保留基线 [N3] |
| 权重：视觉与音频 | 不适用 [N1] | 不适用 | 不适用 |
| 权重：MTP | 共享关系另核 [N1] | 配方未单列 [N8] | 配方未单列 [N2] |
| 权重：输出层 | BF16 [N1] | 排除量化 [N8] | 不在低精度规则中 [N3] |
| 激活：注意力投影输入 | 16 bit | 动态 FP8 [N8] | 按对应算子 [N3] |
| 激活：专家输入 | 16 bit | 动态 FP8 [N8] | 依内核选 FP4 / 16 bit [V1] |
| 激活：路由与残差 | 按实现 | 排除专家量化 [N8] | 排除专家量化 [N3] |
| 运算：Black&shy;well 专家 | BF16 | 支持内核时 FP8 | 原生 FP4 [V1] |
| 运算：Hopper 专家 | BF16 [N1] | 支持内核时 FP8 | W4A16 兼容 [N2][V1] |
| 运算：累加与输出 | 按内核 | 非由 FP8 决定 | 高于 FP4 [H1] |
| K 缓存 | 按示例配置 [N1] | 启动时另设 [N8] | 示例为 FP8 [N2] |
| V 缓存 | 按示例配置 [N1] | 启动时另设 [N8] | 示例为 FP8 [N2] |
| 缓存缩放与注意力 | 按后端 | 按后端 | 按后端 [V2] |
| Mamba 状态缓存 | 示例 FP16 [N1] | 示例 FP16 [N8] | 示例 FP16 [N2] |
| 短卷积状态缓存 | 不适用 | 不适用 | 不适用 |
| 推理验收 | 尚未执行 | 尚未执行 | 配置已解析，推理未执行 |

**配置说明。** N3 是直接读取的发布配置，router/gate、latent projection 等出现在排除列表中；排除规则不等于已逐张量确认 BF16。BF16 发布元数据含 F32 张量，归一化、偏置和状态参数须保留原始 dtype。Red Hat FP8 使用 `Linear` 目标和明确的 ignore 列表；只有匹配目标且未被排除的模块才采用该 FP8 配方 [N8]。

原厂 NVFP4 专家分组大小为 16。N3 共包含 49,344 条模块量化规则：49,152 条 NVFP4 路由专家规则、96 条 FP8 共享专家规则，以及 Mamba 输入、输出投影各 48 条 FP8 规则。这是配置条目数，不是参数量或性能测量。官方示例的 Mamba 状态采用 FP16 加随机舍入；FP8 KV cache 与 Mamba 状态是两套独立设置 [N2]。MTP 的共享关系和未单列模块应通过完整模型配置及张量清单确认。

#### Inkling

发布版本：Thinking Machines Lab BF16、NVFP4；Red Hat AI FP8 [I1][I2][I8]。

| 组件 | 精度：<br>BF16 | 精度：<br>FP8 | 精度：<br>NVFP4 |
|---|---|---|---|
| 权重：词嵌入 | BF16 [I1] | 保留基线 [I8] | BF16 [I3] |
| 权重：注意力投影 | BF16 [I1] | 配置排除 [I9] | BF16 [I3] |
| 权重：路由器 | BF16 [I3] | 保留基线 [I8] | BF16 [I3] |
| 权重：路由专家 | BF16 [I1] | FP8<br>含排除层 [I8] | NVFP4<br>含排除层 [I4] |
| 权重：共享专家 | BF16 [I3] | 保留基线 [I8] | BF16 [I3][I4] |
| 权重：潜空间投影 | 不套用 Nemo&shy;tron [I1] | 不套用 Nemo&shy;tron [I8] | 不套用 Nemo&shy;tron [I3] |
| 权重：Mamba 投影 | 不适用 | 不适用 | 不适用 |
| 权重：Mamba 状态参数 | 不适用 | 不适用 | 不适用 |
| 权重：短卷积 | BF16 [I3] | 保留基线 [I8] | BF16 [I3] |
| 权重：归一化与偏置 | 保留基线 [I1] | 保留基线 [I8] | BF16 为主 [I3] |
| 权重：视觉与音频 | 保留基线 [I1] | 保留基线 [I8] | 编码器排除 [I4] |
| 权重：MTP | BF16 [I3] | 配方未单列 [I8] | BF16 [I3] |
| 权重：输出层 | BF16 [I1] | 保留基线 [I8] | BF16 [I3] |
| 激活：注意力投影输入 | 16 bit | 配置排除 [I9] | BF16 [I3] |
| 激活：专家输入 | 16 bit | 动态 FP8 [I8] | 依内核选 FP4 / 16 bit [I3][V1] |
| 激活：路由与残差 | 按实现 | 保留基线 [I8] | 保留基线 [I3] |
| 运算：Black&shy;well 专家 | BF16 | 支持内核时 FP8 | 原生 FP4，排除层另算 [I3] |
| 运算：Hopper 专家 | BF16 [I3] | 支持内核时 FP8 | H200 解码为 BF16 [I3] |
| 运算：累加与输出 | 按内核 | 非由 FP8 决定 | 高于 FP4 [H1] |
| K 缓存 | 按运行配置 | 按运行配置 [I8] | 导出为 none [I4] |
| V 缓存 | 按运行配置 | 按运行配置 [I8] | 导出为 none [I4] |
| 缓存缩放与注意力 | 区分局部/全局层 [I3] | 按后端 | 按后端 |
| Mamba 状态缓存 | 不适用 | 不适用 | 不适用 |
| 短卷积状态缓存 | 读取运行配置 [I3] | 读取运行配置 | 读取运行配置 [I3] |
| 推理验收 | 尚未执行 | 需固定集成版本，尚未执行 | 配置已解析，推理未执行 |

**配置说明。** Inkling 使用局部与全局 Attention、短卷积及共享专家，不套用 Nemotron 的 Mamba/LatentMoE 精度分配。I4 采用全局 NVFP4 配置加排除列表，其中包括 `model.llm.layers.2.mlp.experts`、共享专家、router 和编码器等。没有逐模块字典不表示没有量化；全局算法也不能覆盖排除项。

Red Hat FP8 模型卡与实际配置对 Attention 的描述有冲突，表中按 I9 的 `.attn` 排除规则处理。输出激活与 KV 配方为空，不表示这些值都是 FP8。NVFP4 导出的 `kv_cache_quant_algo=none` 表示没有在该导出配置中指定缓存量化，运行时仍可另设 K/V dtype。短卷积缓存的 dtype 由其运行实现确定，不归入统一 FP8 或 NVFP4 KV。

表中“原生 FP4”以支持的 Blackwell 内核被实际选中为前提。Hopper 兼容路径、原生路径以及排除层分别处理激活和计算。所有累加、归约与输出精度都受实际内核约束，不由权重名称推断。

Router 负责选择专家，routed experts 负责专家计算。二者是不同组件，低精度专家权重不能被描述为低精度路由器。

### H100 与 H200 的 NVFP4 执行路径

以支持的 W4A16 兼容内核为例，流程是：读取打包的 FP4 权重及 scale，按块在片上解码为 FP16/BF16，和 16 bit 激活做矩阵乘法，再以该内核规定的累加、归约与输出精度返回结果。高效融合内核不需要先把整个模型展开后写回显存；但不是所有加载器都保留同一种内存布局，实际占用必须实测。

$$
\widehat W_g = s_{\mathrm{tensor}}\,s_g\,q_g,\qquad Y\approx X_{16}\widehat W_{16}.
$$

这里 `q_g` 是 E2M1 近似值，`s_g` 是块 scale。解码得到的是已量化的近似权重，**不是原始 BF16 权重恢复原状**。H100 的 FP8 能力也不会自动把这个路径变成 FP8，更不会变成原生 FP4。对 MoE，要单独确认被选中的专家内核，不能拿一个 Linear 层支持 Marlin 就替所有 MoE 算子背书。

```mermaid
flowchart LR
	W["NVFP4 权重与 scale"] --> H["H100/H200 兼容内核"]
	H --> D["片上按块解码为 FP16/BF16"]
	A["16 bit 激活"] --> G["16 bit 浮点矩阵乘法"]
	D --> G
	W --> B["Blackwell 原生 NVFP4 内核"]
	Q["激活量化为 FP4 并生成 scale"] --> B
	B --> F["FP4 操作数矩阵乘法"]
	G --> O["高精度累加与输出"]
	F --> O
	style H fill:#eeeeee,stroke:#555555
	style B fill:#e9f4d5,stroke:#76B900
```

原创解释图：将 NVIDIA 的格式说明、vLLM 的兼容选择规则和模型 recipe 放在同一张路径图中 [H1][V1][I3]。图展示机制与条件，不是执行 trace。Blackwell 分支只有在确实选中原生内核时成立；模型仍可包含 BF16/FP8 的其他模块。

### 部署配置参考

| 模型与版本 | 发布方给出的起点与边界 |
|---|---|
| Muse Spark Open<br>BF16 | Meta 模型卡给出约 2 TB VRAM 量级 [M1]。这不是单卡规格或目标并发保证。 |
| Muse Spark Open<br>NVFP4 | Meta 列四张 Blackwell Ultra 或八张 H200；vLLM recipe 默认八卡 Blackwell [M3][M4]。两份不同部署配方不能合成唯一“最低卡数”。 |
| Nemotron 3 Ultra<br>BF16 | 模型卡摘要列 16 张 H100、8 张 H200 或 8 张 B200 [N1]。这不保证最大上下文加目标并发时的容量。 |
| Nemotron 3 Ultra<br>NVFP4 | 模型卡列四张 B200/GB200 等与八张 H100 [N2]。H100 没有原生 FP4 算力，且引擎支持不同。 |
| Inkling<br>BF16 | 官方发布 BF16；vLLM recipe 的 Hopper 路径需要多节点 [I1][I3]。总显存相加不证明专家布局和通信可行。 |
| Inkling<br>NVFP4 | vLLM recipe 列四张 GB200、八张 H200 路径 [I3]。不能外推成四张任意 Blackwell 或八张任意 Hopper。 |

先以同模型 BF16 建立业务质量基线。NVFP4 和伙伴 FP8 都只是候选；当精度、模态、工具调用或兼容内核未通过验收时，不为减少权重体积而直接替换生产版本。AMD Muse FP8 模型卡的 Deployment 仍写 `Todo`，因此它证明配方与硬件声明，不构成本项目可直接复跑的部署教程 [M8]。

### 权重、计算与缓存配置

| 精度类别 | 必需证据与判断边界 |
|---|---|
| 权重存储 | 检查 checkpoint revision、张量类型、量化配置、缩放与排除列表。文件名中的 NVFP4 不足以证明这些信息。 |
| 矩阵乘法 | 检查 GPU、实际内核、转换步骤与运行日志。能加载权重不表示已确认计算精度。 |
| 缓存精度 | 分别检查 KV cache、Mamba 和短卷积状态设置。不能从权重格式推断缓存精度。 |
| 输出与累加 | 检查内核和算子实现。操作数位宽不决定累加器与输出 dtype。 |

H100/H200 没有 Blackwell 的原生 NVFP4 Tensor Core 计算路径。支持的兼容内核可以在片上把低比特权重转换成 FP16/BF16 后计算，仍可能节省权重存储与读取带宽，但不是原生 FP4 乘法。转换只解码近似值，不恢复量化前丢失的精度。vLLM 明确区分 `NVFP4` 和 `W4A16_NVFP4`，并说明缺少原生 FP4 GEMM 时的 W4A16 回退 [V1]。

Nemotron 的官方 vLLM 示例将 KV cache 设置为 FP8，将 Mamba SSM 状态设置为 FP16，并启用随机舍入 [N2]。因此“缓存都是 FP8 或 FP32”不是该模型的通用结论。Inkling 还有短卷积状态；不能用 Nemotron 的 Mamba 状态公式估算它。

AMD MI350 系列支持 MXFP4，包括 MI350X 和 MI355X；NVFP4 与 MXFP4 的块缩放规则不同，不能当作同一份权重的无条件互换格式 [H2][H3]。Inkling 的 recipe 另列了 `lightseekorg/Inkling-MXFP4` 和 MI355X 原生、MI300X 模拟路径，那是**另一个发布者的 checkpoint 与另一条执行路径**，不是把官方 NVFP4 行直接改名 [I3]。

### 资源估算

先算权重的量级，再加入缓存、工作区、并行复制和余量；不能用一个固定百分比替代实际测量。

我们从六个固定 revision 的公开逐 dtype 张量计数复算得到下面的负载。**这是张量数据字节，不是完整下载大小或峰值显存。** 输入在 [model-evidence.json](data/model-evidence.json)，计算入口为 `node tools/inspect.mjs`；scale 和打包 U8 张量按实际存储类型计数，不把压缩元素数当原始参数量。

| 模型与版本 | 张量负载<br>GB | 张量负载<br>GiB |
|---|---:|---:|
| Muse Spark Open<br>BF16 | 1644.333 | 1531.405 |
| Muse Spark Open<br>NVFP4 | 533.011 | 496.405 |
| Nemotron 3 Ultra<br>BF16 | 1121.049 | 1044.058 |
| Nemotron 3 Ultra<br>NVFP4 | 320.071 | 298.090 |
| Inkling<br>BF16 | 1904.755 | 1773.942 |
| Inkling<br>NVFP4 | 592.005 | 551.348 |

计算只覆盖公开元数据列出的张量，不含文件头、非张量文件、KV/状态缓存、临时工作区或通信缓冲。Nemotron BF16 的 API 总元素字段与逐 dtype 求和有差异，工具保留并报告该差异，不改原数据；更多边界见[验证说明](VALIDATION_CN.md)。

$$
M_{\text{peak}} = M_{\text{weights}} + M_{\text{KV}} + M_{\text{state}} + M_{\text{workspace}} + M_{\text{communication}} + M_{\text{other}}.
$$

下表只用模型卡的标称总参数做**假设性权重计算**，使用十进制 GB，不是下载文件大小、实际显存占用或 GPU 数量建议。NVFP4 一列假设所有参数都采用 4 bit 数值加每 16 个数一个 8 bit 块缩放，即 4.5 bit/参数；真实模型包含更高精度模块、额外缩放及元数据，因此不能直接按这一列配卡 [H2]。

| 模型与总参数 | 格式：BF16<br>理想 GB | 格式：NVFP4<br>理想 GB |
|---|---:|---:|
| Muse Spark Open<br>816B | 1,632 | 459.0 |
| Nemotron 3 Ultra<br>550B | 1,100 | 309.375 |
| Inkling<br>975B | 1,950 | 548.4375 |

计算方法分别为 `参数量 × 2 字节` 与 `参数量 × (4 + 8/16) / 8 字节`。这也解释了为什么不能将 Meta 给出的约 700 GB NVFP4 部署门槛替换为纸面 459 GB：两者口径不同，前者是发布方部署说明，后者只是理想化权重编码计算，不能反推差额全由某个组件造成。

对于标准全 Attention 层，KV cache 的基本估算为：

$$
M_{\text{KV}} \approx 2\,N_{\text{layers}}\,N_{\text{KV heads}}\,D_{\text{head}}\,T_{\text{resident}}\,b_{\text{element}}.
$$

`T_resident` 是所有常驻请求已保留 token 的总数，而非只有一个请求的上下文上限。局部 Attention、缓存复用、张量并行复制、分页、量化 scale 和状态空间模型需要分别处理，不能把标准公式不加修改地套到三个模型。更长的上下文和更多并发都可能让缓存而非权重成为主要约束。

存储至少区分下载与缓存目录、运行使用的权重目录、转换中间文件和日志。不要凭标称参数给出固定磁盘数字；先读取所选 revision 的文件大小并确认是否需要同时保留 BF16 与 NVFP4 两份权重。

### 证据边界

检查日期：2026-11-01。本文采用发布方模型卡、实际配置和推理引擎文档，不用模型榜单或不同环境的历史测试拼成性能对比。三个模型的九个版本均未在本项目执行推理，吞吐、延迟、质量回归、长上下文稳定性和故障恢复均为 **NOT_RUN**。

Nemotron 模型卡同时存在训练配方、权重版本和引擎示例；本文只将明确的导出规则用于模块精度判断。它的模型卡概述中出现“NVFP4 KV caching”，但具体示例使用 FP8 KV cache，本文按可执行参数说明差异，而不将概述视为已验证的缓存能力。

Inkling recipe 同时出现 `vLLM 0.26.0+` 和 nightly 安装提示。前者不是对任意后续 wheel 的保证，后者也不是可复现版本。上线前必须固定实际提交或镜像摘要，并保存成功启动和业务测试记录。

Red Hat Inkling FP8 模型卡概述称 Attention Linear 也量化，但固定 revision 的配置包含 `re:.*\.attn$` 和 `re:.*\.attn\..*` 两条排除规则 [I9]。主表保留这个冲突，按配置不把 `.attn` 子树写成 FP8；实际模块名匹配和加载后 dtype 仍须在运行时验收。两个 Red Hat FP8 配置的 `output_activations` 与 `kv_cache_scheme` 都为空，因此也不能由 FP8 输入规则推断输出和 KV 缓存都是 FP8。

Muse 的详细模块精度、三模型在指定机器上的峰值显存与性能，以及许可证在具体业务模式下的适用性仍需核验。公开模型卡的广泛支持列表不替代某一引擎、精度和模态的完整验收。

## 操作步骤

### 先选可验证路径，再启动服务

| 顺序 | 位置与操作 | 通过条件 |
|---|---|---|
| 1 | **权重仓库与许可证页：**确认模型、精度版本、访问许可和固定 revision。 | 权重可合法取得，版本明确。 |
| 2 | **目标硬件与引擎：**选择同一模型的官方配方，固定 GPU、并行布局和引擎版本。 | 所需模态、缓存和内核都有明确支持。 |
| 3 | **容量规划：**统计权重字节，按目标上下文与并发计算缓存，再预留工作区。 | 每张卡与每个并行分组都有余量，不能只看总和。 |
| 4 | **隔离验证环境：**按官方配方启动，保存实际内核与缓存日志。 | 模型加载、功能调用与数值检查都通过。 |
| 5 | **业务验收环境：**用同一模型 BF16 与量化版本跑相同真实任务。 | 质量、峰值显存、延迟与并发满足预先定义的要求。 |
| 6 | **生产准备：**固定镜像、权重、模板、回退方案和监控。 | 新实例可重复部署；升级与回退有验证记录。 |

部署入口：Muse 使用 Meta 的开发者指南 [M3]；Nemotron 使用相应 BF16/NVFP4 模型卡中的引擎示例 [N1][N2]；Inkling 使用发布方链接的 vLLM recipe [I3]。不要把不同模型的命令拼成一个通用启动脚本，也不要把示例中的上下文长度、并发和并行参数原样当作业务推荐值。

### 不下载权重复算公开元数据

需要 Node.js 20 或更高版本。在本目录的终端执行：

```bash
node tools/inspect.mjs
node --test tests/inspect.test.mjs
```

第一条命令从六个已保存版本的逐 dtype 元素数计算张量负载字节。测试检查版本覆盖、打包字节计算、明确保留的配置缺口和失败处理；两条命令都不调用模型，也不验证 GPU 数量。

要读取当前公开元数据而不是复算快照：

```bash
node tools/inspect.mjs --live
```

该命令调用公开 Hugging Face 模型 API，输出新 revision 并按返回数据重新计算；失败时不会用旧快照伪装成功，不下载权重、不申请权限，也不把旧量化配置的核验结果套到新 revision。结果不包含运行时缓存与工作区。

完整命令、预期语义及未执行项：[验证说明](VALIDATION_CN.md) · [Validation](VALIDATION.md)。数据与范围：[model-evidence.json](data/model-evidence.json)。主表的公开依据见本页来源表。

### 生产验收条件

验收对象是完整组合：**模型 revision + 权重格式 + GPU 型号 + 推理引擎版本 + 计算内核 + 缓存设置 + 并行布局 + 请求负载**。改变其中一项，相关结果就需要重新核验。

必须覆盖实际使用的文本、图像、音频或视频任务、工具调用和结构化输出；用生产代表性输入检查长上下文与目标并发。记录正确率或业务评分、错误类型、峰值显存、首 token 延迟、生成延迟分布及服务吞吐。仅能返回一句话、通过健康检查或模型文件更小，都不等于生产验收通过。

BF16 是对照基线，并不保证答案正确；NVFP4 是候选格式，不是“天然无损”的承诺。若无客户任务、目标上下文和并发条件，最多给出上表这样的条件化建议，不给出假精确的实例数量或 SLA。

### 公开来源

| 编号 | 来源及检查范围 |
|---|---|
| M1 | [Meta Muse Spark Open BF16 模型卡](https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B)：模型身份、参数、访问条件与部署量级 |
| M2 | [Meta Muse Spark Open NVFP4 模型卡](https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B-NVFP4)：公开权重版本、部署量级与限制 |
| M3 | [Meta 开发者部署指南](https://dev.meta.ai/resources/blog/build-with-muse-spark-open)：专家量化范围与四卡 Blackwell Ultra/八卡 H200 声明；命令未执行 |
| M4 | [vLLM Muse recipe](https://recipes.vllm.ai/meta-models/Muse-Spark-Open-816B-A42B)：FP32 路由/残差、无共享专家、八卡 Blackwell 配方；AMD 例子为 text-only |
| M8 | [AMD Muse FP8](https://huggingface.co/amd/Muse-Spark-Open-816B-A42B-Quark-PTPC-FP8)：专家与 Attention 的逐通道权重、逐 token 激活和排除项 |
| N1 | [Nemotron 3 Ultra BF16 模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16)：模型、硬件摘要与各引擎限制 |
| N2 | [Nemotron 3 Ultra NVFP4 模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4)：硬件摘要、vLLM 与缓存示例 |
| N3 | [Nemotron NVFP4 固定版本导出配置][N3]：`quantized_layers` 与 `exclude_modules`；网页过大时通过原始 JSON 读取 |
| N8 | [Red Hat Nemotron FP8-dynamic](https://huggingface.co/RedHatAI/NVIDIA-Nemotron-3-Ultra-550B-A55B-FP8-dynamic)：FP8 配方、ignore 列表和部署例子；不引用其榜单或元数据日期作本项目结果 |
| I1 | [Inkling BF16 模型卡](https://huggingface.co/thinkingmachines/Inkling)：模型、架构、精度与引擎入口 |
| I2 | [Inkling NVFP4 模型卡](https://huggingface.co/thinkingmachines/Inkling-NVFP4)：正式版本与许可 |
| I3 | [vLLM Inkling recipe](https://recipes.vllm.ai/thinkingmachines/Inkling)：混合精度、Blackwell/Hopper 路径、版本提示与缓存结构；发布方模型卡链接此页 |
| I4 | [Inkling 固定 revision 的量化配置](https://huggingface.co/thinkingmachines/Inkling-NVFP4/blob/42a75a99a40eb2ba1e0717db6357a0bf15205044/hf_quant_config.json)：全局 NVFP4、`kv_cache_quant_algo=none`、专家/编码器等排除项 |
| I8 | [Red Hat Inkling FP8-dynamic](https://huggingface.co/RedHatAI/Inkling-FP8-dynamic)：发布者、原模型与集成依赖；其 Attention 概述与配置冲突见 I9 |
| I9 | [Red Hat Inkling FP8 固定配置](https://huggingface.co/RedHatAI/Inkling-FP8-dynamic/blob/cb2bf130a5263e01d7398723ae9b88e0060f4998/config.json)：`ignore` 排除 `.attn`；`output_activations` 与 `kv_cache_scheme` 为空 |
| V1 | [vLLM 稳定版 Model Optimizer 支持](https://docs.vllm.ai/en/stable/features/quantization/modelopt/)：NVFP4、W4A16_NVFP4 与兼容内核选择 |
| V2 | [vLLM KV cache 文档](https://docs.vllm.ai/en/stable/features/quantization/quantized_kvcache/)：缓存存储、scale 与 Attention 计算路径的区别 |
| H1 | [NVIDIA NVFP4 说明](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)：E2M1、16 元素块、FP8 块 scale 与 FP32 tensor scale |
| H2 | [NVIDIA NVFP4 与 MXFP4 格式对照](https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/)：两种块缩放及 NVFP4 的编码开销 |
| H3 | [AMD Instinct MI350 系列](https://www.amd.com/en/products/accelerators/instinct/mi350.html)：MI350X/MI355X 的 MXFP4 支持 |

进一步阅读：[NVFP4](../NVFP4/)、[量化方法对比](../Quantization-Methods-Comparison-and-Practice/)、[大模型显存估算](../LLM-Memory-Estimation/)。这些目录解释通用方法或其他模型的历史结果，不能替代本文三款模型的验收。

[M1]: https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B
[M2]: https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B-NVFP4
[M3]: https://dev.meta.ai/resources/blog/build-with-muse-spark-open
[M4]: https://recipes.vllm.ai/meta-models/Muse-Spark-Open-816B-A42B
[M8]: https://huggingface.co/amd/Muse-Spark-Open-816B-A42B-Quark-PTPC-FP8
[N1]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16
[N2]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4
[N3]: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4/blob/02462641f13d3af838b904f48195b9bb8a1e4ebc/hf_quant_config.json
[N8]: https://huggingface.co/RedHatAI/NVIDIA-Nemotron-3-Ultra-550B-A55B-FP8-dynamic
[I1]: https://huggingface.co/thinkingmachines/Inkling
[I2]: https://huggingface.co/thinkingmachines/Inkling-NVFP4
[I3]: https://recipes.vllm.ai/thinkingmachines/Inkling
[I4]: https://huggingface.co/thinkingmachines/Inkling-NVFP4/blob/42a75a99a40eb2ba1e0717db6357a0bf15205044/hf_quant_config.json
[I8]: https://huggingface.co/RedHatAI/Inkling-FP8-dynamic
[I9]: https://huggingface.co/RedHatAI/Inkling-FP8-dynamic/blob/cb2bf130a5263e01d7398723ae9b88e0060f4998/config.json
[V1]: https://docs.vllm.ai/en/stable/features/quantization/modelopt/
[V2]: https://docs.vllm.ai/en/stable/features/quantization/quantized_kvcache/
[H1]: https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/
[H2]: https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/
[H3]: https://www.amd.com/en/products/accelerators/instinct/mi350.html