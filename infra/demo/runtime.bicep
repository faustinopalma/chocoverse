targetScope = 'subscription'
param image string
param stateAccountName string
param registryName string
param environmentName string
param automationPrincipalId string
param runtimePrincipalId string
param foundryGroup string
param foundryName string
param model string
param modelVersion string
param streamNamespace string
param streamHub string

resource inferenceRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(subscription().id, 'giandoria-demo-chat-inference')
  properties: {
    roleName: 'Giandoria Demo Chat Inference'
    description: 'Invoke existing shared chat deployments only; no model, agent or resource changes.'
    type: 'CustomRole'
    assignableScopes: [subscription().id]
    permissions: [{
      actions: []
      notActions: []
      dataActions: ['Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action']
      notDataActions: []
    }]
  }
}

module runtime 'runtime-job.bicep' = {
  scope: resourceGroup('rg-giandoria-core-demo')
  params: {
    image: image
    stateAccountName: stateAccountName
    registryName: registryName
    environmentName: environmentName
    automationPrincipalId: automationPrincipalId
    foundryEndpoint: 'https://${foundryName}.openai.azure.com'
    model: model
    modelVersion: modelVersion
    streamNamespace: streamNamespace
    streamHub: streamHub
  }
}

module inferenceAccess 'runtime-inference-access.bicep' = {
  scope: resourceGroup(foundryGroup)
  params: {
    foundryName: foundryName
    principalId: runtimePrincipalId
    roleId: inferenceRole.id
  }
}

output jobId string = runtime.outputs.jobId
