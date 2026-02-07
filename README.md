# VA Studio Backend

A production-ready FastAPI backend template for building SaaS applications. Suitable for ecommerce, portfolio, business consulting, and more.

## Features

- **Authentication & Authorization**
  - JWT-based authentication
  - OAuth2 (Google, GitHub)
  - Role-based access control
  - Password reset & email verification

- **Core Modules**
  - User management
  - Project/workspace management
  - Billing & subscriptions (Stripe)
  - Notifications (in-app & email)
  - Blog/CMS
  - Analytics dashboard

- **Infrastructure**
  - Docker & Docker Compose
  - PostgreSQL with async support
  - Redis for caching & sessions
  - Celery for background tasks
  - Alembic for database migrations
  - CI/CD pipeline (GitHub Actions)

- **Developer Experience**
  - OpenAPI documentation
  - Comprehensive test suite
  - Structured logging
  - Health checks
  - Rate limiting

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- Docker (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/va_studio_backend_starter.git
   cd va_studio_backend_starter
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Start services (with Docker)**
   ```bash
   docker-compose up -d db redis
   ```

6. **Run migrations**
   ```bash
   alembic upgrade head
   ```

7. **Seed sample data (optional)**
   ```bash
   python scripts/seed_data.py
   ```

8. **Start the server**
   ```bash
   make dev
   # Or: uvicorn app.main:app --reload
   ```

9. **Open API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Using Docker

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Project Structure

```
va_studio_backend_starter/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── auth/                   # Authentication module
│   │   ├── routes.py           # Auth endpoints
│   │   ├── oauth.py            # OAuth providers
│   │   └── dependencies.py     # Auth dependencies
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Settings
│   │   ├── database.py         # Database connection
│   │   ├── redis.py            # Redis client
│   │   ├── security.py         # JWT & password
│   │   ├── logger.py           # Logging
│   │   ├── middleware.py       # Custom middleware
│   │   └── celery_app.py       # Celery configuration
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   │   ├── users/
│   │   ├── projects/
│   │   ├── billing/
│   │   ├── notifications/
│   │   ├── email/
│   │   ├── analytics/
│   │   ├── blog/
│   │   ├── health/
│   │   └── ai/                 # AI service stubs
│   ├── tests/                  # Test suite
│   └── utils/                  # Utility functions
├── alembic/                    # Database migrations
├── scripts/                    # Utility scripts
├── nginx/                      # Nginx configuration
├── .github/workflows/          # CI/CD pipeline
├── docker-compose.yml          # Docker development
├── docker-compose.prod.yml     # Docker production
├── Dockerfile
├── Makefile
├── requirements.txt
└── README.md
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

### Blog
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/blog/posts` | List posts |
| POST | `/api/v1/blog/posts` | Create post |
| GET | `/api/v1/blog/posts/{id}` | Get post |
| PATCH | `/api/v1/blog/posts/{id}` | Update post |

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT secret key | (required) |
| `CORS_ORIGINS` | Allowed origins | `http://localhost:3000` |
| `STRIPE_SECRET_KEY` | Stripe API key | (optional) |
| `SMTP_HOST` | SMTP server | `smtp.gmail.com` |

See `.env.example` for all options.

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run unit tests only
make test-unit

# Run integration tests
make test-int
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Type checking
make type-check
```

### Database

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Seed data
python scripts/seed_data.py
```

### Celery

```bash
# Start worker
make celery-worker

# Start beat (scheduler)
make celery-beat

# Start Flower (monitoring)
make celery-flower
```

## Deployment

### Production with Docker

1. Build the image:
   ```bash
   docker build -t va-studio-backend:latest .
   ```

2. Configure production environment:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

3. Start services:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Environment Configuration

For production, ensure:
- `DEBUG=false`
- `ENVIRONMENT=production`
- Strong `SECRET_KEY`
- Proper database credentials
- SSL/TLS enabled
- Rate limiting configured

## AI Integration

The template includes stubs for AI agent integration. To enable AI features:

1. Install AI dependencies:
   ```bash
   pip install langchain langchain-openai openai
   ```

2. Configure API keys:
   ```bash
   OPENAI_API_KEY=sk-...
   # or
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Implement agents in `app/services/ai/agents/`

See `app/services/ai/agents/README.md` for detailed instructions.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [/docs](http://localhost:8000/docs)
- Issues: [GitHub Issues](https://github.com/yourusername/va_studio_backend_starter/issues)

---

Built with FastAPI, SQLAlchemy, and love.
