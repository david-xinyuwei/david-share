# Deployment Guide

## Prerequisites

### Required Tools

1. **Azure Developer CLI (azd)**
   ```bash
   # Windows (PowerShell)
   powershell -ex AllSigned -c "Invoke-RestMethod 'https://aka.ms/install-azd.ps1' | Invoke-Expression"
   
   # Verify installation
   azd version
   ```

2. **Azure CLI** (optional, for manual operations)
   ```bash
   # Windows
   winget install Microsoft.AzureCLI
   
   # Verify installation
   az version
   ```

3. **Python 3.9+**
   ```bash
   python --version
   ```

4. **Git**
   ```bash
   git --version
   ```

### Azure Requirements

- Active Azure subscription
- Permissions to create resources
- Access to Azure AI Model Catalog (for MedImageParse models)

## First-Time Deployment

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/MedImageParse.git
cd MedImageParse
```

### Step 2: Login to Azure

```bash
azd auth login
```

This will open a browser for authentication.

### Step 3: Initialize Environment

```bash
azd init
```

You'll be prompted to:
- **Environment Name**: Choose a unique name (e.g., `medimage-prod`)
- **Azure Location**: Select region (e.g., `swedencentral`, `eastus`)

### Step 4: Set Required Parameters

You need to provide the MedImageParse model endpoints and keys:

```bash
azd env set AZURE_OPENAI_ENDPOINT_2D "https://your-2d-endpoint.ml.azure.com/score"
azd env set AZURE_OPENAI_KEY_2D "your-2d-api-key"
azd env set AZURE_OPENAI_ENDPOINT_3D "https://your-3d-endpoint.ml.azure.com/score"
azd env set AZURE_OPENAI_KEY_3D "your-3d-api-key"
```

### Step 5: Deploy Infrastructure and Application

```bash
azd up
```

This single command will:
1. Provision all Azure resources (Resource Group, App Service, Key Vault, Application Insights)
2. Configure security (Managed Identity, RBAC)
3. Store secrets in Key Vault
4. Deploy the application
5. Enable authentication

**Estimated time**: 5-10 minutes

### Step 6: Verify Deployment

```bash
azd show
```

This displays:
- Application URL
- Resource names
- Deployment status

Open the application URL in your browser. You should be redirected to login with your Microsoft account.

## Subsequent Deployments

### Deploy Application Changes Only

```bash
azd deploy
```

This updates the application code without reprovisioning infrastructure.

### Deploy Infrastructure Changes

```bash
azd provision
```

This updates infrastructure based on Bicep template changes.

### Full Redeployment

```bash
azd up
```

## Environment Management

### List Environments

```bash
azd env list
```

### Switch Environment

```bash
azd env select <environment-name>
```

### View Environment Variables

```bash
azd env get-values
```

### Update Environment Variable

```bash
azd env set VARIABLE_NAME "new-value"
```

## Manual Azure Portal Configuration

### Enable Entra ID Authentication (if not auto-configured)

1. Go to Azure Portal → Your App Service
2. Navigate to **Settings > Authentication**
3. Click **Add identity provider**
4. Select **Microsoft**
5. Choose **Create new app registration**
6. Set **Supported account types** to your organization
7. Click **Add**

### Configure Custom Domain (Optional)

1. Go to App Service → **Custom domains**
2. Click **Add custom domain**
3. Enter your domain name
4. Follow DNS validation steps
5. Add SSL certificate

### Scale Up/Out

#### Scale Up (Vertical)

1. Go to App Service → **Scale up (App Service plan)**
2. Select desired tier (B1, S1, P1V2, etc.)
3. Click **Apply**

#### Scale Out (Horizontal)

1. Go to App Service → **Scale out (App Service plan)**
2. Configure auto-scale rules:
   - CPU threshold: 70%
   - Instance count: 1-10
3. Save configuration

## Monitoring Setup

### View Application Insights

1. Go to Application Insights resource
2. Navigate to **Application map** for service topology
3. Check **Live metrics** for real-time monitoring
4. Use **Logs** for KQL queries

### Create Alerts

1. Go to Application Insights → **Alerts**
2. Click **New alert rule**
3. Select signal (e.g., Failed requests)
4. Set threshold (e.g., > 10 in 5 minutes)
5. Add action group (email, SMS, webhook)
6. Name and create alert

### Sample Alert Rules

**High Error Rate**
- Signal: `Failed requests`
- Threshold: > 5% in 5 minutes
- Action: Email to team

**Slow Response Time**
- Signal: `Server response time`
- Threshold: P95 > 10 seconds
- Action: Email to team

**High CPU Usage**
- Signal: `CPU Percentage`
- Threshold: > 80% for 10 minutes
- Action: Auto-scale + Email

## Troubleshooting

### Deployment Fails

**Error**: "Resource group already exists"
```bash
# Solution: Choose different environment name or delete existing
azd down --purge
azd up
```

**Error**: "Key Vault name already taken"
```bash
# Solution: Key Vault name must be globally unique
# Edit infra/main.bicep and change naming pattern
```

**Error**: "Insufficient permissions"
```bash
# Solution: Ensure you have Contributor role on subscription
az role assignment create --assignee <your-email> --role Contributor --scope /subscriptions/<subscription-id>
```

### Application Not Starting

**Check App Service Logs**
```bash
az webapp log tail --name <app-service-name> --resource-group <resource-group>
```

**Common Issues**:
- Missing dependencies: Check `requirements.txt`
- Startup command incorrect: Verify `appCommandLine` in `app-service.bicep`
- Environment variables missing: Check Key Vault and app settings

### Key Vault Access Denied

**Error**: "The user, group or application does not have secrets list permission"

```bash
# Grant yourself Key Vault Secrets Officer role
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <your-email> \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv-name>
```

### Model Endpoint Timeout

**Check endpoint health**:
```bash
curl -X POST <endpoint-url> \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

