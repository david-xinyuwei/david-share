# UniAD 完整架构解析

## 📊 总体结构

```
UniAD (端到端自动驾驶)
├── Stage 1: Track + Map (目标跟踪 + 地图分割)
├── Stage 2: E2E (端到端驾驶决策 + 规划)
└── 基于 MMDetection3D 框架
```

---

## 🏗️ 核心组件层级结构

### 1️⃣ **顶层模型** (Top-level Model)
```
UniAD (总控模型)
├── type: "UniAD"
├── 负责: 整合所有任务头，协调训练/推理
└── 位置: projects/mmdet3d_plugin/uniad/detectors/uniad.py
```

---

### 2️⃣ **骨干网络** (Backbone)
```
img_backbone
├── type: ResNet-101
├── 功能: 从多视角图像提取特征
├── 输出: 3个尺度特征 (C3, C4, C5)
├── 特性:
│   ├── DCNv2 可变形卷积 (stage 3, 4)
│   ├── 冻结参数 (frozen_stages=4)
│   └── BatchNorm 冻结
└── 位置: torchvision.models.resnet101 (MMDetection 封装)
```

---

### 3️⃣ **特征金字塔网络** (Neck)
```
img_neck
├── type: FPN (Feature Pyramid Network)
├── 功能: 多尺度特征融合
├── 输入: [C3, C4, C5] → [512, 1024, 2048] channels
├── 输出: 4 层特征图，统一为 256 channels
└── 位置: mmdet.models.necks.FPN
```

---

### 4️⃣ **BEV Transformer** (核心感知模块)

#### 4.1 **BEV Encoder** (BEVFormerEncoder)
```
encoder (6 layers)
├── type: BEVFormerEncoder
├── 功能: 将多视角图像特征转换为 BEV (鸟瞰图) 特征
├── 每层包含:
│   ├── TemporalSelfAttention (时序自注意力)
│   │   └── 融合历史帧信息 (queue_length=5)
│   ├── SpatialCrossAttention (空间交叉注意力)
│   │   ├── MSDeformableAttention3D (3D可变形注意力)
│   │   └── 从图像特征采样到 BEV 网格
│   └── FFN (前馈神经网络)
├── 输出: BEV 特征 [200×200×256]
└── 位置: projects/mmdet3d_plugin/uniad/modules/encoder.py
```

**关键模块**:
- `BEVFormerLayer`: 单层 Transformer
- `TemporalSelfAttention`: 时序建模
- `SpatialCrossAttention`: 图像→BEV 投影
- `MSDeformableAttention3D`: 3D 可变形注意力采样

#### 4.2 **Detection Decoder** (DetectionTransformerDecoder)
```
decoder (6 layers)
├── type: DetectionTransformerDecoder
├── 功能: 从 BEV 特征预测目标
├── 每层包含:
│   ├── Self-Attention (Query 之间交互)
│   │   ├── 原始: MultiheadAttention
│   │   └── 优化: FlashMultiheadAttention ← 你的改动在这里！
│   ├── Cross-Attention (Query 与 BEV 特征交互)
│   │   └── CustomMSDeformableAttention
│   └── FFN (前馈神经网络)
├── 输入: 900 个 Query (可学习的目标查询)
├── 输出: 900 个目标预测 (bbox, class, tracking ID)
└── 位置: projects/mmdet3d_plugin/uniad/modules/decoder.py
```

**你改了什么？**
```
Decoder 的 6 层 × Self-Attention (第1个attn)
├── 原版: MultiheadAttention (标准PyTorch实现)
└── 优化: FlashMultiheadAttention (FlashAttention-2加速)
       ↓
   所有6层都改了，不只是第6层！
```

---

### 5️⃣ **任务头** (Task Heads)

#### **Stage 1: Track + Map**
```
pts_bbox_head
├── type: BEVFormerTrackHead
├── 功能: 3D 目标检测 + 多目标跟踪
├── 包含:
│   ├── Transformer (上面的 Encoder + Decoder)
│   ├── Query Interaction Module (QIM)
│   │   └── Query 更新和管理
│   ├── Memory Bank (历史目标记忆)
│   └── 输出:
│       ├── 3D BBox (位置、尺寸、朝向)
│       ├── Tracking ID
│       └── 过去/未来轨迹
└── 位置: projects/mmdet3d_plugin/uniad/dense_heads/track_head.py
```

