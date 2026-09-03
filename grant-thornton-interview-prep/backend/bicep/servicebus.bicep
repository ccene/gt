param location string
param namespaceName string
param queueName string = 'orders'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

resource serviceBusQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  name: queueName
  parent: serviceBusNamespace
  properties: {
    lockDuration: 'PT1M'
    maxSizeInMegabytes: 1024
    requiresSession: false
    defaultMessageTtl: 'P1D'
  }
}

output serviceBusNamespaceEndpoint string = serviceBusNamespace.properties.serviceBusEndpoint
output serviceBusConnectionString string = 'Endpoint=${serviceBusNamespace.properties.serviceBusEndpoint};SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=${listKeys(serviceBusNamespace.name, '2022-10-01-preview').primaryKey}'
