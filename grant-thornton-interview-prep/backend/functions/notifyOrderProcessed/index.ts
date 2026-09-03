import { AzureFunction, Context } from '@azure/functions';

interface Order {
  id: string;
  customerName: string;
  customerEmail: string;
}

const eventGridTrigger: AzureFunction = async function (
  context: Context,
  event: any
): Promise<void> {
  context.log('Event Grid trigger: notifyOrderProcessed');

  try {
    // TODO: Parse event
    const order: Order = event.data;
    context.log(`Order processed: ${order.id} for ${order.customerName}`);

    // TODO: Send notification (e.g., email, SMS)
    // Hint: Use @azure/communication-email or a mock
    context.log(`Notification sent for order ${order.id}`);
  } catch (error: any) {
    context.log.error('Error in notification:', error);
    throw error;
  }
};

export default eventGridTrigger;
