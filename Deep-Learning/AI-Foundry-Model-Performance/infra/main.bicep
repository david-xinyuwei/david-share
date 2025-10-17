// Main Bicep template for AI Foundry Model Performance Testing
// This template deploys all required Azure resources for the project

targetScope = 'subscription'

@description('Primary location for all resources')
param location string = 'eastus'

@description('Name of the resource group')
param resourceGroupName string = 'rg-ai-foundry-perf'

@description('Name of the Azure ML workspace')
param mlWorkspaceName string = 'mlw-ai-foundry-perf'

@description('Name of the Application Insights instance')
param appInsightsName string = 'appi-ai-foundry-perf'

@description('Name of the Log Analytics workspace')
param logAnalyticsName string = 'log-ai-foundry-perf'

@description('Name of the Key Vault')
param keyVaultName string = 'kv-ai-foundry-${uniqueString(resourceGroupName)}'

@description('Name of the Storage Account')
param storageAccountName string = 'stai${uniqueString(resourceGroupName)}'

@description('Environment name (dev, prod, etc.)')
param environmentName string = 'dev'

@description('Tags to apply to all resources')
param tags object = {
  Environment: environmentName
  Project: 'AI-Foundry-Model-Performance'
  ManagedBy: 'Bicep'
}

// Create resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// Deploy monitoring resources
module monitoring './modules/monitoring.bicep' = {
  scope: rg
  name: 'monitoring-deployment'
  params: {
    location: location
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    tags: tags
  }
}

// Deploy storage account
module storage './modules/storage.bicep' = {
  scope: rg
  name: 'storage-deployment'
  params: {
    location: location
    storageAccountName: storageAccountName
    tags: tags
  }
}

// Deploy Key Vault
module keyVault './modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault-deployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    tags: tags
  }
}

// Deploy Azure ML Workspace
module mlWorkspace './modules/ml-workspace.bicep' = {
  scope: rg
  name: 'mlworkspace-deployment'
  params: {
    location: location
    workspaceName: mlWorkspaceName
    storageAccountId: storage.outputs.storageAccountId
    keyVaultId: keyVault.outputs.keyVaultId
    appInsightsId: monitoring.outputs.appInsightsId
    tags: tags
  }
}

// Outputs
output resourceGroupName string = rg.name
output mlWorkspaceName string = mlWorkspace.outputs.workspaceName
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output appInsightsInstrumentationKey string = monitoring.outputs.appInsightsInstrumentationKey
output keyVaultName string = keyVault.outputs.keyVaultName
output storageAccountName string = storage.outputs.storageAccountName
