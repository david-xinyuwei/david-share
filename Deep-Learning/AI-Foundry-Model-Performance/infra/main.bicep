// Main Bicep template for AI Foundry Model Performance Testing
// This template deploys all required Azure resources for the project

targetScope = 'subscription'

@minLength(1)
@description('Azure region where all resources will be deployed. IMPORTANT: Choose a region where you have GPU quota available (NC/ND/NV series). Common GPU regions: eastus, eastus2, westus2, westus3, westeurope, northeurope, uksouth, swedencentral, polandcentral, japaneast, australiaeast, southeastasia.')
@allowed([
  'eastus'
  'eastus2'
  'westus'
  'westus2'
  'westus3'
  'centralus'
  'southcentralus'
  'northcentralus'
  'westcentralus'
  'westeurope'
  'northeurope'
  'uksouth'
  'ukwest'
  'francecentral'
  'germanywestcentral'
  'switzerlandnorth'
  'norwayeast'
  'polandcentral'
  'swedencentral'
  'japaneast'
  'japanwest'
  'koreacentral'
  'australiaeast'
  'australiasoutheast'
  'southeastasia'
  'eastasia'
  'southafricanorth'
  'brazilsouth'
  'canadacentral'
  'canadaeast'
  'southindia'
  'centralindia'
  'westindia'
])
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Environment name - used as suffix for resource naming (e.g., dev, test, prod)')
param environmentName string = 'dev'

// Helper function to get short region code (max 6 chars)
var locationCode = {
  eastus: 'eus'
  eastus2: 'eus2'
  westus: 'wus'
  westus2: 'wus2'
  westus3: 'wus3'
  centralus: 'cus'
  southcentralus: 'scus'
  northcentralus: 'ncus'
  westeurope: 'weu'
  northeurope: 'neu'
  uksouth: 'uks'
  japaneast: 'jpe'
  australiaeast: 'aue'
  southeastasia: 'sea'
  eastasia: 'ea'
  swedencentral: 'swe'
  polandcentral: 'pol'
  canadacentral: 'cac'
  brazilsouth: 'brs'
  southindia: 'sin'
}[location]

@description('Name of the resource group')
param resourceGroupName string = 'rg-aif-${locationCode}-${environmentName}'

@description('Name of the Azure ML workspace - max 33 chars, uses short location code')
param mlWorkspaceName string = 'mlw-aif-${locationCode}-${environmentName}'

@description('Name of the Application Insights instance')
param appInsightsName string = 'appi-aif-${locationCode}-${environmentName}'

@description('Name of the Log Analytics workspace')
param logAnalyticsName string = 'log-aif-${locationCode}-${environmentName}'

@description('Name of the Key Vault (uses uniqueString for global uniqueness)')
param keyVaultName string = 'kv-${uniqueString(subscription().subscriptionId, resourceGroupName, location)}'

@description('Name of the Storage Account (uses uniqueString for global uniqueness)')
param storageAccountName string = 'stai${uniqueString(subscription().subscriptionId, resourceGroupName, location)}'

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
