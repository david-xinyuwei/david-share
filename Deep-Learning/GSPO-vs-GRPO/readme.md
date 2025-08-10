# GSPO vs GRPO：为 MoE 模型打造的稳定可扩展强化学习优化方法

## 1. 背景

在大语言模型（LLM）的训练后期，强化学习（RLHF / RLAIF）起到至关重要的作用。
常用的 RL 优化方法 PPO（Proximal Policy Optimization）在工业界存在多种改进版本，其中 **GRPO（Group Relative Policy Optimization）** 是 DeepSeek 等团队推行的工程化方案。

但在 **MoE（Mixture of Experts）** 模型中，GRPO 的 **token 级优化** 容易遇到问题：

- 对专家路由波动敏感 → 训练信号噪声大
- 需要 Routing Replay（重放路由）来稳定训练
- 长时间训练可能崩溃或难以扩展

Qwen 团队在升级 **Qwen3 MoE 系列** 时，提出了新方法
**GSPO（Group Sequence Policy Optimization）**：

✅ 改进点：从 **token-level** 转为 **sequence-level** 优化
✅ 目标：减少 MoE 路由带来的训练不稳定性，提升效率与可扩展性

------

## 2. Dense 模型 vs MoE 模型

### Dense 模型

- 每次前向计算都用全量参数
- 训练信号稳定
- 无路由问题
- 例子：GPT-3、LLaMA、BERT

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/GSPO-vs-GRPO/images/2.png)

### MoE 模型

- 部分层替换为多个“专家网络”（Experts）
- 每个 token 仅激活少数专家
- 参数总量大，但每次计算量相对较低
- 不同 token 路由可能不同 → 波动大
- 例子：Mixtral 8x7B、Qwen3 MoE

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/GSPO-vs-GRPO/images/1.png)

**直观对比**：

| 模型类型 | 参数参与度 | 路由波动 | 稳定性 |
| -------- | ---------- | -------- | ------ |
| Dense    | 100%       | 无       | 高     |
| MoE      | 部分       | 有       | 低     |

------

## 3. GRPO 与 GSPO 核心差异

| 类别           | GRPO                | GSPO             |
| -------------- | ------------------- | ---------------- |
| 优化粒度       | Token-level         | Sequence-level   |
| Ratio 计算     | 每个 token 单独     | 整条序列一次     |
| Clip 操作      | 每个 token 独立剪切 | 整条序列统一剪切 |
| 对路由波动敏感 | 高                  | 低               |
| Routing Replay | 必需                | 不需要           |
| 稳定性（MoE）  | 中等                | 高               |
| Dense 提升     | 几乎无              | 几乎无           |

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/GSPO-vs-GRPO/images/3.png)

------

## 4. GSPO 原理

### Importance Ratio（重要性比）

```
ratio = P_cur / P_ref
```



衡量当前策略（P_cur）与参考策略（P_ref）对同一输出的倾向变化幅度。

- GRPO：逐 token 比例
- GSPO：整段序列比例

### Clipping（剪切）

- 限制 ratio 在 [1-ε, 1+ε]
- 防止一次更新过大导致不稳定
- GRPO：token 级 clip
- GSPO：序列级 clip

------

## 5. "Hello world" 计算示例

假设：

```
token1 = "Hello", token2 = "world"
P_ref: Hello=0.20, world=0.10
P_cur: Hello=0.25, world=0.30
ε=0.2
```



**GRPO：**

```
ratio_t1 = 0.25/0.20 = 1.25 → clip=1.2
ratio_t2 = 0.30/0.10 = 3.0 → clip=1.2
各 token 独立更新
```



**GSPO：**

```
P_ref_seq = 0.20×0.10 = 0.02
P_cur_seq = 0.25×0.30 = 0.075
ratio_seq = 3.75 → clip=1.2
整句一次更新
```



------

## 6. 实验结果（Qwen 团队）

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/GSPO-vs-GRPO/images/4.png)

### MoE 模型：

- GSPO 收敛更快
- 奖励优化更高
- 样本效率更好
- Clip 比例更高也能稳定训练
- 长序列和算力扩展时性能平稳提升

### Dense 模型：

- 无明显提升

------

## 7. 训练时使用的模型结构

无论 GRPO 还是 GSPO，都至少需要：

- **策略模型**（Policy, 会更新）
- **参考模型**（Reference, 冻结或延迟更新）
- **奖励模型**（Reward model）
- （可选）价值网络（Critic）

**参考模型**注意：

- 一般是 SFT 模型拷贝
- 固定不更新，或定期更新
- 不能直接用当前策略的即时参数作参考（ratio 永远=1 无意义）

------

## 8. 适用场景

**适合：**

- 大规模 MoE 模型
- 长序列 RL 微调
- 奖励信号稳定、信息密度高

**不适合或收益低：**

- Dense 模型
- 奖励信号噪声高、分辨率低的任务
- 对单 token 精度极高的场景（token优化粒度更粗）

------

## 9. 优缺点总结



**优势**：

- MoE 稳定性显著提升
- 样本效率高
- 移除 Routing Replay
- 可扩展性好

**劣势**：

- Dense 模型提升有限
- 优化粒度粗
- 对奖励函数依赖高
- Token 级可解释性下降

------

## 10. 常见误区

- **GSPO 是推理算法？** ❌
  → 只在训练时使用，推理不执行 ratio/clip 逻辑
- **GRPO 不支持多 token 推理？** ❌
  → 多 token 推理是解码优化策略，和训练算法无关
- **GSPO 推理直接计算整句概率？** ❌
  → 推理依然是逐 token（或并行批量）生成

------

## 11. Hugging Face TRL 接入

```
SFTConfig(
    importance_sampling_level="sequence"
)
```



- 需要 `TRL >= 0.20`
- Unsloth 截至 2025-07-30 仅支持 `TRL 0.19.1`

------

## 12. 总结

- **GRPO**：token-level 优化信号，适用于 Dense & MoE，但在 MoE 稳定性差
- **GSPO**：sequence-level 优化信号，显著优化 MoE 稳定性与效率
- Dense 模型用 GSPO 不会有明显提升

**一句话**：

> GSPO 是为 MoE 做的定向优化，训练更稳、更快、更可扩展，推理性能也因此受益，但它本身不是推理算法。