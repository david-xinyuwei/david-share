# BiomedParse 微调指南

微调微软 BiomedParse 医学图像分割模型以适配自定义数据集。

**作者**: 魏新宇 (Microsoft AI and Apps GBB)  
**模型**: [microsoft/BiomedParse](https://github.com/microsoft/BiomedParse)  
**论文**: [Nature Methods 2024](https://aka.ms/biomedparse-paper)

---

## 🎯 实验结果

我们进行了 **4 组微调实验**，验证 BiomedParse 在自定义医学影像数据上的适应性。

| 实验 | 模式 | 任务 | 数据量 | 原始 Dice | 微调后 Dice | **提升** |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **实验1** | 2D | CT 肿瘤 | 5训练/2测试 | 16.02% | 97.66% | **+81.64%** 🏆 |
| **实验2** | 3D | CT 器官(3个) | 16训练/8测试 | 0.00% | 16.70% | **+16.70%** |
| **实验3** | 2D | CT 器官(7个) | 122训练/48测试 | 4.75% | 25.68% | **+20.93%** |
| **实验4** | 3D | CT 器官(6个) | 16切片×6器官 | 16.67% | 55.80% | **+39.13%** |

### 核心发现

- 🏆 **单目标任务**（如肿瘤）获得最佳微调效果 (+81.64%)
- 📈 **3D 模式**在多器官分割上优于 2D (+39% vs +21%)
- 💡 **大器官**（肝脏 +81%，肾脏 +77%）比小器官收益更大

---

## 🚀 快速开始

### 2D 微调

```bash
# 克隆 BiomedParse
git clone https://github.com/microsoft/BiomedParse.git
cd BiomedParse

# 运行 2D 微调
python finetune_2d_strong_fast.py \
    --biomedparse_dir . \
    --data_dir /path/to/your/2d_data \
    --output_dir ./output \
    --checkpoint biomedparse_v2.ckpt \
    --epochs 100 \
    --lr 1e-5 \
    --batch_size 8
```

### 3D 微调

```bash
python finetune_3d_strong_v3.py \
    --biomedparse_dir . \
    --data_file /path/to/CT_volume.npz \
    --output_dir ./output \
    --checkpoint biomedparse_v2.ckpt \
    --epochs 100 \
    --organ_ids 1,2,3,4,5,6 \
    --start_slice 20 \
    --num_slices 16
```

---

## 🏗️ 模型架构

```
┌─────────────────────────────────────────────────────────────┐
│                  BiomedParse v2 (371M 参数)                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ 图像编码器    │───▶│  解码器       │───▶│ 掩码头       │  │
│  │ (SAM-based)  │    │ (Transformer)│    │ (逐像素)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ▲                   ▲                              │
│         │                   │                              │
│  ┌──────┴───────┐    ┌──────┴───────┐                      │
│  │ 文本编码器    │    │ 文本提示     │                      │
│  │ (BiomedCLIP) │◀───│ "CT scan of  │                      │
│  │              │    │  liver"      │                      │
│  └──────────────┘    └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

**关键组件：**
- **图像编码器**: 基于 SAM 的视觉 Transformer
- **文本编码器**: BiomedCLIP 用于医学术语
- **解码器**: 跨注意力融合图像-文本特征
- **掩码头**: 逐像素分割预测

---

## 🔧 环境配置

### 前置条件

- Python 3.10+
- CUDA 12.0+ (推荐 A100 80GB)
- PyTorch 2.0+

### 安装

```bash
# 克隆 BiomedParse
git clone https://github.com/microsoft/BiomedParse.git
cd BiomedParse

# 安装依赖
pip install -r requirements.txt

# 下载预训练权重
# 参考官方 README 获取 biomedparse_v2.ckpt
```

---

## 📁 数据格式

### 2D 格式

```
data_2d/
├── train/
│   ├── images/
│   │   ├── case001.png      # 512x512 灰度图
│   │   └── case002.png
│   └── annotations/
│       ├── case001.json     # COCO 格式标注
│       └── case002.json
└── test/
    ├── images/
    └── annotations/
```

**JSON 标注格式：**
```json
{
  "shapes": [
    {
      "label": "liver",
      "points": [[x1,y1], [x2,y2], ...],
      "shape_type": "polygon"
    }
  ]
}
```

### 3D 格式 (NPZ)

```python
import numpy as np

# 创建 3D 数据文件
np.savez('CT_volume.npz',
    imgs=images,           # [N, H, W] uint8 切片
    gts=ground_truths,     # [N, H, W] int 掩码 (0=背景, 1,2,3...=器官ID)
    text_prompts=prompts   # [N] 字符串列表
)
```

**器官 ID 映射 (AMOS 数据集)：**
| ID | 器官 | ID | 器官 |
|:---:|:---|:---:|:---|
| 1 | 脾脏 | 6 | 右肾 |
| 2 | 右肾 | 7 | 左肾 |
| 3 | 左肾 | 8 | 胆囊 |
| 4 | 胆囊 | 9 | 食道 |
| 5 | 肝脏 | 10 | 胃 |

---

## ⚙️ 配置选项

### 2D 微调参数

| 参数 | 默认值 | 说明 |
|:---|:---:|:---|
| `--epochs` | 100 | 训练轮数 |
| `--lr` | 1e-5 | 学习率 |
| `--batch_size` | 8 | 批大小 |
| `--img_size` | 1024 | 输入图像尺寸 |
| `--save_freq` | 10 | 检查点保存频率 |

### 3D 微调参数

| 参数 | 默认值 | 说明 |
|:---|:---:|:---|
| `--organ_ids` | "1,2,3,4,5,6" | 要分割的器官 ID |
| `--start_slice` | 0 | 起始切片索引 |
| `--num_slices` | 16 | 训练切片数量 |
| `--num_test_slices` | 8 | 测试切片数量 |

---

## 📊 详细实验结果

### 实验4: 3D 六器官分割 (最佳 3D 结果)

| 器官 | 原始 Dice | 微调后 Dice | **提升** |
|:---:|:---:|:---:|:---:|
| 脾脏 | 0.00% | 28.59% | +28.59% |
| 右肾 | 0.00% | 77.79% | +77.79% |
| 左肾 | 0.00% | 77.33% | +77.33% |
| 胆囊 | 0.00% | 18.02% | +18.02% |
| 肝脏 | 100.00% | 81.15% | -18.85% |
| 胃 | 0.00% | 51.91% | +51.91% |
| **平均** | 16.67% | 55.80% | **+39.13%** |

---

## 🔍 常见问题

### 1. CUDA 内存不足

```bash
# 减小批大小
python finetune_2d_strong_fast.py --batch_size 4

# 或使用梯度累积（需修改代码）
```

### 2. 训练损失不下降

- 检查数据标注质量
- 降低学习率至 1e-6
- 增加训练轮数

### 3. Dice 分数低

- 确保文本提示与训练数据匹配
- 小器官可能需要更多数据
- 尝试数据增强

---

## 📚 参考文献

1. **BiomedParse**: Zhao et al., "A biomedical foundation segmentation model via knowledge distillation and language grounding", Nature Methods, 2024
2. **SAM**: Kirillov et al., "Segment Anything", ICCV 2023
3. **BiomedCLIP**: Zhang et al., "BiomedCLIP: A Multimodal Biomedical Foundation Model", 2023

---

## 🔗 相关项目

- [MedImageParse](../../Agents/MedImageParse) - 基于 AutoGen 的医学影像分析 Agent，使用 BiomedParse 进行智能分割

---

## 📄 许可证

本项目仅用于研究目的。BiomedParse 模型遵循 [微软研究许可证](https://github.com/microsoft/BiomedParse/blob/main/LICENSE)。

---

*[English Version](README.md)*
