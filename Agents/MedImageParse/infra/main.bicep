targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('MedImageParse 2D Model Endpoint URL')
@secure()
param medImageParse2DEndpoint string = ''

@description('MedImageParse 2D Model API Key')
@secure()
param medImageParse2DKey string = ''

@description('MedImageParse 3D Model Endpoint URL')
@secure()
param medImageParse3DEndpoint string = ''

@description('MedImageParse 3D Model API Key')
@secure()
param medImageParse3DKey string = ''

// Tags for all resources
var tags = {
  'azd-env-name': environmentName
  'project': 'MedImageParse'
  'developed-by': 'Xinyuwei'
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Monitor: Application Insights & Log Analytics
module monitoring './modules/monitor.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    logAnalyticsName: 'log-${environmentName}'
    applicationInsightsName: 'appi-${environmentName}'
  }
}

// Key Vault for secrets
module keyVault './modules/keyvault.bicep' = {
  name: 'keyvault'
  scope: rg
  params: {
    location: location
    tags: tags
    keyVaultName: 'kv-${uniqueString(rg.id)}'
    principalId: principalId
  }
}

// App Service Plan & App Service
module appService './modules/app-service.bicep' = {
  name: 'appservice'
  scope: rg
  params: {
    location: location
    tags: tags
    appServicePlanName: 'asp-${environmentName}'
    appServiceName: 'app-${environmentName}-${uniqueString(rg.id)}'
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    keyVaultEndpoint: keyVault.outputs.keyVaultEndpoint
  }
}

// Store secrets in Key Vault
module secrets './modules/secrets.bicep' = {
  name: 'secrets'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.keyVaultName
    medImageParse2DEndpoint: medImageParse2DEndpoint
    medImageParse2DKey: medImageParse2DKey
    medImageParse3DEndpoint: medImageParse3DEndpoint
    medImageParse3DKey: medImageParse3DKey
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
  }
}

// Grant App Service access to Key Vault
module keyVaultAccess './modules/keyvault-access.bicep' = {
  name: 'keyvault-access'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.keyVaultName
    appServicePrincipalId: appService.outputs.appServicePrincipalId
  }
  dependsOn: [
    secrets
  ]
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

output AZURE_KEY_VAULT_NAME string = keyVault.outputs.keyVaultName
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.keyVaultEndpoint

output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.applicationInsightsName

output APP_SERVICE_NAME string = appService.outputs.appServiceName
output APP_SERVICE_URL string = appService.outputs.appServiceUrl
output APP_SERVICE_PLAN_NAME string = appService.outputs.appServicePlanName
