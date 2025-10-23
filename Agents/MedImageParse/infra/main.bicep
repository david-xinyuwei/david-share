targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

// Tags for all resources
var tags = {
  'azd-env-name': environmentName
  project: 'MedImageParse'
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
  }
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.applicationInsightsName

output APP_SERVICE_NAME string = appService.outputs.appServiceName
output APP_SERVICE_URL string = appService.outputs.appServiceUrl
output APP_SERVICE_PLAN_NAME string = appService.outputs.appServicePlanName

// Service outputs for azd (critical for deployment mapping)
output SERVICE_WEB_NAME string = appService.outputs.appServiceName
output SERVICE_WEB_RESOURCE_GROUP string = rg.name
