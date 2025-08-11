# Secure-by-Default Networking and customer role for an AI Foundry Project

Step-by-step network hardening workflow

1. Create a Private Endpoint for the AI Foundry project.

    • Location: VNet `A100VM-vnet`, subnet `default`

    • Public network access for the Foundry resource is disabled.

2. Deploy a Windows 10 VM in the same subnet `A100VM-vnet/default`.

    • No public IP is assigned.

    • Its NIC is attached to an NSG that blocks **all inbound** ports (default outbound remains allowed).

3. Provision Azure Bastion.

    • Place the Bastion host in the dedicated subnet `A100VM-vnet/AzureBastionSubnet`.

    • Administrators connect to the VM through Bastion over HTTPS; RDP/SSH ports stay closed on the VM’s NSG.

4. Add a subnet-level NAT Gateway.

    • Create a Standard static public IP for SNAT.

    • Create the NAT Gateway and attach the public IP.

    • Associate the NAT Gateway with subnet `A100VM-vnet/default`.

5. Validate.

    • From the Win10 VM (via Bastion), browse to `ai.azure.com`—traffic egresses through the NAT Gateway.

    • External hosts cannot initiate inbound connections to either the VM or the AI Foundry project.

**Result:** end-to-end private connectivity to the Foundry project, zero  public exposure for the VM, and controlled outbound Internet access via  NAT Gateway.

------

## Architecture Overview

```
+--------------------------------------------------------------+
|  VNet: A100VM-vnet  (region: australiaeast)                  |
|                                                              |
|  Subnet: AzureBastionSubnet                                  |
|  • Azure Bastion host  <─ Use to connect following VM        |
|                                                              |
|  Subnet: default                                             |
|  • AI Foundry Private Endpoint  ──► Foundry project (PaaS)   |
|  • Win10 VM  (no public IP)   ──► outbound via NAT Gateway   |
|                                                              |
|+--------------------------------------------------------------+

• AI Foundry Agent: reachable only through Private Link  
• Win10 VM: outbound-only through NAT Gateway  
```

## AI foundry configuration

Disable all public network access:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/2.png)

Create AI foundry private endpoint and attach a subnet:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/7.png)

AI Agent and AOAI model could not be access by my laptop:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/4.png)



## Create a VM in same subnet with AI Foundry

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/5.png)

Do not allocate public IP for the VM:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/6.png)



## Create a baston in different subnet but same vNet with AI Foundry

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/14.png)

Check vNet cofiguration:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/8.png)

## Create NAT Gateway on subnet

```
############################################################
# 0.  EDIT THESE FOUR VARIABLES FIRST
############################################################
RG="A100VM_group"              # resource group that hosts the VNet
VNET="A100VM-vnet"             # VNet name
SUBNET="default"               # subnet that needs outbound Internet
LOC="australiaeast"            # Azure region

# You may also change these resource names if you like
NATGW_NAME="natgw-pe"
PIP_NAME="natgw-ip"

############################################################
# 1. Create a static Standard Public IP (used only for SNAT)
############################################################
az network public-ip create \
  --resource-group $RG \
  --name $PIP_NAME \
  --sku Standard \
  --allocation-method Static \
  --location $LOC

############################################################
# 2. Create the NAT Gateway and attach the Public IP
############################################################
az network nat gateway create \
  --resource-group $RG \
  --name $NATGW_NAME \
  --location $LOC \
  --public-ip-addresses $PIP_NAME \
  --idle-timeout 4          # minutes; optional

############################################################
# 3. Bind the NAT Gateway to the target subnet
############################################################
az network vnet subnet update \
  --resource-group $RG \
  --vnet-name $VNET \
  --name $SUBNET \
  --nat-gateway $NATGW_NAME

```

Open egress 80/443 ports on NSG of VM:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/13.png)

## Validation

Connect VM via Baston:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/9.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/10.png)

Inside the Win10 VM (via Bastion session):

```
nslookup ai.azure.com

# Should succeed – outbound 443 through NAT GW
Test-NetConnection ai.azure.com -Port 443
```

• Curl/Invoke-WebRequest to public sites succeeds.
 • Inbound `Test-NetConnection -Port 3389` from the Internet fails, proving the VM is not exposed

Agent could be accessed within VM:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/11.png)



AODI Model could be accessed within VM:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/12.png)



## Summary

A single Virtual Network hosts everything: an AI Foundry project, a jump-host (Azure Bastion) and a workload VM.
 By combining three native services:

