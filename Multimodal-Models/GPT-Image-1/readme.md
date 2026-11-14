> [!NOTE]
> **Archived.** This project predates June 2026 and uses models or APIs that have since been superseded (GPT-Image-1). It stays here so existing links keep working; check current documentation before reusing the steps. Newer related work: [GPT-Image-2-Token-Bucket-Benchmark](../GPT-Image-2-Token-Bucket-Benchmark/).

```
(base) root@linuxworkvm:~# bash generate_image.sh 
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 2008k  100 2008k  100   139  77516      5  0:00:27  0:00:26  0:00:01  481k
图片已生成并保存为: generated_image.png
Request ID: <resource-id>
(base) root@linuxworkvm:~#
```


## Running on Azure

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |
