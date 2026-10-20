param location string
param tags { *: string }
param operatorRoleId string

module account 'br/public:avm/res/automation/automation-account:0.19.0' = {
  params: {
    name: 'aa-giandoria-demo'
    location: location
    tags: tags
    enableTelemetry: false
    managedIdentities: { systemAssigned: true }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    roleAssignments: []
  }
}

resource existing 'Microsoft.Automation/automationAccounts@2024-10-23' existing = {
  name: 'aa-giandoria-demo'
}
resource runtime 'Microsoft.Automation/automationAccounts/runtimeEnvironments@2024-10-23' = {
  parent: existing
  name: 'GiandoriaPowerShell'
  location: location
  properties: {
    runtime: { language: 'PowerShell', version: '7.4' }
    defaultPackages: { Az: '12.3.0' }
    description: 'Pinned lab lifecycle runtime.'
  }
  dependsOn: [account]
}
var lifecycleSources = [
  {
    name: 'Start-GiandoriaLab'
    help: loadTextContent('../../ops/automation/Start-GiandoriaLab.ps1')
  }
  {
    name: 'Extend-GiandoriaLab'
    help: loadTextContent('../../ops/automation/Extend-GiandoriaLab.ps1')
  }
  {
    name: 'Stop-GiandoriaLab'
    help: loadTextContent('../../ops/automation/Stop-GiandoriaLab.ps1')
  }
]
// The publisher and IaC derive descriptions from the same checked-in help synopsis.
resource lifecycle 'Microsoft.Automation/automationAccounts/runbooks@2024-10-23' = [for source in lifecycleSources: {
  parent: existing
  name: source.name
  location: location
  tags: tags
  properties: {
    runbookType: 'PowerShell'
    runtimeEnvironment: runtime.name
    logProgress: false
    logVerbose: true
    description: trim(replace(replace(split(split(source.help, '.SYNOPSIS')[1], '.DESCRIPTION')[0], '\r', ''), '\n', ' '))
  }
}]
resource permissions 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: existing
  name: guid(existing.id, 'control', operatorRoleId)
  properties: {
    principalId: account.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
    roleDefinitionId: operatorRoleId
  }
}
output accountId string = existing.id
output principalId string = account.outputs.systemAssignedMIPrincipalId!
