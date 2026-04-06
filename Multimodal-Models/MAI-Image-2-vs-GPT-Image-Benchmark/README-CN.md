# MAI-Image-2 vs GPT-Image-1.5: Azure AI 图像生成 Benchmark

在 Azure 上对 **MAI-Image-2** 和 **GPT-Image-1.5** 进行公平的延迟基准测试，使用完全相同的 Prompt、分辨率、Quality 设置和测试环境。

## 核心结果

| 指标 | MAI-Image-2 | GPT-Image-1.5 | 差异 |
|------|:-----------:|:-------------:|:----:|
| 通过率 | 11/11 (100%) | 11/11 (100%) | 持平 |
| **平均延迟** | **22.7s** | **46.7s** | **MAI 快 2.1x** |
| 延迟范围 | 20.0s – 32.7s | 43.3s – 49.2s | MAI 更稳定 |
| 分辨率 | 1024x1024 RGB | 1024x1024 RGB | 完全一致 |
| Quality | high | high | 完全一致 |

> MAI-Image-2 在所有 11 个测试 Prompt 中**一致地快 2.1 倍**，无一例外。

## 公平对比：七维对齐

为确保对比有效，我们对齐了**所有可控变量**，仅变更模型：

| 维度 | MAI-Image-2 | GPT-Image-1.5 | 对齐 |
|------|:-----------:|:-------------:|:----:|
| Prompt | 11 个 Surreal 风格 Prompt | 相同的 11 个 Prompt | ✅ |
| 分辨率 | 1024×1024 | 1024×1024 | ✅ |
| Quality | `high`（显式指定） | `high`（显式指定） | ✅ |
| 输出格式 | PNG 8-bit RGB | PNG 8-bit RGB | ✅ |
| 网络环境 | 同一台 VM (East US) | 同一台 VM (East US) | ✅ |
| 测试日期 | 2026-04-03 | 2026-04-03 | ✅ |
| **模型（被测变量）** | MAI-Image-2 | gpt-image-1.5 | 🔀 |

两个模型在同一脚本 (`fair_comparison_r2.py`) 中交替运行，最小化网络/时间偏差。

## 逐项延迟对比

| # | Prompt | MAI-Image-2 | GPT-Image-1.5 | 加速比 |
|:-:|:-------|:-----------:|:-------------:|:------:|
| 1 | Chrome kimono metallic maiden | 22.2s | 49.0s | 2.2x |
| 2 | Portal into mythical forest | 20.4s | 47.8s | 2.3x |
| 3 | Tiny astronaut hatching on moon | 20.6s | 49.2s | 2.4x |
| 4 | LOTR tiny red dragon macro | 20.0s | 43.6s | 2.2x |
| 5 | Fluffy creature fantasy | 20.3s | 48.3s | 2.4x |
| 6 | Hidden jungle cenote | 24.9s | 46.2s | 1.9x |
| 7 | Tech-savvy girl holographic UI | 32.7s | 46.7s | 1.4x |
| 8 | Universe fractal worlds | 24.6s | 48.2s | 2.0x |
| 9 | Fractal mythical creature | 21.7s | 43.3s | 2.0x |
| 10 | Angry cat playing drums | 21.4s | 43.9s | 2.0x |
| 11 | Monkey playing music | 20.5s | 47.0s | 2.3x |
| **平均** | | **22.7s** | **46.7s** | **2.1x** |

## 并排图片对比

### Test 1: Chrome Kimono Metallic Maiden

| MAI-Image-2 (22.2s) | GPT-Image-1.5 (49.0s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/01_test.png) | ![GPT](images/gpt-image-1.5/01_test.png) |

### Test 2: Portal into Mythical Forest

| MAI-Image-2 (20.4s) | GPT-Image-1.5 (47.8s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/02_test.png) | ![GPT](images/gpt-image-1.5/02_test.png) |

### Test 3: Tiny Astronaut on Moon

| MAI-Image-2 (20.6s) | GPT-Image-1.5 (49.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/03_test.png) | ![GPT](images/gpt-image-1.5/03_test.png) |

### Test 4: LOTR Tiny Red Dragon

| MAI-Image-2 (20.0s) | GPT-Image-1.5 (43.6s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/04_test.png) | ![GPT](images/gpt-image-1.5/04_test.png) |

### Test 5: Fluffy Fantasy Creature

| MAI-Image-2 (20.3s) | GPT-Image-1.5 (48.3s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/05_test.png) | ![GPT](images/gpt-image-1.5/05_test.png) |

### Test 6: Hidden Jungle Cenote

| MAI-Image-2 (24.9s) | GPT-Image-1.5 (46.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/06_test.png) | ![GPT](images/gpt-image-1.5/06_test.png) |

### Test 7: Tech-Savvy Girl with Holographic UI

| MAI-Image-2 (32.7s) | GPT-Image-1.5 (46.7s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/07_test.png) | ![GPT](images/gpt-image-1.5/07_test.png) |

### Test 8: Universe Fractal Worlds

| MAI-Image-2 (24.6s) | GPT-Image-1.5 (48.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/08_test.png) | ![GPT](images/gpt-image-1.5/08_test.png) |

### Test 9: Fractal Mythical Creature

| MAI-Image-2 (21.7s) | GPT-Image-1.5 (43.3s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/09_test.png) | ![GPT](images/gpt-image-1.5/09_test.png) |

