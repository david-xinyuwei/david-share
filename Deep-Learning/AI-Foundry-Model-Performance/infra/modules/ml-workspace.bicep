// Azure ML Workspace module

@description('Azure region for resources')
param location string

@description('Name of the ML workspace')
param workspaceName string

@description('Storage Account resource ID')
param storageAccountId string

@description('Key Vault resource ID')
param keyVaultId string

@description('Application Insights resource ID')
param appInsightsId string

@description('Tags to apply to resources')
param tags object = {}

// Azure ML Workspace
resource mlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: workspaceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: workspaceName
    storageAccount: storageAccountId
    keyVault: keyVaultId
    applicationInsights: appInsightsId
    publicNetworkAccess: 'Enabled'
    hbiWorkspace: false
  }
}

// Outputs
output workspaceName string = mlWorkspace.name
output workspaceId string = mlWorkspace.id
output workspacePrincipalId string = mlWorkspace.identity.principalId
