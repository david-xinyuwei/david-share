#!/bin/bash

# ============================================
# Azure App Service 快速部署脚本
# ============================================

set -e

# 配置变量
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-llm-memory-estimator}"
APP_NAME="${APP_NAME:-llm-memory-$(date +%s)}"
LOCATION="${LOCATION:-eastus}"
SKU="${SKU:-B1}"

echo "=========================================="
echo "  Azure App Service Deployment"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  App Name: $APP_NAME"
echo "  Location: $LOCATION"
echo "  SKU: $SKU"
echo ""

# 检查Azure CLI
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI not found. Please install it first."
    echo "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# 登录检查
echo "1. Checking Azure login..."
if ! az account show &> /dev/null; then
    echo "Please login to Azure..."
    az login
fi

# 创建资源组
echo ""
echo "2. Creating resource group..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table

# 创建App Service Plan
echo ""
echo "3. Creating App Service Plan..."
az appservice plan create \
  --name "plan-llm-estimator" \
  --resource-group "$RESOURCE_GROUP" \
  --is-linux \
  --sku "$SKU" \
  --output table

# 创建Web App
echo ""
echo "4. Creating Web App..."
az webapp create \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --plan "plan-llm-estimator" \
  --runtime "PYTHON:3.11" \
  --output table

# 配置HTTPS
echo ""
echo "5. Enabling HTTPS..."
az webapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --https-only true \
  --output table

# 配置应用设置
echo ""
echo "6. Configuring app settings..."
az webapp config appsettings set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    PYTHON_VERSION=3.11 \
    PORT=8000 \
    WEBSITE_RUN_FROM_PACKAGE=0 \
  --output table

# 配置启动命令
echo ""
echo "7. Setting startup command..."
az webapp config set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --startup-file "startup.sh" \
  --output table

# 部署代码
echo ""
echo "8. Deploying code..."
az webapp up \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --runtime "PYTHON:3.11" \
  --sku "$SKU"

echo ""
echo "=========================================="
echo "  Deployment Complete! ✓"
echo "=========================================="
echo ""
echo "App URL: https://$APP_NAME.azurewebsites.net"
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "Useful commands:"
echo "  View logs:    az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo "  Restart app:  az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo "  Delete all:   az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo ""
echo "=========================================="
