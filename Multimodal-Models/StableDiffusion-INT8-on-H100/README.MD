## StableDiffusion INT8 on H100
在单H100上测试Stable Diffusion XL1.0，验证了一下int8的效果。英伟达声称在H100上，INT8比A100上有优化。

参照repo：

***https://github.com/NVIDIA/TensorRT/tree/release/10.0/demo/Diffusion***

选择TRT10版本的分支进行验证。

#### 根据单个文本提示，使用SDXL以FP16生成图像。


***#python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --hf-token=$HF_TOKEN --version=xl-1.0***


运行时间：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL1U7icPciauNdgMibolw6d6271Jky8kPMKDjw8r17Xy2hvFXnC8BDAyNgA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

图片生成效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLFQhCfrkBOB5LzDp7gvdvpmSXKIpCOEcLL0Q3DAZxAftcAyTjialpOQw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

使用SDXL & INT8 AMMO量化：

- 

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --onnx-dir onnx-sdxl --engine-dir engine-sdxl --int8
```

执行上述命令后，会先对模型进行8位量化。

Building TensorRT engine for onnx/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.opt/model.onnx: engine/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.trt10.0.1.plan

然后再进行推理。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLPallL3kz4wXl2Gz53ZgKHQt9BElISrojuSauMpQ2Ig7ZE4icu322zaA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

查看推理生成的图片：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLJ6Q5Yib3PuDusic7VhLaxJculL2GKicQyiaApnkmwygjuPdFibfoebyoibzg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

我看看到图片生成的质量是相同的，图片占用空间大小也几乎是一样的。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLjT8uL9PfwiaicpxEuGp5zic41GmHU5TCKXR4dsjDdh5IwgUg1c5DJ4VzQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

我们看到INT8的推理速度比FP16增加了20%。

root@d6865c4fc3d8:/workspace/demo/Diffusion# ls -al onnx-sdxl

- 
- 
- 
- 
- 
- 
- 
- 
- 
- 
- 

```
total 408drwxr-xr-x 10 root root   4096 May 21 06:34 .drwx------ 11 root root   4096 May 21 06:34 ..drwxr-xr-x  2 root root   4096 May 21 06:34 clipdrwxr-xr-x  2 root root   4096 May 21 06:34 clip.optdrwxr-xr-x  2 root root   4096 May 21 06:34 clip2drwxr-xr-x  2 root root   4096 May 21 06:35 clip2.optdrwxr-xr-x  2 root root 376832 May 21 06:40 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8drwxr-xr-x  2 root root   4096 May 21 06:41 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.optdrwxr-xr-x  2 root root   4096 May 21 06:41 vaedrwxr-xr-x  2 root root   4096 May 21 06:41 vae.opt
```



root@d6865c4fc3d8:/workspace/demo/Diffusion# ls -al engine-sdxl

- 
- 
- 
- 
- 
- 
- 

```
total 4755732drwxr-xr-x  2 root root       4096 May 21 06:48 .drwx------ 11 root root       4096 May 21 06:34 ..-rw-r--r--  1 root root  248576668 May 21 06:41 clip.trt10.0.1.plan-rw-r--r--  1 root root 1395532052 May 21 06:42 clip2.trt10.0.1.plan-rw-r--r--  1 root root 2880794876 May 21 06:47 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.trt10.0.1.plan-rw-r--r--  1 root root  344938836 May 21 06:48 vae.trt10.0.1.plan
```



如果您已经拥有量化的模型，并且只想进行推理，不需要再次进行量化，那么您可以简化命令行接口（CLI）以专注于加载和使用现有的量化模型进行推理。根据您提供的命令，如果量化模型已经存在并且已经转换为TensorRT引擎格式，您可以直接使用这些引擎文件进行推理。

假设您的量化模型已经是TensorRT引擎格式，并且存储在 `engine-dir` 目录中，CLI可以保持大部分参数不变，主要是确保不再触发任何量化或模型转换的过程。以下是修改后的CLI示例：



- 

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --engine-dir engine-sdxl  
```



 推理速递是0.61，看起来和FP16的持平：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLfDFZMB5T0NTDYwXjjQe1xicC6SPsca9Mf4sqImiaKSlcC9q8nbkzuHCA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLd3ooKlI2DOcQd5fV4mKHhzUHF9WJd1X2fgV10ziciaGz4xduGJA8ukMw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在上述cli末尾增加--int8，推理速度增加20%：



