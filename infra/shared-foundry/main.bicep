// Shared Foundry: one resource group and one Foundry account whose model deployments serve several projects.
// Deploy it with scripts/Deploy-SharedFoundry.ps1 (a subscription-scope deployment stack); see README.md.
targetScope = 'subscription'

metadata name = 'Shared Foundry'
metadata description = 'Resource group and Foundry account with model deployments shared by several projects.'

import { modelDeploymentType, foundryUserType, projectType } from 'types.bicep'

@description('Azure region. The reference tenant denies westeurope; see docs/18-tenant-governance.md.')
param location string

@description('Resource group name.')
@minLength(1)
@maxLength(90)
param resourceGroupName string = 'rg-shared-ai-${location}'

@description('Foundry account name and endpoint subdomain. The hash suffix makes it unique per subscription and region.')
@minLength(2)
@maxLength(64)
param accountName string = 'aif-shared-${location}-${take(uniqueString(subscription().id, location), 6)}'

@description('Model deployments. main.bicepparam reads them from model-plan.json.')
param modelDeployments modelDeploymentType[]

@description('Projects created under the account. Other repositories may add their own projects.')
param projects projectType[] = [
  {
    name: 'proj-shared-playground'
    displayName: 'Shared playground'
    description: 'Default project for trying the shared model deployments.'
  }
]

@description('Principals that receive the Foundry User role on the account.')
param foundryUsers foundryUserType[] = []

@description('Public IPv4 addresses or CIDR ranges allowed to call the endpoints. Empty allows all networks.')
param allowedIpRanges string[] = []

@description('Optional Log Analytics workspace resource ID for an own diagnostic setting.')
param logAnalyticsWorkspaceResourceId string = ''

@description('Send the anonymous AVM usage telemetry to Microsoft.')
param enableTelemetry bool = true

@description('Tags on every resource. There is no "project" tag on purpose: the account is shared.')
param tags object = {
  scope: 'shared'
  workload: 'ai-models'
  'managed-by': 'bicep'
}

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module foundry 'modules/foundry.bicep' = {
  name: 'shared-foundry'
  scope: rg
  params: {
    location: location
    name: accountName
    modelDeployments: modelDeployments
    projects: projects
    foundryUsers: foundryUsers
    allowedIpRanges: allowedIpRanges
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
    enableTelemetry: enableTelemetry
    tags: tags
  }
}

@description('Resource group of the account. scripts/Resolve-ModelPlan.ps1 reads it from the stack outputs.')
output resourceGroupName string = rg.name

@description('Foundry account name. scripts/Resolve-ModelPlan.ps1 reads it from the stack outputs.')
output foundryName string = foundry.outputs.name

@description('Foundry account resource ID.')
output foundryResourceId string = foundry.outputs.resourceId

@description('Default endpoint of the account.')
output endpoint string = foundry.outputs.endpoint

@description('All endpoints of the account, keyed by API name.')
output endpoints object = foundry.outputs.endpoints

@description('Projects with their managed identities and endpoints.')
output projects array = foundry.outputs.projects

@description('Model deployments as requested by the plan.')
output deployments array = foundry.outputs.deployments
