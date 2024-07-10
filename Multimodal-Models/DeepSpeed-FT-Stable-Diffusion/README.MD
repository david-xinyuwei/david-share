DeepSpeed-Chat是专门针对聊天模型的优化技术，它通过简化的强化学习从头训练（RLHF）方法，使得在所有规模上训练类似ChatGPT的模型变得简单、快速和经济 。这意味着DeepSpeed-Chat专注于提高聊天模型的训练效率和降低成本。Deepspeed-chat目前支持的模型如下：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibEvTJWkQ9LoCQicqXNd4dTbj16Tov1FA4VNMPDibY3gYCGSxP7F7pq5icwbwhhRXbc5FHW6zU8A0xQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

另一方面，DeepSpeed-Training是DeepSpeed提供的一系列系统创新，旨在使大规模深度学习训练变得有效和高效。这些创新包括ZeRO、3D-Parallelism、DeepSpeed-MoE、ZeRO-Infinity等技术，它们共同改善了深度学习训练的速度、规模和易用性 。本文我们着重介绍DeepSpeed-Training。

DeepSpeed-Training 表现出对大规模深度学习训练的系统创新，这些创新使得深度学习训练既高效又有效，极大地提升了用户体验，并重新定义了可能达到的训练规模。这些创新技术包括但不限于 ZeRO、3D-Parallelism、DeepSpeed-MoE 和 ZeRO-Infinity 等。这些技术的共同点在于：

- **ZeRO**：通过优化模型的数据并行处理，减少了在训练超大规模模型时所需的内存占用，使得更大规模的模型训练成为可能。

- **3D-Parallelism**：结合了数据并行、模型并行和流水线并行的技术，以有效地缩小通信瓶颈，提高训练速度和扩展性。

- **DeepSpeed-MoE**：使用混合的专家系统（Mixture of Experts，MoE）提高模型的参数效率，并通过实现更高水平的模型并行来提升训练速度。

- **ZeRO-Infinity**：进一步扩展了 ZeRO 技术，通过使用硬盘存储来扩大可训练模型的规模，打破了 GPU 内存的限制。

  DeepSpeed-Training 不仅关注于提升训练过程中的性能和效率，同时也着重于简化用户的使用体验。这通过设计易于使用的API和集成工具来实现，使得深度学习从业者可以轻松地对大型模型进行高效训练，而无需深入了解底层的复杂实现细节 。

  总的来说，DeepSpeed-Training 提供了一种创新的方法来处理大规模深度学习模型的训练，它不仅降低了资源的需求，还通过多种并行化技术提升了训练速度和效率。这为研究人员和开发人员在处理计算资源密集型任务时提供了巨大的灵活性和效率 。



https://github.com/microsoft/DeepSpeedExamples/tree/master/training/stable_diffusion

# cat mytrainbash.sh
```
export MODEL_NAME="stabilityai/stable-diffusion-2-1-base"
export OUTPUT_DIR="./sd-distill-v21"


if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir "$OUTPUT_DIR"
echo "Folder '$OUTPUT_DIR' created"
else
echo "Folder '$OUTPUT_DIR' already exists"
fi




accelerate launch train_sd_distil_lora.py \
           --pretrained_model_name_or_path=$MODEL_NAME  \
           --output_dir=$OUTPUT_DIR \
           --default_prompt="A man dancing" \
           --resolution=512 \
           --train_batch_size=1 \
           --gradient_accumulation_steps=1 \
           --learning_rate=5e-6 \
           --lr_scheduler="constant" \
           --lr_warmup_steps=0

```



再下层的训练脚本内容较多，我大致解释一下它的作用：

主要用于微调稳定扩散模型。它利用HuggingFace的加速器和`diffusers`库进行大规模训练，将深度学习优化到新的水平。下面是一些关键点：

1. **环境和配置设置**：通过argparse库，它提供了大量的配置选项，比如预训练模型路径、batch大小、学习率、优化器设置等，使训练过程高度可定制。

