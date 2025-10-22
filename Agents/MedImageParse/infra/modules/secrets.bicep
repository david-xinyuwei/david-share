param keyVaultName string

@secure()
param medImageParse2DEndpoint string
@secure()
param medImageParse2DKey string
@secure()
param medImageParse3DEndpoint string
@secure()
param medImageParse3DKey string
@secure()
param applicationInsightsConnectionString string

// Reference existing Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

// Store MedImageParse 2D Endpoint
resource secret2DEndpoint 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'AZURE-OPENAI-ENDPOINT-2D'
  properties: {
    value: medImageParse2DEndpoint
  }
}

// Store MedImageParse 2D Key
resource secret2DKey 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'AZURE-OPENAI-KEY-2D'
  properties: {
    value: medImageParse2DKey
  }
}

// Store MedImageParse 3D Endpoint
resource secret3DEndpoint 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'AZURE-OPENAI-ENDPOINT-3D'
  properties: {
    value: medImageParse3DEndpoint
  }
}

// Store MedImageParse 3D Key
resource secret3DKey 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'AZURE-OPENAI-KEY-3D'
  properties: {
    value: medImageParse3DKey
  }
}

// Store Application Insights Connection String
resource secretAppInsights 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  parent: keyVault
  name: 'APPLICATIONINSIGHTS-CONNECTION-STRING'
  properties: {
    value: applicationInsightsConnectionString
  }
}

output secretNames array = [
  secret2DEndpoint.name
  secret2DKey.name
  secret3DEndpoint.name
  secret3DKey.name
  secretAppInsights.name
]
