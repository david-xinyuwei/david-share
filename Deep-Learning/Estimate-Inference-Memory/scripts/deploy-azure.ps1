# ============================================
# Azure App Service Deployment Script (PowerShell)
# ============================================

param(
    [string]$ResourceGroup = "rg-llm-memory-estimator",
    [string]$AppName = "llm-memory-$(Get-Date -Format 'yyyyMMddHHmmss')",
    [string]$Location = "eastus",
    [string]$Sku = "B1"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Azure App Service Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Resource Group: $ResourceGroup"
Write-Host "  App Name: $AppName"
Write-Host "  Location: $Location"
Write-Host "  SKU: $Sku"
Write-Host ""

# Check Azure CLI
Write-Host "1. Checking Azure CLI..." -ForegroundColor Yellow
if (!(Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Azure CLI not found. Please install it first." -ForegroundColor Red
    Write-Host "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
}

# Check login
Write-Host "2. Checking Azure login..." -ForegroundColor Yellow
$account = az account show 2>$null
if (!$account) {
    Write-Host "Please login to Azure..." -ForegroundColor Yellow
    az login
}

# Create resource group
Write-Host ""
Write-Host "3. Creating resource group..." -ForegroundColor Yellow
az group create `
  --name $ResourceGroup `
  --location $Location `
  --output table

# Create App Service Plan
Write-Host ""
Write-Host "4. Creating App Service Plan..." -ForegroundColor Yellow
az appservice plan create `
  --name "plan-llm-estimator" `
  --resource-group $ResourceGroup `
  --is-linux `
  --sku $Sku `
  --output table

# Create Web App
Write-Host ""
Write-Host "5. Creating Web App..." -ForegroundColor Yellow
az webapp create `
  --name $AppName `
  --resource-group $ResourceGroup `
  --plan "plan-llm-estimator" `
  --runtime "PYTHON:3.11" `
  --output table

# Enable HTTPS
Write-Host ""
Write-Host "6. Enabling HTTPS..." -ForegroundColor Yellow
az webapp update `
  --name $AppName `
  --resource-group $ResourceGroup `
  --https-only true `
  --output table

# Configure app settings
Write-Host ""
Write-Host "7. Configuring app settings..." -ForegroundColor Yellow
az webapp config appsettings set `
  --name $AppName `
  --resource-group $ResourceGroup `
  --settings `
    SCM_DO_BUILD_DURING_DEPLOYMENT=true `
    PYTHON_VERSION=3.11 `
    PORT=8000 `
    WEBSITE_RUN_FROM_PACKAGE=0 `
  --output table

# Set startup command
Write-Host ""
Write-Host "8. Setting startup command..." -ForegroundColor Yellow
az webapp config set `
  --name $AppName `
  --resource-group $ResourceGroup `
  --startup-file "startup.sh" `
  --output table

# Deploy code
Write-Host ""
Write-Host "9. Deploying code..." -ForegroundColor Yellow
az webapp up `
  --name $AppName `
  --resource-group $ResourceGroup `
  --runtime "PYTHON:3.11" `
  --sku $Sku

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Deployment Complete! ✓" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "App URL: https://$AppName.azurewebsites.net" -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs:    az webapp log tail --name $AppName --resource-group $ResourceGroup"
Write-Host "  Restart app:  az webapp restart --name $AppName --resource-group $ResourceGroup"
Write-Host "  Delete all:   az group delete --name $ResourceGroup --yes --no-wait"
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
