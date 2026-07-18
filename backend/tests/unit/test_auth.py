"""API integration tests for authentication and protected endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_login_json_invalid_credentials(async_client):
    with patch(
        "app.repositories.user_repository.UserRepository.get_by_email",
        new=AsyncMock(return_value=None),
    ):
        response = await async_client.post(
            "/api/v1/auth/login/json",
            json={"email": "nobody@example.com", "password": "wrongpassword1"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_protected_route_requires_auth(async_client):
    response = await async_client.get("/api/v1/buildings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_status_public(async_client):
    response = await async_client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["api_version"] == "v1"
    assert data["status"] == "operational"
