**一\**、\**stable-diffusion-webui****
**使用如下开源项目：

https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Command-Line-Arguments-and-Settings

LoRA  (Low-Rank Adaptation) 模型，称为小稳定扩散模型，在传统检查点模型中进行了细微调整。LoRA模型的链接包括：像素艺术、幽灵、Barbicore、赛博格以及受Greg Rutkowski启发的风格。LoRA模型不能独立运作，它需要与模型checkpoints协同工作。LoRA通过对相应模型文件引入微妙变化，带来风格上的差异。此外，随着SDXL的发布，StabilityAI已经确认，他们期望在SDXL v1.0基础模型上，LoRA将成为增强图像最流行的方式。LoRA模型可以在https://civitai.com/ 或 https://huggingface.co/ 上找到。

例如我们可以下载下面的LoRA。

https://civitai.com/models/331116?modelVersionId=464939

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXt9kPiaorbF7tPBH1EEwCOuhZj7sj77wmfPic1KcRDoHUjP0OISicrAhZEe8mODz7JXia40yJX1WegHQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

运行stable-diffusion-webui，验证文字生图。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7NoQCibFicCQrGiaZeBZ6wQIicicXgHM3DftSYF5WO1ialRxBj3xtj9FHiaosw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7eqrvj4JfkJxL4nLh5x0rrhibEUicMSVTeAeGrWPjxXoovVpUo5uhLAAQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

接下来，验证图生图，在原图上增加个眼镜，图别的部分不变：

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7Zj4gUmddIR5d6vrh6pfT4JVbvQR5gzMMZic7u3FWyBQfAQFqywwXmEA/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

资源利用率如下：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7UDcXznE99LMGnRwrzy7S9E8utbZqa5IsZtn6F2rp0oYMNjuPoZDvow/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

使用相同的prompt和超参，换一个模型ponyFaetality_v11.safetensors，生成的结果如下：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7MICbMbYU4UsKqVjXxunI6Ib8KV5ZzFp5LenMXMMJZkZFav0pG2gJZw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

根据图生图，给原图女孩增加一顶红色的帽子：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7oiagkjkkGEX9BicjtElmJv20HAcAuHia8iaib7kGR4gUgWa2fZE0Njjhggw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

接下来，定位置修图，将帽子换成黄色（我故意把mask的图留一点红边以验证像素的准确性）。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7NYhWwxOg4MbuWGqxibGJG8SJBJldskenxACSSecSmDgC375wXPeW4Mw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr78EdI7TfcZhuuFuCwvVDCsDSbqzgfibMRz1sDkK8tXwqIyHpDD8TB6aw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

效果很不错。



**二.LoRA的验证**

LoRA没法独立运行，需要与基础模型配合。通常LoRA下载的页面会标明它需要的基础模型。

如：https://civitai.com/models/12597/moxin

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xQzUkm16rndFqo9EkIL1F3G4UuhXo2p1BHf2CfxNkFtEoRnRE60yRw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

上述LoRA需要的基础模型就是SD 1.5。

使用上述LoRA以及SD 1.5，与上一篇相同的prompt和超参的条件下，生成的图片如下：

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xCibnV2JbjhYlxhABooUVj6jR1sWwT7ZeibhHicrHfsAXkgVByNfhtib8w/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr77z2xDVz5KgPqqgElstFaVT0j58vFtFB5ByozPs8HGBVq2LpMIkKrpw/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**二、\**Refiner的验证\****

Stability AI是一家专注于开发深度学习模型的公司，其产品包括一系列用于生成图像和视频的模型。以下是Stability AI模型的发展和进化史的概述：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7hb1ETFYn8NXXIPPMa1kpzpUzz2OxQicibsnkUdnco753zkmVPnmoJUwQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



- Stable Diffusion：Stable Diffusion是一种深度生成人工神经网络，也被称为潜在扩散模型。它主要用于生成详细的图像，这些图像是根据文本描述进行条件设置的，尽管它也可以应用于其他任务，如修复图像、扩展图像和生成由文本提示引导的图像到图像的转换。
- SDXL：这是Stability AI的最新图像生成模型，它是在Stable Diffusion的基础上进行改进的。SDXL使用基础模型进行高噪声扩散阶段，然后使用refiner模型进行低噪声扩散阶段。SDXL的基础分辨率是1024x1024，它能生成几乎任何艺术风格的高质量图像，特别适合生成充满活力和准确色彩的图像。
- Stable Video Diffusion：这是Stability AI开发的一种可以生成视频的模型。它是Stability AI开源模型系列的一部分。
- StableStudio：这是Stability AI的主要界面，用于其新模型和功能2。它最近升级为使用SDXL，我们的最新图像生成模型。



