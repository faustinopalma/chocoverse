@allowed(['swedencentral'])
param location string = 'swedencentral'
param adminMember string
var capacityName = 'fcgiandoriademo${take(uniqueString(subscription().id, 'demo'), 4)}'

module capacity 'br/public:avm/res/fabric/capacity:0.1.2' = {
  params: {
    name: capacityName
    location: location
    skuName: 'F4'
    adminMembers: [adminMember]
    enableTelemetry: false
    tags: {
      project: 'giandoria'
      env: 'demo'
      'managed-by': 'bicep'
      'lab-managed': 'true'
      classification: 'synthetic'
    }
  }
}

output capacityName string = capacity.outputs.name
output capacityResourceId string = capacity.outputs.resourceId
