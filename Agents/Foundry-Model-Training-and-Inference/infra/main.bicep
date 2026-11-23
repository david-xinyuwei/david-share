// The resources that cost nothing while idle: a Microsoft Foundry account, one project, and the role that lets
// the person who runs the scripts call the project's data plane (files, fine-tuning jobs, models, inference).
// The GPU-backed target deployment and the adapter deployments are created later by `up.py --deploy`,
// because they are billed per hour and need the trained adapter first.

@description('Region of the Foundry account and project. Choose one where Managed Training supports Qwen3.8-27B.')
param location string = resourceGroup().location

@description('Foundry account name. It is also the custom subdomain of the endpoint, so it must be globally unique.')
@minLength(2)
@maxLength(64)
param accountName string = 'ftlora-${uniqueString(resourceGroup().id)}'

@description('Foundry project name.')
param projectName string = 'lora-demo'

@description('Object ID of the user, group or service principal that runs up.py, verify.py and down.py.')
param principalId string

@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param principalType string = 'User'

var tags = {
  solution: 'foundry-managed-training-lora'
}

// Built-in role "Foundry User" (formerly "Azure AI User"): data actions on the account and its projects.
var foundryUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    customSubDomainName: accountName
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true // Microsoft Entra ID only: no API key exists to leak
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    displayName: projectName
    description: 'Managed Training of LoRA adapters and adapter serving on managed compute'
  }
}

resource foundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, principalId, foundryUserRoleDefinitionId)
  properties: {
    roleDefinitionId: foundryUserRoleDefinitionId
    principalId: principalId
    principalType: principalType
  }
}

output accountName string = account.name
output projectName string = project.name
output projectEndpoint string = project.properties.endpoints['AI Foundry API']
