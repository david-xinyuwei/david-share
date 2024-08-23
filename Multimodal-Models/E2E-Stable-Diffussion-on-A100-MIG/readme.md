# E2E Stable-Diffussion on A100 MIG
A100/H100 are High end Training GPU, which could also work as Inference. In order to save compute power and GPU memory, We could use NVIDIA Multi-Instance GPU (MIG), then we could run Stable Diffusion on MIG.
I do the test on Azure NC A100 VM.

## Config MIG

### Enabling MIG mode:

Enable MIG on the first physical GPU.
```
sudo nvidia-smi -i 0 -mig 1  
sudo reboot  
```
After the VM reboot, MIG has been enabled.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/1.png)

Lists all available GPU MIG profiles:

```
nvidia-smi mig -lgip  
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/2.png)

At this moment, we need to calculate how to maximise utilize the GPU resource and meet the compute power and GPU memory for SD.

### Config MIG
I divide A100 to four parts: ID 14x3 and ID 20x1

```
root@david1a100:~# sudo nvidia-smi mig -cgi 14,14,14,20 -C
Successfully created GPU instance ID  5 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  5 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID  3 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  3 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID  4 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  4 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID 13 on GPU  0 using profile MIG 1g.10gb+me (ID 20)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID 13 using profile MIG 1g.10gb (ID  0)
```
Check mig:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/3.png)

```
root@david1a100:~# nvidia-smi mig -lgi
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/4.png)

### Persist the MIG configuratgion
After reboot the VM, CPU MIG configuration will be lost, so I need to setup bash script.
``` 
#vi /usr/local/bin/setup_mig.sh 
```
```
#!/bin/bash
nvidia-smi -i 0 -mig 1
sudo nvidia-smi mig -dgi
sudo nvidia-smi mig -cgi 14,14,14,20 -C
```
```
chmod +x /usr/local/bin/setup_mig.sh  
```
```
vi /etc/systemd/system/setup_mig.service  
```
```
[Unit]  
Description=Setup NVIDIA MIG Instances  
After=default.target  

[Service]  
Type=oneshot  
ExecStart=/usr/local/bin/setup_mig.sh  

[Install]  
WantedBy=default.target  
```
```
sudo systemctl daemon-reload  
sudo systemctl enable setup_mig.service  
```
## Prepare Contaner environmement
Install Docker and NVIDIA Container Toolkit

```
sudo apt-get update  
sudo apt-get install -y docker.io  
sudo apt-get install -y aptitude  
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)  
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -  
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list  
sudo apt-get update  
sudo aptitude install -y nvidia-docker2  
sudo systemctl restart docker  
sudo aptitude install -y nvidia-container-toolkit  
sudo systemctl restart docker  
```
Checking Docker Service Status
```
systemctl status docker  
``` 
Start the container and enter the interactive terminal,Use the docker run command to start the container and enter the interactive terminal. 

In the cli 0:3 is the first MIG.

```
sudo docker run --gpus '"device=0:3"' --network host -v /mig1:/mnt/mig1 -it --name mig1_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3  /bin/bash  
```
Related useful commands.
```
sudo docker ps  
sudo docker start mig1_tensorrt_container  
sudo docker exec -it mig1_tensorrt_container /bin/bash  
``` 
Run the nvidia-smi command inside the container to verify that the GPU and MIG instances are available:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/5.png)

## Do SD inference test in Container.
Vlidate tensorrt version in a container
```
root@david1a100:/workspace# pip show tensorrt
```
```
Name: tensorrt
Version: 10.2.0
Summary: A high performance deep learning inference library
Home-page: https://developer.nvidia.com/tensorrt
Author: NVIDIA Corporation
Author-email:
License: Proprietary
Location: /usr/local/lib/python3.10/dist-packages
Requires:
Required-by:
```
Do SD test via github examples, in container：
```
git clone git clone --branch release/10.2 --single-branch https://github.com/NVIDIA/TensorRT.git  
cd TensorRT/demo/Diffusion
pip3 install -r requirements.txt
export HF_TOKEN= ***
pip install accelarate
pip install --upgrade torch torchvision torchaudio
pip install --upgrade nvidia-tensorrt
pip install --upgrade torch onnx  
pip install --upgrade onnxruntime  
pip install onnxruntime-gpu  
```
Genarate inmage 1024*1024 image from test.
```
python3 demo_txt2img.py "a beautiful photograph of Mt. Fuji during cherry blossom" --hf-token=$HF_TOKEN
```
We could check the spped of generating imnage:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/7.png)
 
The output image is as following:
```
#cp ./output/* /mig1
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/E2E-Stable-Diffussion-on-A100-MIG/images/9.png)

We could also genarate from image to image:
```
root@david1a100:/workspace/TensorRT/demo/Diffusion# python3 demo_img2img.py "A fantasy landscape, trending on artstation" --hf-token=$HF_TOKEN --input-image=sketch-mountains-input.jpg
 ```

## Compare Int8 inference speed and qulity on whole H100 GPU
Tested Stable Diffusion XL1.0 on a single H100 to verify the effects of int8. NVIDIA claims that on H100, INT8 is optimised over A100.

```
#python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --hf-token=$HF_TOKEN --version=xl-1.0***
```
Run time:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL1U7icPciauNdgMibolw6d6271Jky8kPMKDjw8r17Xy2hvFXnC8BDAyNgA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Image generation effect:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLFQhCfrkBOB5LzDp7gvdvpmSXKIpCOEcLL0Q3DAZxAftcAyTjialpOQw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Use SDXL & INT8 AMMO quantization：

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --onnx-dir onnx-sdxl --engine-dir engine-sdxl --int8
```
After executing the above command, 8-bit quantisation of the model will be performed first.

