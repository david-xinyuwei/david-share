## Fast Stress Test of DeepSeek 671B on Azure AMD MI300X

**Refer to:**

*https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726*

### Azure GPU VM环境准备

快速创建Spot VM,使用spot VM并且使用密码方式认证：

```
az vm create --name <VMNAME> --resource-group <RESOURCE_GROUP_NAME> --location <REGION>  --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 256 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password <YOUR_PASSWORD>

```

我使用的创建VM cli：

```
xinyu [ ~ ]$ az vm create --name mi300x-xinyu --resource-group amdrg --location westus --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 512 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password azureadmin@123
```

VM部署步骤：

```
Argument '--max-price' is in preview and under development. Reference and support levels: https://aka.ms/CLI_refstatus
Consider upgrading security for your workloads using Azure Trusted Launch VMs. To know more about Trusted Launch, please visit https://aka.ms/TrustedLaunch.
{
  "fqdns": "",
  "id": "/subscriptions/53039473-9bbd-499d-90d7-d046d4fa63b6/resourceGroups/amdrg/providers/Microsoft.Compute/virtualMachines/mi300x-xinyu",
  "location": "westus",
  "macAddress": "60-45-BD-01-4B-AF",
  "powerState": "VM running",
  "privateIpAddress": "10.0.0.4",
  "publicIpAddress": "13.64.8.207",
  "resourceGroup": "amdrg",
  "zones": ""
}
```

系统部署成功后，打开VM NSG的22端口。

然后ssh到VM进行如下环境配置。

```
mkdir -p /mnt/resource_nvme/
sudo mdadm --create /dev/md128 -f --run --level 0 --raid-devices 8 $(ls /dev/nvme*n1)  
sudo mkfs.xfs -f /dev/md128 
sudo mount /dev/md128 /mnt/resource_nvme 
sudo chmod 1777 /mnt/resource_nvme  
```

测试的时候，使用本地NVME临时磁盘用作docker的运行环境，需要注意的是，VM重启以后，临时磁盘上的内容会丢失,针对快速低成本测试这种方式是可行的，针对生产则需要使用持久化文件系统。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/1.png)

首先创建RAID0的挂载目录:

```bash
mkdir –p /mnt/resource_nvme/hf_cache 
export HF_HOME=/mnt/resource_nvme/hf_cache 
```

配置RAID0，并且指定docker使用。

```
mkdir -p /mnt/resource_nvme/docker 
sudo tee /etc/docker/daemon.json > /dev/null <<EOF 
{ 
    "data-root": "/mnt/resource_nvme/docker" 
} 
EOF 
sudo chmod 0644 /etc/docker/daemon.json 
sudo systemctl restart docker 
```

### 进行压力测试

拉取镜像：

```bash
docker pull rocm/sgl-dev:upstream_20250312_v1
```

DS 671B启动的时候，大概需要5分钟左右。

```bash
docker run \
  --device=/dev/kfd \
  --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --cap-add=SYS_PTRACE \
  --group-add video \
  --privileged \
  --shm-size 128g \
  --ipc=host \
  -p 30000:30000 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e GPU_FORCE_BLIT_COPY_SIZE=64 \
  -e DEBUG_HIP_BLOCK_SYN=1024 \
  rocm/sgl-dev:upstream_20250312_v1 \
  python3 -m sglang.launch_server --model deepseek-ai/DeepSeek-R1 --tp 8 --trust-remote-code --chunked-prefill-size 131072 --enable-torch-comple --torch-compile-max-bs 256 --host 0.0.0.0 
```

直到出现类似的内容，表示容器已经启动成功：

```
[2025-04-01 03:42:11 DP7 TP7] Prefill batch. #new-seq: 1, #new-token: 7, #cached-token: 0, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 03:42:15] INFO:     127.0.0.1:37762 - "POST /generate HTTP/1.1" 200 OK
[2025-04-01 03:42:15] The server is fired up and ready to roll!
[2025-04-01 04:00:11] INFO:     172.17.0.1:55994 - "POST /v1/chat/completions HTTP/1.1" 200 OK
[2025-04-01 04:00:11 DP0 TP0] Prefill batch. #new-seq: 1, #new-token: 5, #cached-token: 1, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 04:00:43] INFO:     172.17.0.1:41068 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

确保本地可以访问DS 671B的容器：

```
curl http://localhost:30000/get_model_info 
{"model_path":"deepseek-ai/DeepSeek-R1","tokenizer_path":"deepseek-ai/DeepSeek-R1","is_generation":true} 
curl http://localhost:30000/generate -H "Content-Type: application/json" -d '{ "text": "Once upon a time,", "sampling_params": { "max_new_tokens": 16, "temperature": 0.6 } }'
```

接下来将Azure NSG的 30000端口打开，以便远程访问测试。

登录Linux压测客户端，执行如下cli安装evalscope压测工具：

```
pip install evalscope[perf] -U
pip install gradio
```

然后使用evalscope进行压测，该工具支持指定并发数量、总请求数量、输入输出token以及测试数据集。

- 如图想冲高总的吞吐量，将并发量增加、将输入tokens数量减少，例如100个并发，每个并发的输入tokens 100，关注总的tokens/s。
- 如果想测单请求的效果，将并发减少、将输入tokens数量增加，关注TTFT和单个请求的tokens/s。



在测试中，我使用一个比较极端的情况，即输入10000 tokens。

```
evalscope perf --url http://mi300x-xinyu.westus.cloudapp.azure.com:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --parallel 1 --number 20 --api openai --min-prompt-length 10000 --dataset "longalpaca" --max-tokens 2048 --min-tokens 2048 --stream 
```

接下来我列出几个不同并发和请求数量的测试结果。

单并发

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/2.jpg)



5并发 

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/3.jpg)



10并发

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Stress-Test-DeepSeek-671B-on-Azure-MI300X/images/4.jpg)



### 额外性能参数

```
--enable-torch-compile
```

参数AMD MI300X的环境暂时不支持

```
 --enable-dp-attention 
```

参数AMD环境支持，但在并发量低的时候，设置这个参数无法增加性能；并发量高的时候有待观察。