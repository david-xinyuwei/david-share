# 🚀 Quick Start Checklist

Use this checklist to deploy MedImageParse from scratch. Follow steps in order.

## Phase 1: Azure AI Foundry Model Deployment

> **Estimated Time**: 30-45 minutes (first time)

### Prerequisites Verification

- [ ] **Azure Subscription**: Paid subscription with valid payment method (NOT free/trial)
- [ ] **Payment Method**: Credit card added and verified
- [ ] **Subscription Active**: Check in [Azure Portal](https://portal.azure.com) → Subscriptions

### Step 1: Create Hub-Based Project

- [ ] Navigate to [Azure AI Foundry](https://ai.azure.com)
- [ ] Click **+ New project**
- [ ] Select **Create a new hub**
- [ ] Fill in:
  - Hub name: `medimage-hub`
  - Region: `Sweden Central` (or your choice)
  - Resource group: Create new `rg-medimage`
- [ ] Wait for hub creation (3-5 minutes)

### Step 2: Assign Azure AI Developer Role

- [ ] Go to [Azure Portal](https://portal.azure.com) → Resource Groups
- [ ] Select `rg-medimage`
- [ ] Click **Access control (IAM)** → **+ Add** → **Add role assignment**
- [ ] Search and select **Azure AI Developer**
- [ ] Click **Next** → Select your user account
- [ ] Click **Review + assign**
- [ ] Wait 5 minutes for permissions to propagate

### Step 3: Enable Storage Public Access

- [ ] In resource group `rg-medimage`, find the Storage Account
- [ ] Navigate to **Settings** → **Configuration**
- [ ] Set **Allow Blob public access** to **Enabled**
- [ ] Click **Save**
- [ ] Navigate to **Security + networking** → **Networking**
- [ ] Select **Enabled from all networks**
- [ ] Click **Save**

### Step 4: Deploy MedImageParse 2D Model

- [ ] Return to [Azure AI Foundry](https://ai.azure.com)
- [ ] Click **Model catalog** in left menu
- [ ] Search for **"MedImageParse"**
- [ ] Select the 2D model
- [ ] Click **Deploy**
- [ ] Configure:
  - Deployment name: `medimageparse-2d`
  - VM: `Standard_DS3_v2`
  - Instances: `1`
- [ ] Click **Deploy**
- [ ] Wait 5-10 minutes for deployment
- [ ] Verify status shows **Succeeded**

### Step 5: Deploy MedImageParse 3D Model

- [ ] Click **Model catalog** again
- [ ] Search for **"MedImageParse 3D"** or **"MedImageParse NIfTI"**
- [ ] Click **Deploy**
- [ ] Configure:
  - Deployment name: `medimageparse-3d`
  - VM: `Standard_DS3_v2`
  - Instances: `1`
- [ ] Click **Deploy**
- [ ] Wait 5-10 minutes
- [ ] Verify status shows **Succeeded**

### Step 6: Copy Endpoint Information

- [ ] Navigate to **Endpoints** in left menu
- [ ] Click **medimageparse-2d**
- [ ] Copy and save:
  - [ ] **REST endpoint URL**
  - [ ] **Primary key** (click "Show key")
- [ ] Click back, select **medimageparse-3d**
- [ ] Copy and save:
  - [ ] **REST endpoint URL**
  - [ ] **Primary key**

**✅ Phase 1 Complete! You now have both models deployed.**

---

## Phase 2: Application Deployment with Azure Developer CLI

> **Estimated Time**: 10-15 minutes

### Prerequisites

- [ ] Install [Azure Developer CLI (azd)](https://aka.ms/azure-dev/install)
- [ ] Install [Python 3.9+](https://www.python.org/downloads/)
- [ ] Install [Git](https://git-scm.com/downloads)

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/MedImageParse.git
cd MedImageParse
```

- [ ] Repository cloned successfully

### Step 2: Login to Azure

```bash
azd auth login
```

- [ ] Browser opened and signed in
- [ ] Terminal shows "Logged in as [your-email]"

### Step 3: Initialize Environment

```bash
azd init
```

When prompted:
- [ ] Environment name: `medimage-prod` (or your choice)
- [ ] Location: `Sweden Central` (match your model region)

### Step 4: Configure Model Endpoints

```bash
azd env set AZURE_OPENAI_ENDPOINT_2D "YOUR_2D_ENDPOINT_URL"
azd env set AZURE_OPENAI_KEY_2D "YOUR_2D_API_KEY"
azd env set AZURE_OPENAI_ENDPOINT_3D "YOUR_3D_ENDPOINT_URL"
azd env set AZURE_OPENAI_KEY_3D "YOUR_3D_API_KEY"
```

- [ ] All 4 secrets configured

**Verify configuration**:
```bash
azd env get-values
```

- [ ] All endpoints and keys shown correctly

### Step 5: Deploy Everything

```bash
azd up
```

This will:
1. Provision infrastructure (App Service, Key Vault, App Insights)
2. Store secrets securely in Key Vault
3. Deploy application code
4. Configure Entra ID authentication

- [ ] Deployment started
- [ ] Resource provisioning completed (5-8 minutes)
- [ ] Application deployment completed (2-3 minutes)
- [ ] Command completes with success message

### Step 6: Access Application

```bash
azd show
```

- [ ] Copy the application URL
- [ ] Open URL in browser
- [ ] Redirected to Microsoft login
- [ ] Successfully logged in
- [ ] Application loads correctly

**✅ Phase 2 Complete! Application is live.**

---

## Phase 3: Verification & Testing

### Test 2D Model

- [ ] Select **Language**: Chinese or English
- [ ] Select **Model**: MedImageParse (2D)
- [ ] Upload a test PNG/JPG image
- [ ] Enter prompt: `retina` or `视网膜`
- [ ] Click **Start Analysis** / **开始分析**
- [ ] Wait for result (10-30 seconds)
- [ ] Verify segmentation mask displayed
- [ ] Download results (optional)

### Test 3D Model

- [ ] Select **Model**: MedImageParse 3D
- [ ] Upload a test NIfTI file (.nii or .nii.gz)
- [ ] Preview shows 3D slices correctly
- [ ] Enter prompt: `liver` or `肝脏`
- [ ] Click **Start Analysis**
- [ ] Wait for result (30-60 seconds)
- [ ] Verify 3D visualization shows segmented slices

### Test Monitoring

- [ ] Go to [Azure Portal](https://portal.azure.com)
- [ ] Navigate to your Application Insights resource
- [ ] Click **Live Metrics**
- [ ] Perform an analysis in the app
- [ ] Verify metrics appear in Live Metrics
- [ ] Check **Logs** for application traces

**✅ Phase 3 Complete! Everything is working.**

---

## 📊 Post-Deployment Checklist

### Security

- [ ] Verify HTTPS-only access (URL starts with `https://`)
- [ ] Test Entra ID authentication (logout and login again)
- [ ] Confirm secrets are NOT in application code
- [ ] Check Key Vault contains all 4 secrets

### Cost Management

- [ ] Set up budget alert ($50/month recommended)
- [ ] Review resource SKUs (can scale down for dev)
- [ ] Note: Model endpoints cost ~$0.27/hour each (~$400/month for 2 endpoints 24/7)
- [ ] Consider shutting down endpoints when not in use

### Documentation

- [ ] Update README with your repository URL
- [ ] Document any custom configurations
- [ ] Add team members to Azure resources (RBAC)
- [ ] Share application URL with stakeholders

### Optional Enhancements

- [ ] Configure custom domain
- [ ] Set up staging environment
- [ ] Enable auto-scaling
- [ ] Configure availability alerts
- [ ] Add CI/CD pipeline (GitHub Actions)

---

## 🆘 Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| Model deployment fails | Check [Model Deployment Guide](./docs/model-deployment-guide.md#-common-issues-and-solutions) |
| "Insufficient permissions" | Verify Azure AI Developer role is assigned |
| "Storage access denied" | Enable public network access on storage account |
| `azd up` fails | Check subscription is paid (not free/trial) |
| Application won't load | Check App Service logs: `az webapp log tail --name <app-name> --resource-group <rg-name>` |
| Entra ID login fails | Verify you're in the correct tenant |

**Need more help?**
- 📖 [Model Deployment Guide](./docs/model-deployment-guide.md)
- 📖 [Deployment Guide](./docs/deployment-guide.md)
- 📖 [Architecture Documentation](./ARCHITECTURE.md)
- 🐛 [Open GitHub Issue](https://github.com/your-org/MedImageParse/issues)

---

## ✅ Success Criteria

You're done when:
- ✅ Both models deployed and showing "Succeeded" status in Azure AI Foundry
- ✅ Application accessible via HTTPS URL
- ✅ Login works with your Microsoft account
- ✅ Can successfully segment both 2D and 3D medical images
- ✅ Application Insights shows telemetry data
- ✅ All secrets stored in Key Vault (not hardcoded)

**Congratulations! 🎉 Your MedImageParse platform is ready for use.**

---

**Estimated Total Time**: 45-60 minutes (first time)
**Estimated Total Cost**: ~$20-30/month for infrastructure + ~$400/month for ML endpoints (if running 24/7)

**Cost Saving Tip**: Stop ML endpoints when not in use to save ~$400/month. You can start them again anytime from Azure AI Foundry portal.

---

**Last Updated**: October 2025
**Version**: 1.0.0
