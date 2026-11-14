> [!NOTE]
> **已归档。** 本项目写于 2026 年 6 月之前，所用模型、API 或工具版本可能已经变化。保留在这里是为了让已有链接继续可用；复用其中步骤前请先核对最新文档。

```
pip install git+https://github.com/sberbank-ai/Real-ESRGAN.git
```


## 在 Azure 上运行

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


```
pip install huggingface_hub==0.16.4
```

```
import torch
from PIL import Image
import numpy as np
from RealESRGAN import RealESRGAN

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = RealESRGAN(device, scale=4)
model.load_weights('weights/RealESRGAN_x4.pth', download=True)
#model.load_weights('weights/RealESRGAN_x2plus.pth', download=True)
#model.load_weights('weights/RealESRGAN_x8.pth', download=True)

path_to_image = './low_resolution_input.png'
image = Image.open(path_to_image).convert('RGB')
sr_image = model.predict(image)

sr_image.save('./sr_image-4.png')
```