以下是SD模型和SDXL模型的一些主要区别：

- 设计和架构：SDXL使用基础模型进行高噪声扩散阶段，然后使用refiner模型进行低噪声扩散阶段。而SD模型没有这样的设计。
- 分辨率：SDXL的基础分辨率是1024x1024，而SD模型的基础分辨率可能是512x512。因此，SDXL版本无疑具有更高的基础图像分辨率。
- 性能：SDXL在处理非线性数据、分解信号和提取微妙差异方面表现出色。而SD模型适合分析空间和时间动态，提供准确的模式和趋势预测。然而，SDXL可能在处理大型数据集时会遇到困难，而SD模型可能在处理突变时会遇到问题。
- 训练和生成速度：SDXL的生成和训练速度可能比SD模型慢。



选择使用SDXL模型还是SD模型，主要取决于你的具体需求和应用场景。

- 如果你需要生成高分辨率的图像，或者你的项目需要处理非线性数据、分解信号和提取微妙差异，那么SDXL模型可能是更好的选择。
- 如果你的项目需要快速生成图像，或者你的数据集较大，那么SD模型可能更适合你。

虽然SDXL模型在某些方面可能优于SD模型，但这并不意味着SD模型没有价值。SD模型在处理空间和时间动态，提供准确的模式和趋势预测方面表现出色。因此，根据你的具体需求和资源，SD模型可能是一个很好的选择。



上图提到的SDXL 1.0 base+refiner是一个组合模型。首先，使用基础模型（Base）生成有噪音的潜在变量，然后再由专门用于去噪的精修模型（refiner）进一步处理。经过refiner模型进一步处理的图像对比度更高，发丝的边缘处理更好。

关于下载，SDXL 1.0 BASE和refiner这两个模型是需要单独下载的。你可以在Stability AI的GitHub页面或者其他相关网站找到这两个模型的下载链接。下载完成后，你需要将这两个模型文件放到指定的文件夹中。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7n87icfic5U7ylw82fxiafIXQpp1e6rVgv5XqNLCiaY95ibhsuMW1mlt1QIg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7125jAlm5I56vJaZg4FtmslhxwR2COOrVcAAET4MeTvz0jyicx55cj9A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7IHbcEh079ujHds1j2Q6EHtLKW6rfYnGdhoLv9ziaY16E0K8WoibGKibaw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

我们下载refiner，然后放到和模型相同的目录下，就可以用了。

https://huggingface.co/ptx0/sdxl-refiner/tree/main

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7wMvrLJ2InmydVTLEAefcUeLRIEXoy5OC8v0fmkjWd5ZnDWf6wGxFqg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**三、对比验证**

理论上，SDXL 1.0 BASE、refiner和LoRa可以一起使用。但实测效果是启用了refiner以后，LoRA并没有发挥出作用。LoRA对XL模型也没有发挥出作用。

juggernautXL_juggXRundiffusion.safetensors模型的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7Y6SeFZLxJjnh0juibIiakvib4qLydwicvibfGRZ2icng3waUibyLPe7TM7RHA/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

juggernautXL_juggXRundiffusion.safetensors+MoXinV1.safetensors(LoRA)的效果与上图不加LoRA相同。

v1-5-pruned-emaonly.safetensors [6ce0161689]+sd_xl_refiner_1.0.safetensors的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7lqALeDIbywHQcuBA0ibib8sukCGCLY48ia12xa2cRAw9CacfZHEyoW6sg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

v1-5-pruned-emaonly.safetensors [6ce0161689]+sd_xl_refiner_1.0.safetensors+MoXinV1.safetensors(LoRA)的效果与上图不加LoRA相同。

v1-5-pruned-emaonly.safetensors的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7uYf6q9rposy6zzmGknQOVqWGxneUy20f9pEM0YpnLSr6O33ficoC5YQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

