# VA Studio Backend Starter

Production-ready FastAPI backend template for building SaaS applications. Supports 10+ project types: e-commerce, portfolio, CRM, ERP, blog, and more.

This repo is embedded by **va_studio_ai_builder_backend** (Go, port 8743) to power user-created projects in VA Studio.

**React 18 • Vite 6 • Tailwind CSS • 20 Templates • MIT License**

### VA Studio Frontend Starter (companion)

20 production-ready, fully responsive React templates with dark mode, theme switching, and zero external API dependencies.

Open source collection of beautifully crafted UI templates for rapid prototyping and production apps. Built with React 18, Vite 6, Tailwind CSS, and shadcn/ui components.

For Quick Start, Templates, Features, Tech Stack, and Contributing guides, see the [VA Studio Frontend Starter README](https://github.com/valtunox/va_studio_frontend_starter#readme).

# Multi–Use-Case Backend (valtunox/valtunox studio Style)

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

### Option B: One backend, all use cases (valtunox/valtunox studio style)

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


## Role in VA Studio Architecture

```
  va_studio_ai_builder_frontend (Next.js :3000)
            |
            v
  va_studio_ai_builder_backend (Go/Gin :8743)
    |-- Orchestrates project lifecycle
    |-- Scaffolds from templates
    |-- Runs AI code modifications
    |-- Proxies to starter services
            |                          |
            v                          v
  va_studio_backend_starter        va_studio_frontend_starter
  (FastAPI :5112) <-- THIS REPO    (Vite+React :3008)
            |
            v
  PostgreSQL  /  Redis  /  Celery
```

### How It Fits

1. User creates a project in VA Studio (e.g., "e-commerce store")
2. The AI builder backend scaffolds a project using this starter as the base
3. AI modifies code based on user prompts (add features, change logic)
4. This starter runs as the project's backend API, serving the frontend starter
5. User deploys via Docker when ready

### Integration Points

| System | Connection |
|--------|------------|
| **va_studio_ai_builder_backend** | Orchestrator -- spins up, manages, and modifies this service |
| **va_studio_frontend_starter** | Paired frontend -- consumes this API at `http://localhost:5112` |
| **va_infinityai_ai** | Shares PostgreSQL database (`vacloudopsdb1`) and JWT `SECRET_KEY` for cross-platform auth |
| **PostgreSQL** | Shared database for users, or standalone per-project DB |
| **Redis** | Shared cache/session store |

## Features

- **Authentication & Authorization**
  - JWT-based authentication (HS256, shared secret for cross-platform tokens)
  - OAuth2 (Google, GitHub)
  - Role-based access control (USER, ADMIN, MODERATOR)
  - Password reset & email verification

- **Template Types** (set via `TEMPLATE_TYPE` env var)
  - SaaS -- Dashboard, analytics, team management
  - Portfolio -- Projects, skills, contact
  - E-commerce -- Products, cart, orders, Stripe checkout
  - Blog -- Posts, tags, categories, CMS
  - CRM -- Contacts, companies, deals, pipeline
  - ERP -- Inventory, procurement, orders, finance
  - Leads -- Lead capture, scoring, assignment
  - Candidates -- cloudsystem, applications, interviews
  - Social -- Profiles, feeds, messaging
  - Dashboard -- Analytics, metrics, charts

- **Core Modules**
  - User management with profiles and avatars
  - Project/workspace management
  - Billing & subscriptions (Stripe)
  - Notifications (in-app & email with outbox pattern)
  - Blog/CMS with slug-based URLs
  - Analytics & event tracking
  - AI agent framework (LangChain, OpenAI, Anthropic stubs)

- **Infrastructure**
  - Docker & Docker Compose (dev + prod configs)
  - PostgreSQL with async support (asyncpg, SQLAlchemy 2.0)
  - Redis for caching & sessions
  - Celery for background tasks + Flower monitoring
  - Alembic for database migrations
  - Kafka + RabbitMQ messaging (optional)
  - CI/CD pipeline (GitHub Actions)
  - Nginx reverse proxy configs

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker (optional)

### Installation

```bash
# Clone
git clone https://github.com/yourusername/va_studio_backend_starter.git
cd va_studio_backend_starter

# Virtual environment
python -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env with your settings

# Database
docker-compose up -d db redis
alembic upgrade head

# Run
make dev
# Or: uvicorn app.app:app --reload --port 5112
```

### Using Docker

```bash
docker-compose up -d
# API: http://localhost:5112
# Swagger: http://localhost:5112/docs
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login and get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Logout user |
| POST | `/api/v1/auth/forgot-password` | Request password reset |
| POST | `/api/v1/auth/reset-password` | Reset password |
| GET | `/api/v1/auth/me` | Get current user |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/` | List users (admin) |
| GET | `/api/v1/users/me` | Get profile |
| PATCH | `/api/v1/users/me` | Update profile |
| DELETE | `/api/v1/users/me` | Delete account |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/` | List user's projects |
| POST | `/api/v1/projects/` | Create project |
| GET | `/api/v1/projects/{id}` | Get project |
| PATCH | `/api/v1/projects/{id}` | Update project |
| DELETE | `/api/v1/projects/{id}` | Delete project |

### Billing
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/billing/plans` | List subscription plans |
| GET | `/api/v1/billing/subscription` | Get subscription |
| POST | `/api/v1/billing/checkout` | Create checkout session |
| POST | `/api/v1/billing/portal` | Open billing portal |

### Template-Specific Endpoints

Routes are loaded dynamically based on `TEMPLATE_TYPE`:

- **E-commerce**: `/api/v1/ecommerce/products`, `/api/v1/ecommerce/orders`, `/api/v1/ecommerce/cart`
- **CRM**: `/api/v1/crm/contacts`, `/api/v1/crm/companies`, `/api/v1/crm/deals`
- **ERP**: `/api/v1/erp/inventory`, `/api/v1/erp/procurement`, `/api/v1/erp/orders`
- **Blog**: `/api/v1/blog/posts`, `/api/v1/blog/categories`
- **Leads**: `/api/v1/leads/`
- **Candidates**: `/api/v1/candidates/`

## Project Structure

```
va_studio_backend_starter/
  app/
    app.py                     # FastAPI entry point (public-first architecture)
    auth/                      # JWT auth, OAuth, RBAC
    core/                      # Settings, DB, Redis, Celery, middleware, logger
      alembic/                 # Database migrations
    orm/                       # SQLAlchemy models (user, project, billing, blog, crm, ecommerce)
    schemas/                   # Pydantic request/response schemas
    services/                  # Business logic by domain
      ai/                     # LangChain agent framework
      analytics/              # Event tracking & dashboards
      billing/                # Stripe integration
      blog/                   # CMS
      chat/                   # Real-time messaging
      crm/                    # Customer relationship management
      ecommerce/              # Products, orders, cart
      email/                  # Async SMTP with templates
      erp/                    # Enterprise resource planning
      health/                 # Health checks
      leads/                  # Lead management
      notifications/          # In-app + email notifications
      projects/               # Project CRUD
      users/                  # User management
    tests/
    utils/
  scripts/                     # Seed data, utilities
  nginx/                       # Reverse proxy config
  .github/workflows/           # CI/CD
  Dockerfile                   # Multi-stage build
  docker-compose.yml           # Development
  docker-compose.prod.yml      # Production
  Makefile                     # Dev commands
  alembic.ini
  requirements.txt
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPLATE_TYPE` | Active template (saas, portfolio, ecommerce, blog, crm, erp) | `saas` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://postgres:postgres@localhost:5432/vacloudopsdb1` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (shared with Go backend) | (required) |
| `CORS_ORIGINS` | Allowed origins | `http://localhost:3000,http://localhost:3008` |
| `HOST` / `PORT` | Server bind | `0.0.0.0` / `5112` |
| `DEBUG` | Debug mode | `true` |
| `STRIPE_SECRET_KEY` | Stripe API key | (optional) |

## Development

```bash
make dev              # Start dev server
make test             # Run tests
make test-cov         # Tests with coverage
make lint             # Linting
make format           # Code formatting
make celery-worker    # Start Celery worker
make celery-beat      # Start scheduler
make celery-flower    # Monitoring UI
```

### Database

```bash
alembic revision --autogenerate -m "description"   # Create migration
alembic upgrade head                                # Apply migrations
alembic downgrade -1                                # Rollback
python scripts/seed_data.py                         # Seed data
```

## Deployment

```bash
# Production Docker
docker-compose -f docker-compose.prod.yml up -d
```

Production checklist:
- `DEBUG=false`, `ENVIRONMENT=production`
- Strong `SECRET_KEY` (must match Go backend for cross-platform tokens)
- Proper database credentials
- SSL/TLS enabled
- Rate limiting configured

## AI Integration

AI agent stubs are included for LLM-powered features:

```bash
pip install langchain langchain-openai openai
```

Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`, then implement agents in `app/services/ai/agents/`.

## License

MIT License -- see [LICENSE](LICENSE).

---

Built with FastAPI, SQLAlchemy, and Celery. Part of the VA Studio platform by Valtunox.
