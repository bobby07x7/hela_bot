"""
Minimal JWT auth for the dashboard API.

There's a single "admin" identity, gated by DASHBOARD_PASSWORD (set this to
something real in production). POST /api/auth/login with that password
returns a bearer JWT; every other /api/* route (except /api/health)
requires it via the `get_current_admin` dependency.

Tokens are also recorded in the `dashboard_sessions` table (jti + revoked
flag) so a compromised token can be revoked server-side before its natural
expiry via POST /api/auth/revoke, instead of relying purely on TTL.
"""
from __future__ import annotations

import datetime as dt
import secrets

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from core.config import get_settings
from database.models import DashboardSession
from database.session import get_session

_JWT_ALGORITHM = "HS256"
_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token() -> tuple[str, str]:
    """Returns (token, jti)."""
    settings = get_settings()
    jti = secrets.token_hex(16)
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": "admin",
        "jti": jti,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.dashboard_token_ttl_minutes),
    }
    token = jwt.encode(payload, settings.api_secret_key, algorithm=_JWT_ALGORITHM)
    return token, jti


def verify_password(password: str) -> bool:
    settings = get_settings()
    # Constant-time comparison to avoid a timing side-channel on the password check.
    return secrets.compare_digest(password, settings.dashboard_password)


async def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> str:
    """FastAPI dependency: raises 401 unless a valid, non-revoked JWT is
    presented as `Authorization: Bearer <token>`."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.api_secret_key, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = payload.get("jti")
    async with get_session() as session:
        result = await session.execute(select(DashboardSession).where(DashboardSession.jti == jti))
        record = result.scalar_one_or_none()
        if record is not None and record.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    return payload.get("sub", "admin")
