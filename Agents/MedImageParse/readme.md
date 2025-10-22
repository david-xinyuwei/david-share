# MedImageParse - AI Medical Image Segmentation Platform# MedImageParse - Medical Image Segmentation Platform



An AI-powered medical image segmentation platform built on Azure, featuring support for 2D/3D medical imaging with natural language prompts. **Developed by Xinyuwei**.[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fyour-repo%2FMedImageParse%2Fmain%2Finfra%2Fmain.json)



## 🎬 DemoAn AI-powered medical image segmentation platform built on Azure, featuring support for 2D/3D medical imaging with natural language prompts. Specialized for ophthalmology, pathology, and radiology applications.



Watch the platform in action:## 🎬 Demo



https://github.com/user-attachments/assets/7983ecb1-328d-421c-986f-8e22d7f9813dWatch the platform in action:



*Real-time 2D/3D medical image segmentation with natural language prompts*https://github.com/user-attachments/assets/7983ecb1-328d-421c-986f-8e22d7f9813d



---*See real-time 2D/3D medical image segmentation with natural language prompts*



## 📋 Table of Contents## 🎯 Scenario



- [Features](#-features)MedImageParse enables healthcare professionals and researchers to perform advanced medical image segmentation using natural language descriptions. The platform leverages Azure's MedImageParse AI models to identify and segment anatomical structures, lesions, and abnormalities in medical images.

- [Architecture](#-architecture)

- [Prerequisites](#-prerequisites)### Key Use Cases

- [Quick Start](#-quick-start)

- [Usage](#-usage)- **👁️ Ophthalmology**: Retinal vessel segmentation, diabetic retinopathy detection, glaucoma screening

- [Configuration](#-configuration)- **🔬 Pathology**: Tumor cell identification, tissue structure analysis

- [Troubleshooting](#-troubleshooting)- **🏥 Radiology**: Organ segmentation (liver, lung, kidney), tumor detection, CT/MRI analysis

- [Cost Estimate](#-cost-estimate)- **🧠 Neurology**: Brain anatomy segmentation, hemorrhage detection



---## ✨ Features



## ✨ Features- **2D & 3D Support**: Process both 2D images (PNG, JPG) and 3D volumes (NIfTI format)

- **Natural Language Prompts**: Describe segmentation targets in plain English

- **2D & 3D Support**: Process 2D images (PNG, JPG) and 3D volumes (NIfTI format)- **Interactive Visualization**: Real-time preview with 3D slice browsing

- **Natural Language Prompts**: Describe segmentation targets in plain English (e.g., "segment the liver")- **Multi-object Segmentation**: Segment multiple anatomical structures simultaneously

- **Interactive Visualization**: Real-time preview with 3D slice browsing- **Bilingual UI**: Full Chinese and English language support

- **Multi-object Segmentation**: Segment multiple anatomical structures simultaneously- **Secure Authentication**: Azure Entra ID integration

- **Bilingual UI**: Full Chinese and English language support- **Observability**: Application Insights with correlation tracking

- **Enterprise-Ready**: 

  - Azure Entra ID authentication (SSO)## 🚀 Quick Start

  - Key Vault for secure secret storage

  - Application Insights monitoring with correlation IDs> 🎯 **First-time users**: See [QUICKSTART.md](./QUICKSTART.md) for a complete step-by-step checklist covering both model deployment and application deployment.

  - One-click deployment with Azure Developer CLI

### Prerequisites

### Use Cases

- [Azure Developer CLI (azd)](https://aka.ms/azure-dev/install)

- **👁️ Ophthalmology**: Retinal vessel segmentation, diabetic retinopathy detection- [Python 3.9+](https://www.python.org/downloads/)

- **🔬 Pathology**: Tumor cell identification, tissue structure analysis- **Paid Azure subscription** (free/trial subscriptions are NOT supported)

- **🏥 Radiology**: Organ segmentation (liver, lung, kidney), tumor detection- **MedImageParse models deployed in Azure AI Foundry** - See [Model Deployment Guide](./docs/model-deployment-guide.md) for detailed instructions

- **🧠 Neurology**: Brain anatomy segmentation, hemorrhage detection

> ⚠️ **Critical**: Before deploying this application, you must first deploy the MedImageParse 2D and 3D models in Azure AI Foundry. This requires:

---> - ✅ Hub-based project (NOT standalone project)

> - ✅ Azure AI Developer role assigned

## 🏗️ Architecture> - ✅ Storage account with public network access enabled

> 

```mermaid> Read the [Model Deployment Guide](./docs/model-deployment-guide.md) carefully - these requirements are not obvious and cause the most common deployment failures.

graph TB

    subgraph "Client Layer"### Deploy to Azure

        User[👤 Healthcare Professional]

    end1. **Clone this directory only** (Sparse Checkout)

       ```bash

    subgraph "Azure Cloud"   git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git

        subgraph "Identity & Access"   cd david-share

            EntraID[Azure Entra ID<br/>SSO Authentication]   git sparse-checkout set Agents/MedImageParse

        end   cd Agents/MedImageParse

           ```

        subgraph "Application Layer"   

            AppService[Azure App Service<br/>Streamlit App<br/>Python 3.11]   > 💡 **Why sparse checkout?** This repository contains many other projects. Sparse checkout downloads only the MedImageParse directory, saving time and disk space.

            ManagedIdentity[Managed Identity]

        end2. **Initialize Azure Developer CLI**

           ```bash

        subgraph "Security Layer"   azd auth login

            KeyVault[Key Vault<br/>API Keys & Secrets]   azd init

        end   ```

        

        subgraph "AI/ML Layer"3. **Deploy infrastructure and application** (One-click deployment)

            ML2D[Azure ML Endpoint<br/>MedImageParse 2D]   ```bash

            ML3D[Azure ML Endpoint<br/>MedImageParse 3D]   azd up

        end   ```

           

        subgraph "Observability"   **What does `azd up` install?**

            AppInsights[Application Insights<br/>Monitoring & Logs]   

        end   This single command automatically provisions and configures all Azure resources:

    end   

       | Resource | Description | Purpose |

    User -->|HTTPS + SSO| EntraID   |----------|-------------|---------|

    EntraID -->|Authenticated| AppService   | **Resource Group** | Container for all resources | Organizes and manages related Azure resources |

    AppService -->|Managed Identity| KeyVault   | **App Service Plan** | Linux B1 (Basic tier) | Compute infrastructure for hosting |

    AppService -->|API Calls| ML2D   | **App Service** | Python 3.11 runtime | Hosts the Streamlit web application |

    AppService -->|API Calls| ML3D   | **Key Vault** | Secret management | Securely stores API keys and endpoints |

    AppService -->|Telemetry| AppInsights   | **Application Insights** | APM & monitoring | Tracks performance, logs, and user analytics |

       | **Log Analytics Workspace** | Centralized logging | Stores and queries application logs |

    style User fill:#e1f5ff   | **Managed Identity** | System-assigned | Enables passwordless access to Key Vault |

    style EntraID fill:#fff4e1   | **Entra ID Authentication** | SSO integration | Secures application access |

    style AppService fill:#e8f5e9   

    style KeyVault fill:#fce4ec   **Total deployment time**: ~5-7 minutes

    style ML2D fill:#f3e5f5   

    style ML3D fill:#f3e5f5   **Estimated monthly cost**: ~$18 USD (infrastructure only, excludes ML endpoint costs)

    style AppInsights fill:#e0f2f1

```4. **Access the application**

   ```bash

---   azd show

   ```

## 📦 Prerequisites   Open the displayed URL in your browser.



### 1. Azure Subscription### Local Development

- ⚠️ **Paid subscription required** (free/trial subscriptions do NOT work)

1. **Install dependencies**

### 2. Azure AI Foundry Models (Critical!)   ```bash

   pip install -r src/requirements.txt

**You must deploy MedImageParse models BEFORE deploying this application.**   ```



#### Deployment Requirements:2. **Configure environment**

- ✅ **Hub-based project** (NOT standalone project)   ```bash

- ✅ **Azure AI Developer role** assigned to your account   cp .env.example .env

- ✅ **Storage account** with public network access enabled   # Edit .env with your Azure ML endpoint credentials

   ```

#### Deployment Steps:

3. **Run locally**

1. **Go to Azure AI Foundry**: https://ai.azure.com   ```bash

2. **Create Hub-based project**:   streamlit run src/app.py

   - Create AI Hub first   ```

   - Then create project under the hub

3. **Assign Role**:## 📋 Configuration

   - Go to Hub → Access Control (IAM)

   - Add role assignment: "Azure AI Developer"### Azure ML Endpoints

4. **Enable Storage Access**:

   - Go to Storage Account → NetworkingThe application requires two Azure ML endpoints:

   - Enable "Public network access"

5. **Deploy Models**:1. **MedImageParse 2D**: For 2D image segmentation (1024x1024)

   - Model Catalog → Search "MedImageParse"2. **MedImageParse 3D**: For 3D NIfTI volume segmentation

   - Deploy both 2D and 3D versions

   - Recommended VM: Standard_NC6s_v3 or higher**How to get these endpoints**:

   - **Save endpoints and keys** - you'll need them!1. Follow the [Model Deployment Guide](./docs/model-deployment-guide.md) to deploy both models in Azure AI Foundry

2. Copy the endpoint URLs and API keys from the Azure AI Foundry portal

> 📖 **Detailed Guide**: See [docs/model-deployment-guide.md](./docs/model-deployment-guide.md) for step-by-step instructions with screenshots.3. Configure these in Azure Key Vault after deployment or in `.env` for local development



### 3. Development Tools> 💡 **First-time users**: The Model Deployment Guide includes critical prerequisites like hub-based projects, RBAC roles, and storage account configuration that are not obvious but required for successful deployment.

- [Azure Developer CLI (azd)](https://aka.ms/azure-dev/install)

- [Python 3.9+](https://www.python.org/downloads/)### Environment Variables



---| Variable | Description | Required |

|----------|-------------|----------|

## 🚀 Quick Start| `AZURE_OPENAI_ENDPOINT_2D` | 2D model endpoint URL | Yes |

| `AZURE_OPENAI_KEY_2D` | 2D model API key | Yes |

### Option 1: Deploy to Azure (Recommended)| `AZURE_OPENAI_ENDPOINT_3D` | 3D model endpoint URL | Yes |

| `AZURE_OPENAI_KEY_3D` | 3D model API key | Yes |

**Clone this directory only** (Sparse Checkout):| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection string | Auto-configured |

```bash

git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git## 🏗️ Architecture

cd david-share

git sparse-checkout set Agents/MedImageParseSee [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation.

cd Agents/MedImageParse

```### High-Level Components



**Deploy with one command**:```mermaid

```bashgraph TB

azd auth login    User[User] --> |HTTPS + Entra ID| AppService[Azure App Service<br/>Streamlit Application]

azd up    AppService --> |Secure API Calls| ML2D[Azure ML Endpoint<br/>MedImageParse 2D]

```    AppService --> |Secure API Calls| ML3D[Azure ML Endpoint<br/>MedImageParse 3D]

    AppService --> |Logs & Metrics| AppInsights[Application Insights]

**What does `azd up` deploy?**    AppService --> |Retrieve Secrets| KeyVault[Azure Key Vault]

    AppInsights --> |Analytics| LogAnalytics[Log Analytics]

| Azure Resource | Purpose | Estimated Cost |```

|----------------|---------|----------------|

| Resource Group | Container for all resources | Free |### Key Azure Services

| App Service Plan | Linux B1 (Basic tier) | ~$13/month |

| App Service | Python 3.11 runtime | Included |- **Azure App Service**: Hosts the Streamlit web application

| Key Vault | Secure secret storage | ~$0.03/month |- **Azure Key Vault**: Securely stores API keys and secrets

| Application Insights | Monitoring & logging | ~$5/month |- **Application Insights**: Monitors application performance and usage

| Log Analytics Workspace | Centralized logs | Included |- **Log Analytics**: Centralized logging and analytics

| Managed Identity | Passwordless Key Vault access | Free |- **Azure Entra ID**: User authentication and authorization

| Entra ID Authentication | SSO security | Free |- **Azure ML Endpoints**: MedImageParse model inference



**Total Infrastructure Cost**: ~$18/month  ## 📊 Supported Segmentation Categories

**Total Deployment Time**: 5-7 minutes

The model automatically classifies segmented objects into 16 biomedical categories:

> ⚠️ **Note**: ML endpoint costs are separate (~$394/month for both 2D+3D models)

- **Organs**: liver, lung, kidney, pancreas, heart, spleen

**During deployment, you'll be prompted to enter**:- **Anatomies**: brain/heart/eye anatomies

- MedImageParse 2D Endpoint URL- **Vessels**: arteries, veins, capillaries

- MedImageParse 2D API Key- **Lesions**: tumors, infections, abnormalities

- MedImageParse 3D Endpoint URL- **Ophthalmology**: retina, optic disc, macula, vessels

- MedImageParse 3D API Key- **Others**: fluid disturbances, histology structures



These will be securely stored in Azure Key Vault.### Example Prompts



---```python

# Single object

### Option 2: Run Locally"retina"



**1. Install dependencies**:# Multiple objects

```bash"optic disc & macula"

pip install -r src/requirements.txt

```# Complex descriptions

"diabetic retinopathy lesions & microaneurysms & hemorrhages"

**2. Configure environment**:

```bash# Organ segmentation

cp .env.example .env"liver & kidney & pancreas"

# Edit .env with your Azure ML endpoint credentials

```# Tumor analysis

"tumor core & enhancing tumor & non-enhancing tumor"

**3. Run the application**:```

```bash

streamlit run app_clean.py## 📚 Usage Examples

```

### 2D Image Segmentation

**4. Open browser**: http://localhost:8501

1. Select "MedImageParse (2D)" model

---2. Upload a PNG/JPG medical image

3. Choose a prompt category or enter custom prompt

## 💡 Usage4. Click "Start Analysis"

5. View segmentation mask and overlay results

### 2D Image Segmentation6. Download results as image or JSON



1. **Select Language**: Choose Chinese or English in the sidebar### 3D Volume Segmentation

2. **Choose Model**: Select "MedImageParse (2D)"

3. **Upload Image**: PNG or JPG format (auto-resized to 1024x1024)1. Select "MedImageParse 3D" model

4. **Enter Prompt**: Describe what to segment2. Upload a NIfTI file (.nii or .nii.gz)

   - Example: "segment the retinal vessels"3. Preview volume with interactive slice browser

   - Example: "find the tumor region"4. Enter segmentation prompt

5. **View Results**: Segmentation mask overlaid on original image5. Analyze and view results across multiple slices

6. **Download**: Save results as PNG6. Download 3D segmentation mask



### 3D Volume Segmentation## 🔒 Security



1. **Choose Model**: Select "MedImageParse 3D"- **Authentication**: Azure Entra ID single sign-on

2. **Upload Volume**: NIfTI file (.nii or .nii.gz)- **HTTPS Only**: All traffic encrypted in transit

3. **Enter Prompt**: Describe what to segment- **Key Vault**: Secrets never stored in code or config files

   - Example: "segment the brain"- **Managed Identity**: Service-to-service authentication without credentials

   - Example: "find the liver"- **RBAC**: Role-based access control for Azure resources

4. **Browse Slices**: Use slider to navigate through 3D volume

5. **Download**: Save 3D segmentation mask## 📈 Monitoring & Observability



### Prompt ExamplesThe application includes comprehensive monitoring:



**Ophthalmology**:- **Application Insights**: Performance metrics, exceptions, custom events

- "segment retinal vessels"- **Correlation IDs**: Track requests across service boundaries

- "detect optic disc"- **Structured Logging**: JSON-formatted logs with context

- "find hemorrhages"- **Availability Tests**: Automated health checks

- **Dashboards**: Pre-configured Azure Monitor dashboards

**Radiology**:

- "segment liver"### Key Metrics

- "segment left lung"

- "find tumor"- Request latency (p50, p95, p99)

- Model inference time

**Neurology**:- Error rates and types

- "segment brain"- Active user sessions

- "segment gray matter"- Image processing throughput

- "detect lesions"

## 🧪 Testing

---

```bash

## 🔧 Configuration# Run unit tests

pytest tests/unit/

### Environment Variables

# Run integration tests

Create a `.env` file (or use Azure Key Vault in production):pytest tests/integration/



```env# Run with coverage

# 2D Modelpytest --cov=src tests/

AZURE_OPENAI_ENDPOINT_2D=https://your-endpoint-2d.inference.ml.azure.com/score```

AZURE_OPENAI_KEY_2D=your-2d-api-key

## 🛠️ Troubleshooting

# 3D Model

AZURE_OPENAI_ENDPOINT_3D=https://your-endpoint-3d.inference.ml.azure.com/score### Common Issues

AZURE_OPENAI_KEY_3D=your-3d-api-key

**Issue**: "Model deployment failed in Azure AI Foundry"

# Application Insights (optional for local)- **Solution**: Check [Model Deployment Guide - Common Issues](./docs/model-deployment-guide.md#-common-issues-and-solutions) for detailed troubleshooting

APPLICATIONINSIGHTS_CONNECTION_STRING=your-connection-string

```**Issue**: "Entra ID authentication failed"

- **Solution**: Ensure you're signed in with `az login` and have proper Azure subscription access

### Key Vault Configuration (Production)

**Issue**: "Model endpoint timeout"

When deployed to Azure, the application automatically retrieves secrets from Key Vault:- **Solution**: Large NIfTI files may take time. Check file size and network connectivity



```python**Issue**: "nibabel library not found"

# No hardcoded secrets!- **Solution**: Install dependencies: `pip install nibabel`

config = Config()

endpoint = config.model_2d_endpoint  # Retrieved from Key Vault**Issue**: "Storage account access denied"

```- **Solution**: See [Model Deployment Guide - Storage Public Access](./docs/model-deployment-guide.md#4-storage-account-public-access)



---## 📖 Documentation



## 🛠️ Infrastructure Details- 🔥 **[Model Deployment Guide](./docs/model-deployment-guide.md)** - **START HERE** if you haven't deployed the models yet

- [Architecture Guide](./ARCHITECTURE.md)

### What Gets Deployed- [Deployment Guide](./docs/deployment-guide.md)

- [Contributing Guide](./CONTRIBUTING.md)

All infrastructure is defined in Bicep templates under `infra/`:

## 🚧 Limitations

```

infra/- **2D Model**: Maximum input size 1024x1024 pixels

├── main.bicep                  # Main orchestration- **3D Model**: Supports NIfTI format only

├── main.parameters.json        # Deployment parameters- **File Size**: Recommended max 50MB for optimal performance

└── modules/- **Concurrent Users**: Scales with App Service plan (configurable)

    ├── app-service.bicep       # App Service + Plan- **Model Availability**: Requires active Azure ML endpoints

    ├── keyvault.bicep          # Key Vault with RBAC

    ├── keyvault-access.bicep   # Managed Identity access## 🗺️ Roadmap

    ├── secrets.bicep           # Secret storage

    └── monitor.bicep           # Application Insights- [ ] Support for DICOM format

```- [ ] Batch processing capabilities

- [ ] Custom model fine-tuning

### Monitoring & Observability- [ ] REST API endpoints

- [ ] Mobile app support

**Application Insights** tracks:- [ ] Multi-region deployment

- Request/response times

- Failure rates## 📄 License

- Dependency calls (Key Vault, ML endpoints)

- Custom telemetry with correlation IDsThis project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

- User analytics

## 🤝 Contributing

**Correlation ID Tracking**: Every user session gets a unique correlation ID for distributed tracing across all logs.

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Security Features

## 📞 Support

- ✅ HTTPS-only (TLS 1.2+)

- ✅ Azure Entra ID authentication- **Issues**: [GitHub Issues](https://github.com/your-repo/MedImageParse/issues)

- ✅ No hardcoded secrets (Key Vault + Managed Identity)- **Discussions**: [GitHub Discussions](https://github.com/your-repo/MedImageParse/discussions)

- ✅ RBAC for all Azure resources- **Email**: support@example.com

- ✅ Network security groups

- ✅ Audit logging enabled## 👏 Acknowledgments



---- **MedImageParse Model**: Microsoft Research & Azure AI

- **Developed by**: Xinyuwei

## 🐛 Troubleshooting- **Powered by**: Azure AI & Streamlit



### Common Issues---



#### 1. Model Deployment Failed## 📊 Project Status

**Error**: "Deployment failed: Insufficient permissions"

[![Build Status](https://img.shields.io/github/workflow/status/your-repo/MedImageParse/CI)](https://github.com/your-repo/MedImageParse/actions)

**Solution**:[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

- Verify you have "Azure AI Developer" role on the AI Hub[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)

- Check storage account has public network access enabled[![Azure](https://img.shields.io/badge/Azure-0078D4?logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)

- Ensure using a paid subscription (not free/trial)

**Last Updated**: October 2025 | **Version**: 1.0.0

#### 2. 401 Unauthorized (ML Endpoint)
**Error**: "401 Client Error: Unauthorized"

**Solution**:
- Verify API key is correct (check Azure AI Foundry)
- Ensure endpoint URL matches deployment
- Check Key Vault secrets are set correctly

#### 3. Application Won't Start
**Error**: "Module not found" or "Import error"

**Solution**:
```bash
pip install -r src/requirements.txt --upgrade
```

#### 4. NIfTI File Not Loading
**Error**: "Failed to decode NIfTI"

**Solution**:
- Ensure file is valid NIfTI format (.nii or .nii.gz)
- Check file size < 100MB (upload limit)
- Verify file is not corrupted

#### 5. Key Vault Access Denied
**Error**: "Forbidden: Key Vault access denied"

**Solution**:
- Check Managed Identity is assigned
- Verify RBAC roles on Key Vault
- Wait 5-10 minutes after deployment for permissions to propagate

### Health Check

Check application health:
```bash
curl https://your-app.azurewebsites.net/healthz
```

### View Logs

**Azure Portal**:
1. Go to App Service → Monitoring → Log stream
2. Or use Application Insights → Logs

**CLI**:
```bash
az webapp log tail --name your-app-name --resource-group your-rg
```

---

## 💰 Cost Estimate

### Infrastructure Costs (Monthly)

| Service | Tier | Cost |
|---------|------|------|
| App Service Plan | B1 (Linux) | $13.14 |
| Application Insights | Pay-as-you-go | ~$5.00 |
| Key Vault | Standard | $0.03 |
| Storage (logs) | ~5GB | $0.10 |
| **Infrastructure Total** | | **~$18.27/month** |

### ML Model Costs (Monthly)

| Model | VM Size | Hours/Month | Cost |
|-------|---------|-------------|------|
| MedImageParse 2D | NC6s_v3 | 730 | ~$197 |
| MedImageParse 3D | NC6s_v3 | 730 | ~$197 |
| **ML Total** | | | **~$394/month** |

**Grand Total**: ~$412/month

> 💡 **Cost Optimization**: 
> - Use auto-shutdown for ML endpoints when not in use
> - Consider smaller VM sizes for development/testing
> - Use Azure Reserved Instances for production (up to 72% savings)

---

## 📚 Additional Resources

- **Model Deployment Guide**: [docs/model-deployment-guide.md](./docs/model-deployment-guide.md)
- **Application Deployment Guide**: [docs/deployment-guide.md](./docs/deployment-guide.md)
- **Azure AI Foundry Docs**: https://learn.microsoft.com/azure/ai-foundry/
- **MedImageParse Paper**: [Microsoft Research](https://www.microsoft.com/en-us/research/project/medimageparse/)

---

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

---

## 👨‍💻 Author

**Developed by Xinyuwei**

For questions or issues, please open an issue on GitHub.

---

## 🙏 Acknowledgments

- Microsoft Azure AI team for MedImageParse models
- Azure Machine Learning team
- Streamlit community
