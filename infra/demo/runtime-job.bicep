param image string
param stateAccountName string
param registryName string
param environmentName string
param automationPrincipalId string
param foundryEndpoint string
param model string
param modelVersion string
param streamNamespace string
param streamHub string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: 'id-giandoria-runtime-demo'
}
resource environment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}
resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

module job 'br/public:avm/res/app/job:0.7.2' = {
  params: {
    name: 'job-giandoria-universe-demo'
    location: 'swedencentral'
    tags: { project: 'giandoria', env: 'demo', 'managed-by': 'bicep' }
    enableTelemetry: false
    environmentResourceId: environment.id
    workloadProfileName: 'Consumption'
    triggerType: 'Manual'
    manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    replicaRetryLimit: 0
    replicaTimeout: 90000
    managedIdentities: { userAssignedResourceIds: [identity.id] }
    registries: [{ server: registry.properties.loginServer, identity: identity.id }]
    containers: [{
      name: 'universe'
      image: image
      resources: { cpu: '0.5', memory: '1Gi' }
      env: [
        { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
        { name: 'GIANDORIA_STATE_ACCOUNT', value: stateAccountName }
        { name: 'GIANDORIA_FOUNDRY_ENDPOINT', value: foundryEndpoint }
        { name: 'GIANDORIA_MODEL', value: model }
        { name: 'GIANDORIA_MODEL_VERSION', value: modelVersion }
        { name: 'GIANDORIA_STREAM_NAMESPACE', value: streamNamespace }
        { name: 'GIANDORIA_STREAM_HUB', value: streamHub }
        { name: 'GIANDORIA_RUN_ID', value: 'business-demo-001' }
        { name: 'GIANDORIA_HOURS', value: '744' }
        { name: 'GIANDORIA_TARGET_TICK', value: '17544' }
        { name: 'GIANDORIA_MAX_MODEL_CALLS', value: '128' }
        { name: 'GIANDORIA_MAX_RESERVED_TOKENS', value: '2000000' }
      ]
    }]
    roleAssignments: [{
      roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', guid(subscription().id, 'giandoria-lab-control'))
      principalId: automationPrincipalId
      principalType: 'ServicePrincipal'
    }]
  }
}
output jobId string = job.outputs.resourceId
