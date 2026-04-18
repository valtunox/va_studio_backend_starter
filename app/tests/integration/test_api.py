"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_liveness_check(self, client: AsyncClient):
        """Test liveness check."""
        response = await client.get("/api/v1/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root(self, client: AsyncClient):
        """Test root endpoint."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, client: AsyncClient):
        """Test user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "NewPassword123!",
                "username": "newuser",
                "full_name": "New User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with duplicate email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "Password123!",
                "username": "another",
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, auth_headers):
        """Test getting current user."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without auth."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestUserEndpoints:
    """Tests for user endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_profile(self, client: AsyncClient, auth_headers):
        """Test getting user profile."""
        response = await client.get(
            "/api/v1/users/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    @pytest.mark.asyncio
    async def test_update_user_profile(self, client: AsyncClient, auth_headers):
        """Test updating user profile."""
        response = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"full_name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_list_users_admin_only(self, client: AsyncClient, auth_headers):
        """Test that listing users requires admin."""
        response = await client.get(
            "/api/v1/users/",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_as_admin(
        self, client: AsyncClient, admin_auth_headers
    ):
        """Test listing users as admin."""
        response = await client.get(
            "/api/v1/users/",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestProjectEndpoints:
    """Tests for project endpoints."""

    @pytest.mark.asyncio
    async def test_create_project(self, client: AsyncClient, auth_headers):
        """Test creating a project."""
        response = await client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": "Test Project",
                "description": "A test project",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert "id" in data
        assert "slug" in data

    @pytest.mark.asyncio
    async def test_list_projects(self, client: AsyncClient, auth_headers):
        """Test listing projects."""
        response = await client.get(
            "/api/v1/projects/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_public_projects(self, client: AsyncClient):
        """Test listing public projects (no auth required)."""
        response = await client.get("/api/v1/projects/public")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
