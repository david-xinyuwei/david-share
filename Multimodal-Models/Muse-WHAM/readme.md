##  深度解读微软 Muse / WHAM 世界模型与实战指南

在 2024 年底，微软 Research ‑ Game Intelligence 团队公开了 WHAM（World & Human Action Model）权重与代码，并在 Azure 与 Hugging Face 提供预训练端点。WHAM 能在给定 10 帧上下文的前提下，同时生成「下一帧游戏画面」与「玩家下一步手柄输入」。

在正式介绍内容之前，我先展示我的测试结果：我使用AML上model catalog上MUSE模型，基于下图预测后续50帧，并生成gif的效果。

原始图：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Muse-WHAM/images/1.png)

预测50帧后的gif，我们可以看到帧的顺序是流畅和符合逻辑的：

![示例GIF](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Muse-WHAM/images/dream_x4-50.gif)

这50帧对应的action列表如下：

| step | left_stick_x | left_stick_y | right_stick_x | right_stick_y | trigger_LT | trigger_RT | button_A | button_B | button_X | button_Y | dpad_up | dpad_down | dpad_left | dpad_right | skill_1 | skill_2 |
| ---- | ------------ | ------------ | ------------- | ------------- | ---------- | ---------- | -------- | -------- | -------- | -------- | ------- | --------- | --------- | ---------- | ------- | ------- |
| 1    | 0            | 0            | 1             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 10        | 6          | 5       | 5       |
| 2    | 0            | 0            | 1             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 9         | 6          | 5       | 5       |
| 3    | 0            | 0            | 1             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 9         | 7          | 5       | 5       |
| 4    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 8          | 5       | 5       |
| 5    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 8          | 5       | 5       |
| 6    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 9         | 8          | 5       | 5       |
| 7    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 9         | 8          | 5       | 5       |
| 8    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 8          | 5       | 5       |
| 9    | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 10   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 5       | 5       |
| 11   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 0       | 5       |
| 12   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 9          | 3       | 4       |
| 13   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 8          | 5       | 5       |
| 14   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 8          | 5       | 5       |
| 15   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 8         | 9          | 5       | 5       |
| 16   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 17   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 18   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 19   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 20   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 5       | 5       |
| 21   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 10         | 5       | 5       |
| 22   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 10         | 5       | 5       |
| 23   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 10         | 5       | 5       |
| 24   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 10         | 5       | 5       |
| 25   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 4         | 10         | 5       | 5       |
| 26   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 4         | 10         | 5       | 5       |
| 27   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 4         | 10         | 5       | 5       |
| 28   | 0            | 0            | 0             | 0             | 0          | 0          | 1        | 0        | 0        | 0        | 0       | 0         | 4         | 9          | 5       | 5       |
| 29   | 0            | 0            | 0             | 0             | 0          | 0          | 1        | 0        | 0        | 0        | 0       | 0         | 3         | 9          | 5       | 5       |
| 30   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 3         | 9          | 8       | 6       |
| 31   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 2         | 9          | 10      | 6       |
| 32   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 2         | 8          | 5       | 5       |
| 33   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 1         | 8          | 5       | 5       |
| 34   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 2         | 9          | 5       | 5       |
| 35   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 4         | 9          | 5       | 5       |
| 36   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 5       | 5       |
| 37   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 0       | 5       |
| 38   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 0       | 5       |
| 39   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 6         | 10         | 4       | 5       |
| 40   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 7         | 9          | 5       | 5       |
| 41   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 42   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 43   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 44   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 45   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 46   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 47   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 48   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 49   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 5          | 5       | 5       |
| 50   | 1            | 0            | 0             | 0             | 0          | 0          | 0        | 0        | 0        | 0        | 0       | 0         | 5         | 10         | 1       | 7       |



## 背景与动机

### 为什么 3D 游戏需要世界模型

游戏 AI 在过去 20 年多依赖脚本、有限状态机或手工设计的行为树。这些方法虽然稳定，但在以下场景会捉襟见肘：

- **内容创作**：关卡设计师希望快速「预演」不同场景、不同角色的交互，传统管线需要先写脚本、再进游戏引擎运行，迭代长且费人力。
- **AI 训练**：强化学习在 3D 环境中需要海量 roll‑out，Unity 或 Unreal 级别的真实引擎帧耗高，难以在大规模算力上并行。
- **玩家个性化**：自动生成大量非关键路径动画或场景状态，可极大降低美术与动画师成本。

