# VA Studio Backend Starter

Production-ready FastAPI backend template for building SaaS applications. Supports 10+ project types: e-commerce, portfolio, CRM, ERP, blog, and more.

This repo is embedded by **va_studio_ai_builder_backend** (Go, port 8743) to power user-created projects in VA Studio.

**React 18 • Vite 6 • Tailwind CSS • 20 Templates • MIT License**

### VA Studio Frontend Starter (companion)

20 production-ready, fully responsive React templates with dark mode, theme switching, and zero external API dependencies.

Open source collection of beautifully crafted UI templates for rapid prototyping and production apps. Built with React 18, Vite 6, Tailwind CSS, and shadcn/ui components.

For Quick Start, Templates, Features, Tech Stack, and Contributing guides, see the [VA Studio Frontend Starter README](https://github.com/valtunox/va_studio_frontend_starter#readme).

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
  - Candidates -- Recruitment, applications, interviews
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
