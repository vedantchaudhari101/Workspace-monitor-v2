"""Authentication business logic."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import ConflictError, UnauthorizedError
from app.config import get_settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.utils.security import create_access_token, hash_password, verify_password


class AuthService:
    """Handles login, registration, and token issuance."""

    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(payload.email.lower())
        if user is None or not user.hashed_password:
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is inactive")

        user.last_login = datetime.now(timezone.utc)
        token = create_access_token(user.id, extra_claims={"role": user.role.value})
        settings = get_settings()
        return TokenResponse(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login_with_credentials(self, email: str, password: str) -> TokenResponse:
        return await self.login(LoginRequest(email=email, password=password))

    async def register(self, payload: RegisterRequest) -> UserResponse:
        existing = await self._users.get_by_email(payload.email.lower())
        if existing:
            raise ConflictError("Email already registered")

        user = User(
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
            is_active=True,
        )
        created = await self._users.create(user)
        return self._to_response(created)

    @staticmethod
    def _to_response(user: User) -> UserResponse:
        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )

    def to_response(self, user: User) -> UserResponse:
        return self._to_response(user)
