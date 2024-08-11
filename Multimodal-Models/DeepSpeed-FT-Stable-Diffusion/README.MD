# DeepSpeed FT StableDiffusion
** Refer to：** 

*https://github.com/microsoft/DeepSpeedExamples/tree/master/training/stable_diffusion*

Check traing script:
```
# cat mytrainbash.sh
```
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




接下来，启动训练：

```
(deepspeed) root@davidwei:~/DeepSpeedExamples/training/stable_diffusion# bash mytrainbash.sh

The script has detected 4 GPUs and will use 4 GPUs for concurrent training.



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