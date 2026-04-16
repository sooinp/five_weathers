"""
backend/app/api/deps.py

공통 FastAPI 의존성 재수출.
엔드포인트에서 단일 임포트로 사용:
    from app.api.deps import DBSession, CurrentUser, require_roles

역할 종류:
    commander — 실행 제어, 임무 생성/수정
    operator  — 조회 및 제한된 조작
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RequireJwt, TokenPayload
from app.db.session import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = RequireJwt


def require_roles(*roles: str):
    """지정된 역할 중 하나를 가진 사용자만 허용하는 의존성 팩토리.

    사용 예:
        @router.post("", dependencies=[Depends(require_roles("commander"))])
    """
    def _check(user: CurrentUser) -> TokenPayload:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"이 작업은 {'/'.join(roles)} 역할이 필요합니다.",
            )
        return user
    return _check
