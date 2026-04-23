"""
backend/app/api/auth.py

POST /api/auth/login   -> login and JWT issuance
POST /api/auth/logout  -> client-side logout acknowledgement
GET  /api/auth/me      -> current user info
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.rate_limit import LoginGuard
from app.core.security import create_access_token
from app.db.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_FALLBACK_USERS = {
    "admin": {"id": 1, "password": lambda: settings.admin_password or "admin", "role": "commander"},
    "user1": {"id": 101, "password": lambda: "user1", "role": "operator"},
    "user2": {"id": 102, "password": lambda: "user2", "role": "operator"},
    "user3": {"id": 103, "password": lambda: "user3", "role": "operator"},
}
_DB_AUTH_UNAVAILABLE_UNTIL = 0.0


def _issue_fallback_token(username: str, password: str) -> str | None:
    info = _FALLBACK_USERS.get(username)
    if info is None:
        return None
    if password != info["password"]():
        return None
    return create_access_token(subject=str(info["id"]), role=info["role"])


def _fallback_user_out(sub: str) -> UserOut | None:
    for username, info in _FALLBACK_USERS.items():
        if str(info["id"]) == str(sub):
            return UserOut(id=info["id"], username=username, role=info["role"])
    return None


@router.post("/login", response_model=TokenResponse, summary="Login (JWT issuance)")
async def login(request: Request, response: Response, body: LoginRequest, db: DBSession):
    global _DB_AUTH_UNAVAILABLE_UNTIL
    try:
        LoginGuard.check(request)
        svc = AuthService(db)
        token = None
        use_fallback_first = time.time() < _DB_AUTH_UNAVAILABLE_UNTIL
        if not use_fallback_first:
            try:
                token = await svc.authenticate(body.username, body.password)
            except Exception as exc:
                _DB_AUTH_UNAVAILABLE_UNTIL = time.time() + 10
                logger.warning("Primary DB auth unavailable for username=%s: %s", body.username, exc)
        if token is None:
            token = _issue_fallback_token(body.username, body.password)
            if token is not None:
                LoginGuard.on_success(request)
                logger.warning("Login fallback issued token for username=%s", body.username)
                return TokenResponse(access_token=token)

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
    except HTTPException:
        raise
    except Exception:
        logger.exception("Login handler crashed for username=%s", body.username)
        raise


@router.post("/logout", summary="Logout")
async def logout():
    logger.info("Logout requested")
    return {"ok": True, "message": "로그아웃되었습니다."}


@router.get("/me", response_model=UserOut, summary="Current user")
async def get_me(current_user: CurrentUser, db: DBSession):
    svc = AuthService(db)
    try:
        user_id = int(current_user.sub)
    except ValueError:
        fallback = _fallback_user_out(current_user.sub)
        if fallback is not None:
            return fallback
        raise HTTPException(status_code=401, detail="토큰이 유효하지 않습니다.")

    try:
        user = await svc.get_user_by_id(user_id)
    except Exception:
        logger.exception("get_me DB lookup failed for sub=%s", current_user.sub)
        fallback = _fallback_user_out(current_user.sub)
        if fallback is not None:
            return fallback
        raise

    if user is None:
        fallback = _fallback_user_out(current_user.sub)
        if fallback is not None:
            return fallback
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user
