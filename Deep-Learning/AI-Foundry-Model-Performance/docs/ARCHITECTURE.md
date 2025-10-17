# Architecture Overview

## System Architecture

This document describes the architecture of the AI Foundry Model Performance Testing solution.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Azure Subscription                               │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Resource Group                                 │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │            Azure ML Workspace / AI Foundry Project           │ │ │
│  │  │                                                              │ │ │
│  │  │  ┌─────────────────┐         ┌─────────────────┐           │ │ │
│  │  │  │  Model Catalog  │         │  Online         │           │ │ │
│  │  │  │                 │         │  Endpoints      │           │ │ │
│  │  │  │  • Phi-4        │────────▶│                 │           │ │ │
│  │  │  │  • Llama 3.2    │         │  • Managed      │           │ │ │
│  │  │  │  • Mistral      │         │    Compute      │           │ │ │
│  │  │  │  • DeepSeek     │         │  • GPU VMs      │           │ │ │
│  │  │  │  • 15+ models   │         │    (NC-series)  │           │ │ │
│  │  │  └─────────────────┘         └─────────────────┘           │ │ │
│  │  │                                       │                     │ │ │
│  │  └───────────────────────────────────────┼─────────────────────┘ │ │
│  │                                          │                       │ │
│  │  ┌───────────────────────────────────────▼─────────────────────┐ │ │
│  │  │              Monitoring & Observability                      │ │ │
│  │  │                                                              │ │ │
│  │  │  ┌───────────────────┐      ┌───────────────────┐          │ │ │
│  │  │  │  Application      │      │  Log Analytics    │          │ │ │
│  │  │  │  Insights         │◀────▶│  Workspace        │          │ │ │
│  │  │  │                   │      │                   │          │ │ │
│  │  │  │  • Correlation ID │      │  • Centralized    │          │ │ │
│  │  │  │  • Custom Metrics │      │    Logs           │          │ │ │
│  │  │  │  • Request Trace  │      │  • Query          │          │ │ │
│  │  │  │  • Exceptions     │      │  • Analytics      │          │ │ │
│  │  │  └───────────────────┘      └───────────────────┘          │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Security & Storage                        │ │ │
│  │  │                                                              │ │ │
│  │  │  ┌───────────────┐      ┌───────────────┐                  │ │ │
│  │  │  │  Key Vault    │      │  Storage      │                  │ │ │
│  │  │  │               │      │  Account      │                  │ │ │
│  │  │  │  • API Keys   │      │               │                  │ │ │
│  │  │  │  • Secrets    │      │  • Model      │                  │ │ │
│  │  │  │  • RBAC       │      │    Artifacts  │                  │ │ │
│  │  │  │  • Entra ID   │      │  • Logs       │                  │ │ │
│  │  │  └───────────────┘      └───────────────┘                  │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         Client / User                                    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Python Scripts                                   │ │
│  │                                                                     │ │
│  │  ┌───────────────────┐      ┌───────────────────┐                 │ │
│  │  │  Deployment       │      │  Performance      │                 │ │
│  │  │  Scripts          │      │  Testing          │                 │ │
│  │  │                   │      │                   │                 │ │
│  │  │  • Deploy models  │      │  • Stress test    │                 │ │
│  │  │  • Manage         │      │  • Metrics        │                 │ │
│  │  │    endpoints      │      │  • Reports        │                 │ │
│  │  │  • Cleanup        │      │  • Multi-model    │                 │ │
│  │  └───────────────────┘      └───────────────────┘                 │ │
│  │           │                           │                            │ │
│  │           └───────────┬───────────────┘                            │ │
│  │                       │                                            │ │
│  │            ┌──────────▼──────────┐                                 │ │
│  │            │   Observability     │                                 │ │
│  │            │   Module            │                                 │ │
│  │            │                     │                                 │ │
│  │            │  • Correlation ID   │                                 │ │
│  │            │  • Logging          │                                 │ │
│  │            │  • Metrics          │                                 │ │
│  │            └─────────────────────┘                                 │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. Azure ML Workspace / AI Foundry Project
**Purpose:** Central hub for model deployment and management

**Components:**
- **Model Catalog:** Access to 15+ open-source AI models
- **Online Endpoints:** Deployed models with REST API access
- **Managed Compute:** GPU-based VMs (NC24/48/96 A100, H100)

**Key Features:**
- Automated model deployment
- Scalable inference endpoints
- GPU acceleration (A100/H100)

### 2. Monitoring & Observability
**Purpose:** Track performance, logs, and metrics

**Components:**
- **Application Insights:**
  - Correlation ID for request tracing
  - Custom metrics (TTFT, throughput, latency)
  - Request duration tracking
  - Exception logging

- **Log Analytics Workspace:**
  - Centralized log storage
  - KQL query interface
  - 30-day retention
  - Cross-resource queries

### 3. Security & Storage
**Purpose:** Secure secret management and data storage

**Components:**
- **Key Vault:**
  - API key storage
  - Secret management
  - RBAC authorization
  - Entra ID integration

