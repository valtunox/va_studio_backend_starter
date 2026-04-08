<div align="center">

# VA Studio Backend Starter

### The open-source FastAPI backend that powers AI-generated applications

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Dockerfile)

<br />

**Production-ready** multi-use-case backend template supporting **10+ project types** — SaaS, e-commerce, CRM, ERP, blog, portfolio, and more — all from a single codebase.

<br />

[Quick Start](#-quick-start) · [API Reference](#-api-endpoints) · [Architecture](#-architecture) · [Contributing](#-contributing)

<br />

---

</div>

<br />

## Why VA Studio Backend Starter?

Most backend starters give you auth and a TODO app. This one gives you a **production SaaS platform** out of the box.

- **Multi-use-case by design** — One backend serves e-commerce, CRM, blog, ERP, and more. Each project declares its `template_type`, and the backend gates feature access per endpoint.
- **AI-first architecture** — Built to be scaffolded, modified, and extended by AI. Part of the VA Studio platform where users build full-stack apps through natural language.
- **Battle-tested stack** — FastAPI + SQLAlchemy 2.0 async + PostgreSQL + Redis + Celery. No experimental libraries, no lock-in.
- **Pairs with 20 frontend templates** — Works out of the box with [VA Studio Frontend Starter](https://github.com/valtunox/va_studio_frontend_starter) (React 18, Vite, Tailwind CSS, shadcn/ui).

<br />

## What's Inside

```
Auth & Users          Billing & Payments       Blog / CMS              AI Agents
 JWT (HS256)           Stripe integration        Posts & categories      LangChain stubs
 OAuth2 (Google/GH)    Subscription plans        Tags & slug URLs        OpenAI / Anthropic
 RBAC (roles)          Webhooks                  SEO metadata            Agent framework
 Password reset        Checkout sessions         Featured posts          Chat service

Notifications         Analytics                 E-commerce              Infrastructure
 In-app + email        Event tracking            Products & orders       Docker & Compose
 Outbox pattern        Custom metrics            Project-scoped          Celery + Flower
 Jinja2 templates      Summary dashboards        Cart (planned)          Alembic migrations
```

<br />

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| **Framework** | FastAPI 0.109+ with async/await throughout |
| **ORM** | SQLAlchemy 2.0 with mapped columns + async sessions |
| **Database** | PostgreSQL 16+ via asyncpg |
| **Cache** | Redis 7+ for sessions, rate limiting, and Celery broker |
| **Auth** | JWT (HS256) + OAuth2 + Argon2/bcrypt password hashing |
| **Tasks** | Celery 5.3+ with Redis broker + Flower monitoring |
| **Payments** | Stripe SDK with webhook verification |
| **Email** | Async SMTP (aiosmtplib) with Jinja2 templates |
| **Validation** | Pydantic 2.5+ for all request/response schemas |
| **Migrations** | Alembic with autogenerate support |
| **Monitoring** | Prometheus metrics, structured JSON logging |
| **CI/CD** | GitHub Actions workflows included |
| **Deployment** | Docker multi-stage builds + Nginx configs |

<br />

## Quick Start

### Prerequisites

| Requirement | Version |
|:------------|:--------|
| Python | 3.12+ |
| PostgreSQL | 16+ |
| Redis | 7+ |
| Docker | Optional (recommended) |

### Option 1: Docker (recommended)

```bash
git clone https://github.com/valtunox/va_studio_backend_starter.git
cd va_studio_backend_starter

# Copy environment config
cp .env.example .env

# Start everything
docker-compose up -d
```

That's it. Your API is live:

| Service | URL |
|:--------|:----|
| API | http://localhost:5112 |
| Swagger Docs | http://localhost:5112/docs |
| ReDoc | http://localhost:5112/redoc |
| Health Check | http://localhost:5112/health |

### Option 2: Local Development

```bash
git clone https://github.com/valtunox/va_studio_backend_starter.git
cd va_studio_backend_starter

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database and Redis connection

# Start PostgreSQL and Redis (if not running)
docker-compose up -d db redis

# Run database migrations
alembic upgrade head

# Seed sample data (optional)
python scripts/seed_data.py

# Start the server
make dev
# Or: uvicorn app.app:app --reload --port 5112
```

### Verify Installation

```bash
# Health check
curl http://localhost:5112/health

# Register a user
curl -X POST http://localhost:5112/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "hello@example.com", "password": "SecurePass123!", "full_name": "Jane Doe"}'

# Login
curl -X POST http://localhost:5112/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "hello@example.com", "password": "SecurePass123!"}'
```

<br />

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/v1/auth/register` | Public | Register new user |
| `POST` | `/api/v1/auth/login` | Public | Login, returns access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Public | Refresh access token |
| `POST` | `/api/v1/auth/logout` | JWT | Logout user |
| `POST` | `/api/v1/auth/forgot-password` | Public | Request password reset |
| `POST` | `/api/v1/auth/reset-password` | Public | Reset password with token |
| `GET` | `/api/v1/auth/me` | JWT | Get current user |
| `GET` | `/api/v1/auth/google` | Public | OAuth2 Google login |
| `GET` | `/api/v1/auth/github` | Public | OAuth2 GitHub login |

### Users

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/users/` | Admin | List all users |
| `GET` | `/api/v1/users/me` | JWT | Get profile |
| `PATCH` | `/api/v1/users/me` | JWT | Update profile |
| `POST` | `/api/v1/users/me/change-password` | JWT | Change password |
| `DELETE` | `/api/v1/users/me` | JWT | Delete account |

### Projects

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/projects/` | JWT | List user's projects |
| `GET` | `/api/v1/projects/public` | Public | List public projects |
| `POST` | `/api/v1/projects/` | JWT | Create project |
| `GET` | `/api/v1/projects/{id}` | JWT | Get project by ID |
| `PATCH` | `/api/v1/projects/{id}` | JWT | Update project |
| `DELETE` | `/api/v1/projects/{id}` | JWT | Delete project |

### Billing & Subscriptions

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/billing/plans` | JWT | List subscription plans |
| `GET` | `/api/v1/billing/subscription` | JWT | Get current subscription |
| `POST` | `/api/v1/billing/checkout` | JWT | Create Stripe checkout session |
| `POST` | `/api/v1/billing/portal` | JWT | Open Stripe billing portal |
| `POST` | `/api/v1/billing/webhooks` | Stripe | Stripe webhook handler |

### Blog / CMS

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/blog/posts` | Optional | List posts (published only for anonymous) |
| `POST` | `/api/v1/blog/posts` | JWT | Create post |
| `GET` | `/api/v1/blog/posts/{id}` | Optional | Get post by ID |
| `GET` | `/api/v1/blog/posts/slug/{slug}` | Optional | Get post by slug |
| `PATCH` | `/api/v1/blog/posts/{id}` | JWT | Update post |
| `DELETE` | `/api/v1/blog/posts/{id}` | JWT | Delete post |
| `GET` | `/api/v1/blog/categories` | Public | List categories |
| `POST` | `/api/v1/blog/categories` | JWT | Create category |
| `GET` | `/api/v1/blog/tags` | Public | List tags |
| `POST` | `/api/v1/blog/tags` | JWT | Create tag |

### E-commerce (project-scoped)

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/ecommerce/projects/{pid}/products` | JWT | List products |
| `POST` | `/api/v1/ecommerce/projects/{pid}/products` | JWT | Create product |
| `GET` | `/api/v1/ecommerce/projects/{pid}/orders` | JWT | List orders |
| `POST` | `/api/v1/ecommerce/projects/{pid}/orders` | JWT | Create order |

### Notifications

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/notifications/` | JWT | List notifications |
| `PATCH` | `/api/v1/notifications/{id}` | JWT | Mark as read |
| `DELETE` | `/api/v1/notifications/{id}` | JWT | Delete notification |

### Analytics

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `POST` | `/api/v1/analytics/track` | JWT | Track custom event |
| `GET` | `/api/v1/analytics/events` | JWT | Get events |
| `GET` | `/api/v1/analytics/summary` | JWT | Analytics summary |

### Chat (public, rate-limited)

| Method | Endpoint | Auth | Description |
|:-------|:---------|:-----|:------------|
| `GET` | `/api/v1/chat/session` | Public | Create/get chat session |
| `POST` | `/api/v1/chat/message` | Public | Send message |
| `POST` | `/api/v1/chat/template-request` | Public | Template customization |

### System

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET` | `/` | API info |
| `GET` | `/health` | Health check with dependency status |
| `GET` | `/api/v1/templates/` | List available templates |

> **Full interactive docs** available at `/docs` (Swagger) and `/redoc` (ReDoc) when the server is running.

<br />

## Architecture

### Multi-Use-Case Backend

This isn't a single-purpose API. It's a **multi-use-case backend** where one deployment serves multiple project types:

```
                    ┌─────────────────────────────────┐
                    │     VA Studio Backend Starter    │
                    │         (FastAPI :5112)          │
                    └──────────────┬──────────────────┘
                                   │
            ┌──────────┬───────────┼───────────┬──────────┐
            │          │           │           │          │
         ┌──▼──┐   ┌──▼──┐   ┌───▼──┐   ┌───▼──┐   ┌──▼──┐
         │ SaaS│   │Blog │   │E-com │   │ CRM  │   │ ERP │
         └──┬──┘   └──┬──┘   └──┬───┘   └──┬───┘   └──┬──┘
            │          │         │          │          │
            └──────────┴────┬────┴──────────┴──────────┘
                            │
              ┌─────────────▼─────────────┐
              │    Shared Infrastructure  │
              │  Auth · Users · Billing   │
              │  Notifications · Analytics│
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  PostgreSQL · Redis · Celery│
              └───────────────────────────┘
```

**How it works:**
1. Each project has a `template_type` (saas, blog, ecommerce, crm, erp, etc.)
2. All routers are loaded at startup
3. Endpoints check `project.template_type` to gate feature access
4. Shared modules (auth, users, billing, notifications) work across all types
5. Domain tables for unused types simply stay empty

### Role in the VA Studio Platform

```
  VA Studio Frontend (Next.js :3000)
            │
            ▼
  VA Studio AI Builder Backend (Go/Gin :8743)
    ├── Orchestrates project lifecycle
    ├── Scaffolds from templates
    ├── AI-powered code modifications
    ├── Proxies to starter services
            │                          │
            ▼                          ▼
  Backend Starter ◄── THIS REPO   Frontend Starter
  (FastAPI :5112)                 (Vite+React :3008)
            │
            ▼
  PostgreSQL  ·  Redis  ·  Celery
```

**Integration flow:**
1. User creates a project in VA Studio (e.g., "e-commerce store")
2. The Go backend scaffolds using this starter as the base
3. AI modifies code based on user prompts
4. This starter runs as the project's live backend API
5. User deploys via Docker when ready

<br />

## Project Structure

```
va_studio_backend_starter/
│
├── app/
│   ├── app.py                    # FastAPI entry point
│   │
│   ├── auth/                     # Authentication & authorization
│   │   ├── routes.py             #   Auth endpoints (register, login, refresh, reset)
│   │   ├── auth.py               #   Core auth logic
│   │   ├── dependencies.py       #   JWT dependency injection
│   │   ├── oauth.py              #   OAuth2 (Google, GitHub)
│   │   └── project_dependencies.py  # Project/template authorization
│   │
│   ├── core/                     # Core infrastructure
│   │   ├── settings.py           #   Pydantic settings (all env vars)
│   │   ├── db.py                 #   Async database engine & sessions
│   │   ├── redis.py              #   Redis client wrapper
│   │   ├── security.py           #   JWT tokens, password hashing
│   │   ├── middleware.py         #   Logging, rate-limiting, security headers
│   │   ├── celery_app.py         #   Celery configuration
│   │   ├── cors.py               #   CORS configuration
│   │   ├── logger.py             #   Structured logging
│   │   ├── errors.py             #   Custom exceptions
│   │   └── alembic/              #   Database migrations
│   │
│   ├── orm/                      # SQLAlchemy models
│   │   ├── base.py               #   Base + TimestampMixin + SoftDeleteMixin
│   │   ├── user.py               #   User model (auth, profile, roles)
│   │   ├── project.py            #   Project model (multi-use-case)
│   │   ├── billing.py            #   Subscription, Payment, Invoice
│   │   ├── blog.py               #   Post, Category, Tag
│   │   ├── ecommerce.py          #   Product, Order, OrderItem
│   │   ├── notification.py       #   Notification model
│   │   └── crm.py                #   CRM models (extensible)
│   │
│   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── common.py             #   PaginatedResponse, TokenResponse
│   │   ├── user.py               #   UserCreate, UserResponse
│   │   ├── project.py            #   ProjectCreate, ProjectResponse
│   │   ├── billing.py            #   Subscription schemas
│   │   ├── blog.py               #   Post, Category, Tag schemas
│   │   ├── ecommerce.py          #   Product, Order schemas
│   │   └── notification.py       #   Notification schemas
│   │
│   ├── services/                 # Business logic by domain
│   │   ├── users/                #   User CRUD & profiles
│   │   ├── projects/             #   Project management
│   │   ├── billing/              #   Stripe integration & webhooks
│   │   ├── blog/                 #   CMS (posts, categories, tags)
│   │   ├── ecommerce/            #   Products & orders
│   │   ├── chat/                 #   Public chat (Redis-backed)
│   │   ├── notifications/        #   In-app + email (outbox pattern)
│   │   ├── analytics/            #   Event tracking & metrics
│   │   ├── email/                #   Async SMTP + Jinja2 templates
│   │   ├── ai/                   #   LangChain agent framework
│   │   ├── health/               #   Health check endpoints
│   │   ├── templates/            #   Template registry & service loader
│   │   ├── celery/               #   Background task definitions
│   │   ├── redis/                #   Cache management
│   │   ├── saas/                 #   SaaS core (tenants, subscriptions)
│   │   ├── crm/                  #   CRM (extensible)
│   │   ├── erp/                  #   ERP (extensible)
│   │   └── leads/                #   Lead management
│   │
│   ├── templates/                # Template config & registry
│   │   ├── registry.py           #   Template type definitions
│   │   ├── service_loader.py     #   Dynamic service loading
│   │   └── emails/               #   Email templates (Jinja2)
│   │
│   ├── utils/                    # Helpers & pagination
│   └── tests/                    # Unit, integration, e2e tests
│
├── scripts/
│   ├── seed_data.py              # Sample data seeder
│   └── init_db.py                # Database initialization
│
├── nginx/                        # Reverse proxy configs
├── docs/                         # Architecture documentation
├── .github/workflows/            # CI/CD pipelines
│
├── Dockerfile                    # Multi-stage production build
├── docker-compose.yml            # Development environment
├── Makefile                      # Developer commands
├── alembic.ini                   # Migration configuration
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── LICENSE                       # MIT License
```

<br />

## Configuration

### Required Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `SECRET_KEY` | JWT signing key — **must be strong in production** | *(required)* |
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/vacloudopsdb2` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

### Application Settings

| Variable | Description | Default |
|:---------|:------------|:--------|
| `APP_NAME` | Application name | `VA Studio Backend` |
| `ENVIRONMENT` | `development` / `staging` / `production` | `development` |
| `DEBUG` | Enable debug mode | `false` |
| `HOST` / `PORT` | Server bind address | `0.0.0.0` / `5112` |
| `TEMPLATE_TYPE` | Active template type | `saas` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,http://localhost:3008` |

### Authentication

| Variable | Description | Default |
|:---------|:------------|:--------|
| `JWT_ALGORITHM` | Token signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth2 | *(optional)* |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth2 | *(optional)* |

### Services

| Variable | Description | Default |
|:---------|:------------|:--------|
| `STRIPE_SECRET_KEY` | Stripe API key | *(optional)* |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | *(optional)* |
| `SMTP_HOST` / `SMTP_PORT` | Email server | `smtp.gmail.com` / `587` |
| `SMTP_USER` / `SMTP_PASSWORD` | Email credentials | *(optional)* |
| `CELERY_BROKER_URL` | Celery broker | `redis://localhost:6379/1` |
| `OPENAI_API_KEY` | OpenAI for AI agents | *(optional)* |
| `ANTHROPIC_API_KEY` | Anthropic for AI agents | *(optional)* |

> See `app/core/settings.py` for the complete list of configuration options.

<br />

## Development

### Common Commands

```bash
# Server
make dev                    # Start dev server with hot reload
make run                    # Start production server

# Database
alembic revision --autogenerate -m "add feature"   # Create migration
alembic upgrade head                                # Apply all migrations
alembic downgrade -1                                # Rollback last migration
python scripts/seed_data.py                         # Seed sample data
make db-reset                                       # Reset database

# Background Tasks
make celery-worker          # Start Celery worker
make celery-beat            # Start task scheduler
make celery-flower          # Monitoring UI at :5555

# Testing
make test                   # Run all tests
make test-unit              # Unit tests only
make test-int               # Integration tests only
make test-cov               # Tests with coverage report

# Code Quality
make lint                   # Run flake8 + mypy
make format                 # Auto-format with Black + isort
make type-check             # Type checking with mypy

# Docker
make docker-build           # Build image
make docker-up              # Start all services
make docker-down            # Stop all services
make docker-logs            # Tail logs
make docker-shell           # Shell into app container
```

### Adding a New Domain Module

To add support for a new use case (e.g., inventory management):

1. **Define the ORM model** in `app/orm/inventory.py`
2. **Create Pydantic schemas** in `app/schemas/inventory.py`
3. **Build the service** in `app/services/inventory/service.py`
4. **Add routes** in `app/services/inventory/routes.py`
5. **Register** in `app/templates/registry.py` and `app/templates/service_loader.py`
6. **Generate migration**: `alembic revision --autogenerate -m "add inventory"`
7. **Apply**: `alembic upgrade head`

The existing blog and billing modules serve as reference implementations.

<br />

## Deployment

### Docker (Production)

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose ps
docker-compose logs -f

# Database shell
docker-compose exec db psql -U postgres -d vacloudopsdb2
```

### Production Checklist

- [ ] `DEBUG=false` and `ENVIRONMENT=production`
- [ ] Strong random `SECRET_KEY` (32+ bytes)
- [ ] Secure database credentials (not defaults)
- [ ] SSL/TLS termination (via Nginx or load balancer)
- [ ] Rate limiting enabled and tested
- [ ] CORS origins restricted to your domains
- [ ] Stripe webhook secret configured
- [ ] SMTP credentials configured and tested
- [ ] Redis connection secured (password, TLS)
- [ ] Celery workers and beat scheduler running
- [ ] Log aggregation configured
- [ ] Database backup schedule in place
- [ ] Health check monitoring active

<br />

## Implementation Status

Transparent about what's production-ready and what's scaffolded for extension:

| Module | ORM | Schemas | Routes | Service | Status |
|:-------|:---:|:-------:|:------:|:-------:|:------:|
| **Auth & Users** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Projects** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Billing (Stripe)** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Blog / CMS** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Notifications** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Analytics** | Yes | Yes | Yes | Yes | **Production-ready** |
| **Chat** | -- | Yes | Yes | Yes | **Production-ready** (Redis-backed) |
| **E-commerce** | Yes | Yes | Yes | Partial | **Functional** — Products & Orders work, Cart planned |
| **SaaS Core** | -- | -- | Yes | Partial | **Functional** — In-memory tenants |
| **CRM** | Stub | Stub | Stub | -- | **Scaffolded** — Ready for implementation |
| **ERP** | Stub | Stub | Stub | -- | **Scaffolded** — Ready for implementation |
| **Leads** | Stub | -- | Stub | -- | **Scaffolded** — Ready for implementation |
| **AI Agents** | -- | -- | Stub | Stub | **Scaffolded** — LangChain stubs included |
| **Portfolio** | -- | -- | Stub | -- | **Scaffolded** — Uses Blog + SaaS |

> Scaffolded modules have route files and registry entries in place. Add ORM models, schemas, and service logic to bring them to production. See [Adding a New Domain Module](#adding-a-new-domain-module).

<br />

## Companion Projects

<table>
<tr>
<td width="50%">

### [VA Studio Frontend Starter](https://github.com/valtunox/va_studio_frontend_starter)

**20 production-ready React templates** with dark mode, theme switching, and zero backend dependencies.

React 18 · Vite 6 · Tailwind CSS · shadcn/ui

Templates include: SaaS landing, e-commerce marketplace, analytics dashboard, CRM, ERP, finance, marketing, blog, portfolio, AI assistant, calendar, and more.

</td>
<td width="50%">

### VA Studio AI Builder

The **AI-powered app builder** that uses these starters to let users create full-stack applications through natural language.

Go/Gin backend · Next.js frontend · LangChain agents · Multi-provider LLM support (OpenAI, Anthropic, Gemini)

</td>
</tr>
</table>

<br />

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** your feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to your branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Good First Issues

- Implement CRM models (Lead, Contact, Deal, Pipeline)
- Implement ERP models (Inventory, Procurement, Finance)
- Add Cart model and endpoints for e-commerce
- Complete OAuth2 provider implementations
- Add WebSocket support for real-time notifications
- Write integration tests for billing webhooks
- Add OpenAPI examples to endpoint schemas

### Development Guidelines

- Follow existing code patterns (check `app/services/blog/` as reference)
- Use async/await for all database and I/O operations
- Add Pydantic schemas for all request/response models
- Include soft delete support via `SoftDeleteMixin`
- Run `make format && make lint` before committing

<br />

## License

MIT License — see [LICENSE](LICENSE) for details.

Free to use in personal and commercial projects.

<br />

---

<div align="center">

**Built with [FastAPI](https://fastapi.tiangolo.com), [SQLAlchemy](https://sqlalchemy.org), and [Celery](https://docs.celeryq.dev)**

Part of the [VA Studio](https://github.com/valtunox) platform by **Valtunox**

[Report Bug](https://github.com/valtunox/va_studio_backend_starter/issues) · [Request Feature](https://github.com/valtunox/va_studio_backend_starter/issues) · [Discussions](https://github.com/valtunox/va_studio_backend_starter/discussions)

</div>
