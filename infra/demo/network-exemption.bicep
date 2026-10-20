@allowed(['storage', 'registry', 'foundry'])
param targetKind string
param targetName string
param policyAssignmentId string
@minLength(1)
@maxLength(3)
param policyDefinitionReferenceIds array
@maxLength(512)
param justification string
param retainedControls string

var waiverProperties = {
  displayName: 'Authenticated public endpoints for nonproduction experimentation'
  description: justification
  policyAssignmentId: policyAssignmentId
  policyDefinitionReferenceIds: policyDefinitionReferenceIds
  exemptionCategory: 'Waiver'
  assignmentScopeValidation: 'Default'
  metadata: {
    project: 'giandoria'
    environment: 'demo'
    rationaleDocument: 'docs/19-policy-exemption-experiment.md'
    retainedControls: retainedControls
    residualRisk: 'Public network reachability is accepted; private-network equivalence is not claimed'
    reviewTriggers: 'Confidential data; new consumers; production use; changed controls or tenant requirements'
    autoRenew: false
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = if (targetKind == 'storage') {
  name: targetName
}
resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = if (targetKind == 'registry') {
  name: targetName
}
resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (targetKind == 'foundry') {
  name: targetName
}

resource storageWaiver 'Microsoft.Authorization/policyExemptions@2022-07-01-preview' = if (targetKind == 'storage') {
  scope: storage
  name: 'giandoria-public-network'
  properties: waiverProperties
}
resource registryWaiver 'Microsoft.Authorization/policyExemptions@2022-07-01-preview' = if (targetKind == 'registry') {
  scope: registry
  name: 'giandoria-public-network'
  properties: waiverProperties
}
resource foundryWaiver 'Microsoft.Authorization/policyExemptions@2022-07-01-preview' = if (targetKind == 'foundry') {
  scope: foundry
  name: 'giandoria-public-network'
  properties: waiverProperties
}
