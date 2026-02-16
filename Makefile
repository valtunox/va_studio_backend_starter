.PHONY: help install dev test lint format build run clean docker-build docker-up docker-down db-migrate db-seed

# Variables
PYTHON := python
PIP := pip
DOCKER_COMPOSE := docker-compose
APP_NAME := va_studio_backend

# Default target
help:
	@echo "VA Studio Backend - Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make install      Install dependencies"
	@echo "    make dev          Start development server"
	@echo "    make run          Start production server"
	@echo ""
	@echo "  Testing:"
	@echo "    make test         Run all tests"
	@echo "    make test-unit    Run unit tests"
	@echo "    make test-int     Run integration tests"
	@echo "    make test-cov     Run tests with coverage"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint         Run linting"
	@echo "    make format       Format code"
	@echo "    make type-check   Run type checking"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build Build Docker image"
	@echo "    make docker-up    Start Docker containers"
	@echo "    make docker-down  Stop Docker containers"
	@echo "    make docker-logs  View Docker logs"
	@echo ""
	@echo "  Database:"
	@echo "    make db-migrate   Run database migrations"
	@echo "    make db-seed      Seed database with sample data"
	@echo "    make db-reset     Reset database"
	@echo ""
	@echo "  Utilities:"
	@echo "    make clean        Clean up temporary files"
	@echo "    make shell        Open Python shell"

# Installation
install:
	$(PIP) install -r requirements.txt

# Development
dev:
	uvicorn app.app:app --reload --host 0.0.0.0 --port 5112

run:
	uvicorn app.app:app --host 0.0.0.0 --port 5112 --workers 4

# Testing
test:
	pytest app/tests/ -v

test-unit:
	pytest app/tests/unit/ -v

test-int:
	pytest app/tests/integration/ -v

test-cov:
	pytest app/tests/ -v --cov=app --cov-report=html --cov-report=term-missing

test-watch:
	pytest-watch app/tests/

# Code Quality
lint:
	flake8 app/
	mypy app/

format:
	black app/
	isort app/

format-check:
	black app/ --check
	isort app/ --check-only

type-check:
	mypy app/

# Docker
docker-build:
	docker build -t $(APP_NAME):latest .

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-restart:
	$(DOCKER_COMPOSE) restart

docker-shell:
	$(DOCKER_COMPOSE) exec app /bin/bash

docker-clean:
	$(DOCKER_COMPOSE) down -v --rmi local

# Database
db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

db-seed:
	$(PYTHON) scripts/seed_data.py

db-reset:
	$(DOCKER_COMPOSE) exec db psql -U postgres -c "DROP DATABASE IF EXISTS va_studio;"
	$(DOCKER_COMPOSE) exec db psql -U postgres -c "CREATE DATABASE va_studio;"
	alembic upgrade head

db-shell:
	$(DOCKER_COMPOSE) exec db psql -U postgres -d va_studio

# Celery
celery-worker:
	celery -A app.core.celery_app worker --loglevel=info

celery-beat:
	celery -A app.core.celery_app beat --loglevel=info

celery-flower:
	celery -A app.core.celery_app flower --port=5555

# Utilities
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "htmlcov" -delete
	find . -type f -name ".coverage" -delete

shell:
	$(PYTHON) -c "import IPython; IPython.embed()"

# Generate secret key
secret-key:
	$(PYTHON) -c "import secrets; print(secrets.token_urlsafe(32))"

# Documentation
docs:
	mkdocs serve

docs-build:
	mkdocs build

# CI/CD helpers
ci-lint:
	$(MAKE) format-check
	$(MAKE) lint

ci-test:
	$(MAKE) test-cov

ci-build:
	$(MAKE) docker-build
