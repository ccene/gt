import { AzureFunction, Context } from '@azure/functions';
import { ServiceBusClient, ServiceBusMessage } from '@azure/service-bus';

interface Order {
  id: string;
  customerName: string;
  customerEmail: string;
  items: { productId: string; quantity: number; price: number }[];
}

const serviceBusTrigger: AzureFunction = async function (
  context: Context,
  message: ServiceBusMessage
): Promise<void> {
  context.log('Service Bus trigger: processOrder');

  try {
    // TODO: Parse order from message body
    const order: Order = JSON.parse(message.body.toString());

    // TODO: Process order (e.g., save to database, validate stock)
    context.log(`Processing order ${order.id} for ${order.customerName}`);

    // TODO: Emit Event Grid event
    // Hint: Use @azure/eventgrid package
    // const event = {
    //   eventTime: new Date().toISOString(),
    //   eventType: 'OrderProcessed',
    //   data: order,
    //   topic: 'Orders'
    // };
    // Send to Event Grid

    context.log(`Order ${order.id} processed successfully`);
  } catch (error: any) {
    context.log.error('Error processing order:', error);
    throw error; // Will trigger retry
  }
};

export default serviceBusTrigger;
