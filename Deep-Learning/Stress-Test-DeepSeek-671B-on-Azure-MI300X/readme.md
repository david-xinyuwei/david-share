## Fast Stress Test of DeepSeek 671B on Azure MI300X

**Refer to:**

*https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726*

快速创建Spot VM,使用spot VM并且使用密码方式认证

```
az vm create --name <VMNAME> --resource-group <RESOURCE_GROUP_NAME> --location <REGION>  --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 256 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password <YOUR_PASSWORD>

```

我使用的步骤以及不过部署过程：

```
xinyu [ ~ ]$ az vm create --name mi300x-xinyu --resource-group amdrg --location westus --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 512 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password azureadmin@123
```

部署步骤：

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

系统部署成功后，进行额外的运行准备：

```
mkdir -p /mnt/resource_nvme/
sudo mdadm --create /dev/md128 -f --run --level 0 --raid-devices 8 $(ls /dev/nvme*n1)  
sudo mkfs.xfs -f /dev/md128 
sudo mount /dev/md128 /mnt/resource_nvme 
sudo chmod 1777 /mnt/resource_nvme  
```

使用本地NVME临时磁盘用作docker的运行环境，需要注意的是，VM重启以后，临时磁盘上的内容会丢失：

```bash
mkdir –p /mnt/resource_nvme/hf_cache 
export HF_HOME=/mnt/resource_nvme/hf_cache 
```