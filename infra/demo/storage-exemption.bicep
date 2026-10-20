param storageAccountName string
param policyAssignmentId string
resource account 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName
}

resource waiver 'Microsoft.Authorization/policyExemptions@2022-07-01-preview' = {
  name: 'giandoria-public-storage-poc'
  scope: account
  properties: {
    displayName: 'Giandoria synthetic-data authenticated public Storage'
    description: 'Synthetic-data lab: private networking adds standing cost and complexity disproportionate to data sensitivity. Public routing does not grant data access: Entra RBAC, HTTPS, TLS 1.2, disabled Shared Key and anonymous blobs remain enforced. Only network isolation is waived, not identity, integrity or usage controls. Reassess before confidential data, new consumers or weaker controls; no automatic recreation.'
    policyAssignmentId: policyAssignmentId
    policyDefinitionReferenceIds: ['StorageAccountPublicNetworkModify']
    exemptionCategory: 'Waiver'
    assignmentScopeValidation: 'Default'
    metadata: {
      project: 'giandoria'
      environment: 'demo'
      dataClassification: 'synthetic'
      rationaleDocument: 'docs/19-policy-exemption-experiment.md'
      retainedControls: 'Entra RBAC; HTTPS; TLS 1.2; no Shared Key; no anonymous blobs'
      residualRisk: 'Internet-reachable service endpoint; identity compromise and resource abuse remain relevant'
      reviewTriggers: 'Confidential data; new consumers; production use; changed controls or tenant requirements'
      autoRenew: false
    }
  }
}
