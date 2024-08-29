# End-to-end Stable Diffusion test on Azure NC A100/H100 MIG

A100/H100 are High end Training GPU, which could also work as Inference. In order to save compute power and GPU memory, We could use NVIDIA Multi-Instance GPU (MIG), then we could run Stable Diffusion on MIG.
I do the test on Azure NC A100 VM.

## Config MIG

Enable MIG on the first physical GPU.

```
root@david1a100:~# nvidia-smi -i 0 -mig 1
```

After the VM reboot, MIG has been enabled.

![thumbnail image 1 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613660i473A304D9181F419/image-size/medium?v=v2&px=400)

Lists all available GPU MIG profiles:

```
#nvidia-smi mig -lgip
```

![thumbnail image 2 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613661iE1B4137FB79039DD/image-size/medium?v=v2&px=400)

At this moment, we need to calculate how to maximise utilize the GPU resource and meet the compute power and GPU memory for SD.

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

![thumbnail image 3 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613662iF6005A24A7FA70A0/image-size/medium?v=v2&px=400)

## Persist the MIG configuratgion



After reboot the VM, CPU MIG configuration will be lost, so I need to setup bash script.

```
#vi /usr/local/bin/setup_mig.sh
```

 

```applescript
!/bin/bash
nvidia-smi -i 0 -mig 1
sudo nvidia-smi mig -dgi
sudo nvidia-smi mig -cgi 14,14,14,20 -C
```

 

 

Grant execute permission:

```
chmod +x /usr/local/bin/setup_mig.sh
```

Create a system service:

```
vi /etc/systemd/system/setup_mig.service
```

 

```applescript
[Unit]  
Description=Setup NVIDIA MIG Instances  
After=default.target  

[Service]  
Type=oneshot  
ExecStart=/usr/local/bin/setup_mig.sh  

[Install]  
WantedBy=default.target  
```

 

 

Enable and start setup_mig.service:

```
sudo systemctl daemon-reload 
sudo systemctl enable setup_mig.service
sudo systemctl status setup_mig.service
```

## Prepare MIG Container environment

Install Docker and NVIDIA Container Toolkit on VM

 

```applescript
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

 

 

Configure create Container script on VM

```
#vi createcontainer.sh
```

 

```applescript
#!/bin/bash

# 容器名称数组
CONTAINER_NAMES=("mig1_tensorrt_container" "mig2_tensorrt_container" "mig3_tensorrt_container" "mig4_tensorrt_container")

# 删除已有的容器
for CONTAINER in "${CONTAINER_NAMES[@]}"; do
  if [ "$(sudo docker ps -a -q -f name=$CONTAINER)" ]; then
    echo "Stopping and removing container: $CONTAINER"
    sudo docker stop $CONTAINER
    sudo docker rm $CONTAINER
  fi
done

# 获取MIG设备的UUID
MIG_UUIDS=$(nvidia-smi -L | grep 'MIG' | awk -F 'UUID: ' '{print $2}' | awk -F ')' '{print $1}')
UUID_ARRAY=($MIG_UUIDS)