世界模型（World Model）提供了一个解耦思路——**用神经网络近似「真实引擎 + 玩家行为」的联合分布**。只要模型在像素级别能合成可信画面，同时在动作空间上展现合理控制，就能在纯 GPU 或 TPU 上进行「快进」模拟，大幅压缩开发与训练成本。

### 选择《Bleeding Edge》作为数据源

- **技术原因**：Bleeding Edge 是一款第三人称 4v4 对战游戏，镜头跟随角色，动作多样，且官方可合法获得服务器录像与玩家输入。
- **数据规模**：一年时间、总计 27 990 名玩家、约 500 k 场对局。
- **授权与隐私**：所有录像和控制信号在内部匿名化处理，仅保留操作与像素，不含语音、聊天或玩家标识。

------

## Muse / WHAM 概览

| 指标             | 200 M 版  | 1.6 B 版  |
| ---------------- | --------- | --------- |
| 参数量           | 2.0 × 10⁸ | 1.6 × 10⁹ |
| ckpt 大小        | 3.7 GB    | 18.9 GB   |
| 单帧显存 (A6000) | ≈ 4 GB    | ≈ 28 GB   |
| 推理耗时 (A6000) | 32 ms     | 82 ms     |
| 训练 GPU         | 98×H100   | 同左      |
| 训练时长         | 5 天      | 同左      |

### 三种运行模式

| 模式             | 输入                         | 输出               | 典型用途                  |
| ---------------- | ---------------------------- | ------------------ | ------------------------- |
| World Model      | 10 帧画面 + 10 步动作        | 下一帧画面         | 物理 / 视觉预测、视频压缩 |
| Behaviour Policy | 10 帧画面                    | 下一步动作 (16‑维) | 机器人 / NPC 控制         |
| Full Generation  | 任意长度 prompt (画面或动作) | 下一帧画面 + 动作  | 故事 / 关卡素材生成       |

**亮点**：Muse 的 API 与强化学习的 (sₜ, aₜ) → sₜ₊₁ 完美对齐；开发者可直接把 Muse 视为「超高分辨率环境模拟器」，把上层 RL 或搜索算法无缝套进去。

------

## 数据与训练细节

### 数据管线

1. **原始录像**：服务器端 1080 p → 300 × 180 缩放；帧率下采样为 10 fps（平衡细节与 token 长度）。
2. **手柄信号**：XInput 格式读取，连续值（摇杆 / 扳机）保持浮点，离散按钮 one‑hot 化。
3. **切片**：按「10 帧 + 10 动作」滑窗，生成 (O₀, A₀, …, O₉, A₉, O₁₀) 序列。
4. **离散化图像**：VQ‑GAN encoder → 每张 300×180 图变 75×45×(codebook=1024) token，token 长度 ≈ 3375。
5. **合并序列**：视觉 token 与动作 token interleave，得到总 token ≈ 5560。

### 训练超参

```
batch_size          = 384        # tokens 级别
optimizer           = AdamW
lr_schedule         = cosine
weight_decay        = 0.01
dropout             = 0.1
fp16 + FlashAttention v2
```



- **目标函数**：Cross‑Entropy over next‑token；不需要额外 KL 或维数加权。
- **数据增广**：随机水平翻转、亮度 jitter，保证对称性。

------

## 模型架构深入解析

### VQ‑GAN 编解码器

- **Encoder**：4 层 down‑sampling ResNet，码本 size = 1024，维度 256。
- **Decoder**：对称上采样，并带 bilinear skip。
- **优势**：相比普通 CNN AutoEncoder，VQ‑GAN 提供离散 latent，更适合 Transformer token 化，也减少蓝色条纹伪影。

### Transformer 主干

- **类型**：GPT‑like decoder‑only。
- **深度 × 宽度**：200 M = 16 层 × 1024 hid，1.6 B = 48 层 × 2048。
- **位置编码**：1D learned；每个视觉 token 与动作 token 都有独立 slot。
- **跨模态融合**：Transformer treat 所有 token 同质；上下文中「动作」token 一样能被 attend，隐式学到因果映射。

### Token 排布