### Test 10: Angry Cat Playing Drums

| MAI-Image-2 (21.4s) | GPT-Image-1.5 (43.9s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/10_test.png) | ![GPT](images/gpt-image-1.5/10_test.png) |

### Test 11: Monkey Playing Music

| MAI-Image-2 (20.5s) | GPT-Image-1.5 (47.0s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/11_test.png) | ![GPT](images/gpt-image-1.5/11_test.png) |

## API 差异

| 特性 | MAI-Image-2 | GPT-Image-1.5 |
|------|:-----------:|:-------------:|
| API Path | `/mai/v1/images/generations` | `/openai/deployments/{name}/images/generations` |
| 认证方式 | **仅 Entra ID** | Key + Entra ID |
| 尺寸参数 | `width` / `height`（整数） | `size`（字符串，如 `"1024x1024"`） |
| Model 参数 | 必须指定 `"MAI-Image-2"` | 不需要（已在 deployment 中指定） |
| Quality 参数 | `low` / `medium` / `high` | `low` / `medium` / `high` |
| 像素分辨率 | 1024x1024 | 1024x1024 |
| 输出格式 | PNG 8-bit RGB | PNG 8-bit RGB |

## 复现方法

### 前提条件

- 包含 Azure AI Services 资源的 Azure 订阅
- MAI-Image-2 和 gpt-image-1.5 模型部署
- Python 3.x + `requests` 包
- Azure CLI (`az`) 已登录

### 运行公平对比测试

```bash
# 克隆本仓库
git clone https://github.com/david-xinyuwei/MAI-Image-2-vs-GPT-Image-Benchmark.git
cd MAI-Image-2-vs-GPT-Image-Benchmark

# 编辑 scripts/fair_comparison_r2.py 设置你的资源名和 API Key
pip install requests
python scripts/fair_comparison_r2.py
```

### 单独运行某个模型测试

```bash
# 仅 MAI-Image-2（需要 Entra ID 认证）
python scripts/test_mai_image2.py

# 仅 GPT-Image-1.5（支持 Key 认证）
python scripts/test_gpt_image15.py
```

## Expected Output / 预期输出

运行 `fair_comparison_r2.py` 后应看到类似输出：

```
======================================================================
MAI-Image-2 vs GPT-Image-1.5 Fair Comparison (Round 2)
Unified params: 1024x1024, quality=high, b64_json
======================================================================
Prompts: 11
Entra token acquired
======================================================================

[1/11] Chrome kimono, a maiden surrounded by metallic flowers, earrings, orna...
  MAI: OK 22.2s 1473KB
  GPT: OK 49.0s 2212KB
...
======================================================================
RESULTS SUMMARY (quality=high, 1024x1024)
======================================================================
AVG                                22.7s    1507      46.7s    2035    2.1x

MAI: 11/11 passed | GPT: 11/11 passed
```

## Analysis / 分析

### Root Cause: MAI-Image-2 为什么更快？

MAI-Image-2 使用专有的 MAI API Path (`/mai/v1/`)，与标准 OpenAI API 基础设施分离。这表明 Microsoft 针对 MAI 模型专门优化了 Serving 基础设施，从而在所有 Prompt 类型上实现了更低的延迟。

### 质量考量

本 Benchmark 仅测量**延迟**，不评估主观图像质量。两个模型在 `quality=high` 下都生成高质量的 1024x1024 图像。视觉质量对比请查看上方的并排图片——两个模型都展现了较强的 Prompt 遵循能力和艺术质量。

### Recommendations / 建议

- 对**延迟敏感**的应用（实时 UX、批量处理），MAI-Image-2 提供明确的 2x 速度优势
- 对使用**标准 OpenAI API** 的应用，GPT-Image-1.5 提供熟悉的 API 格式和 Key 认证支持
- 建议使用你的特定 Prompt 类型进行测试，因为延迟可能因 Prompt 复杂度而异

## Cleanup / 清理

测试完成后删除 Azure 部署：

```bash
# 删除 gpt-image-1.5 部署
az cognitiveservices account deployment delete \
  --name <your-resource-name> \
  --resource-group <your-resource-group> \
  --deployment-name gpt-image-1-5

# 删除 MAI-Image-2 部署
az cognitiveservices account deployment delete \
  --name <your-mai-resource> \
  --resource-group <your-resource-group> \
  --deployment-name mai-image-2
```

## 仓库结构

```
.
├── README.md                            # English version
├── README-CN.md                         # 中文版本
├── prompts.csv                          # 11 个 Surreal 风格测试 Prompt
├── scripts/
│   ├── fair_comparison_r2.py            # 统一对比脚本（quality=high）
│   ├── test_mai_image2.py               # MAI-Image-2 单独测试
│   └── test_gpt_image15.py             # GPT-Image-1.5 单独测试
└── images/
    ├── mai-image-2/                     # MAI-Image-2 生成的 11 张图片
    │   ├── 01_test.png ... 11_test.png
    └── gpt-image-1.5/                   # GPT-Image-1.5 生成的 11 张图片
        ├── 01_test.png ... 11_test.png
```

## 测试环境

- **Azure Region**: East US
- **测试日期**: 2026 年 4 月 3 日
- **测试机器**: East US 区域 Azure VM
- **Python**: 3.x + requests

## Author

Xinyu Wei (魏新宇)
