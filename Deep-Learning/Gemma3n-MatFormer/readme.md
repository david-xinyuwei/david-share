# 深度解析 Gemma 3n 与 MatFormer「同心圆」架构

Gemma 3n 的MatFormer不确认是否能够普及起来。就是类似「同心圆」技术＝一份权重、多个体型：

- 把每层 FFN 做成同心矩形；只取前 8 k 行就是 2 B 子网，再加外圈变 4 B——随选随剪，无需再训练。
- 推理时 GPU 只算/只存选中的那几行列，算力、显存线性缩；2 B 档 12 GB 卡就能跑。
- 视觉、音频分支可整段跳过，巨型 PLE 放 SSD 流式读，显存再省一半。

一句话：一份 Gemma 3n 权重，从手机到云端都能按需“变身”。

## 1 模型与背景

1. Gemma 3n
   • 发布方：Google DeepMind，2025 年 5 月预览，2025 年 6 月正式开放 safetensors。
   • 多模态：文本 + 图像 + 音频 + 视频，共用一套编码器-解码器。
   • 单一母模型：E4B（35 层，FFN = 16 384，≈ 4 B effective parameters）。
   • 内嵌子模型：E2B（30 层，FFN = 8 192，≈ 2 B effective）。
   • 许可证：Gemma License，可用于商业部署。
2. 设计目标
   • **弹性推理**：同一权重文件在 12 GB-24 GB GPU 范围内动态缩放。
   • **一次训练，覆盖多档**：不再为 2 B / 4 B 训练两套模型。
   • **保持多模态一致性**：外部裁剪不破坏统一语义空间。

------

## 2 MatFormer 理论基础

### Gemma 3n模型参数加载情况说明

- 左图 (Standard execution) 是传统的方式，模型运行时会一次性全部加载5.44 B（54.4亿）参数到显存：
  - 文本参数 (Text)：1.91B
  - 视觉参数 (Vision)：0.3B
  - 音频参数 (Audio)：0.68B
  - 每层嵌入参数 (Per-Layer Embedding，简称PLE)：2.55B
    这种模式的坏处是，不管你是否真的用到视觉和音频功能，总是要占用那么多显存，导致极大浪费。
- 右图 (With skipped parameters & cached PLE) 是Gemma 3n针对MatFormer推出的优化加载方式：
  - 如果实际场景只需要文本功能，不用视觉和音频，这些未被使用的参数就可以完全不加载（跳过这些分支）。
  - 每层的嵌入向量表（PLE参数）计算需求很低，但很占显存，我们可以提前算完并存储在NVMe高速SSD磁盘上，然后推理时需要用哪个token的向量临时读哪个，这样也能避免占用显存。
  - 通过这种巧妙设计，实际加载进内存或显存的参数量就能显著降低到只有文本所需的1.91B，而之前非常占显存的PLE则通过 SSD临时读取（蓝色虚线表示这一操作）。

总结：
**传统模式显存占用：5.44B → 优化后显存占用：1.91B（少了3倍），速度更快，显存更省。**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Gemma3n-MatFormer/images/1.png)

### MatFormer（“同心圆”）如何实现多个模型尺寸

- 左侧方框是单个Transformer层（MatFormer Block）的结构：
  - 主要包含两部分：Attention(注意力层) 和 FFN(前馈网络)。
  - MatFormer并没有改变经典的Self-attention这一层，只对FFN做了特殊的设计优化。
  - 注意看图中FFN的权重矩阵：它分成了“四个同心大小矩形”，用不同颜色表示（红、橙、蓝、黄）。
  - 代表“小尺寸”的红色权重矩阵是最内圈的最小子网，依次向外延伸层橙、蓝、黄色。因此外面的圈就包含了内圈所有权重，形成类似俄式套娃一般的结构。
- 右上半部分 (Training) 的意思是训练过程中：
  - 每一步都会随机抽取一个不同的宽度组合（比如这次随机用了内圈的红色小矩形，下次又用橙色稍大的矩形）。
  - 通过这种动态随机的训练方式，确保较小的子网（如红色）得到充分训练，而较大的外圈模型可作为增量也能学习到足够的知识。
  - 最终训练结束后，我们“一次训练”即可得到多个不同算力的模型。