v1-5-pruned-emaonly.safetensors+MoXinV1.safetensors(LoRA)的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr75ib4cTcGnKdDwiayQxQDygibEsnDZZ4Ghm4HEzVtnoAENpTSv9DZ2w2HA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**四、一些微调好的模型**

在实际使用中，个人使用的话，用C站上微调好的模型或者HF上其他公司发布的开源模型就可以，大多数情况不用再单独加载Refiner。

下面这个网站既可以下载XL模型，也可以下载LoRA。

https://civitai.com/models

例如下图就是个LoRA模型，它所依赖的基础模型是SDXL，需要单独下载。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7FsQBkKJyGjiagic02TmJGWL0MicxUoYmIHZyfuOuVhNVE70ibicZldUDPiag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)





**一.LoRA的验证**

LoRA没法独立运行，需要与基础模型配合。通常LoRA下载的页面会标明它需要的基础模型。

如：https://civitai.com/models/12597/moxin

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xQzUkm16rndFqo9EkIL1F3G4UuhXo2p1BHf2CfxNkFtEoRnRE60yRw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

上述LoRA需要的基础模型就是SD 1.5。

使用上述LoRA以及SD 1.5，与上一篇相同的prompt和超参的条件下，生成的图片如下：

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xCibnV2JbjhYlxhABooUVj6jR1sWwT7ZeibhHicrHfsAXkgVByNfhtib8w/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr77z2xDVz5KgPqqgElstFaVT0j58vFtFB5ByozPs8HGBVq2LpMIkKrpw/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**二、\**Refiner的验证\****

Stability AI是一家专注于开发深度学习模型的公司，其产品包括一系列用于生成图像和视频的模型。以下是Stability AI模型的发展和进化史的概述：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7hb1ETFYn8NXXIPPMa1kpzpUzz2OxQicibsnkUdnco753zkmVPnmoJUwQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



- Stable Diffusion：Stable Diffusion是一种深度生成人工神经网络，也被称为潜在扩散模型。它主要用于生成详细的图像，这些图像是根据文本描述进行条件设置的，尽管它也可以应用于其他任务，如修复图像、扩展图像和生成由文本提示引导的图像到图像的转换。
- SDXL：这是Stability AI的最新图像生成模型，它是在Stable Diffusion的基础上进行改进的。SDXL使用基础模型进行高噪声扩散阶段，然后使用refiner模型进行低噪声扩散阶段。SDXL的基础分辨率是1024x1024，它能生成几乎任何艺术风格的高质量图像，特别适合生成充满活力和准确色彩的图像。
- Stable Video Diffusion：这是Stability AI开发的一种可以生成视频的模型。它是Stability AI开源模型系列的一部分。
- StableStudio：这是Stability AI的主要界面，用于其新模型和功能2。它最近升级为使用SDXL，我们的最新图像生成模型。



以下是SD模型和SDXL模型的一些主要区别：

- 设计和架构：SDXL使用基础模型进行高噪声扩散阶段，然后使用refiner模型进行低噪声扩散阶段。而SD模型没有这样的设计。
- 分辨率：SDXL的基础分辨率是1024x1024，而SD模型的基础分辨率可能是512x512。因此，SDXL版本无疑具有更高的基础图像分辨率。
- 性能：SDXL在处理非线性数据、分解信号和提取微妙差异方面表现出色。而SD模型适合分析空间和时间动态，提供准确的模式和趋势预测。然而，SDXL可能在处理大型数据集时会遇到困难，而SD模型可能在处理突变时会遇到问题。
- 训练和生成速度：SDXL的生成和训练速度可能比SD模型慢。



选择使用SDXL模型还是SD模型，主要取决于你的具体需求和应用场景。

- 如果你需要生成高分辨率的图像，或者你的项目需要处理非线性数据、分解信号和提取微妙差异，那么SDXL模型可能是更好的选择。
- 如果你的项目需要快速生成图像，或者你的数据集较大，那么SD模型可能更适合你。

虽然SDXL模型在某些方面可能优于SD模型，但这并不意味着SD模型没有价值。SD模型在处理空间和时间动态，提供准确的模式和趋势预测方面表现出色。因此，根据你的具体需求和资源，SD模型可能是一个很好的选择。



