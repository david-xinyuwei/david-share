# Phi3-vision-Inference-on-Edge

**Notice:**

- I have upload my jupyter file named Phi3-vision-Inference-on-Edge.ipynb , I ran the code on Azure NC A100 GPU VM.

- In this test, I will test Phi3-Vision on Edge solution, including on GPU/CPU and different inference server.

## Phi3-Vision Benchmark Score
Previously, we used AI computer vision, mainly using models like Llava and GPT-4o. After Phi3-Vision was released in May, it has surpassed Llava in many aspects:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/2.jpg)

Phi3-Vision is besides capable and suitable for reasoning at the edge end due to the comparatively small number of parameters:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/3.jpg)

From the above figure you can see the memory consumed by the phi3-v loading model for different data types.

## Consideration for edge-side Inference

**1. Whether you need to do fine-tuning the model to meet specific business needs. See my repo for ways to fine tune:**

*https://github.com/davidsajare/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning*

**2. The hardware on which the model is running when reasoning at the edge end. For example, GPU or CPU(Cuda/ROCm).**

**3. Whether there are enough resources, especially memory.Not enough arithmetic causes slow inference, but not enough memory directly causes OOM.**


## Phi3-Vision on CUDA with HF transformer test result
Currently Phi3-v has only 128K contexts in both HF and ONNX formats.

*https://huggingface.co/microsoft/Phi-3-vision-128k-instruct*
Check the memory needs for Phi3-Vision in different datatype.

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/3.jpg)

In this article I use the HF format for validation.

***For testing passports:***
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/usa-passport.jpg)

### 3 Points notice:

##### 1. Does bnb dynamic quantization cause a decrease in inference accuracy, the answer is no.

##### 2. Whether dynamic quantization will cause a decline in reasoning speed, the answer is yes.


For English, whether dynamic quantization are very accurate, whether it is picture intent recognition, picture description or OCR (for example, for passports), are very accurate, and do not need to write too many prompt words.

For Chinese, OCR accuracy needs to be improved, and intent recognition is OK.

With the A100, the inference for a picture after quantization (passport as an example) is around 17 seconds. Memory 6G:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/int4infer.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/int4gpu.jpg)

Without quantization, the FP16 inference for an image (passport as an example) is in the neighborhood of 13 seconds, with close to 12 GB of memory.
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/fp16infer.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/fp16gpu.jpg)

##### 3. The problems encountered in Chinese recognition.

Take the Chinese test ID card as an example:

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/1.png width="400" height="550")

***Inference results:***
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/chinaidres.jpg)


When we look at names and addresses, they are not very accurate.

In addition, summarizing and intent recognition for a picture is more clearly described in English, but not in Chinese.
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/car.jpg)

***Inference time: 4.555504083633423***

*The image shows a white truck driving on a road with trees on both sides. There is a car in front of the truck, and the truck appears to be in motion. The road seems to be in a rural or less-traveled area. There is no immediate indication of danger, but the truck's position and the car's proximity suggest caution is advisable.*


## Phi3-Vision on CUDA with vLLM test result
TODO
## Phi3-Vision with ONNX test result
TODO
