"""
app/security.py

인증 모듈 — API Key (ML 서버용) + JWT (추후 프론트엔드용)

API Key 흐름:
    ML 서버 → POST /api/simulation/result
    요청 헤더: X-API-Key: <키값>
    .env의 ML_API_KEY와 일치해야 통과

JWT 흐름 (추후 구현):
    프론트엔드 → POST /auth/token (id/pw)
    → access_token 발급
    → 이후 요청 헤더: Authorization: Bearer <토큰>
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings


# ──────────────────────────────────────────────
# 공통 설정값 (config.py에 추가 필요)
# ──────────────────────────────────────────────
#
# .env에 아래 항목 추가:
#   ML_API_KEY=your-secret-key-here
#   JWT_SECRET_KEY=your-jwt-secret-here
#   JWT_ALGORITHM=HS256
#   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60


# ──────────────────────────────────────────────
# 1. API Key 인증 (ML 서버 전용)
# ──────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Annotated[str | None, Security(_api_key_header)]) -> str:
    """
    FastAPI Dependency — ML POST 엔드포인트에 적용.
    X-API-Key 헤더가 없거나 틀리면 403 반환.
    """
    expected = getattr(settings, "ml_api_key", None) or os.getenv("ML_API_KEY", "")
    if not expected:
        # .env에 ML_API_KEY가 없으면 서버 설정 오류로 처리
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버에 ML_API_KEY가 설정되지 않았습니다.",
        )
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="유효하지 않은 API 키입니다.",
        )
    return api_key


# 의존성 별칭 (엔드포인트에서 임포트해서 사용)
RequireApiKey = Annotated[str, Depends(verify_api_key)]


# ──────────────────────────────────────────────
# 2. JWT 인증 (프론트엔드용, 추후 활성화)
# ──────────────────────────────────────────────

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


class TokenPayload(BaseModel):
    sub: str          # 사용자 식별자
    exp: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_access_token(subject: str) -> str:
    """JWT access token 생성."""
    secret = getattr(settings, "jwt_secret_key", None) or os.getenv("JWT_SECRET_KEY", "")
    algorithm = getattr(settings, "jwt_algorithm", None) or os.getenv("JWT_ALGORITHM", "HS256")
    expire_minutes = int(
        getattr(settings, "jwt_access_token_expire_minutes", None)
        or os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_jwt_token(token: Annotated[str | None, Depends(_oauth2_scheme)]) -> TokenPayload:
    """
    FastAPI Dependency — 프론트엔드 전용 엔드포인트에 적용 (추후 활성화).
    Authorization: Bearer <token> 헤더를 검증.
    """
    secret = getattr(settings, "jwt_secret_key", None) or os.getenv("JWT_SECRET_KEY", "")
    algorithm = getattr(settings, "jwt_algorithm", None) or os.getenv("JWT_ALGORITHM", "HS256")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        sub: str = payload.get("sub", "")
        if not sub:
            raise credentials_exception
        return TokenPayload(sub=sub, exp=payload["exp"])
    except JWTError:
        raise credentials_exception


# 의존성 별칭
RequireJwt = Annotated[TokenPayload, Depends(verify_jwt_token)]
