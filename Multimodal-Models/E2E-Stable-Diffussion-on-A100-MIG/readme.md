## MIG

### Config MIG
enabling MIG mode:

sudo nvidia-smi -i 0 -mig 1  

sudo reboot  

image1

列出所有可用的 GPU 实例配置文件：

sudo nvidia-smi mig -lgip  

image2


root@david1a100:~# sudo nvidia-smi mig -cgi 14,14,14,20 -C
Successfully created GPU instance ID  5 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  5 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID  3 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  3 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID  4 on GPU  0 using profile MIG 2g.20gb (ID 14)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID  4 using profile MIG 2g.20gb (ID  1)
Successfully created GPU instance ID 13 on GPU  0 using profile MIG 1g.10gb+me (ID 20)
Successfully created compute instance ID  0 on GPU  0 GPU instance ID 13 using profile MIG 1g.10gb (ID  0)


image3


root@david1a100:~# nvidia-smi mig -lgi
4.png

保存 MIG 配置的方法
 

创建一个脚本文件：
创建一个脚本文件，例如 setup_mig.sh，并将配置命令添加到该文件中。


vi /usr/local/bin/setup_mig.sh 
```
#!/bin/bash
sudo nvidia-smi mig -dci  
sudo nvidia-smi mig -dgi  
sudo nvidia-smi mig -cgi 14,14,14,20 -C  

chmod +x /usr/local/bin/setup_mig.sh  

vi /etc/systemd/system/setup_mig.service  
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

sudo systemctl daemon-reload  
sudo systemctl enable setup_mig.service  


1. 确保 Docker 和 NVIDIA Container Toolkit 已安装
 

更新包列表并安装 Docker

sudo apt-get update  
sudo apt-get install -y docker.io  
 

安装 aptitude

sudo apt-get install -y aptitude  
 

添加 NVIDIA Docker 存储库

distribution=$(. /etc/os-release;echo $ID$VERSION_ID)  
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -  
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list  
sudo apt-get update  
 

安装 NVIDIA Container Toolkit

sudo aptitude install -y nvidia-docker2  
sudo systemctl restart docker  
 

安装 nvidia-container-toolkit

sudo aptitude install -y nvidia-container-toolkit  
sudo systemctl restart docker  
 

检查 Docker 服务状态

systemctl status docker  
 

2. 启动容器并进入交互式终端
 
使用 docker run 命令启动容器，并进入交互式终端：


sudo docker run --gpus '"device=0:3"' --network host -v /mig1:/mnt/mig1 -it --name mig1_tensorrt_container nvcr.io/nvidia/pytorch:24.05-py3  /bin/bash  
 

3. 查看正在运行的容器
 
你可以使用以下命令查看正在运行的容器：


sudo docker ps  
 
如果容器已经停止，你可以使用以下命令查看所有容器（包括停止的容器）：


sudo docker ps -a  
 

4. 重新启动并登录到容器
 
如果容器已经停止，你可以使用 docker start 命令重新启动容器：


sudo docker start mig1_tensorrt_container  
 
然后使用 docker exec 命令登录到容器：


sudo docker exec -it mig1_tensorrt_container /bin/bash  
 

5. 验证 GPU 和 MIG 实例
 
在容器内运行 nvidia-smi 命令，验证 GPU 和 MIG 实例是否可用：


nvidia-smi  

image4


在容器里查看tensorrt版本
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


git clone git clone --branch release/10.2 --single-branch https://github.com/NVIDIA/TensorRT.git  
cd TensorRT/demo/Diffusion
pip3 install -r requirements.txt
export HF_TOKEN=

pip install accelarate
 pip install --upgrade torch torchvision torchaudio
  pip install --upgrade nvidia-tensorrt
  pip install --upgrade torch onnx  
  
  解决方案
 

1. 确认 ONNX Runtime 版本
确保你使用的是最新版本的 ONNX Runtime，因为新版本可能包含对更多操作的支持和优化。

pip install --upgrade onnxruntime  
 

2. 使用 GPU 加速
确保你安装了 ONNX Runtime 的 GPU 版本，并且正确配置了 GPU 环境。

pip install onnxruntime-gpu  

   python3 demo_txt2img.py "a beautiful photograph of Mt. Fuji during cherry blossom" --hf-token=$HF_TOKEN
   
 
 
 
 root@david1a100:/workspace/TensorRT/demo/Diffusion# python3 demo_img2img.py "A fantasy landscape, trending on artstation" --hf-token=$HF_TOKEN --input-image=sketch-mountains-input.jpg
 
 7.image
 8.image
 