# Azure App Service 部署指南

## 概述

这个Streamlit应用可以轻松部署到Azure App Service，让用户通过Web访问，无需本地安装。

## 🎯 部署方案

### 方案选择

| 方案 | 适用场景 | 成本 | 复杂度 |
|------|---------|------|--------|
| **Azure App Service (推荐)** | 生产环境 | 💰💰 | ⭐⭐ |
| **Azure Container Instances** | 测试/演示 | 💰 | ⭐⭐⭐ |
| **Azure Web Apps for Containers** | 容器化部署 | 💰💰 | ⭐⭐⭐ |
| **Streamlit Cloud (免费)** | 开源项目 | 免费 | ⭐ |

**推荐**: Azure App Service - 易于管理，支持自动扩展

---

## 📋 准备工作

### 前置要求

1. **Azure订阅**
   - 有效的Azure账户
   - 订阅权限

2. **开发工具**
   - Azure CLI
   - Git
   - Python 3.8+

3. **项目准备**
   - ✅ requirements.txt (已有)
   - ✅ 应用代码 (已有)
   - ⚠️ 需要添加部署配置

---

## 🚀 快速部署 (推荐方法)

### 方法1: 使用Azure Portal Web部署

#### 步骤1: 创建App Service

```bash
# 登录Azure
az login

# 创建资源组
az group create --name rg-llm-memory-estimator --location eastus

# 创建App Service Plan (Linux)
az appservice plan create \
  --name plan-llm-estimator \
  --resource-group rg-llm-memory-estimator \
  --is-linux \
  --sku B1

# 创建Web App
az webapp create \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --plan plan-llm-estimator \
  --runtime "PYTHON:3.11"
```

#### 步骤2: 配置部署

```bash
# 配置Git部署
az webapp deployment source config-local-git \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator

# 获取部署URL
az webapp deployment list-publishing-credentials \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --query "{Username:publishingUserName, Password:publishingPassword}"
```

#### 步骤3: 推送代码

```bash
# 添加Azure远程仓库
git remote add azure <deployment-url>

# 推送到Azure
git push azure master
```

---

### 方法2: 使用Azure CLI 一键部署

创建部署脚本 `deploy-azure.sh`:

```bash
#!/bin/bash

# 配置变量
RESOURCE_GROUP="rg-llm-memory-estimator"
APP_NAME="llm-memory-estimator-$(date +%s)"
LOCATION="eastus"
SKU="B1"

echo "开始部署到Azure App Service..."

# 创建资源组
az group create --name $RESOURCE_GROUP --location $LOCATION

# 创建App Service
az webapp up \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --runtime "PYTHON:3.11" \
  --sku $SKU \
  --location $LOCATION

echo "部署完成！"
echo "访问地址: https://$APP_NAME.azurewebsites.net"
```

---

## 📁 需要的配置文件

### 1. startup.sh (启动脚本)

```bash
#!/bin/bash

# 安装依赖
pip install -r requirements.txt

# 启动Streamlit
streamlit run src/web_estimator.py \
  --server.port 8000 \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false
```

### 2. .deployment (部署配置)

```ini
[config]
command = bash startup.sh
```

### 3. 更新 requirements.txt

确保包含所有依赖：

```txt
transformers>=4.30.0
torch>=2.0.0
streamlit>=1.28.0
```

### 4. .streamlit/config.toml (Streamlit配置)

```toml
[server]
port = 8000
address = "0.0.0.0"
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#0066cc"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

---

## 🔧 Azure App Service 配置

### 应用设置 (Application Settings)

在Azure Portal中配置：

```json
{
  "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
  "WEBSITE_RUN_FROM_PACKAGE": "0",
  "PYTHON_VERSION": "3.11",
  "PORT": "8000"
}
```

### 环境变量

如果需要HF Token:

```bash
az webapp config appsettings set \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --settings HF_API_TOKEN="your-token-here"
```

---

## 🔒 安全性配置

### 1. HTTPS 强制

```bash
az webapp update \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --https-only true
```

### 2. Azure AD 认证 (可选)

```bash
az webapp auth update \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --enabled true \
  --action LoginWithAzureActiveDirectory \
  --aad-client-id <client-id>
```

---

## 📊 监控配置

### Application Insights

```bash
# 创建Application Insights
az monitor app-insights component create \
  --app llm-memory-estimator-insights \
  --location eastus \
  --resource-group rg-llm-memory-estimator \
  --application-type web

