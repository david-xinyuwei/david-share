# Azure 一键部署指南 (使用 Azure Developer CLI)

> **🚀 真正的一键部署** - 使用 Azure Developer CLI (azd) 实现基础设施即代码 (IaC) 和自动化部署

---

## 📋 目录

- [什么是 Azure Developer CLI](#什么是-azure-developer-cli)
- [快速开始](#快速开始)
- [详细步骤](#详细步骤)
- [部署架构](#部署架构)
- [管理和监控](#管理和监控)
- [成本估算](#成本估算)
- [故障排除](#故障排除)

---

## 什么是 Azure Developer CLI

**Azure Developer CLI (azd)** 是微软推出的现代化开发者工具，用于：

- ✅ **基础设施即代码 (IaC)**: 使用 Bicep 模板定义 Azure 资源
- ✅ **一键部署**: 单个命令完成资源创建、应用构建和部署
- ✅ **环境管理**: 轻松管理开发、测试、生产环境
- ✅ **集成监控**: 自动配置 Application Insights
- ✅ **最佳实践**: 遵循 Azure Well-Architected Framework

### azd vs 传统部署方式

| 特性 | azd (推荐) | Azure CLI | Azure Portal |
|------|-----------|-----------|--------------|
| 部署方式 | 一键命令 | 多个命令 | 手动点击 |
| IaC 支持 | ✅ Bicep | ❌ 需手写 | ❌ 无 |
| 环境管理 | ✅ 内置 | ⚠️ 手动 | ⚠️ 手动 |
| 可重复性 | ✅ 高 | ⚠️ 中 | ❌ 低 |
| 学习曲线 | ✅ 简单 | ⚠️ 中等 | ✅ 简单 |
| 适用场景 | 现代应用 | 传统脚本 | 快速测试 |

---

## 快速开始

### 前置条件

1. **Azure Developer CLI** (必需)
2. **Azure 订阅** (必需)
3. **Git** (可选，用于版本控制)

### 🚀 三步部署

```powershell
# 1. 安装 Azure Developer CLI
winget install microsoft.azd

# 2. 登录 Azure
azd auth login

# 3. 一键部署！
azd up
```

**就这么简单！** 🎉

---

## 详细步骤

### 步骤 1: 安装 Azure Developer CLI

#### Windows

```powershell
# 使用 winget (推荐)
winget install microsoft.azd

# 或使用 PowerShell 脚本
powershell -ex AllSigned -c "Invoke-RestMethod 'https://aka.ms/install-azd.ps1' | Invoke-Expression"
```

#### Linux / WSL

```bash
curl -fsSL https://aka.ms/install-azd.sh | bash
```

#### macOS

```bash
brew tap azure/azd && brew install azd
```

#### 验证安装

```powershell
azd version
```

应该看到类似输出：
```
azd version 1.5.0 (commit 1234567)
```

---

### 步骤 2: 登录 Azure

```powershell
azd auth login
```

这会打开浏览器窗口进行身份验证。

#### 验证登录

```powershell
azd auth login --check-status
```

---

### 步骤 3: 部署应用

#### 方式 1: 使用 azd 命令 (推荐)

```powershell
# 在项目根目录执行
azd up
```

`azd up` 会依次执行：
1. **azd provision** - 创建 Azure 资源
2. **azd package** - 打包应用程序
3. **azd deploy** - 部署到 Azure

#### 方式 2: 使用部署脚本

```powershell
# Windows
.\scripts\deploy-azd.ps1

# Linux/Mac
chmod +x scripts/deploy-azd.sh
./scripts/deploy-azd.sh
```

#### 首次部署交互

azd 会询问几个问题：

```
? Enter a new environment name: dev
? Select an Azure Subscription: [选择您的订阅]
? Select an Azure location: East US
```

**推荐配置**:
- Environment name: `dev` (开发), `prod` (生产)
- Location: `eastus` (美东), `eastasia` (东亚), `chinanorth` (中国北部)

---

### 步骤 4: 验证部署

部署完成后，azd 会显示应用 URL：

```
SUCCESS: Your application was provisioned and deployed to Azure in X minutes.

You can view the resources created under the resource group rg-dev in Azure Portal:
https://portal.azure.com/#@/resource/subscriptions/.../resourceGroups/rg-dev

Endpoints:
  web: https://app-dev-xxxxx.azurewebsites.net
```

#### 访问应用

```powershell
# 在浏览器中打开
azd browse

# 或获取 URL
azd env get-values | Select-String "WEB_URI"
```

---

## 部署架构

### 资源拓扑

```
Azure Subscription
└── Resource Group (rg-<env-name>)
    ├── App Service Plan (plan-<env-name>)
    │   └── Web App (app-<env-name>)
    │       ├── Runtime: Python 3.11
    │       ├── Port: 8000
    │       └── Startup: startup.sh
    ├── Log Analytics Workspace (log-<env-name>)
    └── Application Insights (appi-<env-name>)
```

### 项目结构

```
├── azure.yaml                      # azd 配置文件
├── infra/                          # 基础设施即代码 (IaC)
│   ├── main.bicep                  # 主 Bicep 模板
│   └── core/
│       ├── host/
│       │   ├── appserviceplan.bicep
│       │   └── appservice.bicep
│       └── monitor/
│           └── monitoring.bicep
├── src/                            # 应用代码
│   ├── cli_estimator.py
│   └── web_estimator.py
├── requirements.txt                # Python 依赖
└── startup.sh                      # 启动脚本
```

### Bicep 模板说明

#### `infra/main.bicep` - 主模板

定义了整体架构：
- 资源组
- App Service Plan (B1 SKU)
- Web App (Python 3.11, Linux)
- Application Insights

#### `infra/core/host/appservice.bicep` - Web App 配置

```bicep
properties: {
  serverFarmId: appServicePlanId
  siteConfig: {
    linuxFxVersion: 'python|3.11'
    appCommandLine: 'startup.sh'        # 自动执行启动脚本
    alwaysOn: true                      # 避免冷启动
    http20Enabled: true                 # 启用 HTTP/2
    minTlsVersion: '1.2'                # 强制 TLS 1.2+
    appSettings: {
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'  # 自动安装依赖
      ENABLE_ORYX_BUILD: 'true'               # 启用 Oryx 构建
      WEBSITES_PORT: '8000'                   # Streamlit 端口
    }
  }
  httpsOnly: true                       # 强制 HTTPS
}
```

---

## 管理和监控

### 常用命令

#### 查看应用状态

```powershell
# 查看所有环境变量
azd env get-values

# 查看特定变量
azd env get-value WEB_URI
```

#### 重新部署

```powershell
# 仅部署代码更改 (不重新创建资源)
azd deploy

# 完整重新部署
azd up
```

#### 查看日志

```powershell
# 打开 Application Insights 监控面板
azd monitor

# 实时查看应用日志
azd monitor --logs
```

#### 环境管理

```powershell
# 列出所有环境
azd env list

# 切换环境
azd env select <env-name>

# 创建新环境 (如 prod)
azd env new prod
azd up  # 部署到新环境
```

#### 清理资源

```powershell
# 删除所有 Azure 资源
azd down

# 删除资源但保留环境配置
azd down --purge --force
```

---

## 成本估算

### 默认配置 (B1 SKU)

| 资源 | SKU/规格 | 月费用 (美元) |
|------|---------|--------------|
| App Service Plan | B1 (Basic) | ~$55 |
| Application Insights | Pay-as-you-go | ~$2-5 |
| Log Analytics | 5GB 免费额度 | $0 |
| **总计** | | **~$57-60/月** |

### 免费层配置 (F1 SKU)

修改 `infra/main.bicep`:

```bicep
module appServicePlan 'core/host/appserviceplan.bicep' = {
  params: {
    sku: {
      name: 'F1'        // 改为 F1
      tier: 'Free'      // 改为 Free
    }
  }
}
```

| 资源 | SKU/规格 | 月费用 |
|------|---------|--------|
| App Service Plan | F1 (Free) | $0 |
| Application Insights | 免费层 | $0 |
| **总计** | | **$0/月** |

⚠️ **F1 限制**:
- 60 分钟/天 CPU 配额
- 1GB 磁盘空间
- 不支持自定义域名
- 不支持 Always On

### 成本优化建议

1. **开发环境**: 使用 F1 免费层
2. **生产环境**: 使用 B1 基础层
3. **自动关闭**: 使用 azd down 删除不用的环境
4. **监控成本**: 在 Azure Portal 设置成本警报

---

## 故障排除

### 问题 1: azd 命令未找到

**错误**:
```
azd : The term 'azd' is not recognized...
```

**解决**:
```powershell
# 安装 Azure Developer CLI
winget install microsoft.azd

# 重启 PowerShell
```

---

### 问题 2: 部署失败 - 订阅未注册

**错误**:
```
The subscription is not registered to use namespace 'Microsoft.Web'
```

**解决**:
```powershell
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Insights
```

---

### 问题 3: 应用启动失败

**检查日志**:
```powershell
# 方式 1: 使用 azd
azd monitor --logs

# 方式 2: 使用 Azure CLI
az webapp log tail --name app-<env-name> --resource-group rg-<env-name>
```

**常见原因**:
1. **启动脚本权限**: 确保 `startup.sh` 有执行权限
2. **端口配置**: 检查 `WEBSITES_PORT` 设置为 8000
3. **依赖安装失败**: 检查 `requirements.txt` 格式

---

### 问题 4: 健康检查失败

**配置健康检查**:

在 `infra/core/host/appservice.bicep` 添加:

```bicep
healthCheckPath: '/_stcore/health'
```

---

### 问题 5: 部署很慢

**优化建议**:

1. **使用地理位置就近的 Azure 区域**
2. **检查网络连接**
3. **减少依赖包大小**

---

## 高级配置

### 自定义域名

```powershell
# 添加自定义域名
az webapp config hostname add \
  --webapp-name app-<env-name> \
  --resource-group rg-<env-name> \
  --hostname www.yourdomain.com
```

### 配置环境变量

```powershell
# 方式 1: 使用 azd
azd env set HF_API_TOKEN "your-token"
azd deploy

# 方式 2: 直接在 Bicep 中配置
# 编辑 infra/main.bicep，添加到 appSettings
```

### 自动扩展

编辑 `infra/core/host/appserviceplan.bicep`:

```bicep
sku: {
  name: 'S1'
  tier: 'Standard'
  capacity: 2  // 自动扩展到 2 个实例
}
```

### CI/CD 集成

#### GitHub Actions

```yaml
name: Azure Deployment

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install azd
        uses: Azure/setup-azd@v0.1.0
      
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Deploy
        run: azd up --no-prompt
```

---

## 文档参考

### 官方文档

- **Azure Developer CLI**: https://learn.microsoft.com/azure/developer/azure-developer-cli/
- **Bicep 语言**: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
- **App Service**: https://learn.microsoft.com/azure/app-service/

### 命令参考

```powershell
# 获取帮助
azd --help
azd up --help

# 查看详细日志
azd up --debug
```

### 项目模板

浏览更多 azd 模板：
- https://azure.github.io/awesome-azd/

---

## ✅ 总结

使用 Azure Developer CLI 部署的优势：

1. ✅ **一键部署**: `azd up` 完成所有操作
2. ✅ **基础设施即代码**: Bicep 模板版本控制
3. ✅ **环境隔离**: 轻松管理 dev/test/prod
4. ✅ **最佳实践**: HTTPS、监控、日志自动配置
5. ✅ **可重复性**: 任何人都能用相同配置部署
6. ✅ **成本可控**: 轻松切换 SKU 和删除资源

---

**准备好了吗？开始部署吧！** 🚀

```powershell
azd up
```

---

**创建日期**: 2025年10月17日  
**适用版本**: Azure Developer CLI 1.5.0+  
**最后更新**: 2025年10月17日
