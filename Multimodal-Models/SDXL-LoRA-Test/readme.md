# SDXL and LoRA test


## Stability AI Models
Stability AI is a company focused on developing deep learning models, with products that include a range of models for generating images and videos. Here is an overview of the development and evolution of Stability AI's models:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7hb1ETFYn8NXXIPPMa1kpzpUzz2OxQicibsnkUdnco753zkmVPnmoJUwQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

- **Stable Diffusion**: Stable Diffusion is a type of deep generative artificial neural network, also known as a latent diffusion model. It is primarily used to generate detailed images that are conditionally set based on text descriptions, although it can also be applied to other tasks such as image restoration, image extension, and generating image-to-image transformations guided by text prompts.  
  
- **SDXL**: This is Stability AI's latest image generation model, an improvement upon Stable Diffusion. SDXL uses a base model for the high-noise diffusion stage and then employs a refiner model for the low-noise diffusion stage. The base resolution of SDXL is 1024x1024, and it can generate high-quality images in almost any artistic style, particularly excelling in producing vibrant and accurate colors.  
  
- **Stable Video Diffusion**: This is a model developed by Stability AI that can generate videos. It is part of Stability AI's open-source model series.  
  
- **StableStudio**: This is Stability AI's main interface for its new models and features. It has recently been upgraded to use SDXL, our latest image generation model.  
  
The following are some key differences between the SD model and the SDXL model:  
  
- **Design and Architecture**: SDXL uses a base model for the high-noise diffusion stage and then employs a refiner model for the low-noise diffusion stage. The SD model does not have such a design.  
  
- **Resolution**: The base resolution of SDXL is 1024x1024, whereas the base resolution of the SD model might be 512x512. Therefore, the SDXL version undoubtedly has a higher base image resolution.  
  
- **Performance**: SDXL excels in handling nonlinear data, decomposing signals, and extracting subtle differences. The SD model is suitable for analyzing spatial and temporal dynamics, providing accurate pattern and trend predictions. However, SDXL may encounter difficulties when handling large datasets, while the SD model may face issues when dealing with mutations.  
  
- **Training and Generation Speed**: The generation and training speed of SDXL may be slower than that of the SD model. Choosing between the SDXL model and the SD model mainly depends on your specific needs and application scenarios.  
  
  - If you need to generate high-resolution images or your project requires handling nonlinear data, decomposing signals, and extracting subtle differences, the SDXL model might be a better choice.  
    
  - If your project requires fast image generation or your dataset is large, the SD model might be more suitable for you.  
  
Although the SDXL model may outperform the SD model in certain aspects, this does not mean that the SD model lacks value. The SD model excels in handling spatial and temporal dynamics, providing accurate pattern and trend predictions. Therefore, depending on your specific needs and resources, the SD model might be a great choice.  


## stable-diffusion-webui
I se the stable-diffusion-webui to do test:

*https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Command-Line-Arguments-and-Settings*

```
david@h100vm:~$ python3 --version

Python 3.10.14

david@h100vm:~$ source /home/david/stable-diffusion-webui/venv/bin/activate

(venv) david@h100vm:~$ sudo apt-get install python3.10-venv

(venv) david@h100vm:~$ python3 get-pip.py

(venv) david@h100vm:~$ bash webui.sh --listen

```
http://h100vm.eastus.cloudapp.azure.com:7860/

## Image to Image
Run stable-diffusion-webui and verify the text-image.

Use SDXL mode: *https://civitai.com/models/133005/juggernaut-xl* for testing.

On the above link, click the imnage, you could get the prompt and SD metadata:

*https://civitai.com/images/10895925*

