import { submitOrder } from '../../backend/functions/submitOrder/index';
import { Context, HttpRequest } from '@azure/functions';

// Mock Context and HttpRequest
const createMockContext = () => ({
  log: jest.fn(),
  res: {} as any,
  req: {} as any,
  bindings: {},
  done: jest.fn(),
});

const createMockRequest = (body: any): HttpRequest => ({
  body,
  headers: {},
  method: 'POST',
  params: {},
  query: {},
  url: '/api/submitOrder',
} as HttpRequest);

describe('submitOrder Function', () => {
  let context: Context;
  let mockRequest: HttpRequest;

  beforeEach(() => {
    context = createMockContext();
    process.env.SERVICE_BUS_CONNECTION_STRING = 'mock-connection-string';
  });

  afterEach(() => {
    jest.clearAllMocks();
    delete process.env.SERVICE_BUS_CONNECTION_STRING;
  });

  it('should return 400 for empty request body', async () => {
    mockRequest = createMockRequest(null);
    await submitOrder(context, mockRequest);
    expect(context.res.status).toBe(400);
    expect(context.res.body.error).toContain('Request body is required');
  });

  it('should return 400 for invalid order (missing fields)', async () => {
    mockRequest = createMockRequest({ id: '1' }); // Missing customerName and items
    await submitOrder(context, mockRequest);
    expect(context.res.status).toBe(400);
    expect(context.res.body.error).toContain('Invalid order');
  });

  it('should return 201 for valid order', async () => {
    const validOrder = {
      id: '1',
      customerName: 'Test Customer',
      customerEmail: 'test@example.com',
      items: [{ productId: 'p1', quantity: 2, price: 10 }]
    };
    mockRequest = createMockRequest(validOrder);

    // Mock @azure/service-bus
    const mockSendMessages = jest.fn().mockResolvedValue(undefined);
    const mockClose = jest.fn().mockResolvedValue(undefined);
    const mockSender = { sendMessages: mockSendMessages, close: mockClose };
    const mockClient = { createSender: jest.fn().mockReturnValue(mockSender) };
    jest.mock('@azure/service-bus', () => ({
      ServiceBusClient: jest.fn().mockImplementation(() => mockClient)
    }));

    await submitOrder(context, mockRequest);
    expect(context.res.status).toBe(201);
    expect(context.res.body.message).toContain('Order submitted successfully');
    expect(mockSendMessages).toHaveBeenCalled();
  });

  // TODO: Add more tests (Service Bus errors, Key Vault integration, etc.)
});
