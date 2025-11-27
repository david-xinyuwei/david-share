# Deployment Guide for Azure Developer CLI (azd)

This guide explains how to deploy the AI Foundry Model Performance Testing infrastructure using Azure Developer CLI (azd).

## Prerequisites

1. **Install Azure Developer CLI (azd)**
   - Windows: `winget install microsoft.azd`
   - macOS: `brew tap azure/azd && brew install azd`
   - Linux: `curl -fsSL https://aka.ms/install-azd.sh | bash`

2. **Install Azure CLI**
   - Follow instructions at: https://learn.microsoft.com/cli/azure/install-azure-cli

3. **Azure Subscription**
   - Active Azure subscription with appropriate permissions
   - GPU quota for NC-series VMs (A100/H100)

## Quick Start with azd

### 1. Initialize and Login

```powershell
# Login to Azure
azd auth login

# Or use Azure CLI authentication
az login
```

### 2. One-Click Deploy

Deploy all infrastructure and setup the environment:

```powershell
# Deploy everything with one command
azd up
```

This command will:
- Provision all Azure resources (ML Workspace, Storage, Key Vault, App Insights, etc.)
- Set up Python virtual environment
- Install all required dependencies
- Configure environment variables

### 3. Verify Deployment

After deployment completes, verify the resources:

```powershell
# Check deployed resources
azd show

# View environment variables
azd env get-values
```

### 4. Run Performance Tests

```powershell
# Activate Python environment
.\venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate   # Linux/macOS

# Set environment variables from deployment
$env:API_URL = azd env get-value API_URL
$env:APPINSIGHTS_CONNECTION_STRING = azd env get-value APPINSIGHTS_CONNECTION_STRING

# Run deployment script
python scripts/deployment/deploymodels-powershell-20250405.py

# Run performance tests
python scripts/testing/press-phi4-0403.py
```

### 5. Clean Up Resources

When you're done, delete all resources:

```powershell
# Delete all Azure resources
azd down
```

This will:
- Delete all provisioned Azure resources
- Clean up the resource group
- Remove local environment configuration

## Manual Deployment (Alternative)

If you prefer manual deployment using Bicep:

### 1. Deploy Infrastructure

```powershell
# Set variables
$location = "eastus"
$resourceGroup = "rg-ai-foundry-perf"

# Create resource group
az group create --name $resourceGroup --location $location

# Deploy Bicep template
az deployment group create `
  --resource-group $resourceGroup `
  --template-file infra/main.bicep `
  --parameters infra/main.parameters.json
```

### 2. Get Deployment Outputs

```powershell
# Get Application Insights connection string
$appInsightsConnectionString = az deployment group show `
  --resource-group $resourceGroup `
  --name main `
  --query properties.outputs.appInsightsConnectionString.value `
  -o tsv

# Get ML Workspace name
$mlWorkspaceName = az deployment group show `
  --resource-group $resourceGroup `
  --name main `
  --query properties.outputs.mlWorkspaceName.value `
  -o tsv

# Get Key Vault name
$keyVaultName = az deployment group show `
  --resource-group $resourceGroup `
  --name main `
  --query properties.outputs.keyVaultName.value `
  -o tsv

Write-Host "ML Workspace: $mlWorkspaceName"
Write-Host "Key Vault: $keyVaultName"
Write-Host "App Insights Connection String: $appInsightsConnectionString"
```

### 3. Configure Environment

```powershell
# Copy .env.sample to .env
Copy-Item .env.sample .env

# Edit .env with your values
notepad .env
```

Add the values from deployment outputs:
```
APPINSIGHTS_CONNECTION_STRING=<your-connection-string>
AZURE_ML_WORKSPACE=<your-workspace-name>
AZURE_RESOURCE_GROUP=<your-resource-group>
```

### 4. Setup Python Environment

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Observability Features

### Application Insights Integration

The deployment includes Application Insights for observability:

1. **Correlation IDs**: Each request is tracked with a unique correlation ID
2. **Structured Logging**: All logs include context and metadata
3. **Custom Metrics**: Performance metrics are tracked (TTFT, throughput, etc.)
4. **Request Tracking**: API calls and their duration are logged

### Using Observability in Scripts

Example integration in your test scripts:

```python
from scripts.utils.observability import init_observability

# Initialize observability
obs = init_observability()

# Log with correlation ID
obs.log_info("Starting performance test", model="Phi-4", instance_type="NC24")

# Track custom metrics
obs.track_metric("time_to_first_token", ttft_value, model="Phi-4")

# Track requests
obs.track_request("model_inference", duration_ms=1234, success=True)
```

### View Logs and Metrics

1. Go to Azure Portal
2. Navigate to your Application Insights resource
3. Use "Logs" to query telemetry:

```kusto
// View all logs with correlation IDs
traces
| where timestamp > ago(1h)
| project timestamp, message, customDimensions
| order by timestamp desc

// View custom metrics
customMetrics
| where name == "time_to_first_token"
| summarize avg(value), max(value), min(value) by bin(timestamp, 5m)
```

## Security Best Practices

### Environment Variables

Never commit sensitive values to git. Always use:

1. **`.env` file** (git-ignored) for local development
2. **Azure Key Vault** for production secrets
3. **Environment variables** in deployment

### Storing API Keys

Store API keys in Key Vault:

```powershell
# Store API key in Key Vault
az keyvault secret set `
  --vault-name $keyVaultName `
  --name "api-key" `
  --value "your-api-key"

# Retrieve in Python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url=f"https://{keyVaultName}.vault.azure.net/", credential=credential)
api_key = client.get_secret("api-key").value
```

## Troubleshooting

### azd up fails

1. Check Azure CLI authentication: `az account show`
2. Verify subscription has required permissions
3. Check GPU quota availability: `az vm list-usage --location eastus`

### Application Insights not working

1. Verify connection string is set: `echo $env:APPINSIGHTS_CONNECTION_STRING`
2. Check Python packages are installed: `pip list | grep opencensus`
3. View local logs for any errors

### Resource deployment fails

1. Check deployment logs: `azd show`
2. Verify naming constraints (Key Vault name must be unique)
3. Ensure region supports required resources

## Next Steps

- [Deploy Models](../readme.md#deploying-models-methods)
- [Run Performance Tests](../readme.md#performance-test-on-managed-compute)
- [View Test Results](../testlogs/)

## Support

For issues or questions:
- Check the [main README](../readme.md)
- Review [troubleshooting guide](../readme.md#troubleshooting)
- Open an issue on GitHub
