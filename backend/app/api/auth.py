"""Authentication module — JWT-based login and user verification.

Provides:
- POST /auth/login — username/password check, returns JWT
- GET /auth/me — returns current user from valid JWT
- get_current_user dependency for protecting routes

Uses python-jose for JWT creation/validation.
GitHub OAuth will replace the hardcoded user check in a later stage.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.api.schemas import LoginRequest, TokenResponse, UserResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# ---------------------------------------------------------------------------
# Simple password hashing (temporary — replaced by GitHub OAuth later)
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password with PBKDF2-SHA256. Returns 'salt$hash'."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored 'salt$hash' string."""
    parts = stored.split("$", 1)
    if len(parts) != 2:
        return False
    salt, _ = parts
    return hmac.compare_digest(_hash_password(password, salt), stored)


# ---------------------------------------------------------------------------
# Hardcoded seed user (placeholder until GitHub OAuth is wired)
# ---------------------------------------------------------------------------
_ADMIN_HASH = _hash_password("admin123")

_SEED_USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": _ADMIN_HASH,
        "role": "developer",
    },
}

# JWT settings
_ALGORITHM = "HS256"


def _create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    """FastAPI dependency — extracts and validates the JWT from the Authorization header.

    Returns the authenticated user or raises 401.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[_ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return UserResponse(username=username, role=payload.get("role", "developer"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Authenticate with username/password and return a JWT.

    Currently uses a hardcoded seed user. Will be replaced by GitHub OAuth.
    """
    user = _SEED_USERS.get(body.username)
    if user is None or not _verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = _create_access_token(
        data={"sub": user["username"], "role": user["role"]},
    )
    logger.info("User %s logged in", user["username"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Return the current authenticated user."""
    return current_user

