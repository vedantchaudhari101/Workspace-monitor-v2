"""Unit and integration tests for building, seat, and startup CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.models.user import User, UserRole
from app.services.auth import get_current_user
from app.database import get_db_session


@pytest.fixture(autouse=True)
def override_auth(app):
    """Override get_current_user dependency globally for CRUD tests."""
    mock_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


def helper_mock_add(obj):
    """Helper to populate primary key and timestamp fields on mocked insertion."""
    if not getattr(obj, "id", None):
        obj.id = uuid.uuid4()
    if not getattr(obj, "created_at", None):
        obj.created_at = datetime.now(timezone.utc)
    if not getattr(obj, "updated_at", None):
        obj.updated_at = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_create_building(async_client, app):
    """Test creating a building."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    building_data = {
        "name": "HQ Building",
        "address": "123 Main St",
        "city": "Tech City",
        "total_capacity": 100,
        "is_active": True
    }

    mock_db.add = MagicMock(side_effect=helper_mock_add)
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    response = await async_client.post("/api/v1/buildings", json=building_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "HQ Building"
    assert data["city"] == "Tech City"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_building_not_found(async_client, app):
    """Test getting a building that does not exist."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db
    
    mock_db.execute = AsyncMock()
    
    with patch("app.services.building_service.BuildingRepository.get_by_id", new=AsyncMock(return_value=None)):
        building_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/buildings/{building_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == f"Building '{building_id}' not found"


@pytest.mark.asyncio
async def test_create_seat(async_client, app):
    """Test creating a seat."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    # Mock finding the zone and checking for existing seat
    from app.models.zone import Zone, ZoneType
    mock_zone = Zone(id=uuid.uuid4(), name="Zone A", zone_type=ZoneType.OPEN)
    
    mock_db.get = AsyncMock(return_value=mock_zone)
    
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.add = MagicMock(side_effect=helper_mock_add)
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    seat_data = {
        "zone_id": str(mock_zone.id),
        "seat_label": "Seat-01",
        "is_active": True
    }

    response = await async_client.post("/api/v1/seats", json=seat_data)
    assert response.status_code == 201
    data = response.json()
    assert data["seat_label"] == "Seat-01"


@pytest.mark.asyncio
async def test_get_stats_empty(async_client, app):
    """Test get all stats endpoint."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    with patch("app.services.startup_service.StartupService.list_startups", new=AsyncMock(return_value=[])):
        response = await async_client.get("/api/v1/startups/stats")
        assert response.status_code == 200
        assert response.json() == []