- 右下半部分 (Inference) 则指的是实际推理与部署阶段：
  - 我们可根据实际的设备（如手表、手机、电脑、服务器）或场景需求（响应速度快速 or 精度要求更高），自由选取一个合适大小的子网。
  - 举例：手表设备可以只加载最内圈的红色子网，服务器可装载最大圈的完整网络，以此实现同一份权重文件动态伸缩、灵活部署需求。

总结：
**训练时随机组合，得到嵌套不同尺寸模型；使用时根据硬件自由选择，快速完成推理部署。**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Gemma3n-MatFormer/images/2.png)



### 2.1 逐层同心切片（Matryoshka）

以第 *ℓ* 层 FFN 为例
输入维度 *d*<sub>model</sub>，外圈隐藏维度 *d*<sub>FFN</sub><sup>(max)</sup> = 16 384
定义一组嵌套宽度
W = { w₁=8 192 ⊂ w₂=16 384 }

训练时对每个 batch 从 W 采样宽度 *w*<sub>ℓ</sub>：
y = W<sub>gate</sub>[:w, :] · x → act → W<sub>up</sub>[:w,:] · x → …

随机过程保证
• 内圈 (8 192) 梯度覆盖率 100 %
• 外圈 (16 384) 梯度覆盖率 < 100 %，承担“增量容量”角色

### 2.2 Mix-n-Match 调度

推理时给定 recipe = ⟨ffn_hidden_dims, skip_layers⟩

1. 删除 skip_layers 中整层权重
2. 对保留层按 vector-view 读取矩阵前 *w* 行或列
3. 重新编号层索引，更新 config

操作是 **0-copy view → 1-copy save**，无需再训练。

### 2.3 额外工程要点

1. Per-Layer Embeddings (PLE) 可预计算并 NVMe 流化：推理时显存持有权重≈1.9 B (E2B)。
2. KV-Cache 共享：后 2 层 (33、34) 共享 Q,K,V 统计，跳层必须避开。
3. 激活稀疏度 (activation_sparsity_pattern)：前 10 层 95 % sparsity，裁剪时同步更新该表。

------

## 3 训练范式

| 阶段             | 操作                                  | 备注                                |
| ---------------- | ------------------------------------- | ----------------------------------- |
| 预训练           | 随机宽度采样 + 随机跳层 = 随机子网    | 单一损失，140 语言 + 多模态混合语料 |
| 指令后训练 (-it) | 固定 E4B 全宽 + RLHF + 安全过滤       | 生成 instruct 型权重                |
| 社区微调         | 推荐在 **E2B 或裁剪后子网** 上挂 LoRA | 避免破坏 Google 对齐策略            |

------

## 4 与其他高效方案对比

| 维度       | MatFormer       | LoRA       | MoE             | 剪枝 / 量化   |
| ---------- | --------------- | ---------- | --------------- | ------------- |
| 省 FLOPs   | ✅ 行列直接缩    | ❌          | ✅               | 剪枝✅ / 量化❌ |
| 参数共享   | 100 % 共享      | 新增 ΔW    | 仅同专家共享    | 0 %           |
| 目标       | 多档算力 / 精度 | 多任务适配 | 增大计算-性能比 | 存储 / 显存   |
| 是否可叠加 | —               | 可叠加     | 可叠加          | 可叠加        |

LoRA 与 MatFormer 所解决的问题、数学形式、推理开销都完全不同，放在一张对照表里最直观：

