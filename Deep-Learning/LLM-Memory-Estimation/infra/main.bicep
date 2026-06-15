targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string = resourceGroup().location

@description('Id of the user or app to assign application roles')
param principalId string = ''

// Tags that should be applied to all resources.
var tags = {
  'azd-env-name': environmentName
  'app-name': 'llm-memory-estimator'
}

// App Service Plan for hosting
module appServicePlan 'core/host/appserviceplan.bicep' = {
  name: 'appserviceplan'
  params: {
    name: 'plan-${environmentName}'
    location: location
    tags: tags
    sku: {
      name: 'B1'
      tier: 'Basic'
    }
    reserved: true // Required for Linux
  }
}

// Generate unique App Service name using hash
var uniqueSuffix = uniqueString(resourceGroup().id, environmentName)

// Web App
module web 'core/host/appservice.bicep' = {
  name: 'web'
  params: {
    name: 'llm-mem-${environmentName}-${uniqueSuffix}'
    location: location
    tags: union(tags, { 'azd-service-name': 'web' })
    appServicePlanId: appServicePlan.outputs.id
    runtimeName: 'python'
    runtimeVersion: '3.11'
    appCommandLine: 'startup.sh'
    ftpsState: 'Disabled'
    appSettings: {
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
      ENABLE_ORYX_BUILD: 'true'
      WEBSITES_PORT: '8000'
      SCM_COMMAND_IDLE_TIMEOUT: '3600'  // 60 minutes build timeout
      ORYX_BUILD_TIMEOUT: '3600'
    }
  }
}

// Application Insights for monitoring
module monitoring 'core/monitor/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    tags: tags
    logAnalyticsName: 'log-${environmentName}'
    applicationInsightsName: 'appi-${environmentName}'
  }
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup().name

output WEB_URI string = web.outputs.uri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