- 

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --engine-dir engine-sdxl --int8
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLgZJjkboPDPUb35icSsfhgSjiaadQHic9ntwRUiaIpVtLGialI1kFpBHtPaA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLHVVQWqXKdiaiaq2eTngSia2VWiaoGhIL7rNkRpcYUwYaGHvgqB739caYHA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在使用TensorRT进行推理时，指定 `--onnx-dir` 参数通常是在以下几种情况下需要：

1. **引擎构建阶段**：如果您需要从ONNX模型构建TensorRT引擎文件，那么需要指定 `--onnx-dir` 来告诉程序从哪个目录加载ONNX模型文件。这是因为TensorRT引擎构建过程需要读取ONNX模型，然后进行优化和编译以生成针对特定硬件优化的引擎文件。
2. **引擎更新或重新构建**：当原始模型发生变化，或者需要针对新的硬件配置优化引擎时，您可能需要重新从ONNX模型生成新的TensorRT引擎文件。在这种情况下，也需要指定 `--onnx-dir` 来加载最新的ONNX模型。
3. **缺少预构建的引擎文件**：如果出于某种原因，预构建的TensorRT引擎文件不可用或丢失，系统可能需要回退到从ONNX模型动态构建引擎。在这种情况下，指定 `--onnx-dir` 是必要的，以确保系统能够找到并加载ONNX模型进行引擎构建。
4. **首次部署或测试**：在首次部署模型或进行性能测试时，您可能会从ONNX模型开始，构建并测试不同配置的TensorRT引擎，以找到最优的设置。这时，指定 `--onnx-dir` 是进行这些操作的前提。

假设您正在开发一个新的推理应用，需要从头开始构建TensorRT引擎，您的CLI命令可能会包括 `--onnx-dir` 参数，如下所示：

- 

```
python3 inference_script.py --version model_version --onnx-dir path_to_onnx_models --engine-dir path_to_save_engines
```

 
在这个命令中，`--onnx-dir` 指定了ONNX模型文件的位置，这些模型文件将被用来构建TensorRT引擎文件，而构建好的引擎文件将被保存在通过 `--engine-dir` 指定的目录中。

总之，`--onnx-dir` 主要在需要从ONNX模型构建或重新构建TensorRT引擎文件的情况下使用。如果您已经有了预构建的引擎文件，并且只需要进行推理，那么通常不需要指定这个参数。



接下来，我们看SD另外两种加速推理的方法：



### 使用 SDXL + LCM（Latent Consistency Model）LoRA 权重加快文本到图像的转换速度

- 

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --lora-path "latent-consistency/lcm-lora-sdxl" --lora-scale 1.0 --onnx-dir onnx-sdxl-lcm-nocfg --engine-dir engine-sdxl-lcm-nocfg --denoising-steps 4 --scheduler LCM --guidance-scale 0.0
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL6l3ExIj5FSxacKUg8sgtcbPKY0TSooyPoNXiaOiboWc7y3NA3wIzZ2FQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLzwC3tnAl5keulJZR0LPPmbibfQAbm0n5GicqibEO7gF4cu7etcxqPnWwg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

使用 SDXL Turbo 加快文本到图像的速度，下面cli生成512*512的图片。

- 

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-turbo --onnx-dir onnx-sdxl-turbo --engine-dir engine-sdxl-turbo --denoising-steps 1 --scheduler EulerA --guidance-scale 0.0 --width 512 --height 512
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL1xsEZHufSsUBzKvRxoqwMF8B8ycPc71s4TFAibjpPCXQjEdEzws7AvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLYPhPq9PzdYepCor0L9R63AoYtcSzlLs05yucVWd3ZH8tnQIt8MrpDg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

整体上看，还是INT8+SDXL 1.0可以兼顾生成图片的质量以及推理速度。