上图提到的SDXL 1.0 base+refiner是一个组合模型。首先，使用基础模型（Base）生成有噪音的潜在变量，然后再由专门用于去噪的精修模型（refiner）进一步处理。经过refiner模型进一步处理的图像对比度更高，发丝的边缘处理更好。

关于下载，SDXL 1.0 BASE和refiner这两个模型是需要单独下载的。你可以在Stability AI的GitHub页面或者其他相关网站找到这两个模型的下载链接。下载完成后，你需要将这两个模型文件放到指定的文件夹中。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7n87icfic5U7ylw82fxiafIXQpp1e6rVgv5XqNLCiaY95ibhsuMW1mlt1QIg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7125jAlm5I56vJaZg4FtmslhxwR2COOrVcAAET4MeTvz0jyicx55cj9A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7IHbcEh079ujHds1j2Q6EHtLKW6rfYnGdhoLv9ziaY16E0K8WoibGKibaw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

我们下载refiner，然后放到和模型相同的目录下，就可以用了。

https://huggingface.co/ptx0/sdxl-refiner/tree/main

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7wMvrLJ2InmydVTLEAefcUeLRIEXoy5OC8v0fmkjWd5ZnDWf6wGxFqg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**三、对比验证**

理论上，SDXL 1.0 BASE、refiner和LoRa可以一起使用。但实测效果是启用了refiner以后，LoRA并没有发挥出作用。LoRA对XL模型也没有发挥出作用。

juggernautXL_juggXRundiffusion.safetensors模型的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7Y6SeFZLxJjnh0juibIiakvib4qLydwicvibfGRZ2icng3waUibyLPe7TM7RHA/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

juggernautXL_juggXRundiffusion.safetensors+MoXinV1.safetensors(LoRA)的效果与上图不加LoRA相同。

v1-5-pruned-emaonly.safetensors [6ce0161689]+sd_xl_refiner_1.0.safetensors的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7lqALeDIbywHQcuBA0ibib8sukCGCLY48ia12xa2cRAw9CacfZHEyoW6sg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

v1-5-pruned-emaonly.safetensors [6ce0161689]+sd_xl_refiner_1.0.safetensors+MoXinV1.safetensors(LoRA)的效果与上图不加LoRA相同。

v1-5-pruned-emaonly.safetensors的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7uYf6q9rposy6zzmGknQOVqWGxneUy20f9pEM0YpnLSr6O33ficoC5YQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

v1-5-pruned-emaonly.safetensors+MoXinV1.safetensors(LoRA)的效果：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr75ib4cTcGnKdDwiayQxQDygibEsnDZZ4Ghm4HEzVtnoAENpTSv9DZ2w2HA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**五、一些微调好的模型**

在实际使用中，个人使用的话，用C站上微调好的模型或者HF上其他公司发布的开源模型就可以，大多数情况不用再单独加载Refiner。

下面这个网站既可以下载XL模型，也可以下载LoRA。

https://civitai.com/models

例如下图就是个LoRA模型，它所依赖的基础模型是SDXL，需要单独下载。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7FsQBkKJyGjiagic02TmJGWL0MicxUoYmIHZyfuOuVhNVE70ibicZldUDPiag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**六、Web-UI启动方式**

david@h100vm:~$ python3 --version

Python 3.10.14

david@h100vm:~$ source /home/david/stable-diffusion-webui/venv/bin/activate

(venv) david@h100vm:~$ sudo apt-get install python3.10-venv

(venv) david@h100vm:~$ python3 get-pip.py

(venv) david@h100vm:~$ bash webui.sh --listen

http://h100vm.eastus.cloudapp.azure.com:7860/

![Image](C:\Users\xinyuwei\AppData\Local\Temp\Image.png)

![Image](C:\Users\xinyuwei\AppData\Local\Temp\Image.png)

![Image](C:\Users\xinyuwei\AppData\Local\Temp\Image.png)

图生图是提示词累加：

![image-20240729190504852](C:\Users\xinyuwei\AppData\Roaming\Typora\typora-user-images\image-20240729190504852.png)

![image-20240729190519795](C:\Users\xinyuwei\AppData\Roaming\Typora\typora-user-images\image-20240729190519795.png)