| 维度           | LoRA (Low-Rank Adaptation)                                   | MatFormer (“同心圆”/Matryoshka Transformer)                  |
| -------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 核心思路       | 在 **冻结** 的大矩阵 W 旁边插入 ΔW＝A·B（A∈ℝ^{d×r}, B∈ℝ^{r×d}，r≪d），用低秩增量来学习新任务 | 先把大矩阵 W 本身做成 **嵌套子矩阵**：最里圈 8 k 行→小模型；外圈再扩成 16 k 行→大模型。推理时只加载需要的行/列 |
| 结果矩阵秩     | 原 W 的全秩 + 一个低秩 ΔW                                    | 子模型本身就是低维矩阵，秩未必低，但维度变小                 |
| 计算量 (FLOPs) | **不变**：仍要算 (W + ΔW)·x，矩阵乘大小是原来的 d×d          | **按比例减少**：只做 w×d 或直接跳过整层                      |
| 显存/权重体积  | 原模型 + 少量 ΔW（几 MB-百 MB）                              | 选了小圈后，加载的权重/显存 **直接缩小到** 2 B、3 B…         |
| 训练/微调成本  | 仅训练 A、B 两块小矩阵，数百步即可收敛                       | 需要在 **预训练阶段** 就按随机宽度采样联合训练，成本≈一次完整训练 |
| 目标侧重点     | 多任务、个性化、快速增量学习                                 | 同一份权重适配多种硬件/延迟预算                              |
| 可否叠加       | 本身就是独立插件                                             | 可以：先裁 3 B 子模型，再挂 LoRA 做领域适配                  |

用一句话区分：
• LoRA 是“在**不动**大模型算力的前提下，外挂一个低秩补丁让模型学新本领”；
• MatFormer 是“把**同一份**大模型拆成几圈原生子网，需要多少算力就只装多少圈”。

因此 MatFormer 并不是“另一种低秩近似”。它改变的是矩阵的**尺寸**，从源头上减少计算与显存，而 LoRA 改变的是矩阵的**增量**，几乎不触碰计算预算。两者关注点不同且可以同时使用：

1. 先用 MatFormer 从母模型切出 3 B 子模型，显存降到 12 GB；
2. 再在这 3 B 上加 LoRA，几百 MB 参数就能做垂直领域微调。



## 5 性能与资源

| 配方 (示例)    | 层数×宽度   | 有效参数 | 推理显存 (bf16, 4 k ctx) | MMLU (pre-train) |
| -------------- | ----------- | -------- | ------------------------ | ---------------- |
| E2B 官方       | 30×8 192    | 1.9 B    | ≈ 12 GB                  | 71.1             |
| E2.98B (block) | 35×{12↔16k} | 2.98 B   | ≈ 15 GB                  | 74.6             |
| E3.79B (layer) | 35×混合     | 3.79 B   | ≈ 18 GB                  | 75.7             |
| E4B 官方       | 35×16 384   | 3.9 B    | ≈ 22 GB                  | 76.4             |

## 6 端到端裁剪实操

### 6.1 环境

```
python 3.10
pip install "transformers>=4.53" timm safetensors pandas tqdm
```



GPU 可选；裁剪流程仅用 CPU I/O。

### 6.2 关键变量

```
original_model_id = "google/gemma-3n-E4B-it"
config_name       = "Config for E2.98B (block-level)"     # or custom
local_output_path = "gemma3n-e2_98B-slice"
push_hf_repo_id   = "yourname/gemma3n-e2_98B"
```



### 6.3 核心代码片段

