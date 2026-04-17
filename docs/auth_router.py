"""
app/api/auth.py

JWT 토큰 발급 라우터 (추후 프론트엔드 연동 시 활성화)

엔드포인트:
    POST /auth/token   — id/password로 access_token 발급
    GET  /auth/me      — 현재 로그인 사용자 정보 확인

현재는 단일 관리자 계정만 지원 (ADMIN_USERNAME / ADMIN_PASSWORD in .env).
추후 users 테이블 추가 시 DB 조회 방식으로 교체.
"""

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

from app.security import TokenResponse, TokenPayload, create_access_token, RequireJwt

router = APIRouter(prefix="/auth", tags=["auth"])


def _check_credentials(username: str, password: str) -> bool:
    """
    .env의 ADMIN_USERNAME / ADMIN_PASSWORD와 비교.
    타이밍 공격 방지를 위해 secrets.compare_digest 사용.
    """
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    expected_pass = os.getenv("ADMIN_PASSWORD", "")
    if not expected_pass:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버에 ADMIN_PASSWORD가 설정되지 않았습니다.",
        )
    user_ok = secrets.compare_digest(username, expected_user)
    pass_ok = secrets.compare_digest(password, expected_pass)
    return user_ok and pass_ok


@router.post("/token", response_model=TokenResponse, summary="JWT 토큰 발급")
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    OAuth2 Password Flow로 access_token 발급.

    - **username**: 관리자 아이디 (.env ADMIN_USERNAME)
    - **password**: 관리자 비밀번호 (.env ADMIN_PASSWORD)
    """
    if not _check_credentials(form.username, form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=form.username)
    return TokenResponse(access_token=token)


@router.get("/me", summary="현재 로그인 사용자 확인")
async def get_me(current_user: RequireJwt):
    """현재 JWT 토큰의 사용자 정보를 반환합니다."""
    return {"username": current_user.sub, "expires_at": current_user.exp}