# 获取Instrumentation Key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app llm-memory-estimator-insights \
  --resource-group rg-llm-memory-estimator \
  --query instrumentationKey -o tsv)

# 配置到App Service
az webapp config appsettings set \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY
```

### 添加到代码

在 `src/web_estimator.py` 开头添加：

```python
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler

# 配置Application Insights
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=f'InstrumentationKey={os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY")}'
))
```

---

## 💰 成本估算

### 定价层选择

| 层级 | 价格/月 | 适用场景 | 配置 |
|------|---------|---------|------|
| **F1 Free** | $0 | 测试 | 1GB RAM, 60分钟/天 |
| **B1 Basic** | ~$55 | 小型应用 | 1.75GB RAM, 无限制 |
| **S1 Standard** | ~$70 | 生产环境 | 1.75GB RAM, 自动扩展 |
| **P1v2 Premium** | ~$146 | 高性能 | 3.5GB RAM, 更快 |

**推荐**:
- 测试: F1 Free
- 演示: B1 Basic
- 生产: S1 Standard

---

## 🚀 完整部署流程

### 完整的一键部署脚本

创建 `azure-deploy-complete.sh`:

```bash
#!/bin/bash

# ============================================
# Azure App Service 完整部署脚本
# ============================================

set -e

# 配置
RESOURCE_GROUP="rg-llm-memory-estimator"
APP_NAME="llm-memory-$(date +%s)"
LOCATION="eastus"
SKU="B1"

echo "=========================================="
echo "  Azure App Service Deployment"
echo "=========================================="
echo ""

# 1. 登录检查
echo "1. Checking Azure login..."
az account show &> /dev/null || az login

# 2. 创建资源组
echo "2. Creating resource group..."
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --output none

# 3. 创建App Service Plan
echo "3. Creating App Service Plan..."
az appservice plan create \
  --name plan-llm-estimator \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku $SKU \
  --output none

# 4. 创建Web App
echo "4. Creating Web App..."
az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan plan-llm-estimator \
  --runtime "PYTHON:3.11" \
  --output none

# 5. 配置HTTPS
echo "5. Enabling HTTPS..."
az webapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --https-only true \
  --output none

# 6. 配置应用设置
echo "6. Configuring app settings..."
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    PORT=8000 \
  --output none

# 7. 部署代码
echo "7. Deploying code..."
az webapp up \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --runtime "PYTHON:3.11"

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "App URL: https://$APP_NAME.azurewebsites.net"
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "To view logs:"
echo "  az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "To delete resources:"
echo "  az group delete --name $RESOURCE_GROUP --yes"
echo "=========================================="
```

---

## 🧪 部署后测试

### 1. 健康检查

```bash
# 测试应用是否响应
curl https://llm-memory-estimator.azurewebsites.net

# 查看日志
az webapp log tail \
  --name llm-memory-estimator \
  --resource-group rg-llm-memory-estimator
```

### 2. 功能测试

访问以下URL测试：
- 主页: `https://<app-name>.azurewebsites.net`
- 健康检查: `https://<app-name>.azurewebsites.net/_stcore/health`

---

## 🔄 CI/CD 配置

### GitHub Actions

创建 `.github/workflows/azure-deploy.yml`:

```yaml
name: Deploy to Azure App Service

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Deploy to Azure Web App
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'llm-memory-estimator'
        slot-name: 'production'
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

---

## 📝 checklist

部署前检查清单：

- [ ] Azure订阅已准备
- [ ] Azure CLI已安装
- [ ] 项目代码已就绪
- [ ] requirements.txt完整
- [ ] 创建startup.sh
- [ ] 创建.streamlit/config.toml
- [ ] 测试本地运行正常
- [ ] 准备HF Token（如需要）

---

## ❓ 常见问题

### Q: 部署后应用无法访问？
A: 检查端口配置，确保Streamlit运行在8000端口

### Q: 如何查看日志？
A: `az webapp log tail --name <app-name> --resource-group <rg-name>`

### Q: 如何更新应用？
A: 推送新代码到Git或重新运行部署脚本

### Q: 成本如何控制？
A: 使用F1免费层测试，或在不用时停止App Service

---

## 🎯 下一步

部署完成后：

1. ✅ 配置自定义域名
2. ✅ 设置SSL证书
3. ✅ 配置监控和告警
4. ✅ 设置自动扩展规则
5. ✅ 配置备份策略

---

**准备好部署了吗？我可以帮您：**
1. 创建所需的配置文件
2. 生成部署脚本
3. 配置监控
