param location string
param functionAppName string
param storageAccountName string
param serviceBusConnectionString string
param keyVaultName string

resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Web/serverfarms/AzureFunctionsFlexConsumptionPlan-${location}-1'
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage'; value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=core.windows.net;AccountKey=${listKeys(storageAccountName, '2023-01-01').keys[0].value}' }
        { name: 'FUNCTIONS_WORKER_RUNTIME'; value: 'node' }
        { name: 'FUNCTIONS_EXTENSION_VERSION'; value: '~4' }
        { name: 'SERVICE_BUS_CONNECTION_STRING'; value: serviceBusConnectionString }
        { name: 'KEY_VAULT_NAME'; value: keyVaultName }
      ]
    }
    httpsOnly: true
  }
}
