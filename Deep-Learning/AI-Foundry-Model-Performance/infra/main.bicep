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

// Generate short location code automatically (first 3 chars + last 2 chars, max 6 chars)
// This works for ANY Azure region without hardcoding
var locationCode = length(location) <= 6 
  ? location 
  : '${substring(location, 0, 3)}${substring(location, length(location) - 2, 2)}'

// Examples:
//   eastus -> eastus (6 chars)
//   francecentral -> fraal (3+2=5 chars) 
//   southeastasia -> soua (3+2=5 chars)
//   westeurope -> wespe (3+2=5 chars)

// Computed resource names using location code
var resourceGroupName = 'rg-aif-${locationCode}-${environmentName}'
var mlWorkspaceName = 'mlw-aif-${locationCode}-${environmentName}'
var appInsightsName = 'appi-aif-${locationCode}-${environmentName}'
var logAnalyticsName = 'log-aif-${locationCode}-${environmentName}'
var keyVaultName = 'kv-${uniqueString(subscription().subscriptionId, resourceGroupName, location)}'
var storageAccountName = 'stai${uniqueString(subscription().subscriptionId, resourceGroupName, location)}'

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
