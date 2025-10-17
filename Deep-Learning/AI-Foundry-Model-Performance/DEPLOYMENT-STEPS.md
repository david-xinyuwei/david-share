# Azure 部署指南 - 逐步执行

## 前提条件

确保已安装：
- Azure CLI: `az --version`
- Azure Developer CLI: `azd version`

## 步骤 1: 登录 Azure

```powershell
# 登录到 Azure
az login

# 如果有多个订阅，查看列表
az account list --output table

# 设置要使用的订阅
az account set --subscription "您的订阅名称或ID"

# 验证当前订阅
az account show
```

## 步骤 2: 初始化 azd（首次运行）

```powershell
# 在项目目录中初始化
azd init

# 系统会询问：
# - Environment name: 输入 dev 或 prod
# - Subscription: 选择您的订阅
# - Location: 选择 eastus 或其他区域
```

## 步骤 3: 预览将要创建的资源

```powershell
# 查看会创建什么资源（不会真的创建）
azd provision --preview

# 这会显示：
# - 资源组名称
# - 将创建的资源列表
# - 预估费用（如果有）
```

## 步骤 4: 检查和修改配置（可选）

如果您想修改资源名称或位置：

```powershell
# 编辑参数文件
notepad infra\main.parameters.json
```

修改示例：
```json
{
  "parameters": {
    "location": {
      "value": "westus"  # 改成您想要的区域
    },
    "resourceGroupName": {
      "value": "rg-my-custom-name"  # 改成您想要的名称
    }
  }
}
```

## 步骤 5: 部署资源

```powershell
# 方式 1: 一键部署（推荐）
azd up

# 方式 2: 分步部署
azd provision  # 只创建基础设施
azd deploy     # 只部署应用
```

部署过程中会：
1. 创建资源组
2. 部署 Application Insights
3. 部署 Log Analytics
4. 部署 Key Vault
5. 部署 Storage Account
6. 部署 Azure ML Workspace
7. 设置 Python 环境
8. 安装依赖

## 步骤 6: 验证部署

```powershell
# 查看部署状态
azd show

# 获取输出值
azd env get-values

# 查看 Application Insights 连接字符串
azd env get-value APPINSIGHTS_CONNECTION_STRING
```

## 步骤 7: 配置环境变量

```powershell
# 创建 .env 文件
Copy-Item .env.sample .env

# 编辑 .env，填入部署输出的值
notepad .env
```

示例 .env 内容：
```
APPINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;IngestionEndpoint=https://...
AZURE_ML_WORKSPACE=mlw-ai-foundry-perf-dev
AZURE_RESOURCE_GROUP=rg-ai-foundry-perf-dev
```

## 步骤 8: 测试部署

```powershell
# 激活 Python 环境
.\venv\Scripts\Activate.ps1

# 运行可观测性测试
python scripts\testing\example-observability.py

# 查看 Azure Portal
# 打开 Application Insights > Logs
# 运行查询查看日志
```

## 清理资源（当不再需要时）

```powershell
# 删除所有资源
azd down

# 或者只删除资源组
az group delete --name rg-ai-foundry-perf-dev
```

## 预估费用

基于默认配置的月度预估费用：

| 资源 | SKU | 预估费用/月 |
|------|-----|------------|
| Application Insights | 基础 | ~$0-50 (基于使用量) |
| Log Analytics | 按需 | ~$0-30 (基于使用量) |
| Key Vault | 标准 | ~$0.03/10000操作 |
| Storage Account | Standard LRS | ~$5-20 |
| Azure ML Workspace | 基础 | 免费 (仅计算收费) |

**注意：** 
- 大部分费用来自 GPU 计算（当您部署模型时）
- Application Insights 和 Log Analytics 前 5GB/月免费
- 如果只是测试，建议部署后尽快清理

## 故障排除

### 错误：订阅未注册资源提供程序

```powershell
# 注册必需的资源提供程序
az provider register --namespace Microsoft.MachineLearningServices
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.Storage

# 检查注册状态
az provider show --namespace Microsoft.MachineLearningServices --query "registrationState"
```

### 错误：名称已被占用

Key Vault 和 Storage Account 名称必须全局唯一。如果出错：

```powershell
# 修改 infra\main.bicep 中的 uniqueString 或直接指定名称
```

### 错误：配额不足

如果缺少 GPU 配额：

```powershell
# 检查配额
az ml compute list-usage --location eastus --resource-group your-rg --workspace-name your-workspace

# 申请增加配额（通过 Azure Portal）
```

## 常见问题

**Q: 必须部署所有资源吗？**  
A: 不必须。您可以只部署需要的部分，或者修改 Bicep 文件删除不需要的资源。

**Q: 部署需要多长时间？**  
A: 通常 5-10 分钟，取决于网络和 Azure 区域。

**Q: 可以使用现有的资源吗？**  
A: 可以。修改 Bicep 文件使用现有资源的 ID，而不是创建新的。

**Q: 如何只部署监控功能？**  
A: 运行 `az deployment group create` 只部署 monitoring.bicep 模块。

## 下一步

部署成功后：
1. 运行 `python scripts/deployment/deploymodels-powershell-20250405.py` 部署模型
2. 运行 `python scripts/testing/press-phi4-0403.py` 进行性能测试
3. 在 Azure Portal 中查看 Application Insights 的监控数据
4. 使用 correlation ID 在日志中追踪请求

## 需要帮助？

- 查看详细文档：`docs\DEPLOYMENT.md`
- 检查合规性：`docs\COMPLIANCE.md`
- 了解架构：`docs\ARCHITECTURE.md`