```
from huggingface_hub import snapshot_download
from safetensors import safe_open
from safetensors.torch import save_file
import pandas as pd, torch, os, re, gc, json

# 1. 读取配方
df = pd.read_csv("hf://datasets/google/gemma3n-slicing-configs/configs.csv")
row = df.set_index("name").loc[config_name]
layers_to_skip   = eval(row["Layers Skipped"])
ffn_hidden_dims  = eval(row["FFN Hidden Dims"])

# 2. 下载母模型 .safetensors
src = snapshot_download(original_model_id, allow_patterns=["*.safetensors"])

# 3. 流式切片 + 重写索引
kept = [i for i in range(35) if i not in layers_to_skip]
rename = {old:new for new,old in enumerate(kept)}
out_sd, sz, sid, weight_map = {},0,1,{}
os.makedirs(local_output_path, exist_ok=True)

def flush():
    global out_sd, sz, sid
    fname=f"model-{sid:05d}-of-XXXXX.safetensors"
    save_file(out_sd, f"{local_output_path}/{fname}", metadata={"format":"pt"})
    weight_map.update({k:fname for k in out_sd}); out_sd.clear(); sz=0; sid+=1; gc.collect()

for file in os.listdir(src):
    if not file.endswith(".safetensors"): continue
    with safe_open(f"{src}/{file}", framework="pt", device="cpu") as f:
        for name in f.keys():
            t = f.get_tensor(name); new = name
            m=re.search(r"\.layers\.(\d+)\.",name)
            if m:
                old=int(m[1])
                if old in layers_to_skip: continue
                new_idx=rename[old]; new=new.replace(f".layers.{old}.",f".layers.{new_idx}.")
                w=ffn_hidden_dims[new_idx]
                if any(k in new for k in ["gate_proj","up_proj"]): t=t[:w,:]
                elif "down_proj" in new:                           t=t[:,:w]
            out_sd[new]=t; sz+=t.numel()*t.element_size()
            if sz>4_000_000_000: flush()
flush()

# 4. 修正文件名、写 index.json
total=sid-1
for i in range(1,total+1):
    old=f"model-{i:05d}-of-XXXXX.safetensors"
    new=f"model-{i:05d}-of-{total:05d}.safetensors"
    os.rename(f"{local_output_path}/{old}",f"{local_output_path}/{new}")
    for k,v in weight_map.items(): 
        if v==old: weight_map[k]=new
json.dump({"weight_map":weight_map}, open(f"{local_output_path}/model.safetensors.index.json","w"), indent=2)
```



10 分钟即可产出裁剪版权重。

### 6.4 在线验证

```
from transformers import AutoModelForCausalLM
m = AutoModelForCausalLM.from_pretrained(local_output_path,
                                         torch_dtype="bfloat16",
                                         device_map="auto")
print("有效参数:", m.language_model.num_parameters(exclude_embeddings=True))
```



------

## 7 推理与微调实践

1. **vLLM 推理**

   ```
   from vllm import LLM; llm = LLM(model=local_output_path)
   print(llm.generate("用一句话解释 MatFormer 原理"))
   ```

   

2. **LoRA 微调** (`TRL 0.19.0`)

   - 依赖：`peft 0.15.2`
   - 关键参数：`gradient_checkpointing_kwargs={"use_reentrant": False}`
   - 推荐显存 ≥ 18 GB；LoRA rank = 16-32。

------

## 8 局限与未来方向

| 局限           | 说明                                                         |
| -------------- | ------------------------------------------------------------ |
| 训练成本 ↑     | 多宽度采样使 batch 内有效参数增多，需要更大吞吐。            |
| 外圈梯度稀疏   | 大宽度权重更新频率低，极限精度略逊同规模专训模型。           |
| 伸缩维度有限   | 仅 FFN hidden size + 层数，`d_model/num_heads` 不可事后修改。 |
| 工具链仍在迭代 | vLLM 仅支持文本；其他框架对 PLE/NVMe-stream 的支持尚不完善。 |

未来可探索
• 将同心切片扩展到 Q/K/V/O；
• 训练更大母模型（E70B）以提供 5-10 B 级子网；
• 将 MatFormer 与稀疏 MoE 组合，兼得“剪行列”和“剪专家”。

------

## 9 总结

Gemma 3n 把 MatFormer 理念首次落地到可商用的多模态 LLM：

1. 一份 E4B 权重通过同心切片天然包含 E2B 及全部中间档位。
2. Mix-n-Match 让开发者在不重新训练的情况下，获得符合本机算力的最优子模型。
3. 结合 vLLM / LoRA / 量化，可在消费级显卡完成推理与微调。

对需要 **多设备部署、动态 SLA 调度、统一版本管控** 的团队而言，MatFormer 大幅降低了运维与训练成本；对个人研究者，它提供了前所未有的灵活实验平台。现在即可克隆官方 notebook，裁出你的专属子模型，亲手体验“同心圆”带来的硬件弹性。