"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    """JSON login payload (alternative to OAuth2 form)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(ORMModel):
    """Public user profile returned by auth endpoints."""

    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool


class RegisterRequest(BaseModel):
    """Admin-only user registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.VIEWER
