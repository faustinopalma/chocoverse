// Shared user-defined types for the shared Foundry template.
// main.bicep, modules/foundry.bicep and main.bicepparam import them.

@export()
@description('One model deployment on the Foundry account. scripts/Resolve-ModelPlan.ps1 writes these into model-plan.json.')
type modelDeploymentType = {
  @description('Deployment name. The resolver uses the model name, so clients see which model they call.')
  @minLength(2)
  @maxLength(64)
  name: string

  @description('Model as listed in the regional model catalog (az cognitiveservices model list).')
  model: {
    @description('Model format, for example "OpenAI", "Microsoft" or "Black Forest Labs".')
    format: string

    @description('Model name, for example "gpt-6-luna".')
    name: string

    @description('Model version, for example "2026-09-22".')
    version: string
  }

  @description('Deployment type and size.')
  sku: {
    @description('Deployment type, for example "GlobalStandard". The tenant policy denies "ProvisionedManaged".')
    name: string

    @description('Capacity in quota units: 1,000 tokens per minute for chat models, requests per minute for image models.')
    @minValue(1)
    capacity: int
  }

  @description('Optional. Version upgrade policy. Only OpenAI-format models use it.')
  versionUpgradeOption: ('NoAutoUpgrade' | 'OnceCurrentVersionExpired' | 'OnceNewDefaultVersionAvailable')?

  @description('Optional. Content filter (RAI) policy name. Omit to use the default policy.')
  raiPolicyName: string?

  @description('Optional. Notes written by the resolver (family, quota, retirement). Not sent to Azure.')
  metadata: object?
}

@export()
@description('A principal that receives the Foundry User role on the account.')
type foundryUserType = {
  @description('Microsoft Entra object ID of the principal.')
  principalId: string

  @description('Kind of principal.')
  principalType: 'User' | 'Group' | 'ServicePrincipal'
}

@export()
@description('A Foundry project created under the shared account.')
type projectType = {
  @description('Project resource name.')
  @minLength(2)
  @maxLength(64)
  name: string

  @description('Optional. Name shown in the Foundry portal. Defaults to the resource name.')
  displayName: string?

  @description('Optional. Project description.')
  description: string?
}
