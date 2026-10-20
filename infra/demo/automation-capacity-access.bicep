param capacityName string
param principalId string
param operatorRoleId string
resource capacity 'Microsoft.Fabric/capacities@2023-11-01' existing = { name: capacityName }
resource access 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: capacity
  name: guid(capacity.id, principalId, operatorRoleId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: operatorRoleId
  }
}
