param location string
param topicName string
param subscriptionName string
param serviceBusEndpoint string

resource eventGridTopic 'Microsoft.EventGrid/topics@2023-01-01' = {
  name: topicName
  location: location
  properties: {}
}

resource eventGridSubscription 'Microsoft.EventGrid/topics/providers/eventSubscriptions@2023-01-01' = {
  name: subscriptionName
  parent: eventGridTopic
  properties: {
    destination: {
      endpointType: 'ServiceBusQueue'
      properties: {
        serviceBusQueueEndpoint: serviceBusEndpoint
      }
    }
    filter: {
      includedEventTypes: ['OrderProcessed']
    }
  }
}
