param location string
param tags object

param appServicePlanName string
param appServiceName string
param applicationInsightsConnectionString string

// App Service Plan (Linux, Python)
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: 'F1'  // Free tier - $0/month (⚠️ No Always On, cold start issues!)
    tier: 'Free'
    size: 'F1'
    family: 'F'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true  // Required for Linux
  }
}

// App Service (Streamlit Web App)
resource appService 'Microsoft.Web/sites@2022-03-01' = {
  name: appServiceName
  location: location
  tags: union(tags, {
    'azd-service-name': 'web'
  })
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: false  // Free tier doesn't support Always On
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appCommandLine: 'python -m streamlit run app_clean.py --server.port=8000 --server.address=0.0.0.0'
      healthCheckPath: '/healthz'
      appSettings: [
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsightsConnectionString
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS'
          value: '7'
        }
        {
          name: 'ADMIN_PASSWORD'
          value: 'ChangeThisPassword123!'  // ⚠️ IMPORTANT: Change this after deployment!
        }
      ]
    }
  }
}

output appServiceId string = appService.id
output appServiceName string = appService.name
output appServiceUrl string = 'https://${appService.properties.defaultHostName}'
output appServicePrincipalId string = appService.identity.principalId
output appServicePlanName string = appServicePlan.name
output appServicePlanId string = appServicePlan.id
