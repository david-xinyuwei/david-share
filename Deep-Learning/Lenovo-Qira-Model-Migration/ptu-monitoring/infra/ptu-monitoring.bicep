// ============================================================
// Azure OpenAI PTU Monitoring Infrastructure
// ============================================================
// Deploys: Diagnostic Settings + Alert Rules + APIM + Backends
// 
// Usage:
//   az deployment group create \
//     --resource-group <rg> \
//     --template-file ptu-monitoring.bicep \
//     --parameters aoaiResourceName=<your-aoai> \
//                  ptuEndpoint=https://xxx.openai.azure.com \
//                  paygoEndpoint=https://yyy.openai.azure.com \
//                  actionGroupEmail=ops-team@company.com

@description('Name of your existing Azure OpenAI resource')
param aoaiResourceName string

@description('PTU deployment endpoint URL')
param ptuEndpoint string

@description('PAYGO deployment endpoint URL')
param paygoEndpoint string

@description('Email for alert notifications')
param actionGroupEmail string

@description('Location for new resources')
param location string = resourceGroup().location

@description('PTU utilization warning threshold (%)')
param alertWarningThreshold int = 80

@description('PTU utilization critical threshold (%)')
param alertCriticalThreshold int = 95

@description('APIM routing threshold (%)')
param apimRoutingThreshold int = 95

@description('APIM SKU')
param apimSku string = 'Consumption'

// ── Existing AOAI Resource ──
resource aoai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aoaiResourceName
}

// ── Log Analytics Workspace ──
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-ptu-monitor-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ── Diagnostic Settings (AOAI → Log Analytics) ──
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'ptu-diagnostics'
  scope: aoai
  properties: {
    workspaceId: logAnalytics.id
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: { enabled: false, days: 0 }
      }
    ]
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: { enabled: false, days: 0 }
      }
    ]
  }
}

// ── Action Group (email notifications) ──
resource actionGroup 'Microsoft.Insights/actionGroups@2023-09-01-preview' = {
  name: 'ag-ptu-alerts'
  location: 'global'
  properties: {
    groupShortName: 'PTUAlerts'
    enabled: true
    emailReceivers: [
      {
        name: 'OpsTeam'
        emailAddress: actionGroupEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// ── Alert: PTU Utilization > 80% (Warning) ──
resource alertWarning 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-ptu-utilization-warning'
  location: 'global'
  properties: {
    description: 'PTU utilization exceeded ${alertWarningThreshold}% — monitor closely'
    severity: 2 // Warning
    enabled: true
    scopes: [ aoai.id ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'PTU_Warning'
          metricName: 'ProvisionedManagedUtilizationV2'
          metricNamespace: 'Microsoft.CognitiveServices/accounts'
          operator: 'GreaterThan'
          threshold: alertWarningThreshold
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      { actionGroupId: actionGroup.id }
    ]
  }
}

// ── Alert: PTU Utilization > 95% (Critical) ──
resource alertCritical 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-ptu-utilization-critical'
  location: 'global'
  properties: {
    description: 'PTU utilization exceeded ${alertCriticalThreshold}% — APIM should be routing to PAYGO'
    severity: 0 // Critical
    enabled: true
    scopes: [ aoai.id ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT1M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'PTU_Critical'
          metricName: 'ProvisionedManagedUtilizationV2'
          metricNamespace: 'Microsoft.CognitiveServices/accounts'
          operator: 'GreaterThan'
          threshold: alertCriticalThreshold
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      { actionGroupId: actionGroup.id }
    ]
  }
}

// ── Alert: HTTP 429 (Throttled) ──
resource alert429 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-ptu-http429'
  location: 'global'
  properties: {
    description: 'HTTP 429 detected — PTU spillover triggered, APIM routing may have failed'
    severity: 1 // Error
    enabled: true
    scopes: [ aoai.id ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HTTP429'
          metricName: 'AzureOpenAIRequests'
          metricNamespace: 'Microsoft.CognitiveServices/accounts'
          operator: 'GreaterThan'
          threshold: 0
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
          dimensions: [
            {
              name: 'StatusCode'
              operator: 'Include'
              values: [ '429' ]
            }
          ]
        }
      ]
    }
    actions: [
      { actionGroupId: actionGroup.id }
    ]
  }
}

// ── APIM Instance ──
resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: 'apim-ptu-router-${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: apimSku
    capacity: (apimSku == 'Consumption') ? 0 : 1
  }
  properties: {
    publisherEmail: actionGroupEmail
    publisherName: 'PTU Router'
  }
}

// ── APIM Named Values ──
resource nvThreshold 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apim
  name: 'ptu-routing-threshold'
  properties: {
    displayName: 'ptu-routing-threshold'
    value: string(apimRoutingThreshold)
  }
}

resource nvDeployment 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apim
  name: 'ptu-deployment'
  properties: {
    displayName: 'ptu-deployment'
    value: 'gpt-5.4-nano'
  }
}

// ── APIM Backends ──
resource ptuBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'ptu-backend'
  properties: {
    url: '${ptuEndpoint}/openai'
    protocol: 'http'
    description: 'PTU deployment'
  }
}

resource paygoBackend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apim
  name: 'paygo-backend'
  properties: {
    url: '${paygoEndpoint}/openai'
    protocol: 'http'
    description: 'PAYGO deployment (overflow)'
  }
}

// ── Outputs ──
output logAnalyticsWorkspaceId string = logAnalytics.id
output apimName string = apim.name
output apimGatewayUrl string = apim.properties.gatewayUrl
output alertWarningName string = alertWarning.name
output alertCriticalName string = alertCritical.name
output alert429Name string = alert429.name