```
seg_head (语义分割头)
├── type: PansegformerHead
├── 功能: BEV 地图分割 (车道线、人行道等)
├── 输出: 分割掩码
└── 位置: projects/mmdet3d_plugin/uniad/dense_heads/panseg_head.py
```

#### **Stage 2: E2E (完整系统)**
```
motion_head
├── type: MotionHead
├── 功能: 多模态轨迹预测
└── 位置: projects/mmdet3d_plugin/uniad/dense_heads/motion_head.py

occ_head
├── type: OccHead
├── 功能: 占据栅格预测 + 光流
└── 位置: projects/mmdet3d_plugin/uniad/dense_heads/occ_head.py

planning_head
├── 功能: 轨迹规划
└── 输出: 自车未来轨迹
```

---

## 🔗 完整调用链 (Forward Pass)

### **训练/推理流程**

```
输入: 6 个相机图像 (1600×900)
  ↓
[1] img_backbone (ResNet-101)
  ├── 提取多尺度特征
  └── 输出: [C3, C4, C5] 3个尺度
  ↓
[2] img_neck (FPN)
  ├── 特征金字塔融合
  └── 输出: [P2, P3, P4, P5] 4层特征 (256 channels)
  ↓
[3] pts_bbox_head.transformer.encoder (BEVFormerEncoder, 6 layers)
  ├── Layer 1-6: 循环执行
  │   ├── TemporalSelfAttention (融合历史帧)
  │   ├── SpatialCrossAttention (图像→BEV投影)
  │   │   └── MSDeformableAttention3D 采样
  │   └── FFN
  └── 输出: BEV 特征 [1, 200, 200, 256]
  ↓
[4] pts_bbox_head.transformer.decoder (DetectionTransformerDecoder, 6 layers)
  ├── 输入: 900 个 Query [900, 256]
  ├── Layer 1-6: 循环执行
  │   ├── Self-Attention ← FlashMultiheadAttention (你的优化！)
  │   │   └── Query 之间交互
  │   ├── Cross-Attention (CustomMSDeformableAttention)
  │   │   └── Query 从 BEV 特征提取信息
  │   └── FFN
  └── 输出: 900 个refined query [900, 256]
  ↓
[5] pts_bbox_head (BEVFormerTrackHead)
  ├── 分类头: Query → 类别概率 [900, 10]
  ├── 回归头: Query → 3D BBox [900, 10] (x,y,z,w,l,h,sin,cos,vx,vy)
  ├── Query Interaction Module (QIM)
  │   └── 更新/删除/添加 Query
  └── Memory Bank
      └── 存储历史目标用于跟踪
  ↓
输出: 
  ├── 3D 检测框 (位置、尺寸、朝向)
  ├── 目标类别
  ├── Tracking ID
  └── 轨迹 (过去4帧 + 未来4帧)
```

---

## 📦 模块总数统计

### **按层级分类**

| 层级 | 模块名 | 数量 | 功能 |
|------|--------|------|------|
| **Level 1** | UniAD | 1 | 总控模型 |
| **Level 2** | ResNet-101 Backbone | 1 | 图像特征提取 |
| **Level 2** | FPN Neck | 1 | 多尺度融合 |
| **Level 3** | BEVFormerEncoder | 1 | 包含6层 |
| **Level 4** | BEVFormerLayer | 6 | Encoder 层 |
| **Level 5** | TemporalSelfAttention | 6 | 每层1个 |
| **Level 5** | SpatialCrossAttention | 6 | 每层1个 |
| **Level 5** | MSDeformableAttention3D | 6 | 嵌入在 SpatialCrossAttention 内 |
| **Level 3** | DetectionTransformerDecoder | 1 | 包含6层 |
| **Level 4** | DetrTransformerDecoderLayer | 6 | Decoder 层 |
| **Level 5** | FlashMultiheadAttention | 6 | Self-Attention (你的优化！) |
| **Level 5** | CustomMSDeformableAttention | 6 | Cross-Attention |
| **Level 3** | BEVFormerTrackHead | 1 | 检测+跟踪头 |
| **Level 3** | PansegformerHead | 1 | 分割头 (Stage 1) |
| **Level 3** | MotionHead | 1 | 运动预测 (Stage 2) |
| **Level 3** | OccHead | 1 | 占据预测 (Stage 2) |
| **Level 3** | PlanningHead | 1 | 轨迹规划 (Stage 2) |

