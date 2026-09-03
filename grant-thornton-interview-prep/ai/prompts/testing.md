# AI Testing Prompts
Use these to generate test cases for your code.

---

## Azure Functions
- **"Generate 5 Jest test cases for an Azure Function that validates and processes orders. Include edge cases like empty body, missing fields, and invalid data types."**
- **"Write a test for an Azure Function that verifies it sends a message to Service Bus. Mock the Service Bus client."**
- **"Write a test that verifies an Event Grid-triggered Azure Function correctly parses and processes an order event."**

## Angular
- **"Generate Jasmine test cases for an Angular component that displays a list of orders. Include tests for rendering, loading states, error handling, and empty lists."**
- **"Write tests for an Angular service that fetches orders from an API. Mock HttpClient and test success, error, and empty response cases."**
- **"Generate tests for an Angular reactive form. Include tests for validation, form submission, and error states."**

## Integration
- **"Write an end-to-end test that verifies the full flow: submit order via Angular app -> Azure Function -> Service Bus -> Process Order Function -> Event Grid -> Notification Function."**
