"""
backend/app/api/auth.py

POST /api/auth/login   — 로그인 → JWT 발급 (JSON body)
POST /api/auth/logout  — 로그아웃 (클라이언트 토큰 폐기 확인)
GET  /api/auth/me      — 현재 사용자 정보
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DBSession
from app.core.rate_limit import LoginGuard, limiter
from app.db.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="로그인 (JWT 발급)")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: DBSession):
    LoginGuard.check(request)  # IP 잠금 여부 확인 (5회 실패 → 15분 차단)
    svc = AuthService(db)
    token = await svc.authenticate(body.username, body.password)
    if token is None:
        LoginGuard.on_failure(request)
        logger.warning("Login failed: %s", body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    LoginGuard.on_success(request)
    logger.info("Login success: %s", body.username)
    return TokenResponse(access_token=token)


@router.post("/logout", summary="로그아웃")
async def logout():
    """
    클라이언트가 보유한 토큰을 폐기하도록 확인 응답.
    현재 stateless JWT 구조이므로 서버 측 무효화는 없음.
    프론트엔드는 이 응답을 받아 로컬 토큰을 삭제한다.
    """
    logger.info("Logout requested")
    return {"ok": True, "message": "로그아웃되었습니다."}


@router.get("/me", response_model=UserOut, summary="현재 로그인 사용자")
async def get_me(current_user: CurrentUser, db: DBSession):
    svc = AuthService(db)
    try:
        user_id = int(current_user.sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="토큰이 유효하지 않습니다.")
    user = await svc.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user
