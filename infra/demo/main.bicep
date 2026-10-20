targetScope = 'subscription'

@allowed(['swedencentral'])
param location string = 'swedencentral'

@description('Signed-in operator used for data-plane verification. Supplied at execution, never committed.')
param operatorPrincipalId string

@allowed(['Disabled', 'Enabled'])
param storagePublicNetworkAccess string = 'Disabled'

var tags = {
  project: 'giandoria'
  env: 'demo'
  'managed-by': 'bicep'
  classification: 'synthetic'
}
var suffix = take(uniqueString(subscription().id, 'demo'), 4)

resource core 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-giandoria-core-demo'
  location: location
  tags: tags
}

resource ops 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-giandoria-ops-demo'
  location: location
  tags: tags
}

resource fabric 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-giandoria-fabric-demo'
  location: location
  tags: tags
}

module platform 'platform.bicep' = {
  scope: core
  params: {
    location: location
    suffix: suffix
    tags: tags
    operatorPrincipalId: operatorPrincipalId
    storagePublicNetworkAccess: storagePublicNetworkAccess
  }
}

module exports 'storage.bicep' = {
  scope: ops
  params: {
    name: 'stgiandoriaopsdemo${suffix}'
    location: location
    tags: tags
    publicNetworkAccess: storagePublicNetworkAccess
    isStateAccount: false
    dataPrincipals: [
      { principalId: operatorPrincipalId, principalType: 'User' }
      { principalId: platform.outputs.controlPrincipalId, principalType: 'ServicePrincipal' }
    ]
  }
}

output stateAccountName string = platform.outputs.stateAccountName
output opsAccountName string = exports.outputs.name
output environmentName string = platform.outputs.environmentName
output registryName string = platform.outputs.registryName
output fabricResourceGroupName string = fabric.name