# 检查是否获取到足够的MIG设备UUID
if [ ${#UUID_ARRAY[@]} -lt 4 ]; then
  echo "Error: Not enough MIG devices found."
  exit 1
fi

# 启动容器
sudo docker run --gpus '"device='${UUID_ARRAY[0]}'"' -v /mig1:/mnt/mig1 -p 8081:80 -d --name mig1_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3 tail -f /dev/null
sudo docker run --gpus '"device='${UUID_ARRAY[1]}'"' -v /mig2:/mnt/mig2 -p 8082:80 -d --name mig2_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3 tail -f /dev/null
sudo docker run --gpus '"device='${UUID_ARRAY[2]}'"' -v /mig3:/mnt/mig3 -p 8083:80 -d --name mig3_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3 tail -f /dev/null
sudo docker run --gpus '"device='${UUID_ARRAY[3]}'"' -v /mig4:/mnt/mig4 -p 8084:80 -d --name mig4_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3 tail -f /dev/null

# 打印容器状态
sudo docker ps
sudo ufw allow 8081
sudo ufw allow 8082
sudo ufw allow 8083
sudo ufw allow 8084
sudo ufw reload
```

 

 

Check container is accessible from outside.

In container, start 80 listener:

```
root@david1a100:~# sudo docker exec -it mig1_tensorrt_container /bin/bash
root@b6abf5bf48ae:/workspace# python3 -m http.server 80
Serving HTTP on 0.0.0.0 port 80 (http://0.0.0.0:80/) ...
167.220.233.184 - - [23/Aug/2024 10:54:47] "GET / HTTP/1.1" 200 -
```

Curl from my laptop:

```
(base) PS C:\Users\xinyuwei> curl http://20.5.**.**:8081
StatusCode : 200
StatusDescription : OK
Content : <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Directory listing fo...
RawContent : HTTP/1.0 200 OK
Content-Length: 594
Content-Type: text/html; charset=utf-8
Date: Fri, 23 Aug 2024 10:54:47 GMT
Server: SimpleHTTP/0.6 Python/3.10.12
```

In container, ping google.com:

```
root@david1a100:~#sudo docker exec -it mig1_tensorrt_container /bin/bash
root@b6abf5bf48ae:/workspace# pip install ping3
root@b6abf5bf48ae:/workspace# ping3 www.google.com
ping 'www.google.com' ... 2ms
ping 'www.google.com' ... 1ms
ping 'www.google.com' ... 1ms
ping 'www.google.com' ... 1ms
Related useful commands.
```

 

## Do SD inference test in Container.

Check tensorrt version in container:

```
root@david1a100:/workspace# pip show tensorrt
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
git clone --branch release/10.2 --single-branch https://github.com/NVIDIA/TensorRT.git 
cd TensorRT/demo/Diffusion
pip3 install -r requirements.txt
export HF_TOKEN=<your access token>
```

Genarate inmage 512*512 image from test.

```
python3 demo_txt2img.py "a beautiful photograph of Mt. Fuji during cherry blossom" --hf-token=$HF_TOKEN
```

We could check the speed of generating image in different:

In MIG1 container, which has 2 GPC and 20G memory:

![thumbnail image 4 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613665i1AC964E2948C3A89/image-size/medium?v=v2&px=400)

In mig4 container, which has 2 GPC and 20G memory:

![thumbnail image 5 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613666i8E29868AEC483E85/image-size/medium?v=v2&px=400)

Check The output image is as following, copy it to VM and download it.

```
#cp ./output/* /mig1
```

![thumbnail image 6 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613667iDA21E83F74183BF6/image-size/medium?v=v2&px=400)

## Compare Int8 inference speed and quality on H100 GPU

Tested Stable Diffusion XL1.0 on a single H100 to verify the effects of int8. NVIDIA claims that on H100, INT8 is optimised over A100.

```
#python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --hf-token=$HF_TOKEN --version=xl-1.0
```

![thumbnail image 7 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613668i01F1068739BA154C/image-size/medium?v=v2&px=400)

Image generation effect:

![thumbnail image 8 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613669iD5C7A5AF59665197/image-size/medium?v=v2&px=400)

Use SDXL & INT8 AMMO quantization：

```
python3 demo_txt2img_xl.py "a photo of an astronaut riding a horse on mars" --version xl-1.0 --onnx-dir onnx-sdxl --engine-dir engine-sdxl --int8
```

After executing the above command, 8-bit quantisation of the model will be performed first.

```
Building TensorRT engine for onnx/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.opt/model.onnx: engine/unetxl-int8.l2.5.bs2.s30.c32.p1.0.a0.8.trt10.0.1.plan
```

Then do inference

![thumbnail image 9 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613670iCC93F3893A9CA6E5/image-size/medium?v=v2&px=400)

Check generated image:

![thumbnail image 10 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613671i0F0845E2A3768635/image-dimensions/407x406?v=v2)

We see that the quality of the generated images is the same, and the file sizes are almost identical as well.

![thumbnail image 11 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							End-to-end Stable Diffusion test on Azure NC A100/H100 MIG 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613672i8727D9802A938660/image-size/medium?v=v2&px=400)

We observe that the inference speed of INT8 increased by 20% compared to FP16.