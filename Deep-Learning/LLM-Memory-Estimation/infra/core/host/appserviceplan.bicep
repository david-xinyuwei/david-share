param name string
param location string = resourceGroup().location
param tags object = {}

param sku object = {
  name: 'B1'
  tier: 'Basic'
}

param reserved bool = true

resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: name
  location: location
  tags: tags
  sku: sku
  kind: reserved ? 'linux' : ''
  properties: {
    reserved: reserved
  }
}

output id string = appServicePlan.id
output name string = appServicePlan.name
