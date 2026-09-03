import { AzureFunction, Context, HttpRequest } from '@azure/functions';

interface Order {
  id: string;
  customerName: string;
  customerEmail: string;
  items: { productId: string; quantity: number; price: number }[];
}

const httpTrigger: AzureFunction = async function (
  context: Context,
  req: HttpRequest
): Promise<void> {
  context.log('HTTP trigger: submitOrder');

  try {
    // TODO: Validate request body
    if (!req.body) {
      throw new Error('Request body is required');
    }

    const order: Order = req.body;

    // TODO: Validate order fields
    if (!order.id || !order.customerName || !order.items || order.items.length === 0) {
      throw new Error('Invalid order: missing required fields');
    }

    // TODO: Get Service Bus connection string from Key Vault (use environment variable for now)
    const connectionString = process.env.SERVICE_BUS_CONNECTION_STRING;
    if (!connectionString) {
      throw new Error('Service Bus connection string not configured');
    }

    // TODO: Send order to Service Bus queue
    // Hint: Use @azure/service-bus package
    // const client = new ServiceBusClient(connectionString);
    // const sender = client.createSender('orders');
    // await sender.sendMessages({ body: order });
    // await client.close();

    context.res = {
      status: 201,
      body: { message: 'Order submitted successfully', orderId: order.id },
    };
  } catch (error: any) {
    context.log.error('Error submitting order:', error);
    context.res = {
      status: 400,
      body: { error: error.message },
    };
  }
};

export default httpTrigger;