```
- Prompt
beautiful lady,(a very very  little freckles), white skin, big smile, brown hazel eyes, short hair, rainbow color hair, dark makeup, hyperdetailed photography, soft light, head and shoulders portrait, cover

- Negtive Prompt
bad eyes, cgi, airbrushed, plastic, watermark
```
Other metadata:
```
Guidance: 2
Steps: 6
Sampler: DPM++ SDE
Seed: 886204265
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7NoQCibFicCQrGiaZeBZ6wQIicicXgHM3DftSYF5WO1ialRxBj3xtj9FHiaosw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7eqrvj4JfkJxL4nLh5x0rrhibEUicMSVTeAeGrWPjxXoovVpUo5uhLAAQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Next, verify the image-to-image process by adding glasses to the original image while keeping the other parts unchanged(prompt accumulation):

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7Zj4gUmddIR5d6vrh6pfT4JVbvQR5gzMMZic7u3FWyBQfAQFqywwXmEA/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


Using the same prompt and hyperparameters, use the model ponyFaetality_v11.safetensors. The generated result is as follows(prompt accumulation):

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/SDXL-LoRA-Test/images/4.png)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7MICbMbYU4UsKqVjXxunI6Ib8KV5ZzFp5LenMXMMJZkZFav0pG2gJZw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Based on the image-to-image process, add a red hat to the girl in the original image:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7oiagkjkkGEX9BicjtElmJv20HAcAuHia8iaib7kGR4gUgWa2fZE0Njjhggw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Resource utilization rates are shown below:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7UDcXznE99LMGnRwrzy7S9E8utbZqa5IsZtn6F2rp0oYMNjuPoZDvow/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Next, perform position-specific editing to change the hat to yellow (I intentionally left a bit of a red edge on the mask to verify pixel accuracy).


![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7NYhWwxOg4MbuWGqxibGJG8SJBJldskenxACSSecSmDgC375wXPeW4Mw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr78EdI7TfcZhuuFuCwvVDCsDSbqzgfibMRz1sDkK8tXwqIyHpDD8TB6aw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


## SD BaseModle + LoRA Configuration

The LoRA (Low-Rank Adaptation) model, referred to as the small Stable Diffusion model, involves subtle adjustments to traditional checkpoint models. The links for LoRA models include: pixel art, ghost, Barbicore, cyborg, and styles inspired by Greg Rutkowski. The LoRA model cannot operate independently; it needs to work in conjunction with model checkpoints. 

Typically, the download page for LoRA will specify the required base model.

For example：https://civitai.com/models/12597/moxin

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xQzUkm16rndFqo9EkIL1F3G4UuhXo2p1BHf2CfxNkFtEoRnRE60yRw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


Upload LoRA model to Web-UI folder which is differentg from SD:

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/SDXL-LoRA-Test/images/3.png)

Run LoRA model test-image:

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7xCibnV2JbjhYlxhABooUVj6jR1sWwT7ZeibhHicrHfsAXkgVByNfhtib8w/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr77z2xDVz5KgPqqgElstFaVT0j58vFtFB5ByozPs8HGBVq2LpMIkKrpw/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


## SD BaseModle + Refiner Configuration
The SDXL 1.0 base+refiner is a combined model. First, the base model generates noisy latent variables, which are then further processed by a refiner model specifically designed for denoising. Images processed by the refiner model have higher contrast and better edge handling for details like hair strands.  

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7n87icfic5U7ylw82fxiafIXQpp1e6rVgv5XqNLCiaY95ibhsuMW1mlt1QIg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The SDXL 1.0 BASE and refiner models need to be downloaded separately. You can find the download links for these two models on Stability AI's GitHub page or other related websites. After downloading, you need to place these two model files in the specified folder.  

We download the refiner and place it in the same directory as the model, and it will be ready to use. 

https://huggingface.co/ptx0/sdxl-refiner/tree/main

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7wMvrLJ2InmydVTLEAefcUeLRIEXoy5OC8v0fmkjWd5ZnDWf6wGxFqg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7125jAlm5I56vJaZg4FtmslhxwR2COOrVcAAET4MeTvz0jyicx55cj9A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7IHbcEh079ujHds1j2Q6EHtLKW6rfYnGdhoLv9ziaY16E0K8WoibGKibaw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## SDXL effect : sdxlnijiseven

SDXL is very enough, 

sdxlNijiSeven_sdxlNijiSever

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/SDXL-LoRA-Test/images/1.jpeg)

But some SDXL also has a counterpart in LoRA. The image below its base model is SDXL, which needs to be downloaded separately.  

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7FsQBkKJyGjiagic02TmJGWL0MicxUoYmIHZyfuOuVhNVE70ibicZldUDPiag/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


## Comparative verification: refiner, LoRA and SDXL


### SD Base model(v1-5-pruned-emaonly.safetensors):
v1-5-pruned-emaonly.safetensors：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7uYf6q9rposy6zzmGknQOVqWGxneUy20f9pEM0YpnLSr6O33ficoC5YQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### SD Base model(v1-5-pruned-emaonly.safetensors) + LoRA(MoXinV1.safetensors)
v1-5-pruned-emaonly.safetensors+MoXinV1.safetensors(LoRA)：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr75ib4cTcGnKdDwiayQxQDygibEsnDZZ4Ghm4HEzVtnoAENpTSv9DZ2w2HA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### SD Basemodel(v1-5-pruned-emaonly.safetensors) + SDXL Refiner(sd_xl_refiner_1.0.safetensors)

v1-5-pruned-emaonly.safetensors [6ce0161689]+sd_xl_refiner_1.0.safetensors：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7lqALeDIbywHQcuBA0ibib8sukCGCLY48ia12xa2cRAw9CacfZHEyoW6sg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### SD Basemodel(v1-5-pruned-emaonly.safetensors)+SDXL Refiner(sd_xl_refiner_1.0.safetensors) + LoRA(MoXinV1.safetensors)
The effect of v1-5-pruned-emaonly.safetensors [6ce0161689] + sd_xl_refiner_1.0.safetensors + MoXinV1.safetensors (LoRA) is the same as the above image without LoRA.  

### SDXL(juggernautXL_juggXRundiffusion.safetensors)
In theory, SDXL 1.0 BASE, refiner, and LoRA can be used together. However, practical tests show that after enabling the refiner, LoRa does not take effect. LoRa also does not take effect on the XL model. The effect of the juggernautXL_juggXRundiffusion.safetensors model:  

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVXQ0VnhQ5jGGDrrpvQYkr7Y6SeFZLxJjnh0juibIiakvib4qLydwicvibfGRZ2icng3waUibyLPe7TM7RHA/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### SDXL(juggernautXL_juggXRundiffusion.safetensors) + LoRA(MoXinV1.safetensors)

The effect of juggernautXL_juggXRundiffusion.safetensors + MoXinV1.safetensors (LoRA) is the same as the above image without LoRA.


## Some fine-tuned models
In practical use, for personal use, you can use the fine-tuned models available on Civitai or the open-source models released by other companies on HF. In most cases, there is no need to load the Refiner separately. The following website allows you to download both XL models and LoRA: https://civitai.com/models  
  