```
O0_t0 O0_t1 … O0_tN,   A0,   
O1_t0 … ON,   A1,                 ... , O9, A9,   <bos>
```

最后模型预测 O₁₀ 的图像 token；若训练「双头」，同时还预测 A₁₀。

------

## 16 维动作空间全拆解

| idx  | 名称          | float range | 原生含义   | 常见效果        |
| ---- | ------------- | ----------- | ---------- | --------------- |
| 1    | left_stick_x  | –1 ~ 1      | 横向平移   | –1 左移，1 右移 |
| 2    | left_stick_y  | –1 ~ 1      | 纵向平移   | –1 前进，1 后退 |
| 3    | right_stick_x | –1 ~ 1      | 摄像机水平 | –1 左旋，1 右旋 |
| 4    | right_stick_y | –1 ~ 1      | 摄像机垂直 | –1 向上，1 向下 |
| 5    | trigger_LT    | 0 ~ 1       | 瞄准/格挡  | 0.5 半按        |
| 6    | trigger_RT    | 0 ~ 1       | 攻击/射击  | 1 全按          |
| 7    | button_A      | 0/1         | 跳跃       |                 |
| 8    | button_B      | 0/1         | 闪避       |                 |
| 9    | button_X      | 0/1         | 轻击       |                 |
| 10   | button_Y      | 0/1         | 重击       |                 |
| 11   | dpad_up       | 0/1         | 表情/战吼  |                 |
| 12   | dpad_down     | 0/1         | 技能 3     |                 |
| 13   | dpad_left     | 0/1         | 切武器     |                 |
| 14   | dpad_right    | 0/1         | 切武器     |                 |
| 15   | skill_1       | 0/1         | 角色技能   |                 |
| 16   | skill_2       | 0/1         | 角色技能   |                 |

> 小实验：
> 把 **right_stick_x=1** 其余 0 → 视角以 ≈90°/s 速度顺时针；
> 把 **trigger_RT=1** → 大概率角色挥出一次普通攻击。

------

### Python 全流程脚本

脚本功能：

- 命令行 `--steps N` 控制帧数
- 自动检测 `actions` 字段；若无 → 随机 fallback
- 每帧做 Lanczos 4× / Real‑ESRGAN 超分
- 输出 raw PNG、超分 PNG、GIF、CSV

