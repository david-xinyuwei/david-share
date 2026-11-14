> [!NOTE]
> **已归档。** 本项目写于 2026 年 6 月之前，所用模型或 API 已有更新版本（GPT-Image-1）。保留在这里是为了让已有链接继续可用；复用其中步骤前请先核对最新文档。新的相关项目：[GPT-Image-2-Token-Bucket-Benchmark](../GPT-Image-2-Token-Bucket-Benchmark/)。

```
(base) root@linuxworkvm:~# bash generate_image.sh 
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 2008k  100 2008k  100   139  77516      5  0:00:27  0:00:26  0:00:01  481k
图片已生成并保存为: generated_image.png
Request ID: <resource-id>
(base) root@linuxworkvm:~#
```


## 在 Azure 上运行

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


