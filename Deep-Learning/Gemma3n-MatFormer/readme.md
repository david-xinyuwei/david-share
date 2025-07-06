# 深度解析 Gemma 3n 与 MatFormer「同心圆」架构

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