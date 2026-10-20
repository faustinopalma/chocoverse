targetScope = 'subscription'

param stateAccountName string
param capacityName string
param location string = 'swedencentral'
var tags = { project: 'giandoria', env: 'demo', 'managed-by': 'bicep' }

resource operatorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(subscription().id, 'giandoria-lab-control')
  properties: {
    roleName: 'Giandoria Demo Lab Control'
    description: 'Operate recorded demo capacity, schedules and runtime jobs; no deployment or role changes.'
    type: 'CustomRole'
    assignableScopes: [subscription().id]
    permissions: [{
      actions: [
        'Microsoft.Fabric/capacities/read'
        'Microsoft.Fabric/capacities/resume/action'
        'Microsoft.Fabric/capacities/suspend/action'
        'Microsoft.Automation/automationAccounts/read'
        'Microsoft.Automation/automationAccounts/jobs/read'
        'Microsoft.Automation/automationAccounts/schedules/read'
        'Microsoft.Automation/automationAccounts/schedules/write'
        'Microsoft.Automation/automationAccounts/jobSchedules/read'
        'Microsoft.Automation/automationAccounts/jobSchedules/write'
        'Microsoft.App/jobs/read'
        'Microsoft.App/jobs/start/action'
        'Microsoft.App/jobs/stop/action'
        'Microsoft.App/jobs/executions/read'
      ]
      notActions: []
      dataActions: []
      notDataActions: []
    }]
  }
}

module control 'automation-account.bicep' = {
  scope: resourceGroup('rg-giandoria-ops-demo')
  params: { location: location, tags: tags, operatorRoleId: operatorRole.id }
}

module stateAccess 'automation-state-access.bicep' = {
  scope: resourceGroup('rg-giandoria-core-demo')
  params: { stateAccountName: stateAccountName, principalId: control.outputs.principalId }
}

module capacityAccess 'automation-capacity-access.bicep' = {
  scope: resourceGroup('rg-giandoria-fabric-demo')
  params: {
    capacityName: capacityName
    principalId: control.outputs.principalId
    operatorRoleId: operatorRole.id
  }
}

output accountId string = control.outputs.accountId
output principalId string = control.outputs.principalId
