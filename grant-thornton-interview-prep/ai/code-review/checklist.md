# AI-Assisted Code Review Checklist

Use this checklist **with AI** to review your code before committing.

---

## ✅ General
- [ ] **Code compiles** without errors or warnings.
- [ ] **No hardcoded secrets** (use environment variables or Key Vault).
- [ ] **Consistent naming conventions** (e.g., `camelCase` for variables, `PascalCase` for classes).
- [ ] **No unused imports** or variables.
- [ ] **Proper error handling** (try-catch, error boundaries, etc.).
- [ ] **Comments** explain "why" not "what" (avoid obvious comments).

---

## ✅ Azure Functions
- [ ] **Triggers** are correctly configured in `function.json`.
- [ ] **Bindings** are used where possible (e.g., Service Bus, Event Grid).
- [ ] **Environment variables** are used for secrets (not hardcoded).
- [ ] **Logging** is meaningful (not just "error occurred").
- [ ] **Retry policies** are configured for transient errors.
- [ ] **Cold start optimization**: Minimize dependencies, use lightweight packages.

---
## ✅ Bicep
- [ ] **Parameters** are used for customizable values (names, locations, etc.).
- [ ] **Modules** are used to split large templates into reusable components.
- [ ] **Dependencies** between resources are correctly defined.
- [ ] **Outputs** are defined for values needed by other templates.
- [ ] **Secure defaults**: HTTPS only, private endpoints where possible.

---
## ✅ Angular
- [ ] **Components** follow single responsibility principle.
- [ ] **Services** are used for business logic and API calls.
- [ ] **RxJS** operators are used correctly (no memory leaks).
- [ ] **Unsubscribe** from observables in `ngOnDestroy`.
- [ ] **Change detection** is optimized (OnPush where possible).
- [ ] **Forms** use reactive forms with proper validation.
- [ ] **Accessibility**: ARIA labels, semantic HTML, keyboard navigation.

---
## ✅ Testing
- [ ] **Unit tests** cover all public methods and edge cases.
- [ ] **Mock dependencies** (HttpClient, services, etc.).
- [ ] **Test error cases** (API failures, invalid inputs, etc.).
- [ ] **Integration tests** verify component interactions.
- [ ] **E2E tests** cover critical user flows.

---
## ✅ Security
- [ ] **Input validation** on all user inputs (frontend + backend).
- [ ] **CORS** is configured correctly (restrict origins).
- [ ] **Authentication/Authorization** is implemented (Azure AD, JWT, etc.).
- [ ] **Secrets** are stored in Key Vault or environment variables.
- [ ] **Dependencies** are up-to-date (no known vulnerabilities).

---
## ✅ Performance
- [ ] **Lazy loading** is used for routes and modules.
- [ ] **Bundle size** is optimized (tree-shaking, code splitting).
- [ ] **Images** are optimized (compressed, correct formats).
- [ ] **Azure Functions** use appropriate plan (Consumption for sporadic, Premium for high load).
- [ ] **Caching** is implemented where possible (HTTP caching, CDN).

---
## 🤖 AI Review Prompts
For each section, ask AI:
- **"What are the top 3 issues in this code? [PASTE CODE]"**
- **"How can I improve the performance of this [function/component/template]?"**
- **"Are there any security vulnerabilities in this code?"**
- **"What best practices am I missing in this Bicep template?"**
