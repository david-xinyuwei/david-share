# BiomedParse 微调指南

微软 BiomedParse 医学图像分割模型的微调实战指南。

**作者**: 魏新宇 (Microsoft AI and Apps GBB)  
**模型**: [microsoft/BiomedParse](https://github.com/microsoft/BiomedParse)  
**论文**: [Nature Methods 2024](https://aka.ms/biomedparse-paper)  
**测试环境**: NVIDIA A10 24GB GPU

---

## 🌟 微软医疗 AI 的"三驾马车"

在开始微调之前，了解 BiomedParse 在微软医疗 AI 版图中的定位非常有帮助。它们构成了覆盖不同模态的**"三驾马车"**：

| 模型 | 模态 | 核心任务 | 形象比喻 | GitHub 仓库 |
| :--- | :--- | :--- | :--- | :--- |
| **BioGPT** | **纯文本** | 文本生成与挖掘 | "医学界的 ChatGPT" | [microsoft/BioGPT](https://github.com/microsoft/BioGPT) |
| **LLaVA-Med** | **图+文** | 视觉问答 (VQA) | "医生，这张片子里有什么病？" | [microsoft/LLaVA-Med](https://github.com/microsoft/LLaVA-Med) |
| **BiomedParse** | **像素级图像** | **分割与检测** | **"AI 手术刀" (精准勾勒)** | [microsoft/BiomedParse](https://github.com/microsoft/BiomedParse) |

> **BiomedParse 的独特价值**：LLaVA-Med 只能**聊**图片，而 BiomedParse 能**操作**图片（精准分割病灶或器官）。本仓库专注于 **BiomedParse** 的微调实战。

---

## 🎯 结果摘要

| 实验 | 模式 | 任务 | 微调前 Dice | 微调后 Dice | **提升** |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **2D CT 器官** | 2D | 左/右肾、肝脏 | 42.5% | **91.0%** | 🏆 **+48.5%** |
| **3D 肾上腺** | 3D | 左/右肾上腺 | 73.9% | **90.2%** | **+16.3%** |

### 核心发现

- 🏆 **正确的 prompt 提取至关重要**：使用精确的提示词（如 "left kidney"）是性能关键。
- 📈 **3D 模式适合小器官**：肾上腺达到 90%+ Dice
- ⚠️ **输入必须是 0-255 范围**：不要归一化到 0-1

---

## 📊 详细结果

### 2D CT 器官分割

![2D Comparison](./images/biomedparse_2d_comparison.png)

*GT=绿色，微调前=橙色，微调后=青色。"微调前"模型提供了基准分割能力（Dice ~42%），而"微调后"模型显著提升了分割精度（Dice ~91%）。*

| 测试图像 | 提示词 | 微调前 | 微调后 | 提升 |
|----------|--------|--------|--------|------|
| slice025 | left kidney | 34.9% | **97.7%** | +62.8% |
| slice025 | right kidney | 47.6% | **97.5%** | +50.0% |
| slice030 | left kidney | 41.7% | **95.9%** | +54.2% |
| slice030 | liver | 53.2% | **92.0%** | +38.8% |
| slice030 | right kidney | 39.8% | **94.2%** | +54.4% |
| slice035 | left kidney | 37.9% | **68.7%** | +30.8% |
| **平均** | - | **42.5%** | **91.0%** | **+48.5%** |

### 3D 肾上腺分割

![3D Comparison](./images/biomedparse_3d_comparison.png)

*绿色=正确，红色=假阳性，橙色=漏检区域*

| 器官 | 微调前 | 微调后 | 提升 |
|-------|--------|-------|-------------|
| 左肾上腺 | 70.8% | **87.7%** | +16.9% |
| 右肾上腺 | 76.9% | **92.6%** | +15.7% |
| **平均** | **73.9%** | **90.2%** | **+16.3%** |

---

## 🚀 快速开始

### 2D 微调

```bash
# 克隆 BiomedParse
git clone https://github.com/microsoft/BiomedParse.git
cd BiomedParse

# 下载预训练模型
# biomedparse_v2.ckpt (4.4GB) - 放在 BiomedParse 根目录

# 复制微调脚本并编辑路径
cp /path/to/finetune_2d.py .
# 编辑脚本中的: SAVE_DIR, data_root

# 运行 2D 微调
python finetune_2d.py
```

### 3D 微调

```bash
# 复制微调脚本并编辑路径
cp /path/to/finetune_3d.py .
# 编辑脚本中的: SAVE_DIR, NPZ_PATH

# 运行 3D 微调
python finetune_3d.py
```

---

## 📁 数据格式

### 2D 数据结构

```
data_dir/
├── train/
│   ├── slice001_left_kidney.png      # 文件名 = 提示词
│   ├── slice001_right_kidney.png
│   └── ...
├── train_mask/
│   ├── slice001_left_kidney_mask.png
│   └── ...
├── test/
└── test_mask/
```

**重要**：文件名（去掉扩展名后）会成为文本提示词！
- `slice001_left_kidney.png` → 提示词 = `"left kidney"`
- `slice002_liver.png` → 提示词 = `"liver"`

---

## 🏗️ 架构

```mermaid
graph TD
    subgraph BiomedParse["BiomedParse v2 (3.71亿参数)"]
        IMG[CT 图像<br/>1024×1024] --> ENC[图像编码器<br/>SAM-based]
        TXT[文本提示<br/>'left kidney'] --> TENC[文本编码器<br/>BiomedCLIP]
        ENC --> DEC[Transformer 解码器]
        TENC --> DEC
        DEC --> HEAD[掩码头]
        HEAD --> OUT[分割掩码<br/>1024×1024]
    end
    
    style IMG fill:#e1f5fe
    style TXT fill:#fff3e0
    style OUT fill:#e8f5e9
```

### 2D vs 3D 模式

```mermaid
graph LR
    subgraph 2D["2D 模式"]
        A1[单张切片] --> B1[1024×1024 RGB]
        B1 --> C1[逐切片预测]
    end
    
    subgraph 3D["3D 模式"]
        A2[体积堆叠] --> B2[D×H×W 灰度]
        B2 --> C2[体积预测]
    end
```

---

## ⚠️ 已知问题与解决方案

### 问题 1：图像归一化

**现象**：模型输出空白或错误的掩码

**根本原因**：BiomedParse 输入范围是 **0-255**，不是 0-1

```python
# ❌ 错误
img = img / 255.0

# ✅ 正确
img = img.astype(np.float32)  # 保持 0-255 范围
```

### 问题 2：Prompt 不匹配

**现象**：查询 "left kidney" 时模型预测双侧肾脏

**根本原因**：Prompt 提取返回 "kidney" 而非 "left kidney"

```python
# ❌ 错误：返回 "kidney"
organ = fname.split("_")[-1].replace(".png", "")

# ✅ 正确：返回 "left kidney"
def get_prompt(fname):
    base = fname.replace(".png", "")
    parts = base.split("_")[1:]  # 跳过切片编号
    return " ".join(parts)
```

### 问题 3：Hydra 配置冲突

**现象**：第二次加载模型时报错 `GlobalHydra is already initialized`

**解决方案**：重新初始化前清除 Hydra 状态

```python
from hydra.core.global_hydra import GlobalHydra
GlobalHydra.instance().clear()
initialize(config_path="configs/model", ...)
```

### 问题 4：批次大小与不同 Prompt

**现象**：批次包含不同 prompt 时预测结果不一致

**解决方案**：当每个样本 prompt 不同时使用 `batch_size=1`

```python
DataLoader(dataset, batch_size=1)  # 不同 prompt 时使用
```

---


## 📋 训练日志（可复现证据）

### 2D 训练输出

```
============================================================
BiomedParse 2D Fine-tuning - CORRECT (0-255 input)
============================================================

[1/4] 加载模型...
   已加载 1050/1050 参数

[2/4] 加载数据...
   训练集: 72, 测试集: 18
   输入范围: 0 - 255   ← 关键：不做归一化！

[3/4] 评估原始模型...
   原始 Dice: 42.5%

[4/4] 训练 30 轮...
Epoch   1: Loss=0.7854
Epoch   5: Loss=0.5231, Dice=55.2%
Epoch  10: Loss=0.3012, Dice=68.4%
Epoch  15: Loss=0.2076, Dice=78.1%
Epoch  20: Loss=0.1535, Dice=85.4%
Epoch  25: Loss=0.1402, Dice=88.2%
Epoch  30: Loss=0.1359, Dice=91.0%

============================================================
完成！原始: 42.5% -> 最佳: 91.0%
提升: +48.5%
============================================================
```

### 3D 训练输出

```
============================================================
BiomedParse 3D Fine-tuning - Adrenal Glands
============================================================

[1/4] 加载 3D 模型...
   模型已加载！

[2/4] 加载数据...
   输入形状: torch.Size([1, 30, 512, 512]), 范围: 0-255
   左肾上腺: 1247 体素
   右肾上腺: 892 体素

[3/4] 评估原始模型...
   左肾上腺: 70.8%
   右肾上腺: 76.9%
   平均: 73.9%

[4/4] 训练 100 轮...
Epoch  10: Loss=0.4521, Dice=75.6%
Epoch  20: Loss=0.2834, Dice=78.2%
Epoch  30: Loss=0.1956, Dice=80.5%
Epoch  40: Loss=0.1423, Dice=85.1%
Epoch  50: Loss=0.1187, Dice=88.2%  -> 新最佳！
Epoch  60: Loss=0.1023, Dice=89.1%  -> 新最佳！
Epoch  70: Loss=0.0912, Dice=89.8%  -> 新最佳！
Epoch  80: Loss=0.0856, Dice=90.1%  -> 新最佳！
Epoch  90: Loss=0.0798, Dice=90.2%  -> 新最佳！
Epoch 100: Loss=0.0745, Dice=90.2%  -> 新最佳！

============================================================
完成！原始: 73.9% -> 最佳: 90.2%
提升: +16.3%
============================================================
```

### 推理输出（测试集）

```
[2D 测试结果 - 微调后]
slice025 | left kidney  | GT: 2,174px | Pred: 2,117px | Dice: 97.7%
slice025 | right kidney | GT: 1,763px | Pred: 1,786px | Dice: 97.5%
slice030 | left kidney  | GT: 2,079px | Pred: 2,012px | Dice: 95.9%
slice030 | liver        | GT: 1,299px | Pred: 1,423px | Dice: 92.0%
slice030 | right kidney | GT: 2,902px | Pred: 2,834px | Dice: 94.2%
slice035 | left kidney  | GT: 2,897px | Pred: 2,156px | Dice: 68.7%
-----------------------------------------------------------------
平均 Dice: 91.0%

[3D 测试结果 - 微调后]
左肾上腺  | Dice: 87.7% (原始: 70.8%)
右肾上腺 | Dice: 92.6% (原始: 76.9%)
-----------------------------------------------------------------
平均 Dice: 90.2%
```

---
## 🖥️ 测试环境

| 组件 | 值 |
|------|-----|
| GPU | NVIDIA A10 24GB |
| 框架 | PyTorch 2.0+ |
| 模型 | BiomedParse v2 (3.71亿参数) |
| 精度 | FP16 (AMP) |

### 训练配置

| 参数 | 值 | 原因 |
|------|-----|------|
| 微调模式 | 全参数微调 | 全部 3.71 亿参数可训练 |
| 学习率 | 1e-5 | 防止灾难性遗忘 |
| 优化器 | AdamW | weight_decay=0.01 用于正则化 |
| 损失函数 | Dice Loss | 分割任务最优 |
| 调度器 | CosineAnnealingLR | 平滑收敛 |

---

## 📁 文件结构

```
BiomedParse-Fine-Tuning/
├── README.md                    # 英文版
├── README-CN.md                 # 本文件（中文）
├── finetune_2d.py               # 2D 微调脚本
├── finetune_3d.py               # 3D 微调脚本
├── visualize_2d.py              # 2D 对比图生成
├── visualize_3d.py              # 3D 对比图生成
└── images/
    ├── biomedparse_2d_comparison.png  # 2D 结果
    ├── biomedparse_3d_comparison.png  # 3D 结果
```

---

## 🧠 技术深度解析：工作原理

### 1. 模型"眼中"的世界 (输入数据)
与人类不同，模型看到的不是图片，而是 **4维张量 (4D Tensor)**。

| 模式 | 输入张量形状 | 含义 | 数值范围 |
| :--- | :--- | :--- | :--- |
| **2D** | `[1, 3, H, W]` | 批次=1, **RGB 通道**, 高, 宽 | **0.0 - 255.0** (Float32) |
| **3D** | `[1, D, H, W]` | 批次=1, **深度 (切片数)**, 高, 宽 | **0.0 - 255.0** (Float32) |

> **关键点**：输入数据**没有**归一化到 0-1，而是保留了原始像素强度 (0-255)。

<div align="center">
  <img src="./images/doc_tensor_view.png" width="200" alt="模拟张量视图" />
  <p><em>图示：模型眼中的数据（模拟张量视图，0-255 范围）</em></p>
</div>

### 2. "画图"的本质 (分割)
医学图像分割本质上是 **像素级的 0/1 分类**。
*   **任务**：模型拿到一张黑纸（全0矩阵）和一句提示（如 "left kidney"）。
*   **动作**：它拿着一支"白笔"（值为1），把它认为是肾脏的像素点涂白。
*   **输出**：一张概率图，其中 `0` = 背景，`1` = 器官。

### 3. 训练闭环
1.  **看题**：模型接收 **原始影像** + **文本提示词**。
2.  **猜图**：模型"画"出它认为的器官形状。
3.  **对答案**：与 **医生标注 (Ground Truth)** 进行比对。
    *   *来源*：CT-AMOS 数据集（由放射科医生手工逐层标注，极其昂贵）。
4.  **纠错**：
    *   画得像（重合度高）→ 奖励。
    *   画得不像（重合度低）→ 惩罚（计算 Loss）。

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="./images/doc_real_input.png" width="250" alt="真实输入" /><br/><b>1. 输入 (原始 CT)</b></td>
      <td align="center"><img src="./images/doc_real_mask.png" width="250" alt="真实掩码" /><br/><b>2. 医生标注 (Ground Truth)</b></td>
    </tr>
  </table>
  <p><em>真实训练对：模型学习将左侧的输入映射到右侧的掩码</em></p>
</div>

### 4. 为什么 BiomedParse 很有价值？
高质量的医学标注数据**极其稀缺且昂贵**，因为需要资深医生花费数小时进行手工描边。
*   **传统 AI**：通常需要 1000+ 例标注数据才能训练。
*   **BiomedParse**：作为一个**基础模型**，它已经"阅读"了海量的生物医学论文和图像。因此，它只需要 **~20-50 例** 数据（少样本学习）就能快速适应新任务（如分割肾上腺），极大地降低了医疗 AI 的开发门槛。

### 5. 核心秘籍：为什么是 Dice Loss？
你可能会问：*"这不就是简单的有监督微调 (SFT) 吗？"*
**是的！** 但成功的关键在于**我们如何定义"错误"**。

*   **难题**：在一张 CT 扫描中，**99% 都是黑色背景**，只有 **1% 是器官**。
*   **陷阱**：如果使用普通的像素准确率，模型只要学会"全涂黑"，准确率就能高达 99%！但这毫无意义。
*   **解法 (Dice Loss)**：
    *   我们使用 **Dice Loss**，它只关注预测结果与医生标注的**重合度 (Overlap)**。
    *   公式：$Loss = 1 - \frac{2 \times |预测 \cap 标注|}{|预测| + |标注|}$
    *   **效果**：它强迫模型死死盯着那 1% 的关键区域。如果漏掉了器官，Loss 会非常大，逼迫模型去学习微小的边缘细节。

### 6. 2D vs 3D："切片面包"理论
2D 和 3D 微调的底层逻辑是**完全一致**的（都是 SFT + Dice Loss）。唯一的区别在于维度。

*   **直观理解**：
    *   **3D (Volume)**：就像一整条**切片面包**。
    *   **2D (Slice)**：就是从里面抽出来的**每一片面包**。
*   **3D 的上帝视角优势**：
    *   **2D 模型**：它是"近视眼"，只看得到当前这一层。它不知道上一层是肾脏，这一层突然消失了是不是正常的。
    *   **3D 模型**：它拥有"透视眼"，能同时看到器官的**连续性**。它知道肾脏是一个连续的球体，不会在中间突然断开。这使得 3D 微调在处理复杂、立体的器官（如血管、不规则肿瘤）时，效果通常比 2D 更好。

---

## 📚 参考资料

- [BiomedParse GitHub](https://github.com/microsoft/BiomedParse)
- [BiomedParse 论文](https://aka.ms/biomedparse-paper) - Nature Methods, 2024
- [CT-AMOS 数据集](https://amos22.grand-challenge.org/)

---

*在 NVIDIA A10 24GB 上验证 | 2024年12月*
