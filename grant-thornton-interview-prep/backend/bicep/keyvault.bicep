param location string
param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      name: 'standard'
      family: 'A'
    }
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: 'TO_REPLACE_WITH_YOUR_AZURE_AD_OBJECT_ID' // Replace in deployment
        permissions: {
          keys: ['all']
          secrets: ['all']
          certificates: ['all']
        }
      }
    ]
    enabledForDeployment: true
    enabledForTemplateDeployment: true
  }
}
