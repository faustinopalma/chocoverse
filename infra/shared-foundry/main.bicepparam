using 'main.bicep'

// The model list is generated. Run scripts/Resolve-ModelPlan.ps1, review the diff of model-plan.json, then deploy.
var plan = loadJsonContent('model-plan.json')

param location = plan.location
param modelDeployments = plan.deployments

// Tenant-specific values come from environment variables, so no ID is committed.
// scripts/common.ps1 loads them from the .env file at the repository root; see .env.example.
var userIds = split(readEnvironmentVariable('SHARED_FOUNDRY_USER_OBJECT_IDS', ''), ',')
var groupIds = split(readEnvironmentVariable('SHARED_FOUNDRY_GROUP_OBJECT_IDS', ''), ',')
var ipRanges = split(readEnvironmentVariable('SHARED_FOUNDRY_ALLOWED_IP_RANGES', ''), ',')

param foundryUsers = concat(
  map(filter(userIds, id => !empty(trim(id))), id => { principalId: trim(id), principalType: 'User' }),
  map(filter(groupIds, id => !empty(trim(id))), id => { principalId: trim(id), principalType: 'Group' })
)

param allowedIpRanges = map(filter(ipRanges, r => !empty(trim(r))), r => trim(r))

param logAnalyticsWorkspaceResourceId = readEnvironmentVariable('SHARED_FOUNDRY_LOG_ANALYTICS_WORKSPACE_ID', '')

param enableTelemetry = toLower(readEnvironmentVariable('SHARED_FOUNDRY_ENABLE_TELEMETRY', 'true')) != 'false'
