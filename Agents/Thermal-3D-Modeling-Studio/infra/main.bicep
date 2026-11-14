// Every Azure resource the Thermal 3D Modeling Studio needs, in one resource group.
// Deployed by infra/up.ps1 (which also installs the studio on the VM); removed by infra/down.ps1.
targetScope = 'resourceGroup'

@description('Region of every resource. The model deployments need quota in this region.')
param location string = resourceGroup().location

@description('Lowercase prefix of the resource names. A hash of the resource group id is appended where a name must be globally unique.')
@minLength(3)
@maxLength(12)
param namePrefix string = 'thermal'

@description('Deployment type of gpt-6-astra: GlobalStandard or DataZoneStandard (up.ps1 picks the one with free quota).')
@allowed([
  'GlobalStandard'
  'DataZoneStandard'
])
param gpt6Sku string = 'GlobalStandard'

@description('gpt-6-astra capacity in thousands of tokens per minute.')
@minValue(1)
param gpt6Capacity int = 100

@description('gpt-6-astra model version.')
param gpt6ModelVersion string = '2026-09-03'

@description('Deploy an image model for Tracks C and D (photoreal render, concept image).')
param deployImageModel bool = true

@description('Image model, used as the deployment name too.')
param imageModelName string = 'gpt-image-2.5-sunburst'

@description('Image model version.')
param imageModelVersion string = '2026-09-08'

@description('Image model capacity (GlobalStandard quota units of the model).')
@minValue(1)
param imageCapacity int = 2

@description('VM size: 4 vCPUs are enough for the studio and the OCCT builds.')
param vmSize string = 'Standard_D4as_v5'

@description('Disk controller of the VM: the v6 sizes take NVMe only.')
@allowed([
  'SCSI'
  'NVMe'
])
param diskControllerType string = 'SCSI'

@description('Admin user of the VM.')
param adminUsername string = 'azureuser'

@description('SSH public key of the admin user. up.ps1 creates a key pair when none is given; the installer itself uses Run Command, not SSH.')
param adminPublicKey string

@description('Address or CIDR allowed to reach SSH (port 22). Empty: no inbound SSH.')
param allowSshFrom string = ''

@description('Object id of a user or service principal that also gets model access, for running the studio on your own machine. Empty: none.')
param deployerPrincipalId string = ''

@allowed([
  'User'
  'ServicePrincipal'
])
param deployerPrincipalType string = 'User'

var prefix = toLower(namePrefix)
var suffix = uniqueString(resourceGroup().id)
var aiName = '${prefix}-ai-${suffix}'
// Built-in role "Cognitive Services OpenAI User": inference calls with a Microsoft Entra token, nothing else.
var openAiUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')

resource ai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: aiName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true // Microsoft Entra tokens only; the VM uses its managed identity
  }
}

resource gpt6 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: ai
  name: 'gpt-6-astra'
  sku: {
    name: gpt6Sku
    capacity: gpt6Capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-6-astra'
      version: gpt6ModelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource image 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployImageModel) {
  parent: ai
  name: imageModelName
  dependsOn: [
    gpt6 // one deployment operation at a time per resource
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: imageCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: imageModelName
      version: imageModelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-vm-identity'
  location: location
}

resource vmModelAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ai.id, identity.id, openAiUserRole)
  scope: ai
  properties: {
    roleDefinitionId: openAiUserRole
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deployerModelAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(ai.id, deployerPrincipalId, openAiUserRole)
  scope: ai
  properties: {
    roleDefinitionId: openAiUserRole
    principalId: deployerPrincipalId
    principalType: deployerPrincipalType
  }
}

var webRules = [
  {
    name: 'allow-https'
    properties: {
      priority: 100
      direction: 'Inbound'
      access: 'Allow'
      protocol: 'Tcp'
      sourceAddressPrefix: 'Internet'
      sourcePortRange: '*'
      destinationAddressPrefix: '*'
      destinationPortRange: '443'
    }
  }
  {
    name: 'allow-http-for-certificate'
    properties: {
      priority: 110
      direction: 'Inbound'
      access: 'Allow'
      protocol: 'Tcp'
      sourceAddressPrefix: 'Internet'
      sourcePortRange: '*'
      destinationAddressPrefix: '*'
      destinationPortRange: '80'
    }
  }
]
var sshRule = empty(allowSshFrom) ? [] : [
  {
    name: 'allow-ssh'
    properties: {
      priority: 120
      direction: 'Inbound'
      access: 'Allow'
      protocol: 'Tcp'
      sourceAddressPrefix: allowSshFrom
      sourcePortRange: '*'
      destinationAddressPrefix: '*'
      destinationPortRange: '22'
    }
  }
]

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${prefix}-nsg'
  location: location
  properties: {
    securityRules: concat(webRules, sshRule)
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${prefix}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.40.0.0/24'
      ]
    }
    subnets: [
      {
        name: 'vm'
        properties: {
          addressPrefix: '10.40.0.0/26'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${prefix}-ip'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: '${prefix}-${suffix}'
    }
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${prefix}-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: '${prefix}-vm'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    storageProfile: {
      diskControllerType: diskControllerType
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 64
        deleteOption: 'Delete'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
      }
    }
    osProfile: {
      computerName: '${prefix}-vm'
      adminUsername: adminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: adminPublicKey
            }
          ]
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
          properties: {
            deleteOption: 'Delete'
          }
        }
      ]
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        secureBootEnabled: true
        vTpmEnabled: true
      }
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

output vmName string = vm.name
output fqdn string = publicIp.properties.dnsSettings.fqdn
output aiName string = ai.name
output aiEndpoint string = 'https://${aiName}.openai.azure.com'
output gpt6Deployment string = gpt6.name
output gpt6Sku string = gpt6Sku
output imageDeployment string = deployImageModel ? imageModelName : ''
output identityClientId string = identity.properties.clientId
output location string = location
