# Multi–Use-Case Backend (Lovable/Replit Style)

**Implemented.** Single backend serves all templates; project `template_type` gates feature access.

## Current state

### What works today

| Use case | ORM | Schemas | Routes | Notes |
|----------|-----|---------|--------|--------|
| **SaaS** | ✅ User, Project, Billing, Notification | ✅ | ✅ auth, users, projects, billing, notifications, analytics, ai, **saas (core)** | Full flow; saas core uses in-memory tenants (can be moved to DB). |
| **Blog** | ✅ Post, Category, Tag | ✅ | ✅ blog | List/create posts, categories, tags. |
| **Portfolio** | ✅ (uses Blog + User) | ✅ | ✅ blog, auth, users | Registry asks for "portfolio" router — **router does not exist** (see below). |

### What does **not** work yet

- **E-commerce**: No `Product`, `Order`, `Cart` (or similar) ORM; no schemas; no `app.services.ecommerce.routes` (loader points to it but the module does not exist).
- **CRM**: No Lead/Contact/Pipeline ORM/schemas; no `app.services.crm.routes`.
- **ERP**: No Inventory/HR/Finance ORM/schemas; no `app.services.erp.routes`.
- **Portfolio**: No `app.services.portfolio.routes` (only `app.services.saas.core.routes` exists).
- **Leads / Candidates**: Same — no ORM, no schemas, no route modules.

So: **ORM and schemas only fully “work” for SaaS (billing, projects, notifications), Blog, and shared auth/users.** For ecommerce, blogging-as-feature, CRM, ERP, etc., the backend is missing the corresponding models, schemas, and route modules.

---

## How the backend is wired

1. **One template per process**  
   `TEMPLATE_TYPE` in settings (env) is read at startup. Only that template’s `required_services` are loaded (see `app/templates/registry.py` and `app/templates/service_loader.py`).

2. **Router loading**  
   `ServiceLoader.SERVICE_MODULES` maps names like `"ecommerce"` to `("app.services.ecommerce.routes", "router")`. Those modules don’t exist for ecommerce, crm, erp, portfolio, leads, candidates — so `load_router` returns `None` and no router is mounted. The app still starts; those use cases simply have no API.

3. **Shared vs domain data**  
   - **Shared (all use cases):** User, auth, (optional) billing, notifications.  
   - **Domain-specific:** Blog (Post, Category, Tag), Billing (Subscription, Payment, Invoice), and in the future: Product/Order (ecommerce), Lead/Contact (crm), etc.

So: **Yes, FastAPI can support all those use cases.** The gap is not FastAPI itself but missing ORM models, schemas, and route modules for each domain, and the decision of “one backend for all” vs “one template per deployment.”

---

## Two ways to support “any use case” on one backend

### Option A: One backend, one template per deployment (current model, extended)

- Keep reading `TEMPLATE_TYPE` at startup and loading only that template’s services.
- Add the missing pieces **per use case** when you need them:
  - **E-commerce:** ORM (e.g. `Product`, `Order`, `OrderItem`, `Cart`), schemas, `app.services.ecommerce.routes` (and point `SERVICE_MODULES["ecommerce"]` to it, or to a new path under `app/services/saas/ecommerce/routes.py` and fix the loader).
  - **CRM:** ORM (e.g. `Lead`, `Contact`, `Pipeline`, `Deal`), schemas, `app.services.crm.routes`.
  - **ERP / Portfolio / Leads / Candidates:** same idea — ORM + schemas + routes, then register in registry + service_loader.
- **Pros:** Smallest change, clear separation, only the code for the chosen template is loaded.  
- **Cons:** To support “user picks ecommerce **or** blog” you either run multiple backends (one per template) or move to Option B.

### Option B: One backend, all use cases (Lovable/Replit style)

- **Single deployment**, one API serves all frontend templates (ecommerce, blog, crm, etc.).
- **Per-project (or per-tenant) type:**  
  Store in DB something like `Project.template_type` or `Tenant.app_type` (e.g. `saas | blog | ecommerce | crm | erp`).
- **Load all routers** (or all that you implement): don’t filter by `TEMPLATE_TYPE` at startup; mount ecommerce, blog, crm, etc. in one app.
- **Feature visibility / authorization:**  
  In each route (or in a dependency), resolve the current project/tenant and check `template_type` / `app_type`; return 404 or 403 for endpoints that don’t apply to that project (e.g. ecommerce routes when `app_type == "blog"`).
- **ORM / DB:**  
  One database, one set of migrations. Shared tables: User, Project (with `template_type`), Notification, etc. Domain tables: Post/Category/Tag (blog), Product/Order (ecommerce), Lead/Contact (crm). Unused tables for a given project stay empty.
- **Pros:** One backend URL, user can have multiple “apps” (projects) with different types.  
- **Cons:** More logic to “which routes/models apply to this project”; need to design tenant/project isolation and billing if multiple projects per user.

---

## Will ORM and schemas work?

- **Today:**  
  - **Yes** for: auth, users, projects, notifications, **blog** (Post, Category, Tag), **billing** (Subscription, Payment, Invoice).  
  - **No** for: ecommerce, crm, erp, portfolio, leads, candidates — no ORM/schemas/routes yet.
- **After you add them:**  
  - **Option A:** ORM and schemas work the same way as blog/billing: add `app/orm/ecommerce.py`, `app/schemas/ecommerce.py`, and routes that use them; ensure the ecommerce router is loaded when `TEMPLATE_TYPE=ecommerce`.  
  - **Option B:** Same ORM/schemas, but you add a layer “this project is ecommerce, so allow only ecommerce (and shared) resources” and optionally tenant/project scoping (e.g. `Project.id` or `Tenant.id` on Product/Order).

So: **ORM and schemas will work for any use case once you define the models and schemas and wire them into the template/registry and service loader** (and, for Option B, add project/tenant and template-type checks).

---

## Recommended next steps

1. **Fix router paths for template-specific services**  
   Either create the missing route modules (e.g. `app/services/ecommerce/routes.py`) or point `SERVICE_MODULES` to existing ones (e.g. under `app/services/saas/...`) so that when a template requires "ecommerce", a real router is loaded.

2. **Decide strategy:**  
   - **Option A:** Keep one-template-per-deploy; add ORM + schemas + routes only for the templates you want to support (e.g. ecommerce first).  
   - **Option B:** Move to “one backend, all use cases” with `Project.template_type` (or equivalent), load all routers, and add project/tenant and template-type checks.

3. **Implement one extra use case end-to-end**  
   Example: ecommerce — add `Product`, `Order`, `OrderItem` (and optionally `Cart`) in `app/orm/`, Pydantic schemas in `app/schemas/`, and `app/services/ecommerce/routes.py` (or under saas) using `get_db` and existing auth. Then you have a pattern to repeat for CRM, ERP, etc.

4. **Alembic**  
   After adding new ORM models, create and run migrations so all tables (shared + domain) exist in one DB; for Option B that’s the same DB for every use case.

If you tell me which option you prefer (A vs B) and which use case you want first (e.g. ecommerce), I can outline the exact files and changes (ORM, schemas, routes, registry, service_loader) step by step.
