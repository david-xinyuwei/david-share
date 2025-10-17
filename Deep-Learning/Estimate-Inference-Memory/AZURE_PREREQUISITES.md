# Azure 部署前置条件检查

## ⚠️ 重要提示

在部署到Azure之前，您需要先完成以下准备工作。

---

## 📋 前置条件检查清单

### 1. ✅ Azure CLI 安装

#### 检查是否已安装

```powershell
az --version
```

如果看到错误"无法将'az'项识别为 cmdlet..."，说明需要安装。

#### 安装 Azure CLI

**Windows**:
```powershell
# 方法1: 使用 winget (推荐)
winget install -e --id Microsoft.AzureCLI

# 方法2: 下载MSI安装包
# 访问: https://aka.ms/installazurecliwindows
```

**Linux**:
```bash
# Ubuntu/Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# RHEL/CentOS
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo dnf install azure-cli
```

**Mac**:
```bash
brew update && brew install azure-cli
```

---

### 2. ✅ Azure 订阅

#### 检查订阅状态

```powershell
# 登录Azure
az login

# 查看当前订阅
az account show

# 列出所有订阅
az account list --output table
```

#### 如果没有订阅

1. 访问 [Azure Portal](https://portal.azure.com)
2. 注册Azure账户
3. 创建订阅（可使用免费试用）

---

### 3. ✅ 权限验证

确保您的账户有以下权限：
- ✅ 创建资源组
- ✅ 创建App Service
- ✅ 配置网络设置

```powershell
# 验证权限
az group create --name test-permissions --location eastus --dry-run
```

---

## 🚀 快速安装指南

### Windows 完整步骤

```powershell
# 1. 安装 Azure CLI
winget install -e --id Microsoft.AzureCLI

# 2. 重启 PowerShell 使路径生效
# 关闭当前窗口，重新打开

# 3. 验证安装
az --version

# 4. 登录 Azure
az login

# 5. 验证登录
az account show

# 6. 现在可以部署了！
.\scripts\deploy-azure.ps1
```

---

## 🧪 部署前测试

### 测试1: Azure CLI 可用性

```powershell
az --version
```

**期望输出**:
```
azure-cli                         2.x.x
core                              2.x.x
telemetry                         1.x.x
...
```

### 测试2: 登录状态

```powershell
az account show
```

**期望输出**:
```json
{
  "environmentName": "AzureCloud",
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "isDefault": true,
  "name": "Your Subscription Name",
  "state": "Enabled",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "user": {
    "name": "user@example.com",
    "type": "user"
  }
}
```

### 测试3: 权限检查

```powershell
# 测试是否可以创建资源组
az group create --name test-deployment --location eastus --output table

# 清理测试资源
az group delete --name test-deployment --yes --no-wait
```

---

## ⚠️ 常见问题

### Q1: Azure CLI 安装后仍然找不到 `az` 命令

**解决方法**:
1. 关闭所有 PowerShell 窗口
2. 重新打开 PowerShell
3. 如果还不行，重启电脑

### Q2: `az login` 无法打开浏览器

**解决方法**:
```powershell
# 使用设备代码登录
az login --use-device-code
```

### Q3: 没有Azure订阅

**解决方法**:
1. 访问 https://azure.microsoft.com/free/
2. 注册免费账户（包含$200信用额度）
3. 创建订阅

### Q4: 权限不足

**解决方法**:
1. 联系Azure管理员
2. 请求"Contributor"角色
3. 或使用个人订阅

---

## 💰 成本估算（Azure免费试用）

### 免费试用包含

- ✅ $200 美元信用额度（30天）
- ✅ 12个月免费服务
- ✅ 永久免费的基础服务

### 本项目预估成本

**免费层 (F1)**:
- 费用: $0/月
- 限制: 60分钟/天

**基础层 (B1)**:
- 费用: ~$55/月
- 用免费试用额度: 可运行3-4个月

---

## ✅ 准备完成检查

运行此检查脚本确认所有条件满足：

```powershell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Azure Deployment Prerequisites Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Azure CLI
Write-Host "1. Checking Azure CLI..." -ForegroundColor Yellow
$azVersion = az --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Azure CLI installed" -ForegroundColor Green
} else {
    Write-Host "   ✗ Azure CLI NOT installed" -ForegroundColor Red
    Write-Host "   Install: winget install -e --id Microsoft.AzureCLI" -ForegroundColor Yellow
    exit 1
}

# 检查登录状态
Write-Host ""
Write-Host "2. Checking Azure login..." -ForegroundColor Yellow
$account = az account show 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Logged in to Azure" -ForegroundColor Green
    $accountInfo = $account | ConvertFrom-Json
    Write-Host "   Subscription: $($accountInfo.name)" -ForegroundColor Cyan
} else {
    Write-Host "   ✗ NOT logged in" -ForegroundColor Red
    Write-Host "   Run: az login" -ForegroundColor Yellow
    exit 1
}

# 检查权限
Write-Host ""
Write-Host "3. Checking permissions..." -ForegroundColor Yellow
$testRG = "test-permissions-$(Get-Random)"
$createTest = az group create --name $testRG --location eastus 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Has required permissions" -ForegroundColor Green
    # 清理测试资源
    az group delete --name $testRG --yes --no-wait 2>&1 | Out-Null
} else {
    Write-Host "   ✗ Insufficient permissions" -ForegroundColor Red
    Write-Host "   Contact your Azure administrator" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✓ All prerequisites met!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Ready to deploy! Run:" -ForegroundColor Cyan
Write-Host "  .\scripts\deploy-azure.ps1" -ForegroundColor Yellow
Write-Host ""
```

保存为 `scripts/check-azure-prerequisites.ps1`

---

## 🎯 下一步

### 如果所有检查都通过

```powershell
# 部署到Azure！
.\scripts\deploy-azure.ps1
```

### 如果检查失败

1. 按照错误提示安装/配置
2. 重新运行检查脚本
3. 确认所有项都是 ✓

---

## 📞 需要帮助？

### 官方文档

- Azure CLI安装: https://docs.microsoft.com/cli/azure/install-azure-cli
- Azure免费账户: https://azure.microsoft.com/free/
- App Service文档: https://docs.microsoft.com/azure/app-service/

### 社区支持

- Azure论坛: https://docs.microsoft.com/answers/
- Stack Overflow: 标签 `azure-cli`, `azure-app-service`

---

**准备好了吗？按照上面的步骤完成准备工作，然后就可以部署了！** 🚀

创建日期: 2025年10月17日  
最后更新: 2025年10月17日