**Solutions**:
- Increase timeout in app code
- Check network connectivity
- Verify endpoint is running
- Check Azure ML endpoint quota

## Cleanup

### Remove All Resources

```bash
azd down
```

This deletes:
- Resource Group
- All contained resources
- Environment configuration (locally)

### Keep Environment Configuration

```bash
azd down --no-prompt
```

### Purge Soft-Deleted Resources

```bash
azd down --purge
```

This also removes:
- Soft-deleted Key Vaults
- Soft-deleted App Insights

## CI/CD with GitHub Actions

### Setup

1. **Create Service Principal**
   ```bash
   az ad sp create-for-rbac --name "MedImageParse-CI" --role Contributor --scopes /subscriptions/<subscription-id>
   ```

2. **Add GitHub Secrets**
   
   Go to GitHub repository → Settings → Secrets → Actions
   
   Add the following secrets:
   - `AZURE_CLIENT_ID`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_ENV_NAME`
   - `AZURE_LOCATION`
   - `AZURE_OPENAI_ENDPOINT_2D`
   - `AZURE_OPENAI_KEY_2D`
   - `AZURE_OPENAI_ENDPOINT_3D`
   - `AZURE_OPENAI_KEY_3D`

3. **Enable Workflow**
   
   The workflow at `.github/workflows/azure-deploy.yml` will automatically:
   - Run tests on PR
   - Deploy on push to main

## Cost Management

### Monitor Costs

```bash
az consumption usage list --query "[].{name: instanceName, cost: pretaxCost}" --output table
```

### Set Budget Alert

1. Go to Azure Portal → **Cost Management + Billing**
2. Navigate to **Budgets**
3. Click **Add**
4. Set amount (e.g., $50/month)
5. Configure alert at 80% and 100%
6. Add email notification

### Stop App Service (Non-Prod)

```bash
az webapp stop --name <app-name> --resource-group <rg-name>
```

### Start App Service

```bash
az webapp start --name <app-name> --resource-group <rg-name>
```

## Security Hardening

### Enable VNET Integration (Optional)

1. Create Virtual Network
2. Go to App Service → **Networking**
3. Click **VNET integration**
4. Select your VNET and subnet
5. Update Key Vault and ML endpoint firewall rules

### Enable Managed Identity for ML Endpoints

1. Create Managed Identity
2. Assign identity to App Service
3. Grant identity access to ML endpoints
4. Update app code to use DefaultAzureCredential

### Review Security Recommendations

```bash
az security assessment list --query "[?status.code=='Unhealthy']"
```

## Backup and Restore

### Backup Infrastructure

Infrastructure is code (Bicep), so it's automatically backed up in Git.

### Backup Key Vault Secrets

```bash
az keyvault secret backup --vault-name <kv-name> --name <secret-name> --file backup.blob
```

### Restore Key Vault Secret

```bash
az keyvault secret restore --vault-name <kv-name> --file backup.blob
```

## Support

For issues:
- Check [Troubleshooting](#troubleshooting) section
- Review [Architecture Documentation](./ARCHITECTURE.md)
- Open [GitHub Issue](https://github.com/your-org/MedImageParse/issues)
- Contact: support@example.com

---

**Last Updated**: October 2025
**Version**: 1.0.0
