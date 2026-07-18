"""Tests for system health and status endpoints.

Validates that the platform's liveness and API status endpoints respond
correctly and include the expected metadata fields.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    """Health endpoint should return 200 with healthy status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_v1_status(async_client):
    """API v1 status endpoint should return operational status."""
    response = await async_client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["api_version"] == "v1"
    assert data["status"] == "operational"
