metadata name = 'Shared Foundry account'
metadata description = 'Foundry account (kind AIServices) with model deployments, projects and Foundry User role assignments.'

import { modelDeploymentType, foundryUserType, projectType } from '../types.bicep'

@description('Azure region of the account and its projects.')
param location string

@description('Account name. It is also the endpoint subdomain, so it must be globally unique.')
@minLength(2)
@maxLength(64)
param name string

@description('Model deployments to create on the account.')
param modelDeployments modelDeploymentType[]

@description('Projects to create under the account.')
param projects projectType[]

@description('Principals that receive the Foundry User role on the account.')
param foundryUsers foundryUserType[]

@description('Public IPv4 addresses or CIDR ranges allowed to call the endpoints. Empty allows all networks.')
param allowedIpRanges string[]

@description('Log Analytics workspace resource ID for an own diagnostic setting. Empty creates none.')
param logAnalyticsWorkspaceResourceId string

@description('Send the anonymous AVM usage telemetry to Microsoft.')
param enableTelemetry bool

@description('Tags for the account and its projects.')
param tags object

// Built-in role "Foundry User" (formerly "Azure AI User"): data actions Microsoft.CognitiveServices/*.
// Key access is disabled, so this role is what lets a person or an app call the models.
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

module account 'br/public:avm/res/cognitive-services/account:0.19.1' = {
  name: 'foundry-account'
  params: {
    name: name
    location: location
    kind: 'AIServices'
    sku: 'S0'
    customSubDomainName: name
    managedIdentities: {
      systemAssigned: true
    }
    allowProjectManagement: true
    // The tenant policy forces key access off. Setting it here keeps the template equal to what Azure stores.
    disableLocalAuth: true
    // The AVM module disables public access when this is null and networkAcls is empty, so pass it explicitly.
    publicNetworkAccess: 'Enabled'
    networkAcls: empty(allowedIpRanges)
      ? null
      : {
          defaultAction: 'Deny'
          bypass: 'AzureServices'
          ipRules: map(allowedIpRanges, ip => { value: ip })
        }
    // true would block agent tools and file or URL inputs that need outbound calls.
    restrictOutboundNetworkAccess: false
    deployments: [
      for d in modelDeployments: {
        name: d.name
        model: d.model
        sku: d.sku
        versionUpgradeOption: d.?versionUpgradeOption
        raiPolicyName: d.?raiPolicyName
      }
    ]
    roleAssignments: [
      for u in foundryUsers: {
        roleDefinitionIdOrName: foundryUserRoleId
        principalId: u.principalId
        principalType: u.principalType
      }
    ]
    diagnosticSettings: empty(logAnalyticsWorkspaceResourceId)
      ? []
      : [
          {
            workspaceResourceId: logAnalyticsWorkspaceResourceId
          }
        ]
    enableTelemetry: enableTelemetry
    tags: tags
  }
}

resource accountRef 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: name
}

@batchSize(1)
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = [
  for p in projects: {
    parent: accountRef
    name: p.name
    location: location
    identity: {
      type: 'SystemAssigned'
    }
    properties: {
      displayName: p.?displayName ?? p.name
      description: p.?description ?? ''
    }
    tags: tags
    dependsOn: [
      account
    ]
  }
]

// The portal gives each project identity the Foundry User role on the account; a template must do it itself.
// Agents and evaluations of the project call the models with this identity.
resource projectFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (p, i) in projects: {
    name: guid(accountRef.id, p.name, foundryUserRoleId)
    scope: accountRef
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
      principalId: project[i].identity.principalId
      principalType: 'ServicePrincipal'
      description: 'Foundry User for the managed identity of project ${p.name}.'
    }
  }
]

@description('Account name.')
output name string = account.outputs.name

@description('Account resource ID.')
output resourceId string = account.outputs.resourceId

@description('Default endpoint of the account.')
output endpoint string = account.outputs.endpoint

@description('All endpoints of the account, keyed by API name.')
output endpoints object = account.outputs.endpoints

@description('Object ID of the account system-assigned identity.')
output principalId string = account.outputs.?systemAssignedMIPrincipalId ?? ''

@description('Projects with their managed identities and endpoints.')
output projects array = [
  for (p, i) in projects: {
    name: project[i].name
    resourceId: project[i].id
    principalId: project[i].identity.principalId
    endpoint: 'https://${name}.services.ai.azure.com/api/projects/${p.name}'
  }
]

@description('Model deployments as requested by the plan.')
output deployments array = [
  for d in modelDeployments: {
    name: d.name
    model: d.model.name
    version: d.model.version
    sku: d.sku.name
    capacity: d.sku.capacity
  }
]