2. **数据处理**：它使用`load_dataset`加载数据集，并定义了`DreamBoothDataset`处理图像和文本提示，这包括图像的大小调整和裁剪以及文本提示的token化。

3. **模型加载**：脚本加载了多个模型组件，包括UNet2DConditionModel、AutoencoderKL（如果有必要）、以及文本编码器，这些都是基于从huggingface.co/models获得的预训练模型。

4. **训练循环**：在训练循环中，它首先对模型的输入（图像和噪声）进行处理，然后结合文本提示的编码进行前向传播。损失计算是基于模型预测和实际噪声之间的差异。

5. **梯度累计和优化器步骤**：为了在有限的硬件资源上实现更有效的训练，它支持梯度累计，并在适当的时间点上进行优化器更新。

6. **模型保存和上传**：训练结束后，脚本将训练好的模型保存并上传到Hugging Face Hub，方便以后的使用和共享。

7. **高级特性支持**：它还提供了多种高级训练特性的支持，比如混合精度训练、梯度裁剪、学习率调度器、对8位Adam优化器的支持等，这些都是为了提升训练效率和模型性能。

   整个脚本展示了利用现代深度学习库和预训练模型进行复杂任务训练的复杂性和强大功能，同时保持了代码的可读性和模块化。



接下来，启动训练：

```
(deepspeed) root@davidwei:~/DeepSpeedExamples/training/stable_diffusion# bash mytrainbash.sh
脚本检测到4个GPU，会用4个GPU进行并发训练：
接下里，会自动下载数据集：
启动训练：训练结束：最终的损失率：
```



训练中资源利用率：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibEvTJWkQ9LoCQicqXNd4dTibFYys1zheG08Jpo44uB0RnCzMjygJkzFkq0zR7wSlGgUsO7Kibt1NAg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

接下来，验证推理，会用微调前的基础模型（stabilityai/stable-diffusion-2-1-base）和我刚才微调后的模型进行生成图片对比：

(deepspeed) root@davidwei:~/DeepSpeedExamples/training/stable_diffusion# python inf_txt2img_loop.py --ft_model ./sd-distill-v21/

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbQP8iaDvPlF5icA7Wx2nc3iaBatWewpCyhagCiaouSlXibn71JfBJdA2p4BQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

接下来展示对比，每组图片都是**先展示基础模型的生图效果，再展示微调后的模型生图效果。**

第一组：A road that is going down a hill

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbjd3BafYGQe0zHC1gl4YD8Ox4GWtN8d728ZSia5kjW8wcKMWR3GbsaGw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbTH3HwWibEImkjiaI0PVV7DzLXy7dGPnZIQxqOShiaCLsf4Wb35BW2ThNg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

第二组：A photo of a person dancing in the rain

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMb1K6TyP7DiavvjUUp226oCoibbssCTqoPxyVwNyG5uR6ibTnUJzibfiapwBg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbUpDicFgIXeAdpmHo2PsBTJwEsdYy8Vq4mg0YLhic4BXQYG4y3QIsh9LA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



第三组：A beach with a lot of waves on it

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbcDMVXJWm5cHbtDmsOHz79DJEJHZ0eOmmqwF8uAXsOOloEFhNh1m29g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbhcB2yezaDB4Ja1uZ2WFNVqGhSemWHScrkeZt2xW814wziauVwU1cIWA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

第四组：3d rendering of 5 tennis balls on top of a cake

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbrYIGeAXzue5zj0HPDgxHxGp79EjdXmmu20BaicjRiapib4FsMA7moCAnw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbXgLkoicFyxHRt30AWtJFmdSuPNeFDsZkS4tyMwNH25e29NSxjOQNZgg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

第五组：A person holding a drink of soda

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMb4NgEFPKXqwbxcgjfFhxv5ibDctRTQtEjniafQHukkzyAV6R730BHBPFw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWnicoxGopS7cyhd9Ems2icMbS2aDyPlZibKFNg14NGx7SSlPvqyrjiaP6r7KoZpHlbrYxqIic9HOr7FeA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



效果对比，不言而喻。