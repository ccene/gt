# Day 1: Azure Backend & Infrastructure
**Goal**: Build a serverless order processing system and deploy it to Azure.

---

## 📌 Tasks
| # | Task | Time | Status |
|---|------|------|--------|
| 1 | Set up Azure CLI + create resource group | 1h | ⬜ |
| 2 | Implement `submitOrder` Function (HTTP trigger) | 1h | ⬜ |
| 3 | Implement `processOrder` Function (Service Bus trigger) | 1h | ⬜ |
| 4 | Implement `notifyOrderProcessed` Function (Event Grid trigger) | 1h | ⬜ |
| 5 | Secure secrets in Key Vault | 1h | ⬜ |
| 6 | Write Bicep templates for all resources | 2h | ⬜ |
| 7 | Deploy to Azure using Bicep | 1h | ⬜ |
| 8 | Create Azure DevOps CI/CD pipeline | 2h | ⬜ |

---
## 🛠️ Setup
1. Install dependencies for all functions:
   ```bash
   cd backend/functions/submitOrder
   npm install @azure/functions @azure/service-bus @azure/identity
   cd ../processOrder
   npm install @azure/functions @azure/service-bus @azure/identity
   cd ../notifyOrderProcessed
   npm install @azure/functions @azure/eventgrid @azure/identity
   ```

2. Start Azure Functions locally:
   ```bash
   cd backend/functions
   func start
   ```

---
## 📚 Key Concepts
- **Azure Functions**: Triggers (HTTP, Service Bus, Event Grid), bindings, scaling
- **Service Bus**: Queues vs. Topics, sessions, dead-letter queues
- **Event Grid**: Publishers/subscribers, event filtering, retries
- **Key Vault**: Secrets, Keys, Certificates, access policies
- **Bicep**: Modules, parameters, outputs, resource dependencies
- **Azure DevOps**: Pipelines, stages, jobs, tasks, variables