```
(AIF) root@pythonvm:~/AIFperformance# cat call_muse_iterative_debug.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
call_muse_iterative_debug.py  (2025‑04‑27)

功能
-----
1. 命令行 --steps N 控制生成帧数（默认 10）
2. 调 Muse / WHAM 端点，保存原帧 raw/ 与 4× Lanczos 帧 sr/
3. 生成 GIF (sr/dream_x4.gif)
4. 打印服务器响应前 2 KB；自动捕获任意 16‑维动作数组
5. 若端点无动作 → 使用“更丰富”的随机 fallback（摇杆+按钮），便于观察画面变化
依赖
-----
pip install pillow imageio
(可选 AI 超分) pip install realesrgan torch
"""

import argparse, base64, io, json, os, random, time, urllib.request
from typing import List, Optional
from PIL import Image
import imageio.v3 as imageio

# ========== 必改 ==========
ENDPOINT_URL = "https://xinyu-workspace-westus-qatee.westus.inference.ml.azure.com/score"      # ★改成你的
API_KEY      = "9Oms7vSUWIFwYpqSErPiJn0lBNdoywia2JIbUkGiVJ2IbksBKWBjJQQJ99BDAAAAAAAAAAAAINFRAZML27vQ"  
# ==========================

SLEEP_SEC   = 3
RAW_DIR, SR_DIR = "raw", "sr"
GIF_PATH, CSV_PATH = "sr/dream_x4.gif", "actions.csv"
PAYLOAD_PATH = "musePayload.txt"

# ---------- 是否启用 Real‑ESRGAN ----------
USE_SR = False    # True→需安装 realesrgan+torch

if USE_SR:
    try:
        from realesrgan import RealESRGAN
        import torch, numpy as np
        _dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _sr = RealESRGAN(_dev, 4); _sr.load_weights("RealESRGAN_x4.pth")
        print("✅ Real‑ESRGAN 4× 已启用")
    except Exception as e:
        print("⚠️  Real‑ESRGAN 初始化失败，回退 Lanczos:", e)
        USE_SR = False

def upsample(img: Image.Image) -> Image.Image:
    if USE_SR:
        import numpy as np
        return Image.fromarray(_sr.predict(np.array(img)))
    return img.resize((img.width*4, img.height*4), Image.Resampling.LANCZOS)

HEAD = ["left_stick_x","left_stick_y","right_stick_x","right_stick_y",
        "trigger_LT","trigger_RT","button_A","button_B","button_X","button_Y",
        "dpad_up","dpad_down","dpad_left","dpad_right","skill_1","skill_2"]

def build_headers(api_key:str):
    return {"Content-Type":"application/json",
            "Accept":"application/json",
            "Authorization":"Bearer "+api_key}

def fallback_action() -> List[float]:
    """更丰富的随机动作：摇杆 -1~1, RT 40%, 随机点方向键"""
    v = [0.0]*16
    v[0], v[1] = random.uniform(-1,1), random.uniform(-1,1)      # 左摇杆
    v[2], v[3] = random.uniform(-1,1), random.uniform(-1,1)      # 右摇杆
    v[5] = 1.0 if random.random()<0.4 else 0.0                   # RT
    dpad_index = 10 + random.randint(0,3)                        # 任一方向键
    v[dpad_index] = 1.0
    return v

def pil_to_b64(img: Image.Image, size=(300,180)) -> str:
    buf = io.BytesIO()
    img.resize(size, Image.Resampling.LANCZOS).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def muse_call(payload:dict, hdr:dict, url:str):
    req = urllib.request.Request(url, json.dumps(payload).encode(), hdr)
    with urllib.request.urlopen(req) as r:
        js = json.loads(r.read().decode())

    # 调试：打印前 2 KB
    print("── server response (first 2 KB) ──")
    print(json.dumps(js, indent=2)[:2048], "\n────────────────────────")

    img_b64 = js["results"][0]["image"]
    img = Image.open(io.BytesIO(base64.b64decode(img_b64)))

    act, act_key = None, None
    for k, v in js["results"][0].items():
        if isinstance(v, (list, tuple)) and len(v) == 16 and all(isinstance(x,(int,float)) for x in v):
            act, act_key = list(map(float, v)), k
            break
    return img, act, act_key, list(js["results"][0].keys())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=10, help="迭代帧数 (默认 10)")
    args = parser.parse_args()
    total_iter = args.steps

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(SR_DIR,  exist_ok=True)

    payload = json.load(open(PAYLOAD_PATH, "r", encoding="utf-8"))
    ctx, ctx_len = payload["input_data"]["context"], len(payload["input_data"]["context"])

    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write("step," + ",".join(HEAD) + "\n")

    hdr = build_headers(API_KEY)

    for step in range(total_iter):
        print(f"\n🚀 调用 {step+1}/{total_iter}")
        try:
            img, act, act_key, keys = muse_call(payload, hdr, ENDPOINT_URL)
        except Exception as e:
            print("❌ HTTP 错误：", e)
            break

        if act is None:
            act = fallback_action()
            print(f"⚠️  未检测到 16 维动作，使用随机 fallback (keys={keys})")
        else:
            print(f"✅ 捕获动作字段: '{act_key}'")

        # 保存图像
        raw_path = f"{RAW_DIR}/{step+1:02d}.png"; img.save(raw_path)
        upsample(img).save(f"{SR_DIR}/{step+1:02d}_x4.png")

        # 写 CSV
        with open(CSV_PATH, "a", encoding="utf-8") as f:
            f.write(f"{step+1}," + ",".join(map(str, act)) + "\n")

        # 更新 context
        if len(ctx) >= ctx_len:
            ctx.pop(0)
        ctx.append({"image": pil_to_b64(img), "actions": act, "actions_output": act, "tokens": []})

        if step < total_iter - 1:
            time.sleep(SLEEP_SEC)

    # 合成 GIF
    frames = [imageio.imread(f"{SR_DIR}/{i+1:02d}_x4.png") for i in range(step+1)]
    imageio.imwrite(GIF_PATH, frames, duration=0.25, loop=0)
    print(f"\n🎉 完成 {step+1} 帧。GIF: {GIF_PATH}  CSV: {CSV_PATH}")

if __name__ == "__main__":
    main()
```



