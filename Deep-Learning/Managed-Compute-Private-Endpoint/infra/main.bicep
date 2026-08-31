targetScope = 'resourceGroup'

@description('Full resource ID of an existing Microsoft.CognitiveServices/accounts Foundry resource.')
param foundryAccountResourceId string

@description('Full resource ID of an existing subnet dedicated to Private Endpoints. The linked VNet is derived from this ID.')
param privateEndpointSubnetResourceId string

@description('Azure region of the existing VNet. Derive it with the documented az network vnet show preflight.')
param privateEndpointLocation string

@description('Private endpoint resource name.')
param privateEndpointName string = 'pe-foundry-account'

type existingPrivateDnsZoneIds = {
  cognitiveservices: string
  openai: string
  servicesAi: string
}

@description('Optional existing Private DNS zone IDs. Supply the complete typed object or omit it. Existing zones must already be linked or resolvable through customer DNS.')
param existingPrivateDnsZoneResourceIds existingPrivateDnsZoneIds?

var subnetResourceMarker = '/subnets/'
var virtualNetworkResourceId = substring(privateEndpointSubnetResourceId, 0, lastIndexOf(toLower(privateEndpointSubnetResourceId), subnetResourceMarker))
var useExistingPrivateDnsZones = existingPrivateDnsZoneResourceIds != null

var privateDnsZoneDefinitions = [
  {
    name: 'privatelink.cognitiveservices.azure.com'
    configName: 'cognitiveservices'
    parameterName: 'cognitiveservices'
  }
  {
    name: 'privatelink.openai.azure.com'
    configName: 'openai'
    parameterName: 'openai'
  }
  {
    name: 'privatelink.services.ai.azure.com'
    configName: 'services-ai'
    parameterName: 'servicesAi'
  }
]

resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zone in privateDnsZoneDefinitions: if (!useExistingPrivateDnsZones) {
  name: zone.name
  location: 'global'
}]

resource privateDnsLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zone, index) in privateDnsZoneDefinitions: if (!useExistingPrivateDnsZones) {
  parent: privateDnsZones[index]
  name: 'link-${uniqueString(resourceGroup().id, virtualNetworkResourceId, zone.name)}'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetworkResourceId
    }
  }
}]

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: privateEndpointName
  location: privateEndpointLocation
  properties: {
    subnet: {
      id: privateEndpointSubnetResourceId
    }
    privateLinkServiceConnections: [
      {
        name: 'connection-${privateEndpointName}'
        properties: {
          privateLinkServiceId: foundryAccountResourceId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
  dependsOn: [
    privateDnsLinks
  ]
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [for (zone, index) in privateDnsZoneDefinitions: {
      name: zone.configName
      properties: {
        privateDnsZoneId: useExistingPrivateDnsZones
          ? existingPrivateDnsZoneResourceIds![zone.parameterName]
          : privateDnsZones[index].id
      }
    }]
  }
}

output privateEndpointId string = privateEndpoint.id
output virtualNetworkId string = virtualNetworkResourceId
output supportedPrivateDnsZones array = [for zone in privateDnsZoneDefinitions: zone.name]
output privateDnsOwnership string = useExistingPrivateDnsZones ? 'existing-customer-managed' : 'created-by-deployment'
