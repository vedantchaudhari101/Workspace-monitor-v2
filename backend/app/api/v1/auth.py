"""Authentication API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="OAuth2 password login")
async def login(
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """Authenticate with email (username field) and password.

    Returns a JWT bearer token for subsequent API calls.
    """
    service = AuthService(db)
    return await service.login_with_credentials(form_data.username, form_data.password)


@router.post("/login/json", response_model=TokenResponse, summary="JSON login")
async def login_json(db: DbSession, payload: LoginRequest) -> TokenResponse:
    """Alternative JSON-based login endpoint."""
    service = AuthService(db)
    return await service.login(payload)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user (admin only)",
)
async def register(
    db: DbSession,
    _admin: AdminUser,
    payload: RegisterRequest,
) -> UserResponse:
    """Create a new platform user. Restricted to ADMIN role."""
    service = AuthService(db)
    return await service.register(payload)


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(db: DbSession, user: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile."""
    return AuthService(db).to_response(user)


@router.post("/logout", response_model=MessageResponse, summary="Logout")
async def logout(_user: CurrentUser) -> MessageResponse:
    """Stateless JWT logout — discard the client-side token."""
    return MessageResponse(message="Logged out successfully")