### **核心组件总数**

```
总模块数: 50+
├── Backbone + Neck: 2
├── BEV Transformer: 25
│   ├── Encoder Layers: 6
│   ├── Encoder Attentions: 12 (6 temporal + 6 spatial)
│   ├── Decoder Layers: 6
│   └── Decoder Attentions: 12 (6 self + 6 cross)
├── Task Heads: 5 (Track, Seg, Motion, Occ, Planning)
└── 辅助模块: 15+ (QIM, Memory Bank, Loss functions等)
```

---

## 🎯 FlashAttention 优化点总结

**你改了哪里？**
```
DetectionTransformerDecoder 的 6 层
├── 每层的第 1 个注意力 (Self-Attention)
│   ├── 原版: MultiheadAttention (embed_dims=256, num_heads=8)
│   └── 优化: FlashMultiheadAttention (同样参数)
├── 每层的第 2 个注意力 (Cross-Attention)
│   └── CustomMSDeformableAttention (保持不变)
└── 结果: 6 层 × 1 个 Self-Attention = 6 个模块被优化
```

**为什么只改 Decoder Self-Attention？**
1. **Encoder 不改**: MSDeformableAttention3D 是稀疏注意力，不适合 FlashAttention
2. **Decoder Cross-Attention 不改**: CustomMSDeformableAttention 也是稀疏注意力
3. **只改 Decoder Self-Attention**: 标准的密集注意力，完美匹配 FlashAttention-2

**实际加速**:
- FP32 → FP16: 1.255x
- FP32 → FP16+FA2: 1.291x
- FP16 → FP16+FA2: **1.029x** (额外 2.9% 提升)

---

## 📁 代码文件组织

```
UniAD/
└── projects/mmdet3d_plugin/
    └── uniad/
        ├── detectors/
        │   └── uniad.py              # UniAD 总模型
        ├── modules/
        │   ├── encoder.py            # BEVFormerEncoder + BEVFormerLayer
        │   ├── decoder.py            # DetectionTransformerDecoder
        │   ├── flash_attention.py    # FlashMultiheadAttention (你的贡献！)
        │   ├── temporal_self_attention.py
        │   ├── spatial_cross_attention.py
        │   └── custom_base_transformer_layer.py
        ├── dense_heads/
        │   ├── track_head.py         # BEVFormerTrackHead
        │   ├── panseg_head.py        # PansegformerHead
        │   ├── motion_head.py        # MotionHead
        │   ├── occ_head.py           # OccHead
        │   └── planning_head.py
        └── core/
            ├── bbox/                 # BBox 编解码器
            └── track/                # 跟踪算法
```

---

## 🔑 关键配置参数

```python
# 基础参数
_dim_ = 256              # 特征维度
_num_levels_ = 4         # FPN 层数
bev_h_ = 200            # BEV 高度 (网格)
bev_w_ = 200            # BEV 宽度 (网格)
queue_length = 5        # 历史帧数量

# Transformer 参数
num_encoder_layers = 6  # Encoder 层数
num_decoder_layers = 6  # Decoder 层数
num_query = 900         # 目标查询数量
num_heads = 8           # 注意力头数

# 训练参数
batch_size = 1          # 每 GPU batch
total_epochs = 6        # Stage 1 训练轮数
lr = 2e-4               # 学习率
```

---

## ✅ 总结

**UniAD 是一个多层级、多模块的端到端自动驾驶系统**:
- **50+ 核心模块**，分 5 个层级
- **核心**: BEV Transformer (Encoder 6层 + Decoder 6层)
- **你的优化**: 6 个 Decoder Self-Attention 改用 FlashAttention-2
- **调用链**: 图像 → Backbone → FPN → BEV Encoder → BEV Decoder → Task Heads → 输出
- **性能提升**: 训练加速 1.029x，显存节省 1.3 GB

**一句话**: UniAD 用 BEV Transformer 把多视角图像转成鸟瞰图特征，然后用多个任务头完成检测、跟踪、分割、预测、规划等自动驾驶任务。你优化了其中 Decoder 的 6 层 Self-Attention，实现了加速！
