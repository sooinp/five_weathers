"""
backend/app/core/security.py

비밀번호 해시/검증 + JWT 생성/검증 + Refresh Token 생성.
엔드포인트 인증 의존성(RequireJwt) 제공.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── 비밀번호 ──────────────────────────────────────────────

def hash_password(plain: str) -> str:
    if not plain or not isinstance(plain, str):
        raise ValueError("Password must be a non-empty string")
    plain_bytes = plain.encode("utf-8")
    if len(plain_bytes) > 72:
        raise ValueError(
            f"Password too long for bcrypt: {len(plain_bytes)} bytes (max 72)"
        )
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    role: str = "operator"
    exp: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_access_token(subject: str, role: str = "operator") -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str | None) -> TokenPayload:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        sub: str = payload.get("sub", "")
        if not sub:
            raise exc
        return TokenPayload(
            sub=sub,
            role=payload.get("role", "operator"),
            exp=payload["exp"],
        )
    except JWTError:
        raise exc


def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
) -> TokenPayload:
    return _decode_token(token)


# 엔드포인트 의존성 별칭
RequireJwt = Annotated[TokenPayload, Depends(get_current_user)]


# ── Refresh Token ─────────────────────────────────────────

REFRESH_TOKEN_EXPIRE_DAYS = 7


def generate_refresh_token() -> tuple[str, str, datetime]:
    """랜덤 refresh token 생성.

    Returns:
        (raw_token, token_hash, expires_at)
        raw_token  — 클라이언트에게 전달할 원문
        token_hash — DB에 저장할 SHA-256 해시
        expires_at — 만료 시각 (UTC)
    """
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, token_hash, expires_at


def hash_refresh_token(raw: str) -> str:
    """원문 refresh token → SHA-256 해시."""
    return hashlib.sha256(raw.encode()).hexdigest()
