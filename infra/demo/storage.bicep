param name string
param location string
param tags { *: string }
@allowed(['Disabled', 'Enabled'])
param publicNetworkAccess string
param isStateAccount bool
param dataPrincipals {
  principalId: string
  principalType: 'User' | 'ServicePrincipal'
}[]

var roles = isStateAccount
  ? ['Storage Blob Data Contributor', 'Storage Table Data Contributor', 'Storage Queue Data Contributor']
  : ['Storage Blob Data Contributor']
var tables = [for tableName in ['runs', 'ledger', 'leases', 'agentmemory', 'budgets']: { name: tableName }]
var queues = [for queueName in ['lab-requests', 'universe-commands']: { name: queueName }]
var assignments = flatten(map(dataPrincipals, principal => map(roles, role => {
  roleDefinitionIdOrName: role
  principalId: principal.principalId
  principalType: principal.principalType
})))

module account 'br/public:avm/res/storage/storage-account:0.33.1' = {
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: false
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    accessTier: 'Hot'
    publicNetworkAccess: publicNetworkAccess
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'None'
      defaultAction: publicNetworkAccess == 'Enabled' ? 'Allow' : 'Deny'
    }
    blobServices: {
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: 7
      containerDeleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: 7
      isVersioningEnabled: true
      containers: [
        for containerName in (isStateAccount
          ? ['lab-state', 'snapshots', 'decisions', 'outbox', 'scenarios', 'genesis']
          : ['exports-demo']): {
          name: containerName
          publicAccess: 'None'
        }
      ]
    }
    tableServices: isStateAccount
      ? { tables: tables }
      : {}
    queueServices: isStateAccount
      ? { queues: queues }
      : {}
    roleAssignments: assignments
  }
}

output name string = account.outputs.name