- **Storage Account:**
  - Model artifacts
  - Test results
  - Log files
  - TLS 1.2+ enforced

### 4. Client Scripts
**Purpose:** Deployment and testing automation

**Components:**
- **Deployment Scripts:**
  - Automated model deployment
  - Endpoint management
  - Resource cleanup

- **Performance Testing:**
  - Multi-scenario testing
  - Real prompt evaluation
  - Metrics collection
  - Report generation

## Data Flow

### Model Deployment Flow

```
User Script → Azure ML SDK → Model Catalog → Online Endpoint → GPU VM
                    │
                    └──────→ App Insights (Deployment Logs)
```

### Performance Testing Flow

```
Test Script → HTTPS Request → Online Endpoint → Model Inference
     │                                                 │
     │                                                 ▼
     └────→ Observability Module ──────→ Application Insights
                    │
                    └──────→ Correlation ID Tracking
                    │
                    └──────→ Metrics (TTFT, Throughput)
```

### Monitoring Flow

```
Application Insights → Log Analytics → KQL Queries → Dashboard
                           │
                           └──────→ Alerts & Notifications
```

## Security Architecture

### Authentication & Authorization

```
┌────────────────┐
│     User       │
└────────┬───────┘
         │
         ▼
┌────────────────────┐
│  Azure Entra ID    │
│  Authentication    │
└────────┬───────────┘
         │
         ├──────→ Azure ML Workspace (RBAC)
         │
         ├──────→ Key Vault (RBAC)
         │
         └──────→ Storage Account (Managed Identity)
```

### Secret Management

```
API Key → Environment Variable → Key Vault
                                    │
                                    └──→ Script (DefaultAzureCredential)
```

### Network Security

- ✅ HTTPS only for all endpoints
- ✅ TLS 1.2+ enforced
- ✅ Azure backbone network
- ✅ Public access can be restricted (configurable)

## Deployment Architecture

### Infrastructure as Code

```
azure.yaml (azd config)
    │
    ├──→ infra/main.bicep
    │        │
    │        ├──→ modules/monitoring.bicep
    │        ├──→ modules/ml-workspace.bicep
    │        ├──→ modules/keyvault.bicep
    │        └──→ modules/storage.bicep
    │
    └──→ Deployment Hooks
             │
             ├──→ preprovision
             ├──→ postprovision
             ├──→ predeploy
             └──→ postdeploy
```

### One-Click Deployment

```
azd up
    │
    ├──→ 1. Provision Resources (Bicep)
    │        ├── Resource Group
    │        ├── ML Workspace
    │        ├── Application Insights
    │        ├── Key Vault
    │        └── Storage Account
    │
    ├──→ 2. Setup Environment (Hooks)
    │        ├── Python venv
    │        ├── Install dependencies
    │        └── Configure environment variables
    │
    └──→ 3. Output Configuration
             ├── Workspace name
             ├── App Insights connection string
             └── Resource URLs
```

## Performance Monitoring

### Metrics Collected

1. **Time to First Token (TTFT)**
   - Time from request to first response token
   - Per-model tracking
   - Per-request logging

2. **Throughput**
   - Tokens per second
   - Requests per second
   - Concurrent request handling

3. **Latency**
   - End-to-end request duration
   - Network latency
   - Model inference time

4. **Resource Utilization**
   - GPU usage
   - Memory consumption
   - Instance count

### Observability Features

```
Every Request:
    │
    ├──→ Unique Correlation ID
    ├──→ Timestamp
    ├──→ Model name
    ├──→ Instance type
    ├──→ Request parameters
    ├──→ Response metrics
    └──→ Success/Failure status
         │
         └──→ Application Insights
                   │
                   └──→ Queryable via KQL
```

## Scalability

### Horizontal Scaling
- Multiple endpoint instances
- Load balancing across instances
- Auto-scaling support (configurable)

### Vertical Scaling
- GPU selection (NC24, NC48, NC96, H100)
- Memory allocation
- Instance type optimization

## High Availability

- Multiple Azure regions supported
- Endpoint redundancy
- Automatic failover (via Azure infrastructure)
- Health probes configured

## Cost Optimization

- GPU compute billed per hour
- Auto-shutdown when idle (configurable)
- Instance count optimization
- Storage lifecycle management

## Disaster Recovery

- Infrastructure as Code (quick redeploy)
- Automated backup (Storage Account)
- Cross-region deployment support
- State recovery via IaC

## Compliance

- ✅ Entra ID authentication
- ✅ RBAC for all resources
- ✅ Audit logs in Log Analytics
- ✅ No secrets in code
- ✅ TLS 1.2+ enforcement
- ✅ Data encryption at rest and in transit

## Future Enhancements

- [ ] Multi-region deployment
- [ ] Auto-scaling policies
- [ ] CI/CD pipeline integration
- [ ] Grafana dashboards
- [ ] Alerting rules
- [ ] Cost analysis reports

---

## Related Documentation

- [Main README](../readme.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Compliance Checklist](COMPLIANCE.md)
- [Observability Module](../scripts/utils/observability.py)
