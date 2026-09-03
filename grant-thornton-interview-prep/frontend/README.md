# Day 2: Frontend & Integration
**Goal**: Build an Angular app that interacts with your Day 1 backend.

---
## 📌 Tasks
| # | Task | Time | Status |
|---|------|------|--------|
| 1 | Set up Angular project | 30m | ⬜ |
| 2 | Create `Order` model + `ApiService` | 1h | ⬜ |
| 3 | Build `OrderListComponent` | 1.5h | ⬜ |
| 4 | Build `OrderDetailComponent` + routing | 1.5h | ⬜ |
| 5 | Build `OrderFormComponent` | 2h | ⬜ |
| 6 | Add NgRx for state management | 2h | ⬜ |
| 7 | Add Azure AD authentication | 1h | ⬜ |
| 8 | Deploy to Azure Static Web Apps | 1h | ⬜ |

---
## 🛠️ Setup
1. Install dependencies:
   ```bash
   cd frontend/angular-app
   npm install
   ```

2. Start Angular app:
   ```bash
   ng serve
   ```
   Open [http://localhost:4200](http://localhost:4200)

---
## 📚 Key Concepts
- **Angular**: Components, services, modules, dependency injection, routing
- **RxJS**: Observables, operators (map, switchMap, catchError), subjects
- **State Management**: NgRx (actions, reducers, effects, selectors) vs. simple services
- **Forms**: Reactive forms, validation, form controls
- **Authentication**: Azure AD, JWT, guards, interceptors
