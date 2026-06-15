# Azure AI Foundry Model Deployment Guide

## 🎯 Overview

This guide provides step-by-step instructions for deploying MedImageParse models (2D and 3D) in Azure AI Foundry, including critical prerequisites and common issues.

> ⚠️ **Important**: This guide is based on lessons learned from actual deployment experience. Please read all prerequisites carefully before starting.

## 📋 Prerequisites

### 1. Azure Subscription Requirements

**Critical**: You must have:
- ✅ **Paid Azure subscription** with valid payment method
- ❌ Free or trial Azure subscriptions **DO NOT WORK**

If you don't have a paid subscription:
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Subscriptions**
3. Click **Add** → Choose **Pay-As-You-Go**
4. Complete payment method registration

### 2. Hub-Based Project Requirement

**Critical**: You must create a **Hub-based project** (not standalone project).

#### Why Hub-Based?
- Required for deploying models from AI Foundry catalog
- Provides shared resources and governance
- Enables cross-project resource sharing

#### How to Create Hub-Based Project

**Option 1: Azure Portal**
1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Click **+ New project**
3. Select **Create a new hub** (DO NOT select "Use existing hub" if you don't have one)
4. Fill in details:
   - **Hub name**: `medimage-hub`
   - **Resource group**: Create new or use existing
   - **Region**: `Sweden Central` (or your preferred region)
5. Click **Create**

**Option 2: Azure CLI**
```bash
# Create resource group
az group create --name rg-medimage-hub --location swedencentral

# Create AI Hub
az ml workspace create \
  --kind hub \
  --name medimage-hub \
  --resource-group rg-medimage-hub \
  --location swedencentral

# Create project under hub
az ml workspace create \
  --kind project \
  --hub-id /subscriptions/<sub-id>/resourceGroups/rg-medimage-hub/providers/Microsoft.MachineLearningServices/workspaces/medimage-hub \
  --name medimage-project \
  --resource-group rg-medimage-hub
```

### 3. Azure Role-Based Access Control (RBAC)

**Critical**: Your user account must have **Azure AI Developer** role.

#### Required Role
- **Role**: `Azure AI Developer`
- **Scope**: Resource Group containing the hub/project

#### Check Your Permissions

```bash
# List your role assignments
az role assignment list --assignee <your-email> --output table

# Look for "Azure AI Developer" role in the output
```

#### Grant Azure AI Developer Role

**Option 1: Azure Portal**
1. Go to **Resource Groups** → Select your resource group
2. Click **Access control (IAM)**
3. Click **+ Add** → **Add role assignment**
4. Search for **Azure AI Developer**
5. Click **Next** → Select your user account
6. Click **Review + assign**

**Option 2: Azure CLI**
```bash
# Get your user object ID
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)

# Assign Azure AI Developer role
az role assignment create \
  --role "Azure AI Developer" \
  --assignee-object-id $USER_OBJECT_ID \
  --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group-name>
```

### 4. Storage Account Public Access

**Critical**: The storage account associated with your hub **MUST** have public network access enabled.

#### Why Public Access Required?
- Model deployment process needs to download model files
- Endpoint provisioning requires access to artifacts
- Deployment fails silently if storage is private-only

#### Enable Public Access

**Option 1: Azure Portal**
1. Go to your resource group
2. Find the Storage Account (usually named like `st<randomstring>`)
3. Navigate to **Settings** → **Configuration**
4. Under **Allow Blob public access**, select **Enabled**
5. Click **Save**
6. Navigate to **Security + networking** → **Networking**
7. Under **Firewalls and virtual networks**, select **Enabled from all networks**
8. Click **Save**

**Option 2: Azure CLI**
```bash
# Find storage account name
STORAGE_ACCOUNT=$(az storage account list \
  --resource-group <resource-group-name> \
  --query "[0].name" -o tsv)

# Enable public blob access
az storage account update \
  --name $STORAGE_ACCOUNT \
  --resource-group <resource-group-name> \
  --allow-blob-public-access true

# Enable public network access
az storage account update \
  --name $STORAGE_ACCOUNT \
  --resource-group <resource-group-name> \
  --public-network-access Enabled

# Update network rules to allow all
az storage account network-rule add \
  --account-name $STORAGE_ACCOUNT \
  --resource-group <resource-group-name> \
  --action Allow
```

## 🚀 Deployment Steps

### Step 1: Access AI Foundry Portal

1. Navigate to [Azure AI Foundry](https://ai.azure.com)
2. Sign in with your Azure account
3. Select your hub-based project

### Step 2: Deploy MedImageParse 2D Model

1. In the left navigation, click **Model catalog**
2. Search for **"MedImageParse"**
3. Select **MedImageParse** (2D version)
4. Click **Deploy**
5. Configure deployment:
   - **Deployment name**: `medimageparse-2d`
   - **Virtual machine**: Standard_DS3_v2 (or higher)
   - **Instance count**: 1
   - **Endpoint type**: Real-time
6. Click **Deploy**
7. Wait 5-10 minutes for deployment to complete

### Step 3: Deploy MedImageParse 3D Model

1. Return to **Model catalog**
2. Search for **"MedImageParse 3D"**
3. Select **MedImageParse 3D** (NIfTI version)
4. Click **Deploy**
5. Configure deployment:
   - **Deployment name**: `medimageparse-3d`
   - **Virtual machine**: Standard_DS3_v2 (or higher)
   - **Instance count**: 1
   - **Endpoint type**: Real-time
6. Click **Deploy**
7. Wait 5-10 minutes for deployment to complete

### Step 4: Retrieve Endpoint Information

1. Navigate to **Endpoints** in the left menu
2. Click on **medimageparse-2d**
3. Copy:
   - **REST endpoint URL** (e.g., `https://xxx.swedencentral.inference.ml.azure.com/score`)
   - **Primary key** (click "Show key")
4. Repeat for **medimageparse-3d**

### Step 5: Test Endpoints

```bash
# Test 2D endpoint
curl -X POST <2d-endpoint-url> \
  -H "Authorization: Bearer <2d-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"test": "connection"}'

# Test 3D endpoint
curl -X POST <3d-endpoint-url> \
  -H "Authorization: Bearer <3d-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"test": "connection"}'
```

Expected response: HTTP 200 or validation error (not connection refused)

## ⚠️ Common Issues and Solutions

### Issue 1: "Deployment Failed" with No Clear Error

**Symptoms**:
- Deployment shows "Failed" status
- No detailed error message
- Logs show "Unable to download model"

**Root Cause**: Storage account public access disabled

**Solution**:
1. Enable public access on storage account (see [Prerequisites](#4-storage-account-public-access))
2. Delete failed deployment
3. Retry deployment

### Issue 2: "Insufficient Permissions"

**Symptoms**:
- Cannot see "Deploy" button
- "Access Denied" when trying to deploy

**Root Cause**: Missing Azure AI Developer role

**Solution**:
1. Grant Azure AI Developer role (see [Prerequisites](#3-azure-role-based-access-control-rbac))
2. Sign out and sign back in
3. Wait 5 minutes for permissions to propagate

### Issue 3: "Subscription Not Supported"

**Symptoms**:
- "Your subscription type is not supported for this operation"
- Cannot proceed with deployment

**Root Cause**: Using free or trial subscription

**Solution**:
1. Upgrade to paid subscription
2. Ensure payment method is valid
3. Check subscription status in Azure Portal

### Issue 4: "Hub Not Found" or "Project Not Found"

**Symptoms**:
- Cannot find project in AI Foundry portal
- "No hubs available" message

**Root Cause**: Created standalone project instead of hub-based

**Solution**:
1. Create new hub-based project (see [Prerequisites](#2-hub-based-project-requirement))
2. Do NOT try to convert standalone to hub-based (not supported)

### Issue 5: Endpoint Returns 401 Unauthorized

**Symptoms**:
- API calls return 401 status
- "Invalid authentication" error

**Root Cause**: Incorrect API key or endpoint URL

**Solution**:
1. Verify endpoint URL is exactly as shown in portal
2. Re-copy API key (ensure no extra spaces)
3. Check if key has expired or been regenerated
4. Use "Primary key" (not secondary unless primary doesn't work)

### Issue 6: Deployment Stuck in "Creating" State

**Symptoms**:
- Deployment shows "Creating" for > 20 minutes
- No progress updates

**Root Cause**: Resource quota exceeded or backend issue

**Solution**:
1. Check quota: Azure Portal → Subscriptions → Usage + quotas
2. Request quota increase if needed
3. Cancel deployment and retry
4. Try different VM size
5. Try different region

## 📝 Configuration Reference

### Recommended VM Sizes

| Model | Minimum | Recommended | High Performance |
|-------|---------|-------------|------------------|
| 2D | Standard_DS2_v2 | Standard_DS3_v2 | Standard_DS4_v2 |
| 3D | Standard_DS3_v2 | Standard_DS4_v2 | Standard_DS5_v2 |

### Pricing Estimates

Approximate costs (Pay-As-You-Go, Sweden Central):

| VM Size | vCPU | RAM | Hourly Cost | Monthly Cost (730h) |
|---------|------|-----|-------------|---------------------|
| Standard_DS2_v2 | 2 | 7 GB | $0.14 | ~$102 |
| Standard_DS3_v2 | 4 | 14 GB | $0.27 | ~$197 |
| Standard_DS4_v2 | 8 | 28 GB | $0.54 | ~$394 |

*Prices are estimates and may vary by region and subscription type*

### Scaling Recommendations

**Development/Testing**:
- VM: Standard_DS2_v2
- Instances: 1
- Auto-scale: Disabled

**Production**:
- VM: Standard_DS3_v2 or higher
- Instances: 2-5
- Auto-scale: Enabled (based on CPU/requests)

## 🔒 Security Best Practices

### 1. Rotate API Keys Regularly

```bash
# Regenerate primary key
az ml online-endpoint regenerate-keys \
  --name medimageparse-2d \
  --resource-group <rg-name> \
  --workspace-name <workspace-name> \
  --key primary
```

### 2. Use Key Vault for Secret Storage

**Never** hardcode API keys in your application:

```python
# ❌ BAD - Hardcoded
api_key = "abc123..."

# ✅ GOOD - From Key Vault
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

client = SecretClient(vault_url="https://your-kv.vault.azure.net/", credential=DefaultAzureCredential())
api_key = client.get_secret("medimageparse-2d-key").value
```

### 3. Restrict Network Access (Production)

Once deployed, restrict storage account access:
1. Go to Storage Account → Networking
2. Select **Enabled from selected virtual networks and IP addresses**
3. Add your application's outbound IPs
4. Keep Azure services access enabled

### 4. Enable Managed Identity (Advanced)

Replace API keys with Managed Identity:
1. Enable managed identity on your app
2. Grant identity access to ML endpoint
3. Use `DefaultAzureCredential` in code

## 📚 Additional Resources

### Official Documentation
- [Deploy MedImageParse - Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/healthcare-ai/deploy-medimageparse?tabs=medimageparse)
- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [Azure RBAC Documentation](https://learn.microsoft.com/en-us/azure/role-based-access-control/)

### Support Channels
- **Azure Support**: Create support ticket in Azure Portal
- **Community**: [Microsoft Q&A - Azure AI](https://learn.microsoft.com/en-us/answers/tags/133/azure-ai-studio)
- **GitHub Issues**: [MedImageParse Repository Issues](https://github.com/your-org/MedImageParse/issues)

### Troubleshooting Checklist

Before opening a support ticket, verify:
- [ ] Paid Azure subscription (not free/trial)
- [ ] Hub-based project created
- [ ] Azure AI Developer role assigned
- [ ] Storage account public access enabled
- [ ] Waited at least 15 minutes for deployment
- [ ] Checked deployment logs in Azure Portal
- [ ] Tested with correct endpoint URL and key
- [ ] No typos in API key (copy-paste recommended)

## 🎓 Training and Certification

If you're new to Azure AI Foundry:
1. [Microsoft Learn - Azure AI Fundamentals](https://learn.microsoft.com/en-us/training/paths/get-started-with-artificial-intelligence-on-azure/)
2. [Azure AI Engineer Associate Certification](https://learn.microsoft.com/en-us/certifications/azure-ai-engineer/)

---

## 📞 Need Help?

If you encounter issues not covered in this guide:

1. **Check Prerequisites**: Re-read all prerequisites carefully
2. **Review Common Issues**: Most problems are listed above
3. **Open GitHub Issue**: Provide detailed logs and screenshots
4. **Contact Support**: For Azure-specific issues, contact Azure Support

---

**Document Author**: Xinyuwei (based on real deployment experience)
**Last Updated**: October 2025
**Version**: 1.0.0

**Acknowledgments**: Special thanks to community members who helped resolve the original deployment issues, particularly regarding hub-based projects, RBAC roles, and storage account configuration.
