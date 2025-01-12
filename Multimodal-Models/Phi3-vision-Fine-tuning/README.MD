# Phi3-vision-Fine-tuning

**Reference Link:**

*https://wandb.ai/byyoung3/mlnews3/reports/How-to-fine-tune-Phi-3-vision-on-a-custom-dataset--Vmlldzo4MTEzMTg3*


I have upload my jupyter file named Phi3-v.ipynb , I ran the code on Azure NC H100 GPU VM.
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/Phi3-vision-Fine-tuning/images/4.png)

In this test, I use Burberry's data to fine-tune Phi3-Vision comprehensively. The goal is to enable the fine-tuned model to predict brand, description, category, and price information based on product images.



## Base Model capability before SFT

Phi-3-v base model gives wrong answer based on text question "1.what is the price in 6.5? 2.What is the good?" and image.

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/7.png)



Phi-3.5-v base model gives wrong answer based on text question "1.what is the price in 6.5? 2.What is the good?" and image.

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/8.png)

 

## Training Steps

Original training data URL:

https://huggingface.co/datasets/DBQ/Burberry.Product.prices.United.States


After processing the original training data with the code, a CSV file and a directory containing product images will be generated locally on the Azure GPU VM:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/1.png)
Here is a preview of the CSV file contents:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/2.png)

Here is a sample image from the images directory:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/3.png)

Training Results:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/5.png)
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/6.png)

We could also check training report on wandb:

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/9.png)

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/10.png)

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/12.png)

## Inference validation

Since the training data consists entirely of Burberry items, the model's predictions for Burberry products are highly accurate. I won't elaborate on this further. I tried using an image of Nike shoes for prediction. If only the shoe image is provided, the model can correctly identify the brand and features but not the price. However, if the e-commerce image information is provided, it can accurately describe the item.

***prompt = "<|user|>\n<|image_1|>1.what is the price in 6.5? 2.What is the good?<|end|><|assistant|>\n"***

image_path_or_url = "/root/5.jpg"  

![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/7.jpg)

Inference Results:

***Predicted Text: 1. The price for size 6.5 is $115.00. 2. The good is Nike Dunk Low DD1503-101 Women's White Black Leather Sneaker Shoes Size 9 PRO43.***

You can see that I specifically asked for the price of the product of size 6.5 in the prompt. The response was quite accurate. This scenario is particularly suitable for e-commerce quality inspectors performing edge inference detection.
