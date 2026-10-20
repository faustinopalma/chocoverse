param location string
param suffix string
param tags { *: string }
param operatorPrincipalId string
@allowed(['Disabled', 'Enabled'])
param storagePublicNetworkAccess string

module identities 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = [
  for kind in ['runtime', 'control']: {
    params: {
      name: 'id-giandoria-${kind}-demo'
      location: location
      tags: tags
      enableTelemetry: false
    }
  }
]

module state 'storage.bicep' = {
  params: {
    name: 'stgiandoriademo${suffix}'
    location: location
    tags: tags
    publicNetworkAccess: storagePublicNetworkAccess
    isStateAccount: true
    dataPrincipals: [
      { principalId: operatorPrincipalId, principalType: 'User' }
      { principalId: identities[0].outputs.principalId, principalType: 'ServicePrincipal' }
      { principalId: identities[1].outputs.principalId, principalType: 'ServicePrincipal' }
    ]
  }
}

module logs 'br/public:avm/res/operational-insights/workspace:0.16.1' = {
  params: {
    name: 'log-giandoria-demo'
    location: location
    tags: tags
    enableTelemetry: false
    skuName: 'PerGB2018'
    dataRetention: 30
    dailyQuotaGb: '0.1'
    forceCmkForQuery: false
    features: { disableLocalAuth: true }
  }
}

module insights 'br/public:avm/res/insights/component:0.8.0' = {
  params: {
    name: 'appi-giandoria-demo'
    location: location
    tags: tags
    enableTelemetry: false
    workspaceResourceId: logs.outputs.resourceId
    retentionInDays: 30
    disableLocalAuth: true
    disableIpMasking: false
    roleAssignments: [
      for i in range(0, 2): {
        roleDefinitionIdOrName: 'Monitoring Metrics Publisher'
        principalId: identities[i].outputs.principalId
        principalType: 'ServicePrincipal'
      }
    ]
  }
}

module registry 'br/public:avm/res/container-registry/registry:0.13.1' = {
  params: {
    name: 'crgiandoriademo${suffix}'
    location: location
    tags: tags
    enableTelemetry: false
    acrSku: 'Basic'
    acrAdminUserEnabled: false
    anonymousPullEnabled: false
    zoneRedundancy: 'Disabled'
    retentionPolicyStatus: 'disabled'
    exportPolicyStatus: 'enabled'
    publicNetworkAccess: 'Enabled'
    networkRuleSetDefaultAction: 'Allow'
    roleAssignmentMode: 'LegacyRegistryPermissions'
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'AcrPull'
        principalId: identities[0].outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'AcrPull'
        principalId: identities[1].outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'AcrPush'
        principalId: operatorPrincipalId
        principalType: 'User'
      }
    ]
  }
}

module environment 'br/public:avm/res/app/managed-environment:0.16.0' = {
  params: {
    name: 'cae-giandoria-demo'
    location: location
    tags: tags
    enableTelemetry: false
    zoneRedundant: false
    publicNetworkAccess: 'Enabled'
    internal: false
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
    appLogsConfiguration: { destination: 'azure-monitor' }
    diagnosticSettings: [
      {
        name: 'giandoria-logs'
        workspaceResourceId: logs.outputs.resourceId
        logCategoriesAndGroups: [{ categoryGroup: 'allLogs' }]
        metricCategories: [{ category: 'AllMetrics' }]
      }
    ]
  }
}

output stateAccountName string = state.outputs.name
output controlPrincipalId string = identities[1].outputs.principalId
output environmentName string = environment.outputs.name
output registryName string = registry.outputs.name
