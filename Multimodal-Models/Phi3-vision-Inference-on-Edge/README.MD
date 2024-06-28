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

***For testing picture which is a sample passports:***


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

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/1.png)

***Inference results:***

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/chinaidres.jpg)


When we look at names and addresses, they are not very accurate.

In addition, summarizing and intent recognition for a picture is more clearly described in English, but not in Chinese.
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/car.jpg)

***Inference time: 4.555504083633423***

*The image shows a white truck driving on a road with trees on both sides. There is a car in front of the truck, and the truck appears to be in motion. The road seems to be in a rural or less-traveled area. There is no immediate indication of danger, but the truck's position and the car's proximity suggest caution is advisable.*


## Phi3-Vision FP16 on CUDA with vLLM test result

As of now, the support for Phi3-V in vLLM is still in a preview state. Therefore, if you want to test the support for Phi3-V in vLLM, you need to compile and install vLLM from the source code. The local compilation time will take about 5-10 minutes.

*#conda activate vllm-phi3-v*
*#git clone https://github.com/vllm-project/vllm.git*
*#cd vllm/*
*#pip install -r requirements-common.txt*
*#pip install -r requirements-cuda.txt.txt*
*#pip install -r requirements-cuda.txt*
*#pip install .*

In terms of vLLM performance, I finally compared the performance using Transformer FP16 and vLLM FP16. I still used the previous example of recognizing a U.S. passport. The inference speed was 2.96 seconds.

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/vllm-h100-infer.png)

The memory usage was around 22GB.

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/vllm-h100-gpu.png)


If using HF inference with FP16 on H100, the inference speed is 8.5 seconds. Although this method is slower, it saves 2/3 of the memory compared to the vLLM method. This is mainly because the accelerate library used by vLLM at the underlying level requires pre-allocating K-V cache. Even though I set max_model_len and gpu_memory_utilization in the code, it still needs more memory than HF. Therefore, when performing edge inference, it is necessary to evaluate both memory utilization and speed.

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/TF-h100-FP16-infer.png)

## Phi3-Vision FP8 on CUDA with vLLM test result
vLLM FP8 of Phi3-V is still under developing by vLLM. Previous AMMO library has been depreciated:

https://github.com/vllm-project/vllm/blob/v0.5.0/examples/fp8/quantizer/quantize.py

*(vllm-phi3v) root@h100vm:~/5/vllm/examples/fp8/quantizer# python quantize.py --model_dir /root/5/phi3-v-fp16 --dtype float16 --qformat fp8 --kv_cache_dtype fp8 --output_dir  /root/5/phi3-v-fp8 --calib_size 512 --tp_size 1*

*/opt/miniconda/envs/vllm-phi3v/lib/python3.11/site-packages/ammo/__init__.py:17: UserWarning:
`nvidia-ammo` package is now deprecated and renamed as `nvidia-modelopt`.
Please see more details at https://github.com/NVIDIA/TensorRT-Model-Optimizer?tab=readme-ov-file#release-notes*


## Phi3-Vision with ONNX test result
Till now, ONNX runtime need CUDA 11:
```
root@h100vm:~# nvcc --version
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2020 NVIDIA Corporation
Built on Thu_Jun_11_22:26:38_PDT_2020
Cuda compilation tools, release 11.0, V11.0.194
Build cuda_11.0_bu.TC445_37.28540450_0
root@h100vm:~#
root@h100vm:~# nvidia-smi
Fri Jun 28 02:49:23 2024
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 555.42.02              Driver Version: 555.42.02      CUDA Version: 12.5     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA H100 NVL                Off |   00000001:00:00.0 Off |                    0 |
| N/A   35C    P0             64W /  400W |     142MiB /  95830MiB |      0%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A      1656      G   /usr/lib/xorg/Xorg                            107MiB |
|    0   N/A  N/A      2757      G   /usr/bin/gnome-shell                           16MiB |
+-----------------------------------------------------------------------------------------+
```
The inference of Phi3-V based on ONNX can be referenced:
https://onnxruntime.ai/docs/genai/tutorials/phi3-v.html

I slightly modified the inference script from the above link to be able to measure the inference time. The inference speed is very fast, around 4 seconds for FP16, but the inference accuracy is not as good as HF and vLLM.
```
(phi3) root@h100vm:~# python3 1phi3v.py -m cuda-fp16
Loading model...
Image Path (leave empty if no image): /root/usa-passport.jpg
Loading image...
Prompt: OCR the text of the image. Extract the text of the following fields and put it in a JSON format: {'Type / Type / Tipo': '', 'Code / Code / Código': '', 'Passport No. / No de passeport / Pasaporte n.º': '', 'Surname / Nom / Apellido': '', 'Given Names / Prénom / Nombre': '', 'Nationality / Nationalité / Nacionalidad': '', 'Date of birth / Date de naissance / Fecha de nacimiento': '', 'Place of birth / Lieu de naissance / Lugar de nacimiento': '', 'Date of issue / Date de délivrance / Fecha de expedición': '', 'Date of expiration / Date d'expiration / Fecha de vencimiento': '', 'Sex / Sexe / Sexo': '', 'Authority / Autorité / Autoridad': '', 'Endorsements / Mentions / Anotaciones': ''}. Ensure all fields are extracted accurately from the image, especially 'Type / Type / Tipo', 'Code / Code / Código', 'Passport No. / No de passeport / Pasaporte n.º', 'Sex / Sexe / Sexo', and 'Authority / Autorité / Autoridad'.
Processing image and prompt...
Generating response...
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/onnxinfer.png)
From the results, it can be seen that even though I wrote a very detailed prompt, the scanned results are still incomplete. This is much worse compared to HF and vLLM. The GPU memory utilization is around 11GB.
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Phi3-vision-Inference-on-Edge/images/onnxgpu.png)