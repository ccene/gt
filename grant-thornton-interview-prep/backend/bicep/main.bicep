param location string = resourceGroup().location
param storageAccountName string = 'st${resourceGroup().name}${uniqueString(resourceGroup().id)}'
param serviceBusNamespaceName string = 'sb${resourceGroup().name}${uniqueString(resourceGroup().id)}'
param functionAppName string = 'func${resourceGroup().name}${uniqueString(resourceGroup().id)}'
param keyVaultName string = 'kv${resourceGroup().name}${uniqueString(resourceGroup().id)}'
param queueName string = 'orders'
param eventGridTopicName string = 'orderEvents'
param eventGridSubscriptionName string = 'orderProcessedSub'

// Storage Account for Function App
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
  }
}

// Service Bus Namespace + Queue
module serviceBus 'servicebus.bicep' = {
  name: 'deployServiceBus'
  params: {
    location: location
    namespaceName: serviceBusNamespaceName
    queueName: queueName
  }
}

// Event Grid Topic + Subscription
module eventGrid 'eventgrid.bicep' = {
  name: 'deployEventGrid'
  params: {
    location: location
    topicName: eventGridTopicName
    subscriptionName: eventGridSubscriptionName
    serviceBusEndpoint: serviceBus.outputs.serviceBusNamespaceEndpoint
  }
}

// Key Vault
module keyVault 'keyvault.bicep' = {
  name: 'deployKeyVault'
  params: {
    location: location
    keyVaultName: keyVaultName
  }
}

// Function App
module functionApp 'functionapp.bicep' = {
  name: 'deployFunctionApp'
  params: {
    location: location
    functionAppName: functionAppName
    storageAccountName: storageAccount.name
    serviceBusConnectionString: serviceBus.outputs.serviceBusConnectionString
    keyVaultName: keyVaultName
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output serviceBusNamespaceName string = serviceBusNamespaceName
output functionAppName string = functionAppName
output keyVaultName string = keyVaultName