1. **Private Endpoint** for Foundry (ingress locked to VNet),
2. **Azure Bastion** for admin access (RDP/SSH over HTTPS only)
3. **Subnet-level NAT Gateway** for outbound-only Internet

we achieve “secure-by-default” networking:

• The Foundry project is visible only on the VNet’s RFC-1918 address; no public DNS/IP exists.
 • The Windows 10 VM has **zero** public IPs yet can browse external sites (ai.azure.com) through the NAT Gateway.
 • NSG keeps every inbound port closed; attackers on the Internet have no path to either resource.



## Define customer role of AI foundry

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/19.png)

This part shows you how to automate RBAC setup for Azure AI Foundry:

1. upload or update a custom role “AI Developer without Compute”;
2. assign that role to a chosen user, group, or service principal;
3. (optionally) create a new Entra ID user with a temporary password and require MFA;
4. verify the assignment.
   After running it, the principal can explore and invoke existing AI resources but cannot deploy online endpoints or create managed compute, giving you fine-grained control over development privileges while keeping infrastructure changes restricted.

```
(base) root@linuxworkvm:~# cat role.json
{
  "Name": "AI Developer without Compute",
  "IsCustom": true,
  "Description": "Can perform all actions within an Azure AI resource besides managing the resource itself and deploying models",
  "Actions": [
    "Microsoft.MachineLearningServices/workspaces/*/read",
    "Microsoft.MachineLearningServices/workspaces/*/action",
    "Microsoft.MachineLearningServices/workspaces/*/delete",
    "Microsoft.MachineLearningServices/workspaces/*/write",
    "Microsoft.MachineLearningServices/locations/*/read",
    "Microsoft.Authorization/*/read"
  ],
  "NotActions": [
    "Microsoft.MachineLearningServices/workspaces/delete",
    "Microsoft.MachineLearningServices/workspaces/write",
    "Microsoft.MachineLearningServices/workspaces/listKeys/action",
    "Microsoft.MachineLearningServices/workspaces/hubs/write",
    "Microsoft.MachineLearningServices/workspaces/hubs/delete",
    "Microsoft.MachineLearningServices/workspaces/featurestores/write",
    "Microsoft.MachineLearningServices/workspaces/featurestores/delete",
    "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/*/write",
    "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/*/delete",
    "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments/*/write",
    "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments/*/delete",
    "Microsoft.MachineLearningServices/workspaces/computes/*/write",
    "Microsoft.MachineLearningServices/workspaces/computes/*/delete",
    "Microsoft.Resources/deployments/*"
  ],
  "DataActions": [
    "Microsoft.CognitiveServices/accounts/OpenAI/*",
    "Microsoft.CognitiveServices/accounts/SpeechServices/*",
    "Microsoft.CognitiveServices/accounts/ContentSafety/*"
  ],
  "NotDataActions": [],
  "AssignableScopes": [
    "/subscriptions/08f95cf**"
  ]
}
```

**Run steps:**

Set env：

```
#——— 用户可自定义的 5 个变量 ———#
SUBSCRIPTION_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
ROLE_FILE="./role.json"                               # 若文件名不同请修改
ROLE_NAME="AI Developer without Compute"
USER_UPN="xinyuwei@mngenv183724.onmicrosoft.com"      # 目标用户或组/应用
TENANT_ID="9812**"      # 可省略；多租户时指定
```

Login azure:

```
#——— 登陆租户并切换订阅 ———#
az login --tenant $TENANT_ID            # 已登录可跳过
az account set --subscription $SUBSCRIPTION_ID
```

Define new role:

```
#——— 创建或更新自定义角色 ———#
az role definition create  --role-definition $ROLE_FILE \
  || az role definition update --role-definition $ROLE_FILE
  
```

Get  ObjectId and assign role to  ObjectId:

```
#——— 获取主体对象 ID（用户 / 组 / 服务主体） ———#
ObjectId=$(az ad user show --id $USER_UPN --query id -o tsv)
echo "ObjectId = $ObjectId"
#——— 分配角色 ———#
az role assignment create \
  --assignee $ObjectId \
  --role "$ROLE_NAME" \
  --scope /subscriptions/$SUBSCRIPTION_ID
```

After login with AI foundry with xinyuwei@mngenv183724.onmicrosoft.com, user could only using existing models, rather than create models:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/16.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/AI-Agent-Private-Endpoint/images/18.png)

**Refer to：**

***https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/configure-private-link?tabs=azure-portal&pivots=fdp-project***