```
Building TensorRT engine for onnx/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.opt/model.onnx: engine/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.trt10.0.1.plan
```
Then do inference

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLPallL3kz4wXl2Gz53ZgKHQt9BElISrojuSauMpQ2Ig7ZE4icu322zaA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Check generated image:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLJ6Q5Yib3PuDusic7VhLaxJculL2GKicQyiaApnkmwygjuPdFibfoebyoibzg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

We see that the quality of the generated images is the same, and the file sizes are almost identical as well.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLjT8uL9PfwiaicpxEuGp5zic41GmHU5TCKXR4dsjDdh5IwgUg1c5DJ4VzQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

We observed that the inference speed of INT8 increased by 20% compared to FP16

```
root@d6865c4fc3d8:/workspace/demo/Diffusion# ls -al onnx-sdxl
```
```
total 408
drwxr-xr-x 10 root root   4096 May 21 06:34 .
drwx------ 11 root root   4096 May 21 06:34 ..
drwxr-xr-x  2 root root   4096 May 21 06:34 clip
drwxr-xr-x  2 root root   4096 May 21 06:34 clip.opt
drwxr-xr-x  2 root root   4096 May 21 06:34 clip2
drwxr-xr-x  2 root root   4096 May 21 06:35 clip2.opt
drwxr-xr-x  2 root root 376832 May 21 06:40 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8
drwxr-xr-x  2 root root   4096 May 21 06:41 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.opt
drwxr-xr-x  2 root root   4096 May 21 06:41 vae
drwxr-xr-x  2 root root   4096 May 21 06:41 vae.opt
```


root@d6865c4fc3d8:/workspace/demo/Diffusion# ls -al engine-sdxl
```

total 4755732
drwxr-xr-x  2 root root       4096 May 21 06:48 .
drwx------ 11 root root       4096 May 21 06:34 ..
-rw-r--r--  1 root root  248576668 May 21 06:41 clip.trt10.0.1.plan
-rw-r--r--  1 root root 1395532052 May 21 06:42 clip2.trt10.0.1.plan
-rw-r--r--  1 root root 2880794876 May 21 06:47 unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.trt10.0.1.plan
-rw-r--r--  1 root root  344938836 May 21 06:48 vae.trt10.0.1.plan
```
If you already have a quantized model and only need to perform inference without re-quantization, you can simplify the command-line interface (CLI) to focus on loading and using the existing quantized model for inference. Assuming your quantized model has already been converted to the TensorRT engine format and is stored in the engine-dir directory, you can directly use these engine files for inference without re-quantization or model conversion.

For example, you can use the following command to perform inference:
```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --engine-dir engine-sdxl 
```
 
In this way, most of the CLI parameters can remain unchanged, but it ensures that no additional quantization or model conversion processes are triggered.


The inference speed is 0.61, which seems to be on par with FP16.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLfDFZMB5T0NTDYwXjjQe1xicC6SPsca9Mf4sqImiaKSlcC9q8nbkzuHCA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLd3ooKlI2DOcQd5fV4mKHhzUHF9WJd1X2fgV10ziciaGz4xduGJA8ukMw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Appending --int8 at the end of the above CLI increases the inference speed by 20%

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --engine-dir engine-sdxl --int8
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLgZJjkboPDPUb35icSsfhgSjiaadQHic9ntwRUiaIpVtLGialI1kFpBHtPaA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLHVVQWqXKdiaiaq2eTngSia2VWiaoGhIL7rNkRpcYUwYaGHvgqB739caYHA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



Next, we look at two other methods of accelerated reasoning in SD:

Accelerated text-to-image conversion using SDXL + LCM (Latent Consistency Model) LoRA weights
```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --lora-path "latent-consistency/lcm-lora-sdxl" --lora-scale 1.0 --onnx-dir onnx-sdxl-lcm-nocfg --engine-dir engine-sdxl-lcm-nocfg --denoising-steps 4 --scheduler LCM --guidance-scale 0.0
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL6l3ExIj5FSxacKUg8sgtcbPKY0TSooyPoNXiaOiboWc7y3NA3wIzZ2FQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLzwC3tnAl5keulJZR0LPPmbibfQAbm0n5GicqibEO7gF4cu7etcxqPnWwg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Use SDXL Turbo to speed up text to image, the following cli generates 512*512 images.

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-turbo --onnx-dir onnx-sdxl-turbo --engine-dir engine-sdxl-turbo --denoising-steps 1 --scheduler EulerA --guidance-scale 0.0 --width 512 --height 512
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOL1xsEZHufSsUBzKvRxoqwMF8B8ycPc71s4TFAibjpPCXQjEdEzws7AvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUj0hByhSBicSUTicZOnjWGOLYPhPq9PzdYepCor0L9R63AoYtcSzlLs05yucVWd3ZH8tnQIt8MrpDg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Overall, it is still INT8+SDXL 1.0 that can balance the quality of the generated images and improve the inference speed.